import socket
import threading
import json

UDP_PORT = 9998
TCP_PORT = 9999

connected_sensors = {}

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", UDP_PORT))

    print(f"[BROKER] Escutando dados UDP na porta {UDP_PORT}")

    while True:
        data, addr = sock.recvfrom(4096)

        try:
            message = json.loads(data.decode())

            print("\n--- DADO RECEBIDO ---")
            print("Sensor:", message.get("source"))
            print("Tipo:", message.get("type"))
            print("Tempo:", message.get("time"))
            print("Dados:", message.get("data"))

        except:
            print("Mensagem inválida:", data)

def handle_sensor(conn, addr):
    print(f"[BROKER] Sensor conectado: {addr}")

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            message = json.loads(data.decode())
            if message["type"] == "register":
                sensor_name = message["name"]
                connected_sensors[sensor_name] = conn
                print(f"[BROKER] Sensor registrado: {sensor_name}")
    
    except:
        pass

    conn.close()
    print(f"[BROKER] Sensor desconectado: {addr}")

#################
def tcp_server():
    """
    Servidor TCP para registro e comandos
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("0.0.0.0", TCP_PORT))
    sock.listen()

    print(f"[BROKER] Servidor TCP escutando na porta {TCP_PORT}")

    while True:

        conn, addr = sock.accept()

        thread = threading.Thread(target=handle_sensor, args=(conn, addr))
        thread.start()

def main():

    print("BROKER INICIADO\n")

    udp_thread = threading.Thread(target=udp_listener)
    tcp_thread = threading.Thread(target=tcp_server)

    udp_thread.start()
    tcp_thread.start()

    udp_thread.join()
    tcp_thread.join()


if __name__ == "__main__":
    main()