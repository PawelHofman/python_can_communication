import can
import os
import time

def setup_can(interface='can1', bitrate=125000):
    os.system(f"sudo ip link set {interface} down")
    os.system(f"sudo ip link set {interface} up type can bitrate {bitrate}")
    time.sleep(0.5)

setup_can('can1')

bus = can.interface.Bus(channel='can1', bustype='socketcan')

print("Nasłuchiwanie...")

while True:
    msg = bus.recv()
    if msg and msg.arbitration_id == 0x0A0:
        print(msg)
