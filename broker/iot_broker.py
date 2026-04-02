import socket
from aux import *
import threading

def handle_client(connection, address):
    """Essa função roda em uma Thread separada para cada cliente."""
    print(f"🧵 Thread iniciada para {address}")
    with connection:
        try:
            while True:
                packet_type, flags, remaining_length = read_fixed_header(connection)
                
                if packet_type is None: break
                
                payload_data = connection.recv(remaining_length) if remaining_length > 0 else b''
                
                match packet_type:
                    case Pkt.CONNECT:
                        sent_connack(connection)
                    case Pkt.PUBLISH:
                        process_publisher(connection, flags, payload_data)
                    case Pkt.SUBSCRIBE:
                        register_subscription(connection, payload_data)
                    case Pkt.DISCONNECT:
                        break
        except Exception as e:
            print(f"⚠️ Erro no cliente {address}: {e}")
    print(f"🔌 Conexão encerrada com {address}")

def start_broker():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(100)
    
    while True:
        conn, addr = server_socket.accept()
        client_thread = threading.Thread(target=handle_client, args=(conn, addr))
        client_thread.daemon = True 
        client_thread.start()