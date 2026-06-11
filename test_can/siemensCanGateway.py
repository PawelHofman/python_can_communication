#!/usr/bin/env python3

# ==========================================================
# KONFIGURACJA INTERFEJSOW
# ==========================================================
PILOT_CAN = "can1"
SYSTEM_CAN = "can0"

# ==========================================================
# KONFIGURACJA PLC (Siemens S7-1200)
# ==========================================================
PLC_IP = "192.168.0.1"
PLC_RACK = 0
PLC_SLOT = 1

DB_SEND = 191
DB_RECV = 192

# GLOBALNE
MODIFY_MODE = 0
PLC_SPEED = 0
SPEED_LIMIT_ACTIVE = 0

import can
import threading
import signal
import sys
import time
import snap7

# ==========================================================
# MAPA TRYBOW
# ==========================================================
MODES = {
    1: (0x23, 5),
    2: (0xC3, 6),
    3: (0x0B, 7),
    4: (0x13, 7),
}

# ==========================================================
# THREAD PLC
# ==========================================================
def plc_thread():

    global MODIFY_MODE, PLC_SPEED, SPEED_LIMIT_ACTIVE

    client = snap7.client.Client()

    while True:
        try:
            if not client.get_connected():
                print("Connecting to PLC...")
                client.connect(PLC_IP, PLC_RACK, PLC_SLOT)
                print("PLC connected")

            data = client.db_read(DB_SEND, 0, 3)

            cmd = data[0]
            speed = data[1]
            speed_limit = data[2]

            PLC_SPEED = max(0, min(255, speed))
            SPEED_LIMIT_ACTIVE = speed_limit

            # TUTAJ ODKOMENTUJ ZEBY BYLY LOGI 

            # print(f"PLC -> cmd:{cmd} speed:{speed} limit:{speed_limit}")

            # TRYB
            if cmd == 0:
                MODIFY_MODE = 0
            elif cmd in MODES:
                MODIFY_MODE = cmd
            else:
                MODIFY_MODE = 0

            # LIFE BIT
            life = int(time.time()) % 2
            client.db_write(DB_RECV, 0, bytearray([life]))

        except Exception as e:
            print(f"PLC error: {e}")

            MODIFY_MODE = 0

            try:
                client.disconnect()
            except:
                pass

        time.sleep(0.1)

threading.Thread(target=plc_thread, daemon=True).start()

# ==========================================================
# CAN
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

        global MODIFY_MODE, PLC_SPEED, SPEED_LIMIT_ACTIVE

        try:

            # ===============================
            # TRYB TRANSPARENT
            # ===============================
            if MODIFY_MODE == 0:

                if (
                    SPEED_LIMIT_ACTIVE == 1
                    and msg.arbitration_id == 0x3A0
                    and msg.dlc == 8
                ):
                    data = bytearray(msg.data)

                    # ograniczenie prędkości
                    # for i in [5, 6, 7]:
                    #     data[i] = min(data[i], 20)

                    limit = 20

                    for i in (5, 6, 7):
                        if i < len(data):
                            if data[i] > limit:
                                data[i] = limit

                    msg = can.Message(
                        arbitration_id=msg.arbitration_id,
                        data=data,
                        dlc=msg.dlc,
                        is_extended_id=msg.is_extended_id
                    )

                system_bus.send(msg)
                return

            # ===============================
            # TRYB MODYFIKACJI
            # ===============================
            if MODIFY_MODE in MODES and msg.arbitration_id == 0x3A0 and msg.dlc == 8:

                data = bytearray(msg.data)

                byte1, indexX = MODES[MODIFY_MODE]

                data[1] = byte1
                data[indexX] = PLC_SPEED

                msg = can.Message(
                    arbitration_id=msg.arbitration_id,
                    data=data,
                    dlc=msg.dlc,
                    is_extended_id=msg.is_extended_id
                )

            system_bus.send(msg)

        except Exception as e:
            print(f"CAN error P->S: {e}")
            MODIFY_MODE = 0


# ==========================================================
# SYSTEM -> PILOT
# ==========================================================
class SystemToPilot(can.Listener):

    def on_message_received(self, msg):

        try:
            pilot_bus.send(msg)

        except Exception as e:
            print(f"CAN error S->P: {e}")


# ==========================================================
# NOTIFIER
# ==========================================================
notifier_pilot = can.Notifier(pilot_bus, [PilotToSystem()])
notifier_system = can.Notifier(system_bus, [SystemToPilot()])

print("\nGateway running\n")

# ==========================================================
# SHUTDOWN
# ==========================================================
def shutdown(sig, frame):

    print("\nShutdown...")

    notifier_pilot.stop()
    notifier_system.stop()

    pilot_bus.shutdown()
    system_bus.shutdown()

    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

signal.pause()

