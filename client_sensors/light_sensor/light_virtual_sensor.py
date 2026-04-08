import socket
import json
import time
import random
import os

BROKER_IP = os.environ.get("BROKER_IP", "127.0.0.1")
PORT = int(os.environ.get("BROKER_PORT", "9998"))
CLIENT_ID = "LIGHT_NODE_03"
TOPIC = "greenhouse/light"

def read_sensor_data(last_value):
    drift = random.uniform(-15.0, 15.0)
    
    if last_value > 900.0: drift -= 10.0
    if last_value < 100.0: drift += 10.0
    
    new_lux = last_value + drift
    return round(max(0.0, new_lux), 1)

def encode_remaining_length(length):
    encoded = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 0x80
        encoded.append(byte)
        if length == 0:
            break
    return encoded

def build_connect_packet(client_id):
    proto = "MQTT".encode('utf-8')
    var_h = bytearray([0x00, 0x04]) + proto + bytearray([0x04, 0x02, 0x00, 0x3C])
    cid = client_id.encode('utf-8')
    payload = bytearray([len(cid) >> 8, len(cid) & 0xFF]) + cid
    rl_bytes = encode_remaining_length(len(var_h) + len(payload))
    return bytearray([0x10]) + rl_bytes + var_h + payload

def build_mqtt_packet(packet_type, topic, payload_dict):
    payload = json.dumps(payload_dict).encode('utf-8')
    topic_bytes = topic.encode('utf-8')
    
    header = (packet_type << 4) | 0x00
    topic_len = len(topic_bytes)
    topic_header = bytearray([topic_len >> 8, topic_len & 0xFF])
    
    var_h_and_payload = topic_header + topic_bytes + payload
    rl_bytes = encode_remaining_length(len(var_h_and_payload))
    
    return bytearray([header]) + rl_bytes + var_h_and_payload

def run_node():
    current_lux = 500.0 
    print(f"[{CLIENT_ID}] Initializing Light Monitoring Node...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        
        conn_pkt = build_connect_packet(CLIENT_ID)
        sock.sendall(conn_pkt)
        time.sleep(0.5)
        
        print(f"[{CLIENT_ID}] Successfully connected to Fransmitto at {BROKER_IP}:{PORT}.")

        while True:
            current_lux = read_sensor_data(current_lux)
            
            data = {
                "id": CLIENT_ID,
                "value": current_lux,
                "unit": "lux",
                "ts": int(time.time())
            }
            
            packet = build_mqtt_packet(3, TOPIC, data)
            sock.sendall(packet)
            
            print(f"[{CLIENT_ID}] Luminosity: {current_lux} lux")
            
            time.sleep(2)
            
    except Exception as e:
        print(f"[{CLIENT_ID}] Connection Lost: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_node()