# import socket
# import json
# import time
# import random
# import os
# import logging

# BROKER_IP = os.environ.get("BROKER_IP", "127.0.0.1")
# PORT = int(os.environ.get("BROKER_PORT", "9998"))
# CLIENT_ID = "HUMID_NODE_02"
# TOPIC = "greenhouse/humidity"

# def read_sensor_data(last_value):
#     drift = random.uniform(-0.15, 0.15)
    
#     if last_value > 85: drift -= 0.1
#     if last_value < 35: drift += 0.1
    
#     new_rh = last_value + drift
#     return round(max(0, min(100, new_rh)), 1)

# def encode_remaining_length(length):
#     encoded = bytearray()
#     while True:
#         byte = length % 128
#         length //= 128
#         if length > 0:
#             byte |= 0x80
#         encoded.append(byte)
#         if length == 0:
#             break
#     return encoded

# def build_connect_packet(client_id):
#     proto = "MQTT".encode('utf-8')
#     var_h = bytearray([0x00, 0x04]) + proto + bytearray([0x04, 0x02, 0x00, 0x3C])
#     cid = client_id.encode('utf-8')
#     payload = bytearray([len(cid) >> 8, len(cid) & 0xFF]) + cid
#     rl_bytes = encode_remaining_length(len(var_h) + len(payload))
#     return bytearray([0x10]) + rl_bytes + var_h + payload

# def build_mqtt_packet(packet_type, topic, payload_dict):
#     payload = json.dumps(payload_dict).encode('utf-8')
#     topic_bytes = topic.encode('utf-8')
    
#     header = (packet_type << 4) | 0x00
#     topic_len = len(topic_bytes)
#     topic_header = bytearray([topic_len >> 8, topic_len & 0xFF])
    
#     var_h_and_payload = topic_header + topic_bytes + payload
#     rl_bytes = encode_remaining_length(len(var_h_and_payload))
    
#     return bytearray([header]) + rl_bytes + var_h_and_payload

# def run_node():
#     current_rh = 60.0 
#     logging.warning(f"[{CLIENT_ID}] Starting Humidity Monitoring System...")
    
#     try:
#         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         sock.connect((BROKER_IP, PORT))
        
#         conn_pkt = build_connect_packet(CLIENT_ID)
#         sock.sendall(conn_pkt)
#         time.sleep(0.5)
        
#         logging.warning(f"[{CLIENT_ID}] Connected to BROKER at {BROKER_IP}:{PORT}.")

#         while True:
#             current_rh = read_sensor_data(current_rh)
            
#             data = {
#                 "id": CLIENT_ID,
#                 "value": current_rh,
#                 "unit": "%",
#                 "ts": int(time.time())
#             }
            
#             packet = build_mqtt_packet(3, TOPIC, data)
#             sock.sendall(packet)
            
#             logging.warning(f"[{CLIENT_ID}] Humidity: {current_rh}%")
            
#             time.sleep(10)
            
#     except Exception as e:
#         logging.warning(f"[{CLIENT_ID}] Connection Failed: {e}")

#     finally:
#         sock.close()

# if __name__ == "__main__":
#     run_node()

import socket
import threading
import time
import json
import random
import os

BROKER_IP = os.environ.get("BROKER_IP", "127.0.0.1")
PORT = int(os.environ.get("BROKER_PORT", "9998"))
NUM_CLIENTS = 200
MESSAGES_PER_CLIENT = 50
DELAY_BETWEEN_MSGS = 0.1

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
    proto = b"MQTT"
    var_h = bytearray([0x00, 0x04]) + proto + bytearray([0x04, 0x02, 0x00, 0x3C])
    cid = client_id.encode('utf-8')
    payload = bytearray([len(cid) >> 8, len(cid) & 0xFF]) + cid
    rl = encode_remaining_length(len(var_h) + len(payload))
    return bytearray([0x10]) + rl + var_h + payload

def build_publish_packet(topic, payload_dict):
    payload = json.dumps(payload_dict).encode('utf-8')
    tb = topic.encode('utf-8')
    th = bytearray([len(tb) >> 8, len(tb) & 0xFF])
    content = th + tb + payload
    rl = encode_remaining_length(len(content))
    return bytearray([0x30]) + rl + content

def simulate_heavy_client(client_id):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        sock.sendall(build_connect_packet(client_id))
        
        time.sleep(random.uniform(0.1, 1.0))
        
        for i in range(MESSAGES_PER_CLIENT):
            data = {"id": client_id, "value": random.uniform(20.0, 30.0), "load_test": True}
            pkt = build_publish_packet("greenhouse/temp", data)
            sock.sendall(pkt)
            time.sleep(DELAY_BETWEEN_MSGS)
            
        sock.close()
        print(f"[{client_id}] Success")
    except Exception as e:
        print(f"[{client_id}] Error: {e}")

if __name__ == "__main__":
    print(f"Starting MQTT Load Test on {BROKER_IP}:{PORT}...")
    start_time = time.time()
    threads = []
    
    for i in range(NUM_CLIENTS):
        t = threading.Thread(target=simulate_heavy_client, args=(f"LOAD_NODE_{i}",))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    duration = time.time() - start_time
    total_messages = NUM_CLIENTS * MESSAGES_PER_CLIENT
    throughput = total_messages / duration
    
    print(f"Duration: {duration:.2f} s")
    print(f"Throughput: {throughput:.2f} msg/s")












# import socket
# import json
# import time
# import random
# import os
# import logging
# import sys

# BROKER_IP = os.environ.get("BROKER_IP", "127.0.0.1")
# PORT = int(os.environ.get("BROKER_PORT", "9998"))
# CLIENT_ID = "HUMID_NODE_03"
# TOPIC = "greenhouse/humidity"

# # Configuração de logging para facilitar a leitura no terminal
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# def read_sensor_data(last_value):
#     drift = random.uniform(-0.15, 0.15)
#     if last_value > 85: drift -= 0.1
#     if last_value < 35: drift += 0.1
#     new_rh = last_value + drift
#     return round(max(0, min(100, new_rh)), 1)

# def encode_remaining_length(length):
#     encoded = bytearray()
#     while True:
#         byte = length % 128
#         length //= 128
#         if length > 0:
#             byte |= 0x80
#         encoded.append(byte)
#         if length == 0:
#             break
#     return encoded

# def build_connect_packet(client_id):
#     proto = "MQTT".encode('utf-8')
#     # Flags: 0x02 (Clean Session)
#     # Keep-Alive: 0x00 0x0F (15 segundos)
#     var_h = bytearray([0x00, 0x04]) + proto + bytearray([0x04, 0x02, 0x00, 0x0F])
    
#     cid = client_id.encode('utf-8')
#     payload = bytearray([len(cid) >> 8, len(cid) & 0xFF]) + cid
    
#     rl_bytes = encode_remaining_length(len(var_h) + len(payload))
#     return bytearray([0x10]) + rl_bytes + var_h + payload

# def build_mqtt_packet_qos2(topic, payload_dict, packet_id):
#     payload = json.dumps(payload_dict).encode('utf-8')
#     topic_bytes = topic.encode('utf-8')
    
#     # Header de PUBLISH com QoS 2 (Bits 1 e 2 = 10, Retain = 0) -> 0x34
#     header = 0x34
    
#     topic_len = len(topic_bytes)
#     var_header = bytearray([topic_len >> 8, topic_len & 0xFF]) + topic_bytes
    
#     # QoS 1 e 2 exigem obrigatoriamente o Packet Identifier (2 bytes)
#     var_header += bytearray([packet_id >> 8, packet_id & 0xFF])
    
#     var_h_and_payload = var_header + payload
#     rl_bytes = encode_remaining_length(len(var_h_and_payload))
    
#     return bytearray([header]) + rl_bytes + var_h_and_payload

# def build_pingreq_packet():
#     # Tipo 12 (0xC) com flags 0 -> 0xC0, Remaining length 0 -> 0x00
#     return bytearray([0xC0, 0x00])

# def run_node():
#     current_rh = 55.0 
#     logging.info(f"[{CLIENT_ID}] Starting Humidity Node (TESTE KEEP-ALIVE/QoS2)...")
    
#     try:
#         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         sock.connect((BROKER_IP, PORT))
        
#         # Enviar CONNECT
#         sock.sendall(build_connect_packet(CLIENT_ID))
#         time.sleep(0.5)
#         logging.info(f"[{CLIENT_ID}] Connected to BROKER at {BROKER_IP}:{PORT} (Keep-Alive: 15s).")

#         # ==============================================================
#         # FASE 1: SOBRECARGA COM PACOTES QoS 2
#         # ==============================================================
#         logging.warning(f"[{CLIENT_ID}] INICIANDO FASE 1: Rajada de pacotes QoS 2 (0x34)")
#         for packet_id in range(1, 6):
#             current_rh = read_sensor_data(current_rh)
#             data = {"id": CLIENT_ID, "value": current_rh, "unit": "%"}
            
#             packet = build_mqtt_packet_qos2(TOPIC, data, packet_id)
#             sock.sendall(packet)
#             logging.info(f"[{CLIENT_ID}] PUBLISH (QoS 2 | ID: {packet_id}) -> Enviado")
#             time.sleep(0.1) # Pausa muito curta para simular sobrecarga/burst
        
#         # ==============================================================
#         # FASE 2: MANUTENÇÃO DE SESSÃO COM PINGREQ (Silêncio de telemetria)
#         # ==============================================================
#         logging.warning(f"[{CLIENT_ID}] INICIANDO FASE 2: Silêncio de telemetria. Enviando apenas PINGREQ.")
#         ping_count = 1
#         while True:
#             # Esperamos 10 segundos (inferior ao Keep-Alive de 15s)
#             time.sleep(10)
            
#             logging.info(f"[{CLIENT_ID}] Enviando PINGREQ (Ping #{ping_count})...")
#             sock.sendall(build_pingreq_packet())
#             ping_count += 1
            
#             # Nota: O broker enviará o PINGRESP (0xD0) de volta. 
#             # Como é um teste de robustez, o sensor confia no socket aberto e não faz o recv().
            
#     except Exception as e:
#         logging.error(f"[{CLIENT_ID}] Connection Failed: {e}")
#     finally:
#         sock.close()

# if __name__ == "__main__":
#     run_node()


import socket
import json
import time
import random
import os
import logging
import sys

BROKER_IP = os.environ.get("BROKER_IP", "127.0.0.1")
PORT = int(os.environ.get("BROKER_PORT", "9998"))
CLIENT_ID = "HUMID_NODE_02"
TOPIC = "greenhouse/humidity"

def read_sensor_data(last_value):
    drift = random.uniform(-0.15, 0.15)
    if last_value > 85: drift -= 0.1
    if last_value < 35: drift += 0.1
    new_rh = last_value + drift
    return round(max(0, min(100, new_rh)), 1)

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

def build_connect_packet_with_lwt(client_id):
    proto = "MQTT".encode('utf-8')
    
    # Flags: 0x02 (Clean Session) + 0x04 (Will Flag) = 0x06
    # Keep-Alive: 0x00 0x0A (10 segundos) -> Para deteção rápida de falha
    var_h = bytearray([0x00, 0x04]) + proto + bytearray([0x04, 0x06, 0x00, 0x0A])
    
    cid = client_id.encode('utf-8')
    payload = bytearray([len(cid) >> 8, len(cid) & 0xFF]) + cid
    
    # Adicionando o Tópico de Testamento (LWT)
    will_topic = "greenhouse/alerts".encode('utf-8')
    payload += bytearray([len(will_topic) >> 8, len(will_topic) & 0xFF]) + will_topic
    
    # Adicionando a Mensagem de Testamento (LWT)
    will_msg = json.dumps({"alert": "CRITICAL", "message": f"{CLIENT_ID} CONNECTION LOST!"}).encode('utf-8')
    payload += bytearray([len(will_msg) >> 8, len(will_msg) & 0xFF]) + will_msg
    
    rl_bytes = encode_remaining_length(len(var_h) + len(payload))
    return bytearray([0x10]) + rl_bytes + var_h + payload

def build_mqtt_packet_qos1(packet_type, topic, payload_dict, packet_id):
    payload = json.dumps(payload_dict).encode('utf-8')
    topic_bytes = topic.encode('utf-8')
    
    # Configurando bits 1 e 2 para QoS 1 -> 0x02
    header = (packet_type << 4) | 0x02 
    
    topic_len = len(topic_bytes)
    var_header = bytearray([topic_len >> 8, topic_len & 0xFF]) + topic_bytes
    
    # OBRIGATÓRIO PARA QoS 1: Adicionar o Packet ID (2 bytes) após o nome do tópico
    var_header += bytearray([packet_id >> 8, packet_id & 0xFF])
    
    var_h_and_payload = var_header + payload
    rl_bytes = encode_remaining_length(len(var_h_and_payload))
    
    return bytearray([header]) + rl_bytes + var_h_and_payload

def run_node():
    current_rh = 60.0 
    logging.warning(f"[{CLIENT_ID}] Starting Humidity Monitoring System (TESTE LWT/QoS1)...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((BROKER_IP, PORT))
        
        # 1. Enviar pacote de conexão com LWT ativado
        conn_pkt = build_connect_packet_with_lwt(CLIENT_ID)
        sock.sendall(conn_pkt)
        time.sleep(0.5)
        
        logging.warning(f"[{CLIENT_ID}] Connected to BROKER at {BROKER_IP}:{PORT}.")

        packet_id_counter = 1
        
        while True:
            current_rh = read_sensor_data(current_rh)
            data = {"id": CLIENT_ID, "value": current_rh, "unit": "%", "ts": int(time.time())}
            
            # 2. Enviar mensagem como QoS 1
            packet = build_mqtt_packet_qos1(3, TOPIC, data, packet_id_counter)
            sock.sendall(packet)
            
            logging.warning(f"[{CLIENT_ID}] PUBLISH (QoS 1 | ID: {packet_id_counter}) -> {current_rh}%")
            
            # 3. Simular a queda abrupta
            if packet_id_counter == 3:
                logging.warning(f"[{CLIENT_ID}] >>> SIMULANDO FALHA DE ENERGIA ABRUPTA! <<<")
                # os._exit fecha o processo no SO instantaneamente, sem enviar pacotes de encerramento TCP (FIN)
                os._exit(1)
            
            packet_id_counter += 1
            time.sleep(3) # Tempo mais curto para acelerar o teste
            
    except Exception as e:
        logging.warning(f"[{CLIENT_ID}] Connection Failed: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_node()