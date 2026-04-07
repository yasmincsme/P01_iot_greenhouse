import socket
import json
import time
import math
import random

# Network Config
BROKER_IP = "127.0.0.1"
PORT = 1883
CLIENT_ID = "LIGHT_NODE_03"
TOPIC = "greenhouse/light"

# --- HARDWARE LAYER (DATA ACQUISITION) ---
def read_sensor_data():
    """
    Simulates a BH1750 or LDR sensor measuring luminosity in Lux.
    Uses a sine wave base to simulate the 24h solar cycle + random noise.
    """
    # 1. Base cycle (Simulation of daylight based on system time)
    t = time.localtime()
    seconds_since_midnight = t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec
    day_fraction = seconds_since_midnight / 86400
    
    # Peak at 12:00 PM (Sine wave)
    intensity = math.sin((day_fraction * 2 * math.pi) - (math.pi / 2))
    ambient_lux = max(0, intensity * 800) # Max 800 Lux (bright day)
    
    # 2. Add high-frequency noise or "events" (cloud passing or light switch)
    event_noise = random.uniform(-5, 5)
    if random.random() > 0.97:
        event_noise += 200 # Sudden light increase
        
    return round(max(0, ambient_lux + event_noise), 1)

# --- NETWORK LAYER (BITWISE PROTOCOL) ---
def build_mqtt_packet(packet_type, topic, payload_dict):
    """
    Constructs a raw MQTT-like packet using bitwise operations.
    [Control Header] [Remaining Length] [Topic Length MSB/LSB] [Topic] [Payload]
    """
    payload = json.dumps(payload_dict).encode('utf-8')
    topic_bytes = topic.encode('utf-8')
    
    # 1. Control Packet Type (3 = PUBLISH) << 4
    # Result: 0x30
    header = (packet_type << 4) | 0x00
    
    # 2. Topic Length (2-byte MSB/LSB) - Critical for Broker's parser
    topic_len = len(topic_bytes)
    topic_header = bytearray([topic_len >> 8, topic_len & 0xFF])
    
    # 3. Remaining Length (Bytes following the length byte)
    remaining_length = len(topic_header) + len(topic_bytes) + len(payload)
    
    packet = bytearray()
    packet.append(header)
    
    # Encoding length (Standard 7-bit encoding for small packets)
    packet.append(remaining_length & 0x7F)
    
    packet.extend(topic_header)
    packet.extend(topic_bytes)
    packet.extend(payload)
    
    return packet

def run_node():
    print(f"[{CLIENT_ID}] Starting Optical Monitoring System...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        print(f"[{CLIENT_ID}] Connected to Fransmitto Broker.")

        while True:
            # 1. Read (Hardware Abstraction)
            current_lux = read_sensor_data()
            
            # 2. Prepare Payload
            data = {
                "id": CLIENT_ID,
                "lux": current_lux,
                "unit": "lx",
                "ts": int(time.time())
            }
            
            # 3. Bitwise Assembly and Transmission
            packet = build_mqtt_packet(3, TOPIC, data)
            sock.sendall(packet)
            
            # Monitoring Output
            print(f"[{CLIENT_ID}] Luminosity: {current_lux} Lux")
            
            # Sampling rate: 2 seconds (faster for lighting automation)
            time.sleep(2)
            
    except Exception as e:
        print(f"[{CLIENT_ID}] Runtime Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_node()