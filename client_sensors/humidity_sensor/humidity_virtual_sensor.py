import socket
import json
import time
import random

# Network Config
BROKER_IP = "127.0.0.1"
PORT = 1883
CLIENT_ID = "HUMID_NODE_02"
TOPIC = "greenhouse/humidity"

# --- HARDWARE LAYER (DATA ACQUISITION) ---
def read_sensor_data(last_value):
    """
    Simulates a capacitive humidity sensor (like DHT22).
    Includes small drifts and noise typical of high-quality industrial probes.
    """
    # 1. Base drift: Small random walk
    drift = random.uniform(-0.15, 0.15)
    
    # 2. Boundary logic: Keep it between 20% and 95% for a realistic greenhouse
    if last_value > 85: drift -= 0.1
    if last_value < 35: drift += 0.1
    
    new_rh = last_value + drift
    return round(max(0, min(100, new_rh)), 1)

# --- NETWORK LAYER (BITWISE PROTOCOL) ---
def build_mqtt_packet(packet_type, topic, payload_dict):
    """
    Constructs a raw MQTT-like packet using bitwise operations.
    [Control Header] [Remaining Length] [Topic Length MSB/LSB] [Topic] [Payload]
    """
    payload = json.dumps(payload_dict).encode('utf-8')
    topic_bytes = topic.encode('utf-8')
    
    # 1. Control Packet Type (3 = PUBLISH) << 4
    # Binary: 0011 0000 -> 0x30
    header = (packet_type << 4) | 0x00
    
    # 2. Topic Length (2-byte MSB/LSB)
    topic_len = len(topic_bytes)
    topic_header = bytearray([topic_len >> 8, topic_len & 0xFF])
    
    # 3. Remaining Length (Topic Header + Topic + Payload)
    remaining_length = len(topic_header) + len(topic_bytes) + len(payload)
    
    packet = bytearray()
    packet.append(header)
    
    # Encoding length (7-bit byte format)
    packet.append(remaining_length & 0x7F)
    
    packet.extend(topic_header)
    packet.extend(topic_bytes)
    packet.extend(payload)
    
    return packet

def run_node():
    # Initial Relative Humidity (RH) setpoint
    current_rh = 60.0 
    print(f"[{CLIENT_ID}] Initializing Humidity Monitoring Node...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        print(f"[{CLIENT_ID}] Successfully connected to Fransmitto.")

        while True:
            # 1. Read (Hardware Abstraction)
            current_rh = read_sensor_data(current_rh)
            
            # 2. Prepare Data
            data = {
                "id": CLIENT_ID,
                "rh": current_rh,
                "unit": "%",
                "ts": int(time.time())
            }
            
            # 3. Bitwise Assembly and Transmission (Type 3 = PUBLISH)
            packet = build_mqtt_packet(3, TOPIC, data)
            sock.sendall(packet)
            
            # Monitoring Output
            print(f"[{CLIENT_ID}] Humidity: {current_rh}% | Sent {len(packet)} bytes.")
            
            # Sampling rate: 10 seconds (Standard for slow-changing environmental variables)
            time.sleep(10)
            
    except Exception as e:
        print(f"[{CLIENT_ID}] Connection Lost: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_node()