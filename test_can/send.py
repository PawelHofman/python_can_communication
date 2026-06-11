import can
import time
import os

os.system(f"sudo ip link set can0 down")
os.system(f"sudo ip link set can0 up type can bitrate 125000 restart-ms 50")
time.sleep(0.5)


# Konfiguracja magistrali CAN
bus = can.interface.Bus(channel='can0', bustype='socketcan')

# Dane ramki
arbitration_id = 0x0A0
data = [0x11, 0x00, 0xFF, 0xAA]

# Tworzenie wiadomości
msg = can.Message(arbitration_id=arbitration_id,
                  data=data,
                  is_extended_id=False)






print("Wysyłanie ramek CAN co 200 ms...")

try:
    while True:
        bus.send(msg)
        print(f"Wysłano: ID={hex(arbitration_id)} DATA={data}")
        time.sleep(0.2)

except KeyboardInterrupt:
    print("Zatrzymano program")
