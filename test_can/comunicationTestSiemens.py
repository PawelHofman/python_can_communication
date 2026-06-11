
import snap7
import time

# =========================
# KONFIGURACJA
# =========================
PLC_IP = "192.168.0.1"
RACK = 0
SLOT = 1

cnt = 1

DB_READ = 191   # odczyt
DB_WRITE = 192  # zapis

# =========================
# POŁĄCZENIE
# =========================
client = snap7.client.Client()

print("Connecting to PLC...")
client.connect(PLC_IP, RACK, SLOT)
print("Connected")

# =========================
# PĘTLA GŁÓWNA
# =========================
while True:
    try:
        # odczyt 3 bajtów z DB991
        data = client.db_read(DB_READ, 0, 3)

        byte0 = data[0]
        byte1 = data[1]
        byte2 = data[2]

        print(f"READ -> b0:{byte0} b1:{byte1} b2:{byte2}")

        # inkrementacja (0–255)
        cnt = (cnt + 1) % 255
        # new_value = (byte0 + 1)

        # zapis do DB992
        send_buf = bytearray(1)
        send_buf[0] = cnt

        client.db_write(DB_WRITE, 0, send_buf)

        print(f"WRITE -> b0:{cnt}")

    except Exception as e:
        print(f"ERROR: {e}")
        try:
            client.disconnect()
        except:
            pass

        time.sleep(2)

        try:
            client.connect(PLC_IP, RACK, SLOT)
        except:
            pass

    time.sleep(1)
