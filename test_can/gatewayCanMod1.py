#!/usr/bin/env python3
# sudo ip link set can0 up type can bitrate 125000 restart-ms 100
# sudo ip link set can1 up type can bitrate 125000 restart-ms 100
# sudo chrt -f 80 python3 gatewayCanMod1.py
# ==========================================================
# KONFIGURACJA INTERFEJSÓW
# Zmieniasz tylko tutaj gdy zamienisz kable 
# ==========================================================
PILOT_CAN = "can1"     # <-- Pilot
SYSTEM_CAN = "can0"    # <-- Reszta nodów

MODIFY_FRAME = False


import can
import threading
import signal
import sys


# ==========================================================
# THREAD DO OBSŁUGI KLAWIATURY
# ==========================================================
def keyboard_listener():
    global MODIFY_FRAME

    while True:
        key = input()

        if key == "1":
            MODIFY_FRAME = not MODIFY_FRAME
            print(f"Frame modification: {MODIFY_FRAME}")


threading.Thread(target=keyboard_listener, daemon=True).start()


# ==========================================================
# OTWIERANIE CAN
# ==========================================================
print(f"Pilot on  : {PILOT_CAN}")
print(f"System on : {SYSTEM_CAN}")

pilot_bus = can.interface.Bus(channel=PILOT_CAN, interface='socketcan')
system_bus = can.interface.Bus(channel=SYSTEM_CAN, interface='socketcan')


# ==========================================================
# PILOT -> SYSTEM (tu możemy manipulować ramką)
# ==========================================================
class PilotToSystem(can.Listener):

    def on_message_received(self, msg):

        global MODIFY_FRAME

        try:

            if MODIFY_FRAME and msg.arbitration_id == 0x3A0:

                data = bytearray(msg.data)

                # modyfikujemy tylko pełne ramki
                if msg.dlc == 8:

                    # przykład:
                    # 02 03 00 00 00 4F 00 00
                    # ->
                    # 02 23 00 00 00 50 00 00

                    data[1] = 0x23
                    data[5] = 0x50

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
# SYSTEM -> PILOT (transparentny most)
# ==========================================================
class SystemToPilot(can.Listener):

    def on_message_received(self, msg):

        try:
            pilot_bus.send(msg)

        except can.CanError:
            pass


# ==========================================================
# NOTIFIERS (event-driven = mały jitter + małe CPU)
# ==========================================================
notifier_pilot = can.Notifier(pilot_bus, [PilotToSystem()])
notifier_system = can.Notifier(system_bus, [SystemToPilot()])


print("\nGateway running.")
print("Press '1' to toggle frame modification.\n")


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


# zero CPU usage
signal.pause()
