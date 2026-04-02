import socket
import threading

class Pkt:
    CONNECT     = 0b0001
    CONNACK     = 0b0010
    PUBLISH     = 0b0011
    PUBACK      = 0b0100
    PUBREC      = 0b0101
    PUBREL      = 0b0110  
    PUBCOMP     = 0b0111
    SUBSCRIBE   = 0b1000
    SUBACK      = 0b1001
    UNSUBSCRIBE = 0b1010
    UNSUBACK    = 0b1011
    PINGREQ     = 0b1100
    PINGRESP    = 0b1101
    DISCONNECT  = 0b1110

QOS_0 = 0b00
QOS_1 = 0b01
QOS_2 = 0b10

FLAG_RETAIN = 0b0001 
FLAG_DUP    = 0b1000

FLAG_RESERVED_REQUIRED = 0b0010

HOST = '0.0.0.0' 
PORT = 1883    

subscriptions = {}
subscriptions_lock = threading.Lock()

def read_fixed_header(connection):
    """Lê o Byte 1 e decodifica o Remaining Length da conexão TCP."""
    
    byte_1_raw = connection.recv(1)
    if not byte_1_raw:
        return None, None, None
    
    byte_1 = byte_1_raw[0]
    packet_type = byte_1 >> 4
    flags = byte_1 & 0x0F #0b00001111

    multiplier = 1
    remaining_length = 0

    for i in range(4):
        byte_2_raw = connection.recv(1) #atualização do ponteiro para segundo byte
        if not byte_2_raw:
            return None, None, None
        
        byte_2 = byte_2_raw[0]
        remaining_length += (byte_2 & 0x7F) * multiplier #exclui o bit de decisão da conta
        multiplier *= 128

        if(byte_2 & 0x80) == 0:
            break

    else:
        print("ERRO: Remaining Length excedeu 4 bytes. Pacote malformado!")
        return None, None, None
    
    return packet_type, flags, remaining_length

def sent_connack(connection):
    """Envia o pacote de confirmação de conexão (CONNACK) para o cliente."""

    packet_type_n_flags = 0x20 #byte 1
    remaining_length = 0x02 #byte2
    session_present = 0x00 #byte3
    return_code = 0x00 #byte 4

    packet_connack = bytes([packet_type_n_flags, remaining_length, session_present, return_code])

    connection.sendall(packet_connack)

def process_publisher(connection, flags, payload_data):
    """Desempacota o PUBLISH e repassa para todos os inscritos no tópico."""
    if len(payload_data) < 2: return

    topic_len = int.from_bytes(payload_data[0:2], byteorder='big')
    topic_name = payload_data[2 : 2 + topic_len].decode('utf-8')
    
    mensagem = payload_data[2 + topic_len:].decode('utf-8')
    
    print(f"   [PUBLISH] {topic_name} ➜ {mensagem}")

    with subscriptions_lock:
        if topic_name in subscriptions:
            dead_clients = []
            
            for client_sock in subscriptions[topic_name]:
                if client_sock == connection: continue 
                
                try:
                    msg_bytes = mensagem.encode('utf-8')
                    top_bytes = topic_name.encode('utf-8')
                    pass 
                except:
                    dead_clients.append(client_sock)

            for dead in dead_clients:
                subscriptions[topic_name].remove(dead)

def register_subscription(connection, payload_data):
    """Lê o pedido de SUBSCRIBE e armazena o socket do cliente no tópico."""
    if len(payload_data) < 4: return

    packet_id = payload_data[0:2]
    topic_len = int.from_bytes(payload_data[2:4], byteorder='big')
    topic_name = payload_data[4 : 4 + topic_len].decode('utf-8')
    
    with subscriptions_lock:
        if topic_name not in subscriptions:
            subscriptions[topic_name] = []
        if connection not in subscriptions[topic_name]:
            subscriptions[topic_name].append(connection)

    print(f"   [SUBSCRIBE] Cliente assinou: {topic_name}")

    suback = bytes([0x90, 0x03, packet_id[0], packet_id[1], 0x00])
    connection.sendall(suback)