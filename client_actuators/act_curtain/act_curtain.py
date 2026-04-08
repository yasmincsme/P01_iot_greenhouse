import socket
import json
import time
import threading

BROKER_IP = "127.0.0.1"
PORT = 9998
CLIENT_ID = "ACT_CURTAIN_01"
COMMAND_TOPIC = "greenhouse/actuators/curtain"
current_position = 0

def build_connect_packet(client_id):
    protocol_name = "MQTT".encode('utf-8')
    var_header = bytearray([0x00, 0x04]) + protocol_name + bytearray([0x04, 0x02, 0x00, 0x3C])
    
    client_id_bytes = client_id.encode('utf-8')
    payload = bytearray([len(client_id_bytes) >> 8, len(client_id_bytes) & 0xFF]) + client_id_bytes
    
    remaining_length = len(var_header) + len(payload)
    packet = bytearray([0x10, remaining_length]) + var_header + payload
    
    return packet

def build_subscribe_packet(topic):
    topic_bytes = topic.encode('utf-8')
    topic_len = len(topic_bytes)
    
    header = (8 << 4) | 0x02
    packet_id = bytearray([0x00, 0x01])
    payload = bytearray([topic_len >> 8, topic_len & 0xFF]) + topic_bytes + b'\x00'
    
    remaining_length = len(packet_id) + len(payload)
    packet = bytearray([header, remaining_length & 0x7F]) + packet_id + payload
    return packet

def build_ping_packet():
    return bytearray([0xC0, 0x00])

def process_command(raw_payload):
    global current_position
    data = json.loads(raw_payload.decode('utf-8'))
    target_pos = data.get("position", current_position)
    
    if target_pos > current_position:
        print(f"[{CLIENT_ID}] Closing to {target_pos}%...")
    elif target_pos < current_position:
        print(f"[{CLIENT_ID}] Opening to {target_pos}%...")
    
    current_position = target_pos

def status_loop():
    while True:
        print(f"[{CLIENT_ID}] Current position: {current_position}%")
        time.sleep(5)

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
        
        conn_packet = build_connect_packet(CLIENT_ID)
        sock.sendall(conn_packet)
        time.sleep(0.5)
        
        sub_packet = build_subscribe_packet(COMMAND_TOPIC)
        sock.sendall(sub_packet)

        status_thread = threading.Thread(target=status_loop)
        status_thread.daemon = True
        status_thread.start()

        ping_thread = threading.Thread(target=ping_loop, args=(sock,))
        ping_thread.daemon = True
        ping_thread.start()

        while True:
            packet = sock.recv(1024)
            if not packet: 
                break
            
            json_start = packet.find(b'{')
            if json_start != -1:
                process_command(packet[json_start:])

    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_actuator()