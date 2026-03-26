import random
import socket
from datetime import datetime
import json
import time
import os

class HumiditySensor:

    def __init__(self, name, min_range = 0, max_range = 60):
        self.name = name
        self.min_range = min_range
        self.max_range = max_range
        pass

    def read_humidity(self): #Gerar valor aleatório
        return round(random.uniform(self.min_range, self.max_range), 3)

class VirtualSensorSystem:

    def __init__(self, broker_ip, broker_port):
        self.sensor = HumiditySensor(name=f"Humidity Sensor", min_range=0, max_range=60)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broker_ip = broker_ip
        self.broker_port = broker_port
        pass

    def send_data(self):
        sensor_data = self.sensor.read_humidity()

        message = {
            "source": "Crazyfile_Humidity_sensor",
            "time": str(datetime.now()),
            "type": "Humidity",
            "data": sensor_data
        }

        json_msg = json.dumps(message)
        self.socket.sendto(json_msg.encode(), (self.broker_ip, self.broker_port))

def main():
    broker_ip = os.getenv("BROKER_IP", "127.0.0.0")
    broker_port = int(os.getenv("BROKER_PORT", 9998))

    humidity_sensor = VirtualSensorSystem(broker_ip, broker_port)

    print("\nSistema de sensores iniciando...\n")

    try:
        while True:
            humidity_sensor.send_data()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando sistema...")

if __name__ == "__main__":
    main()