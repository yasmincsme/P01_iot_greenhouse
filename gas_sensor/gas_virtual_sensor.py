# import random
# import socket
# from datetime import datetime
# import json
# import time
# import os

# class GasSensor:

#     def __init__(self, name, min_range = 100, max_range = 200):
#         self.name = name
#         self.min_range = min_range
#         self.max_range = max_range
#         pass

#     def read_gas(self): 
#         return round(random.uniform(self.min_range, self.max_range), 3)


# class MqttLiteClient:

#     def __init__(self, client_id, broker_ip, broker_port):
#         self.client_id = client_id
#         self.sensor = GasSensor(name=f"Gas Sensor", min_range=100, max_range=200)
#         self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         self.broker_ip = broker_ip
#         self.broker_port = broker_port
#         pass

#     def send_data(self):
#         sensor_data = self.sensor.read_gas()

#         message = {
#             "source": "Crazyfile_Gas_sensor",
#             "time": str(datetime.now()),
#             "type": "Gas",
#             "data": sensor_data
#         }

#         json_msg = json.dumps(message)
#         self.socket.sendto(json_msg.encode(), (self.broker_ip, self.broker_port))

# def main():
#     broker_ip = os.getenv("BROKER_IP", "127.0.0.0")
#     broker_port = int(os.getenv("BROKER_PORT", 9998))

#     gas_sensor = VirtualSensorSystem(broker_ip, broker_port)

#     print("\nSistema de sensores iniciando...\n")

#     try:
#         while True:
#             gas_sensor.send_data()
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("\nEncerrando sistema...")

# if __name__ == "__main__":
#     main()

import random
import socket
import json
import time
import os
from datetime import datetime

class MqttLiteSensor:
    def __init__(self, client_id, sensor_type, topic, broker_ip, broker_port):
        self.client_id = client_id
        self.sensor_type = sensor_type
        self.topic = topic
        self.broker_ip = broker_ip
        self.broker_port = broker_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def read_value(self):
        # Simula leitura baseada no tipo
        if self.sensor_type == "Gas":
            return round(random.uniform(100, 200), 2)
        elif self.sensor_type == "Light":
            return round(random.uniform(300, 800), 2)
        return round(random.random(), 2)

    def publish(self):
        payload = self.read_value()
        message = {
            "client_id": self.client_id,
            "topic": self.topic,
            "payload": payload,
            "type": self.sensor_type,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        
        msg_bytes = json.dumps(message).encode()
        self.socket.sendto(msg_bytes, (self.broker_ip, self.broker_port))
        print(f"[PUB] {self.topic} -> {payload}")

if __name__ == "__main__":
    # O Docker preencherá essas variáveis
    cid = os.getenv("SENSOR_ID", "sensor_01")
    stype = os.getenv("SENSOR_TYPE", "Gas")
    stopic = os.getenv("SENSOR_TOPIC", "greenhouse/zone_A/gas")
    b_ip = os.getenv("BROKER_IP", "127.0.0.1")
    b_port = int(os.getenv("BROKER_PORT", 9998))

    client = MqttLiteSensor(cid, stype, stopic, b_ip, b_port)
    
    try:
        while True:
            client.publish()
            time.sleep(random.randint(2, 5)) # Sensores publicam em tempos diferentes
    except KeyboardInterrupt:
        print("Encerrando...")