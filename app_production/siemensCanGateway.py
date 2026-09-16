# ==========================================================
# WERSJA 0006_1_2_3
# _1 dodano zmienna IN_MODE
# _2 dodano zmienna RECEIVED_3A0
# _2 dodano zmienna MODIFIED_1_4_3A0_SENT
# ==========================================================

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

# ==========================================================
# GLOBALNE
# ==========================================================
MODIFY_MODE = 0
PLC_SPEED = 0
SPEED_LIMIT_ACTIVE = 0
NO_PILOT_ACTION = 0

PILOT_ALIVE = 0
LAST_PILOT_MSG_TIME = 0
IN_MODE = 99
# JESLI 99 TO NIE MA TRYBU 
# 1 = NO PILOT
# 2 = TRANSPARETNY 
# 3 = TRANSPARETNY + OGRANICZENIE PREDKOSCI 
# IN_MODE = 10 + byte1 
    # 11 - TRYB 1 
    # 12 - TRYB 2 
    # 13 - TRYB 3 
    # 14 - TRYB 4 
RECEIVED_3A0 = 0 # LICZNIK ODEBRANYCH RAMEK 3A0 | 8 BYTE
MODIFIED_1_4_3A0_SENT = 0 # licznik zmodyfikowanych ramek w modach 1-4

import can
import threading
import signal
import sys
import time
import snap7

# ==========================================================
# MAPA TRYBOW
# mode : (byte1, index_speed)
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

    global MODIFY_MODE
    global PLC_SPEED
    global SPEED_LIMIT_ACTIVE
    global NO_PILOT_ACTION
    global PILOT_ALIVE
    global LAST_PILOT_MSG_TIME
    global IN_MODE
    global RECEIVED_3A0
    global MODIFIED_1_4_3A0_SENT


    client = snap7.client.Client()

    while True:

        try:

            # ==================================================
            # CONNECT PLC
            # ==================================================
            if not client.get_connected():

                print("Connecting to PLC...")

                client.connect(
                    PLC_IP,
                    PLC_RACK,
                    PLC_SLOT
                )

                print("PLC connected")

            # ==================================================
            # READ PLC DB
            # byte0 = cmd
            # byte1 = speed
            # byte2 = speed_limit
            # byte3 = no_pilot
            # ==================================================
            data = client.db_read(DB_SEND, 0, 4)

            cmd = data[0]
            speed = data[1]
            speed_limit = data[2]
            no_pilot = data[3]

            PLC_SPEED = max(0, min(255, speed))

            SPEED_LIMIT_ACTIVE = speed_limit
            NO_PILOT_ACTION = no_pilot

            print(
                f"PLC -> "
                f"cmd={cmd} "
                f"speed={speed} "
                f"limit={speed_limit} "
                f"no_pilot={no_pilot}"
            )
            # ==================================================
            # TRYB
            # ==================================================
            if cmd == 0:
                MODIFY_MODE = 0

            elif cmd in MODES:
                MODIFY_MODE = cmd

            else:
                MODIFY_MODE = 0

            
            # ==================================================
            # PILOT ALIVE
            # ==================================================
            if (time.time() - LAST_PILOT_MSG_TIME) < 2.0:
                PILOT_ALIVE = 1
            else:
                PILOT_ALIVE = 0


            # ==================================================
            # LIFE BIT
            # ==================================================
            life = int(time.time()) % 2

            send_buf = bytearray(5)

            send_buf[0] = life
            send_buf[1] = PILOT_ALIVE
            send_buf[2] = IN_MODE
            send_buf[3] = RECEIVED_3A0
            send_buf[4] = MODIFIED_1_4_3A0_SENT

            client.db_write(
                DB_RECV,
                0,
                send_buf
            )

        except Exception as e:

            print(f"PLC error: {e}")

            # FAILSAFE
            MODIFY_MODE = 0
            SPEED_LIMIT_ACTIVE = 0
            NO_PILOT_ACTION = 0
            PILOT_ALIVE = 0
            
            try:
                client.disconnect()
            except:
                pass

        time.sleep(0.05)

# ==========================================================
# START PLC THREAD
# ==========================================================
threading.Thread(
    target=plc_thread,
    daemon=True
).start()


# ==========================================================
# ==========================================================
# ==========================================================
# ==========================================================
# ==========================================================
# ==========================================================
# CAN
# ==========================================================
# ==========================================================
print(f"Pilot on  : {PILOT_CAN}")
print(f"System on : {SYSTEM_CAN}")

pilot_bus = can.interface.Bus(
    channel=PILOT_CAN,
    interface='socketcan'
)

system_bus = can.interface.Bus(
    channel=SYSTEM_CAN,
    interface='socketcan'
)

# ==========================================================
# PILOT -> SYSTEM
# ==========================================================
class PilotToSystem(can.Listener):

    def on_message_received(self, msg):

        global MODIFY_MODE
        global PLC_SPEED
        global SPEED_LIMIT_ACTIVE
        global NO_PILOT_ACTION
        global LAST_PILOT_MSG_TIME

        LAST_PILOT_MSG_TIME = time.time()

        global IN_MODE
        global RECEIVED_3A0
        global MODIFIED_1_4_3A0_SENT


        try:

            # ==================================================
            # LOKALNA KOPIA
            # ==================================================
            mode = MODIFY_MODE
            speed = PLC_SPEED
            speed_limit = SPEED_LIMIT_ACTIVE
            no_pilot = NO_PILOT_ACTION

            # IN_MODE = 99

            # ==================================================
            # LICZENIE RAMEK arbitration_id == 0x3A0 & dlc == 8
            # ==================================================
            if (
                msg.arbitration_id == 0x3A0
                and msg.dlc == 8
            ):
                RECEIVED_3A0 = RECEIVED_3A0 + 1

                if (RECEIVED_3A0 > 250):
                    RECEIVED_3A0 = 0

            # ==================================================
            # NO PILOT ACTION
            # ==================================================
            if (
                no_pilot == 1
                and mode == 0
                and msg.arbitration_id == 0x3A0
                and msg.dlc == 8
            ):

                # print("NO PILOT ACTIVE")

                # zachowaj oryginalną ramkę
                data = bytearray(msg.data)

                # neutral command
                data[1] = 0x03

                # WYŁĄCZENIE JOYSTICKA
                data[2] = 0x00
                data[3] = 0x00
                data[4] = 0x00
                data[5] = 0x00
                data[6] = 0x00
                data[7] = 0x00

                # print("BLOCKED:", data.hex())

                IN_MODE = 1

                msg = can.Message(
                    arbitration_id=msg.arbitration_id,
                    data=data,
                    dlc=8,
                    is_extended_id=msg.is_extended_id
                )

                system_bus.send(msg)
                return

            # ==================================================
            # TRYB TRANSPARENT
            # ==================================================
            if (
                mode == 0
                and no_pilot == 0
            ):

                IN_MODE = 2

                if (
                    speed_limit == 1
                    and msg.arbitration_id == 0x3A0
                    and msg.dlc == 8
                ):

                    data = bytearray(msg.data)

                    # LIMIT PREDKOSCI
                    limit = 20

                    for i in (5, 6, 7):

                        if i < len(data):

                            data[i] = min(
                                data[i],
                                limit
                            )

                    IN_MODE = 3

                    msg = can.Message(
                        arbitration_id=msg.arbitration_id,
                        data=data,
                        dlc=msg.dlc,
                        is_extended_id=msg.is_extended_id
                    )

                system_bus.send(msg)
                return

            # ==================================================
            # TRYB MODYFIKACJI
            # ==================================================
            if (
                mode in MODES
                and msg.arbitration_id == 0x3A0
                and msg.dlc == 8
            ):

                data = bytearray(msg.data)

                byte1, indexX = MODES[mode]

                data[1] = byte1
                data[indexX] = speed

                IN_MODE = 10 + mode

                msg = can.Message(
                    arbitration_id=msg.arbitration_id,
                    data=data,
                    dlc=msg.dlc,
                    is_extended_id=msg.is_extended_id
                )

                system_bus.send(msg)

                MODIFIED_1_4_3A0_SENT = MODIFIED_1_4_3A0_SENT + 1
                
                if (MODIFIED_1_4_3A0_SENT > 250):
                    MODIFIED_1_4_3A0_SENT = 0

                return

            # ==================================================
            # SEND
            # ==================================================
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
notifier_pilot = can.Notifier(
    pilot_bus,
    [PilotToSystem()]
)

notifier_system = can.Notifier(
    system_bus,
    [SystemToPilot()]
)

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
