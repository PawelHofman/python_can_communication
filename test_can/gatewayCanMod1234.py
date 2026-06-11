#!/usr/bin/env python3
# sudo ip link set can0 up type can bitrate 125000 restart-ms 100
# sudo ip link set can1 up type can bitrate 125000 restart-ms 100
# sudo chrt -f 80 python3 gatewayCanMod1234.py

# ==========================================================
# KONFIGURACJA INTERFEJSOW
# ==========================================================
PILOT_CAN = "can1"
SYSTEM_CAN = "can0"

# 0 = brak modyfikacji
MODIFY_MODE = 0


import can
import threading
import signal
import sys


# ==========================================================
# MAPA TRYBOW
# mode : (wartosc_bajtu_1, index_drugiego_bajtu, wartosc)
# ==========================================================
MODES = {
    1: (0x23, 5, 0x50),  # data[1], data[5]
    2: (0xC3, 6, 0x90),  # data[1], data[6]
    3: (0x0B, 7, 0x9f),  # data[1], data[7]
    4: (0x13, 7, 0xff),  # data[1], data[7]
}


# ==========================================================
# THREAD DO OBSLUGI KLAWIATURY
# ==========================================================
def keyboard_listener():
    global MODIFY_MODE

    while True:
        key = input()

        if key.isdigit():
            MODIFY_MODE = int(key)
            print(f"\nModify mode -> {MODIFY_MODE}\n")


threading.Thread(target=keyboard_listener, daemon=True).start()


# ==========================================================
# OTWIERANIE CAN
# ==========================================================
print(f"Pilot on  : {PILOT_CAN}")
print(f"System on : {SYSTEM_CAN}")

pilot_bus = can.interface.Bus(channel=PILOT_CAN, interface='socketcan')
system_bus = can.interface.Bus(channel=SYSTEM_CAN, interface='socketcan')


# ==========================================================
# PILOT -> SYSTEM
# ==========================================================
class PilotToSystem(can.Listener):

    def on_message_received(self, msg):

        global MODIFY_MODE

        try:

            # tylko interesujące nas ID
            if MODIFY_MODE in MODES and msg.arbitration_id == 0x3A0:

                data = bytearray(msg.data)

                # gateway safety
                if msg.dlc == 8:

                    byte1, indexX, valueX = MODES[MODIFY_MODE]

                    data[1] = byte1
                    data[indexX] = valueX

                else:
                    system_bus.send(msg)
                    return

                new_msg = can.Message(
                    arbitration_id=msg.arbitration_id,
                    data=data,
                    dlc=msg.dlc,
                    is_extended_id=msg.is_extended_id
                )

                system_bus.send(new_msg)

            else:
                # transparentny forwarding
                system_bus.send(msg)

        except can.CanError:
            pass


# ==========================================================
# SYSTEM -> PILOT (transparentnie)
# ==========================================================
class SystemToPilot(can.Listener):

    def on_message_received(self, msg):

        try:
            pilot_bus.send(msg)

        except can.CanError:
            pass


# ==========================================================
# NOTIFIERS
# ==========================================================
notifier_pilot = can.Notifier(pilot_bus, [PilotToSystem()])
notifier_system = can.Notifier(system_bus, [SystemToPilot()])


print("\nGateway running.\n")

print("0 = no modification")
for mode in MODES:
    print(f"{mode} = modify mode {mode}")

print("")


# ==========================================================
# GRACEFUL SHUTDOWN
# ==========================================================
def shutdown(sig, frame):

    print("\nShutting down gateway...")

    notifier_pilot.stop()
    notifier_system.stop()

    pilot_bus.shutdown()
    system_bus.shutdown()

    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

signal.pause()
