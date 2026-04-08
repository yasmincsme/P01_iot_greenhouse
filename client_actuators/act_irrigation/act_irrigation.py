import socket
import json
import time
import threading
import os
import logging

BROKER_IP = os.environ.get("BROKER_IP", "127.0.0.1")
PORT = int(os.environ.get("BROKER_PORT", "9998"))
CLIENT_ID = "ACT_IRRIGATION_01"
COMMAND_TOPIC = "greenhouse/actuators/irrigation"

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

def build_subscribe_packet(topic):
    topic_bytes = topic.encode('utf-8')
    pid = bytearray([0x00, 0x01])
    payload = bytearray([len(topic_bytes) >> 8, len(topic_bytes) & 0xFF]) + topic_bytes + b'\x00'
    var_h_and_payload = pid + payload
    rl_bytes = encode_remaining_length(len(var_h_and_payload))
    return bytearray([0x82]) + rl_bytes + var_h_and_payload

def build_ping_packet():
    return bytearray([0xC0, 0x00])

def read_fixed_header(sock):
    byte_1_raw = sock.recv(1)
    if not byte_1_raw:
        return None, None, None
    byte_1 = byte_1_raw[0]
    packet_type = byte_1 >> 4
    flags = byte_1 & 0x0F
    
    multiplier = 1
    remaining_length = 0
    for _ in range(4):
        byte_2_raw = sock.recv(1)
        if not byte_2_raw:
            return None, None, None
        byte_2 = byte_2_raw[0]
        remaining_length += (byte_2 & 0x7F) * multiplier
        multiplier *= 128
        if (byte_2 & 0x80) == 0:
            break
    else:
        return None, None, None
    return packet_type, flags, remaining_length

def process_command(raw_payload):
    try:
        data = json.loads(raw_payload.decode('utf-8'))
        duration = data.get("duration_sec", 0)
        
        if duration > 0:
            logging.warning(f"[{CLIENT_ID}] Valve open! Irrigating for {duration} seconds...")
            time.sleep(duration)
            logging.warning(f"[{CLIENT_ID}] Irrigation complete. Valve closed.")
    except Exception as e:
        logging.warning(f"[{CLIENT_ID}] Failed to process command: {e}")

def ping_loop(sock):
    while True:
        time.sleep(45)
        try:
            sock.sendall(build_ping_packet())
        except:
            break

def run_actuator():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        
        sock.sendall(build_connect_packet(CLIENT_ID))
        time.sleep(0.5)
        sock.sendall(build_subscribe_packet(COMMAND_TOPIC))
        logging.warning(f"[{CLIENT_ID}] Successfully connected and listening on: {COMMAND_TOPIC}")

        threading.Thread(target=ping_loop, args=(sock,), daemon=True).start()

        while True:
            packet_type, flags, remaining_length = read_fixed_header(sock)
            if packet_type is None:
                break
                
            payload_data = b''
            while len(payload_data) < remaining_length:
                chunk = sock.recv(remaining_length - len(payload_data))
                if not chunk:
                    break
                payload_data += chunk
            
            if packet_type == 3:
                qos = (flags & 0x06) >> 1
                topic_len = int.from_bytes(payload_data[0:2], byteorder='big')
                offset = 2 + topic_len
                if qos > 0:
                    offset += 2
                message_bytes = payload_data[offset:]
                process_command(message_bytes)

    except Exception as e:
        logging.warning(f"[{CLIENT_ID}] Runtime Error: {e}")
    finally:
        try:
            sock.close()
        except:
            pass

if __name__ == "__main__":
    run_actuator()