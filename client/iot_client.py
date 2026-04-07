import socket
import json
import threading
import sys
import time

BROKER_IP = "127.0.0.1"
PORT = 1883
CLIENT_ID = "CLI_DASH_01"

greenhouse_state = {
    "temp": 0.0,
    "rh": 0.0,
    "lux": 0.0,
    "gas": 0.0
}

def calculate_health_percentage():
    return abs(greenhouse_state["temp"]) + abs(greenhouse_state["rh"]) + abs(greenhouse_state["lux"]) + abs(greenhouse_state["gas"])

def build_connect_packet(client_id):
    protocol_name = "MQTT".encode('utf-8')
    var_header = bytearray([0x00, 0x04]) + protocol_name + bytearray([0x04, 0x02, 0x00, 0x3C])
    
    client_id_bytes = client_id.encode('utf-8')
    payload = bytearray([len(client_id_bytes) >> 8, len(client_id_bytes) & 0xFF]) + client_id_bytes
    
    remaining_length = len(var_header) + len(payload)
    packet = bytearray([0x10, remaining_length]) + var_header + payload
    
    return packet

def build_publish_packet(topic, payload_dict):
    payload = json.dumps(payload_dict).encode('utf-8')
    topic_bytes = topic.encode('utf-8')
    
    header = (3 << 4) | 0x00
    topic_len = len(topic_bytes)
    topic_header = bytearray([topic_len >> 8, topic_len & 0xFF])
    remaining_length = len(topic_header) + len(topic_bytes) + len(payload)
    
    packet = bytearray([header, remaining_length & 0x7F]) + topic_header + topic_bytes + payload
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

def ping_loop(sock):
    while True:
        time.sleep(45)
        try:
            sock.sendall(build_ping_packet())
        except:
            break

def receive_loop(sock):
    while True:
        try:
            raw_data = sock.recv(1024)
            if not raw_data: 
                print("\n[ERROR] Connection to Broker lost.")
                sys.exit(0)

            print(f"\n[BROKER -> CLI] Hex Packet: {raw_data.hex().upper()}")

            json_start = raw_data.find(b'{')
            if json_start != -1:
                payload = json.loads(raw_data[json_start:].decode('utf-8'))
                
                sid = payload.get("id", "")
                if "TEMP" in sid: greenhouse_state["temp"] = payload.get("val", payload.get("value", 0.0))
                elif "HUMID" in sid: greenhouse_state["rh"] = payload.get("rh", 0.0)
                elif "LIGHT" in sid: greenhouse_state["lux"] = payload.get("lux", 0.0)
                elif "GAS" in sid: greenhouse_state["gas"] = payload.get("ppm", 0.0)

                health = calculate_health_percentage()
                print("-" * 60)
                print(f"GREENHOUSE LIFE INDEX: {health}")
                print(f"Temp: {greenhouse_state['temp']}C | RH: {greenhouse_state['rh']}% | Lux: {greenhouse_state['lux']} | Gas: {greenhouse_state['gas']}ppm")
                print("-" * 60)
                
            print("Command > ", end="", flush=True)
            
        except Exception:
            pass

def input_loop(sock):
    time.sleep(1)
    print("\n" + "="*60)
    print(" ACTUATOR CONTROL PANEL")
    print("="*60)
    print("Available commands:")
    print("  curtain <0-100>")
    print("  irrigation <seconds>")
    print("  exit")
    print("="*60 + "\n")

    while True:
        cmd = input("Command > ").strip().lower()
        if not cmd: continue

        topic = ""
        payload = {}

        if cmd.startswith("curtain"):
            topic = "greenhouse/actuators/curtain"
            try:
                pos = int(cmd.split()[1])
                payload = {"position": pos}
            except:
                print("[ERROR] Invalid format. Use: curtain 50")
                continue
                
        elif cmd.startswith("irrigation"):
            topic = "greenhouse/actuators/irrigation"
            try:
                sec = int(cmd.split()[1])
                payload = {"duration_sec": sec}
            except:
                print("[ERROR] Invalid format. Use: irrigation 10")
                continue
                
        elif cmd == "exit":
            print("Closing Dashboard...")
            sock.close()
            sys.exit(0)
            
        else:
            print("[ERROR] Unknown command.")
            continue

        packet = build_publish_packet(topic, payload)
        
        print(f"[CLI -> BROKER] Hex Packet: {packet.hex().upper()}")
        sock.sendall(packet)

def start_cli():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        print(f"[{CLIENT_ID}] Connected to Broker at {BROKER_IP}")

        conn_packet = build_connect_packet(CLIENT_ID)
        print(f"[CLI -> BROKER] CONNECT Hex: {conn_packet.hex().upper()}")
        sock.sendall(conn_packet)
        
        time.sleep(0.5)

        topics_to_monitor = [
            "greenhouse/temp",
            "greenhouse/humidity",
            "greenhouse/light",
            "greenhouse/gas",
            "greenhouse/state/curtain"
        ]

        for topic in topics_to_monitor:
            sub_packet = build_subscribe_packet(topic)
            print(f"[CLI -> BROKER] SUBSCRIBE '{topic}' Hex: {sub_packet.hex().upper()}")
            sock.sendall(sub_packet)
            time.sleep(0.1)

        ping_thread = threading.Thread(target=ping_loop, args=(sock,))
        ping_thread.daemon = True
        ping_thread.start()

        listener = threading.Thread(target=receive_loop, args=(sock,))
        listener.daemon = True
        listener.start()

        input_loop(sock)

    except Exception as e:
        print(f"Failed to start CLI: {e}")

if __name__ == "__main__":
    start_cli()