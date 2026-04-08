import socket
import threading
import time
from aux import *

subscriptions = {}
retained_messages = {}
clients = {}
broker_lock = threading.Lock()

def read_fixed_header(connection):
    byte_1_raw = connection.recv(1)
    if not byte_1_raw:
        return None, None, None
    
    byte_1 = byte_1_raw[0]
    packet_type = byte_1 >> 4
    flags = byte_1 & 0x0F

    multiplier = 1
    remaining_length = 0

    for _ in range(4):
        byte_2_raw = connection.recv(1)
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

def read_string(payload, offset):
    length = int.from_bytes(payload[offset:offset+2], byteorder='big')
    offset += 2
    text = payload[offset:offset+length].decode('utf-8')
    return text, offset + length

def send_connack(connection, client_id="Unknown", return_code=0x00):
    print(f"[OUT] [{client_id}] Sending CONNACK")
    packet = bytes([(Pkt.CONNACK << 4), 0x02, 0x00, return_code])
    connection.sendall(packet)

def send_publish(connection, topic, message, qos=0, retain=0, packet_id=None, client_id="Unknown"):
    print(f"[OUT] [{client_id}] Sending PUBLISH to topic: {topic}")
    flags = (qos << 1) | retain
    packet_type_n_flags = (Pkt.PUBLISH << 4) | flags
    
    topic_bytes = topic.encode('utf-8')
    message_bytes = message.encode('utf-8')

    topic_length = len(topic_bytes)
    variable_header = bytes([topic_length >> 8, topic_length & 0xFF]) + topic_bytes
    
    if qos > 0 and packet_id:
        variable_header += packet_id

    total_length = len(variable_header) + len(message_bytes)
    
    remaining_length_bytes = bytearray()
    val = total_length
    while True:
        byte = val % 128
        val = val // 128
        if val > 0:
            byte |= 0x80
        remaining_length_bytes.append(byte)
        if val == 0:
            break

    packet = bytes([packet_type_n_flags]) + remaining_length_bytes + variable_header + message_bytes
    connection.sendall(packet)

def send_ack(connection, pkt_type, packet_id, client_id="Unknown"):
    print(f"[OUT] [{client_id}] Sending ACK (Type: {pkt_type})")
    flags = 0x02 if pkt_type == Pkt.PUBREL else 0x00
    packet = bytes([(pkt_type << 4) | flags, 0x02, packet_id[0], packet_id[1]])
    connection.sendall(packet)

def handle_connect(connection, address, payload_data):
    if len(payload_data) < 10:
        return None

    protocol_name, offset = read_string(payload_data, 0)
    protocol_level = payload_data[offset]
    offset += 1
    
    connect_flags = payload_data[offset]
    offset += 1
    
    keep_alive = int.from_bytes(payload_data[offset:offset+2], byteorder='big')
    offset += 2

    clean_session = (connect_flags & 0x02) >> 1
    will_flag = (connect_flags & 0x04) >> 2
    will_qos = (connect_flags & 0x18) >> 3
    will_retain = (connect_flags & 0x20) >> 5

    client_id, offset = read_string(payload_data, offset)
    print(f"[IN] [{client_id}] CONNECT received from {address}")

    will_topic = None
    will_message = None
    if will_flag:
        will_topic, offset = read_string(payload_data, offset)
        will_message, offset = read_string(payload_data, offset)

    with broker_lock:
        clients[client_id] = {
            'socket': connection,
            'address': address,
            'keep_alive': keep_alive,
            'last_seen': time.time(),
            'clean_session': clean_session,
            'lwt': {
                'topic': will_topic,
                'message': will_message,
                'qos': will_qos,
                'retain': will_retain
            } if will_flag else None,
            'clean_disconnect': False
        }

    send_connack(connection, client_id)
    return client_id

def route_publish(topic, message, qos, retain, source_client_id):
    print(f"[ROUTING] Distributing PUBLISH on topic '{topic}' from [{source_client_id}]")
    with broker_lock:
        if retain:
            if message == "":
                retained_messages.pop(topic, None)
                print(f"[ROUTING] Retained message cleared for topic '{topic}'")
            else:
                retained_messages[topic] = {'message': message, 'qos': qos}
                print(f"[ROUTING] Message retained for topic '{topic}'")

        if topic in subscriptions:
            dead_clients = []
            for client_id in subscriptions[topic]:
                if client_id == source_client_id:
                    continue
                if client_id in clients:
                    try:
                        send_publish(clients[client_id]['socket'], topic, message, qos, 0, None, client_id)
                    except:
                        dead_clients.append(client_id)
                else:
                    dead_clients.append(client_id)
            for dead in dead_clients:
                subscriptions[topic].remove(dead)

def handle_publish(connection, flags, payload_data, client_id):
    if len(payload_data) < 2:
        return

    qos = (flags & 0x06) >> 1
    retain = flags & 0x01
    
    topic_len = int.from_bytes(payload_data[0:2], byteorder='big')
    topic_name = payload_data[2:2+topic_len].decode('utf-8')
    
    offset = 2 + topic_len
    packet_id = None

    if qos > 0:
        packet_id = payload_data[offset:offset+2]
        offset += 2
        
    message = payload_data[offset:].decode('utf-8')
    print(f"[IN] [{client_id}] PUBLISH received on topic '{topic_name}'")

    if qos == 1 and packet_id:
        send_ack(connection, Pkt.PUBACK, packet_id, client_id)
    elif qos == 2 and packet_id:
        send_ack(connection, Pkt.PUBREC, packet_id, client_id)

    route_publish(topic_name, message, qos, retain, client_id)

def handle_subscribe(connection, payload_data, client_id):
    if len(payload_data) < 4:
        return

    packet_id = payload_data[0:2]
    offset = 2
    
    return_codes = []
    
    while offset < len(payload_data):
        topic_name, offset = read_string(payload_data, offset)
        qos_req = payload_data[offset]
        offset += 1
        print(f"[IN] [{client_id}] SUBSCRIBE requested for topic '{topic_name}'")

        with broker_lock:
            if topic_name not in subscriptions:
                subscriptions[topic_name] = []
            if client_id not in subscriptions[topic_name]:
                subscriptions[topic_name].append(client_id)

            return_codes.append(qos_req)

            if topic_name in retained_messages:
                ret_msg = retained_messages[topic_name]
                try:
                    print(f"[ROUTING] Sending retained message to [{client_id}] for topic '{topic_name}'")
                    send_publish(connection, topic_name, ret_msg['message'], ret_msg['qos'], 1, None, client_id)
                except:
                    pass

    print(f"[OUT] [{client_id}] Sending SUBACK")
    suback = bytes([(Pkt.SUBACK << 4), 2 + len(return_codes), packet_id[0], packet_id[1]]) + bytes(return_codes)
    connection.sendall(suback)

def handle_unsubscribe(connection, payload_data, client_id):
    if len(payload_data) < 4:
        return

    packet_id = payload_data[0:2]
    offset = 2
    
    while offset < len(payload_data):
        topic_name, offset = read_string(payload_data, offset)
        print(f"[IN] [{client_id}] UNSUBSCRIBE requested for topic '{topic_name}'")
        
        with broker_lock:
            if topic_name in subscriptions:
                if client_id in subscriptions[topic_name]:
                    subscriptions[topic_name].remove(client_id)
                if not subscriptions[topic_name]:
                    del subscriptions[topic_name]

    send_ack(connection, Pkt.UNSUBACK, packet_id, client_id)

def trigger_lwt(client_id):
    with broker_lock:
        if client_id in clients:
            client_data = clients[client_id]
            if not client_data['clean_disconnect'] and client_data['lwt']:
                print(f"[LWT] Triggering Last Will and Testament for [{client_id}]")
                lwt = client_data['lwt']
                threading.Thread(target=route_publish, args=(lwt['topic'], lwt['message'], lwt['qos'], lwt['retain'], client_id)).start()

def keep_alive_monitor():
    while True:
        time.sleep(5)
        current_time = time.time()
        dead_clients = []
        
        with broker_lock:
            for client_id, data in clients.items():
                if data['keep_alive'] > 0:
                    limit = data['keep_alive'] * 1.5
                    if (current_time - data['last_seen']) > limit:
                        print(f"[SYSTEM] Keep-alive timeout for [{client_id}]")
                        dead_clients.append(client_id)

        for client_id in dead_clients:
            trigger_lwt(client_id)
            try:
                clients[client_id]['socket'].close()
            except:
                pass
            with broker_lock:
                if client_id in clients:
                    del clients[client_id]

def clean_client_session(client_id):
    print(f"[SYSTEM] Cleaning session for [{client_id}]")
    with broker_lock:
        empty_topics = []
        for topic, subs in subscriptions.items():
            if client_id in subs:
                subs.remove(client_id)
            if not subs:
                empty_topics.append(topic)

        for topic in empty_topics:
            del subscriptions[topic]

def handle_client(connection, address):
    client_id = None
    print(f"[CONNECTION] New socket connection from {address}")
    try:
        while True:
            packet_type, flags, remaining_length = read_fixed_header(connection)
            
            if packet_type is None:
                print(f"[CONNECTION] Client at {address} disconnected abruptly")
                break
                
            payload_data = connection.recv(remaining_length) if remaining_length > 0 else b''
            
            if client_id:
                with broker_lock:
                    if client_id in clients:
                        clients[client_id]['last_seen'] = time.time()
            
            if packet_type == Pkt.CONNECT:
                client_id = handle_connect(connection, address, payload_data)
            elif packet_type == Pkt.PUBLISH and client_id:
                handle_publish(connection, flags, payload_data, client_id)
            elif packet_type == Pkt.PUBACK:
                print(f"[IN] [{client_id}] PUBACK received")
            elif packet_type == Pkt.PUBREC:
                print(f"[IN] [{client_id}] PUBREC received")
                if len(payload_data) >= 2:
                    send_ack(connection, Pkt.PUBREL, payload_data[0:2], client_id)
            elif packet_type == Pkt.PUBREL:
                print(f"[IN] [{client_id}] PUBREL received")
                if len(payload_data) >= 2:
                    send_ack(connection, Pkt.PUBCOMP, payload_data[0:2], client_id)
            elif packet_type == Pkt.PUBCOMP:
                print(f"[IN] [{client_id}] PUBCOMP received")
            elif packet_type == Pkt.SUBSCRIBE and client_id:
                handle_subscribe(connection, payload_data, client_id)
            elif packet_type == Pkt.UNSUBSCRIBE and client_id:
                handle_unsubscribe(connection, payload_data, client_id)
            elif packet_type == Pkt.PINGREQ:
                print(f"[IN] [{client_id}] PINGREQ received")
                print(f"[OUT] [{client_id}] Sending PINGRESP")
                connection.sendall(bytes([(Pkt.PINGRESP << 4), 0x00]))
            elif packet_type == Pkt.DISCONNECT and client_id:
                print(f"[IN] [{client_id}] DISCONNECT received")
                with broker_lock:
                    clients[client_id]['clean_disconnect'] = True
                break

    except Exception as e:
        print(f"[ERROR] Socket error with {address}: {e}")
    finally:
        if client_id:
            print(f"[CONNECTION] Closing session for [{client_id}]")
            trigger_lwt(client_id)
            clean_session = False
            
            with broker_lock:
                if client_id in clients:
                    clean_session = clients[client_id]['clean_session']
                    del clients[client_id]
                    
            if clean_session:
                clean_client_session(client_id)
                
        try:
            connection.close()
        except:
            pass

def start_broker():
    monitor_thread = threading.Thread(target=keep_alive_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 9998))
    server_socket.listen(100)
    
    print("[SYSTEM] MQTT Broker started on 0.0.0.0:9998. Awaiting connections...")
    
    while True:
        conn, addr = server_socket.accept()
        client_thread = threading.Thread(target=handle_client, args=(conn, addr))
        client_thread.daemon = True 
        client_thread.start()

if __name__ == "__main__":
    start_broker()