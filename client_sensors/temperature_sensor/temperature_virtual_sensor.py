import socket
import json
import time
import random

BROKER_IP = "127.0.0.1"
PORT = 1883
CLIENT_ID = "TEMP_NODE_01"
TOPIC = "greenhouse/temp"

def read_sensor_data(current_temp):
    variation = random.uniform(-0.2, 0.2)
    return round(current_temp + variation, 2)

def build_mqtt_packet(packet_type, topic, payload_dict):
    """
    Constructs a raw MQTT-like packet using bitwise operations.
    Structure: [Control Header] [Remaining Length] [Topic Length] [Topic] [Payload]
    """

    payload = json.dumps(payload_dict).encode('utf-8')
    topic_bytes = topic.encode('utf-8')

    header = (packet_type << 4) | 0x00 
    
    topic_len = len(topic_bytes)
    topic_header = bytearray([topic_len >> 8, topic_len & 0xFF])
    
    remaining_length = len(topic_header) + len(topic_bytes) + len(payload)
    
    packet = bytearray()
    packet.append(header)
    
    packet.append(remaining_length & 0x7F)
    
    packet.extend(topic_header)
    packet.extend(topic_bytes)
    packet.extend(payload)
    
    return packet

def run_node():
    current_temp = 25.0
    print(f"[{CLIENT_ID}] Initializing Bitwise Sensor Node...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        print(f"[{CLIENT_ID}] TCP Socket Established.")

        while True:
            # 1. Read
            current_temp = read_sensor_data(current_temp)
            
            # 2. Prepare Data
            data = {"id": CLIENT_ID, "val": current_temp, "u": "C"}
            
            # 3. Build & Send (Type 3 = PUBLISH)
            packet = build_mqtt_packet(3, TOPIC, data)
            sock.sendall(packet)
            
            # Debug: View raw bytes being sent
            print(f"[{CLIENT_ID}] Sent {len(packet)} bytes: {packet.hex().upper()}")
            print(f"[{CLIENT_ID}] Temperature: {current_temp} C")
            
            time.sleep(5)
            
    except Exception as e:
        print(f"[{CLIENT_ID}] Runtime Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_node()