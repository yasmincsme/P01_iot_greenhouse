import socket
import json
import time
import random

# Network Config
BROKER_IP = "127.0.0.1"
PORT = 1883
CLIENT_ID = "GAS_NODE_04"
TOPIC = "greenhouse/gas"

# --- HARDWARE LAYER (DATA ACQUISITION) ---
def read_sensor_data():
    """
    Simulates an MQ-2 Gas Sensor measuring CO2/Smoke in PPM.
    """
    base_ppm = 18.0  # Unificando o nome da variável
    
    # 2% chance of a spike (leak simulation)
    if random.random() > 0.98:
        return round(base_ppm + random.uniform(150, 400), 2)
    
    # Normal environmental fluctuation (usando a variável correta agora)
    return round(base_ppm + random.uniform(-1.5, 1.5), 2)

# --- NETWORK LAYER (BITWISE PROTOCOL) ---
def build_mqtt_packet(packet_type, topic, payload_dict):
    """
    Constructs a raw MQTT-like packet using bitwise operations.
    [Control Header] [Remaining Length] [Topic Length MSB/LSB] [Topic] [Payload]
    """
    payload = json.dumps(payload_dict).encode('utf-8')
    topic_bytes = topic.encode('utf-8')
    
    # 1. Control Packet Type (3 = PUBLISH)
    # Binary: 0011 0000 -> 0x30
    header = (packet_type << 4) | 0x00
    
    # 2. Topic Length (2-byte MSB/LSB)
    topic_len = len(topic_bytes)
    topic_header = bytearray([topic_len >> 8, topic_len & 0xFF])
    
    # 3. Remaining Length
    # Total bytes following the 'Remaining Length' byte
    remaining_length = len(topic_header) + len(topic_bytes) + len(payload)
    
    packet = bytearray()
    packet.append(header)
    
    # Encoding length (Assuming < 127 bytes for simplicity)
    packet.append(remaining_length & 0x7F)
    
    packet.extend(topic_header)
    packet.extend(topic_bytes)
    packet.extend(payload)
    
    return packet

def run_node():
    print(f"[{CLIENT_ID}] Starting Gas Monitoring System...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        print(f"[{CLIENT_ID}] Connected to Fransmitto Broker.")

        while True:
            # 1. Read (Hardware Abstraction)
            gas_ppm = read_sensor_data()
            
            # 2. Logic: Define if it's a dangerous level
            is_danger = gas_ppm > 100.0
            
            # 3. Prepare Payload
            data = {
                "id": CLIENT_ID,
                "ppm": gas_ppm,
                "alert": is_danger,
                "ts": int(time.time())
            }
            
            # 4. Bitwise Assembly and Transmission (Type 3 = PUBLISH)
            packet = build_mqtt_packet(3, TOPIC, data)
            sock.sendall(packet)
            
            # Monitoring Output
            status = "!!! DANGER !!!" if is_danger else "NORMAL"
            print(f"[{CLIENT_ID}] Gas Level: {gas_ppm} PPM | Status: {status}")
            print(f"DEBUG: Sent {len(packet)} raw bytes.")
            
            # Fast sampling for safety-critical data
            time.sleep(3)
            
    except Exception as e:
        print(f"[{CLIENT_ID}] Connection Failed: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_node()