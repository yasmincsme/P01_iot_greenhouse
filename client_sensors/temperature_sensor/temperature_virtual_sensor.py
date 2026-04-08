import socket
import json
import time
import random
import os
import logging

BROKER_IP = os.environ.get("BROKER_IP", "127.0.0.1")
PORT = int(os.environ.get("BROKER_PORT", "9998"))
CLIENT_ID = "TEMP_NODE_01"
TOPIC = "greenhouse/temp"

def read_sensor_data(last_value):
    drift = random.uniform(-0.5, 0.5)
    
    if last_value > 35.0: drift -= 0.3
    if last_value < 15.0: drift += 0.3
    
    new_temp = last_value + drift
    return round(new_temp, 2)

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
    current_temp = 25.0 
    logging.warning(f"[{CLIENT_ID}] Starting Temperature Monitoring System...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        
        conn_pkt = build_connect_packet(CLIENT_ID)
        sock.sendall(conn_pkt)
        time.sleep(0.5)
        
        logging.warning(f"[{CLIENT_ID}] Connected to BROKER at {BROKER_IP}:{PORT}.")

        while True:
            current_temp = read_sensor_data(current_temp)
            
            data = {
                "id": CLIENT_ID,
                "value": current_temp,
                "unit": "C",
                "ts": int(time.time())
            }
            
            packet = build_mqtt_packet(3, TOPIC, data)
            sock.sendall(packet)
            
            logging.warning(f"[{CLIENT_ID}] Temperature: {current_temp} C")
            
            time.sleep(5)
            
    except Exception as e:
        logging.warning(f"[{CLIENT_ID}] Connection Failed: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_node()