#!/usr/bin/env python3
# sudo ip link set can0 up type can bitrate 125000 restart-ms 100
# sudo ip link set can1 up type can bitrate 125000 restart-ms 100
# sudo chrt -f 80 python3 gatewayCanMod12.py

# ==========================================================
# KONFIGURACJA INTERFEJSÓW
# ==========================================================
PILOT_CAN = "can1"
SYSTEM_CAN = "can0"

# 0 = brak modyfikacji
# 1 = tryb pierwszy
# 2 = tryb drugi
MODIFY_MODE = 0


import can
import threading
import signal
import sys


# ==========================================================
# KLAWIATURA
# ==========================================================
def keyboard_listener():
    global MODIFY_MODE

    while True:
        key = input()

        if key in ["0", "1", "2"]:
            MODIFY_MODE = int(key)
            print(f"Modify mode -> {MODIFY_MODE}")


threading.Thread(target=keyboard_listener, daemon=True).start()


# ==========================================================
print(f"Pilot on  : {PILOT_CAN}")
print(f"System on : {SYSTEM_CAN}")

pilot_bus = can.interface.Bus(channel=PILOT_CAN, interface='socketcan')
system_bus = can.interface.Bus(channel=SYSTEM_CAN, interface='socketcan')


# ==========================================================
class PilotToSystem(can.Listener):

    def on_message_received(self, msg):

        global MODIFY_MODE

        try:

            if MODIFY_MODE > 0 and msg.arbitration_id == 0x3A0:

                data = bytearray(msg.data)

                if msg.dlc == 8:

                    # =============================
                    # TRYB 1
                    # =============================
                    if MODIFY_MODE == 1:
                        data[1] = 0x23
                        data[5] = 0x50

                    # =============================
                    # TRYB 2
                    # =============================
                    elif MODIFY_MODE == 2:
                        data[1] = 0xC3
                        data[6] = 0x50

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
                system_bus.send(msg)

        except can.CanError:
            pass


# ==========================================================
class SystemToPilot(can.Listener):

    def on_message_received(self, msg):

        try:
            pilot_bus.send(msg)

        except can.CanError:
            pass


# ==========================================================
notifier_pilot = can.Notifier(pilot_bus, [PilotToSystem()])
notifier_system = can.Notifier(system_bus, [SystemToPilot()])


print("\nGateway running.")
print("0 = no modification")
print("1 = modify mode 1")
print("2 = modify mode 2\n")


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
