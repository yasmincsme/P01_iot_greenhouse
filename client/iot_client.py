import tkinter as tk
import customtkinter as ctk
import socket
import json
import threading
import time
import os
import math

BROKER_IP = os.environ.get("BROKER_IP", "172.16.201.16")
PORT = int(os.environ.get("BROKER_PORT", "9998"))
CLIENT_ID = "CLI_DASH_01"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

class EnvironmentalAI:
    MAX_TEMP = 50.0
    MAX_HUM = 100.0
    MAX_GAS = 217.79
    MAX_LIGHT = 1086.46

    W1 = [
        [0.76127756, -1.14999, -1.3243964, 1.0532789, -0.5648892, -0.35137573, -0.02234721, -0.97573954],
        [0.0390515, 0.19636367, 0.04113916, -0.27672333, 1.0549195, 0.55996454, -0.11504948, 1.0107998],
        [0.0651774, 0.07326719, -0.0230303, -0.08702946, -0.38678792, -0.68653685, 0.03985898, 0.3901636],
        [-1.0542206, 0.10372138, -0.2699437, 0.5364545, -0.02500459, -0.50767237, 0.790702, -0.15410507]
    ]
    b1 = [0.23017338, 0.32451043, 0.7052842, -0.37595168, 0.09138247, 0.06862238, -0.2987081, 0.32811505]

    W2 = [-2.3351076, -1.8962342, -4.0220113, -0.7348212, 1.2856134, 1.095262, -1.9509647, 1.2919254]
    b2 = 0.2667996

    @staticmethod
    def _relu(x):
        return max(0.0, x)

    @staticmethod
    def _sigmoid(x):
        if x < -709: return 0.0
        if x > 709: return 1.0
        return 1.0 / (1.0 + math.exp(-x))

    @classmethod
    def predict_life_chance(cls, temp, hum, gas, lux):
        x = [
            temp / cls.MAX_TEMP,
            hum / cls.MAX_HUM,
            gas / cls.MAX_GAS,
            lux / cls.MAX_LIGHT
        ]

        hidden = [0.0] * 8
        for i in range(8):
            hidden[i] = cls.b1[i]
            for j in range(4):
                hidden[i] += x[j] * cls.W1[j][i]
            hidden[i] = cls._relu(hidden[i])

        output = cls.b2
        for i in range(8):
            output += hidden[i] * cls.W2[i]

        chance = cls._sigmoid(output)
        return chance * 100.0

class GreenhouseDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Greenhouse Dashboard")
        self.geometry("900x700")
        self.minsize(800, 600)

        self.sensors = {"temp": 0.0, "rh": 0.0, "lux": 0.0, "gas": 0.0}
        self.sock = None
        self.connected = False

        self._build_ui()
        self.after(500, self._connect_broker)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        ctk.CTkLabel(header, text="GREENHOUSE DASHBOARD", font=("Consolas", 20, "bold")).pack(side="left")
        self.status_label = ctk.CTkLabel(header, text="CONNECTING...", font=("Consolas", 12), text_color="#f59e0b")
        self.status_label.pack(side="right")

        sensor_frame = ctk.CTkFrame(self, fg_color="transparent")
        sensor_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=12)
        for i in range(4):
            sensor_frame.grid_columnconfigure(i, weight=1)

        configs = [
            ("Temperature", "temp", "C", "#ef4444"),
            ("Humidity", "rh", "%", "#3b82f6"),
            ("Luminosity", "lux", "lux", "#eab308"),
            ("Gas", "gas", "ppm", "#a855f7"),
        ]
        
        self.sensor_labels = {}
        for i, (label, key, unit, color) in enumerate(configs):
            card = ctk.CTkFrame(sensor_frame, corner_radius=10)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            ctk.CTkLabel(card, text=label, font=("Consolas", 11), text_color="gray").pack(pady=(10, 2))
            val_label = ctk.CTkLabel(card, text="0.0", font=("Consolas", 28, "bold"), text_color=color)
            val_label.pack()
            ctk.CTkLabel(card, text=unit, font=("Consolas", 10), text_color="gray").pack(pady=(0, 10))
            self.sensor_labels[key] = val_label

        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_columnconfigure(1, weight=1)
        mid.grid_rowconfigure(0, weight=1)

        health_card = ctk.CTkFrame(mid, corner_radius=10)
        health_card.grid(row=0, column=0, padx=(0, 4), sticky="nsew")
        ctk.CTkLabel(health_card, text="ENVIRONMENTAL INDEX", font=("Consolas", 11), text_color="gray").pack(pady=(16, 4))
        self.health_label = ctk.CTkLabel(health_card, text="0.0", font=("Consolas", 48, "bold"), text_color="#22c55e")
        self.health_label.pack(expand=True)
        ctk.CTkLabel(health_card, text="Prediction Model", font=("Consolas", 9), text_color="gray").pack(pady=(0, 16))

        cmd_card = ctk.CTkFrame(mid, corner_radius=10)
        cmd_card.grid(row=0, column=1, padx=(4, 0), sticky="nsew")
        ctk.CTkLabel(cmd_card, text="ACTUATOR PANEL", font=("Consolas", 11), text_color="gray").pack(pady=(16, 8))

        row1 = ctk.CTkFrame(cmd_card, fg_color="transparent")
        row1.pack(padx=16, pady=4, fill="x")
        ctk.CTkLabel(row1, text="Curtain", font=("Consolas", 12), width=80, anchor="w").pack(side="left")
        self.curtain_entry = ctk.CTkEntry(row1, width=70, font=("Consolas", 12), placeholder_text="0-100")
        self.curtain_entry.pack(side="left", padx=4)
        self.curtain_entry.insert(0, "50")
        ctk.CTkLabel(row1, text="%", font=("Consolas", 10), text_color="gray").pack(side="left")
        ctk.CTkButton(row1, text="SEND", width=70, font=("Consolas", 11), command=self._send_curtain).pack(side="left", padx=(8, 0))

        row2 = ctk.CTkFrame(cmd_card, fg_color="transparent")
        row2.pack(padx=16, pady=4, fill="x")
        ctk.CTkLabel(row2, text="Irrigation", font=("Consolas", 12), width=80, anchor="w").pack(side="left")
        self.irrig_entry = ctk.CTkEntry(row2, width=70, font=("Consolas", 12), placeholder_text="sec")
        self.irrig_entry.pack(side="left", padx=4)
        self.irrig_entry.insert(0, "10")
        ctk.CTkLabel(row2, text="s", font=("Consolas", 10), text_color="gray").pack(side="left")
        ctk.CTkButton(row2, text="SEND", width=70, font=("Consolas", 11), command=self._send_irrigation).pack(side="left", padx=(8, 0))

        log_frame = ctk.CTkFrame(self, corner_radius=10)
        log_frame.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(log_frame, text="COMMUNICATION LOG", font=("Consolas", 11), text_color="gray").pack(anchor="w", padx=12, pady=(8, 4))
        self.log_text = ctk.CTkTextbox(log_frame, font=("Consolas", 10), state="disabled", height=140)
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _log(self, direction, msg):
        ts = time.strftime("%H:%M:%S")
        tags = {"in": "[BROKER -> CLI]", "out": "[CLI -> BROKER]", "system": "[SYSTEM]", "error": "[ERROR]"}
        line = f"{ts}  {tags.get(direction, '')}  {msg}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _connect_broker(self):
        threading.Thread(target=self._connect_thread, daemon=True).start()

    def _connect_thread(self):
        self.after(0, lambda: self._log("system", f"Connecting to {BROKER_IP}:{PORT}..."))
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((BROKER_IP, PORT))
            self.connected = True
            self.after(0, lambda: self.status_label.configure(text="ONLINE", text_color="#22c55e"))
            
            conn_pkt = self._build_connect_packet(CLIENT_ID)
            self.sock.sendall(conn_pkt)
            self.after(0, lambda: self._log("out", "CONNECT sent"))

            time.sleep(0.5)
            topics = ["greenhouse/temp", "greenhouse/humidity", "greenhouse/light", "greenhouse/gas"]
            for t in topics:
                self.sock.sendall(self._build_subscribe_packet(t))
                self.after(0, lambda t=t: self._log("out", f"SUBSCRIBE '{t}'"))
                time.sleep(0.1)

            threading.Thread(target=self._ping_loop, daemon=True).start()
            threading.Thread(target=self._receive_loop, daemon=True).start()

        except Exception as e:
            self.after(0, lambda: self.status_label.configure(text="OFFLINE", text_color="#ef4444"))
            self.after(0, lambda: self._log("error", f"Connection failed: {e}"))

    def _read_fixed_header(self):
        byte_1_raw = self.sock.recv(1)
        if not byte_1_raw:
            return None, None, None
        
        byte_1 = byte_1_raw[0]
        packet_type = byte_1 >> 4
        flags = byte_1 & 0x0F

        multiplier = 1
        remaining_length = 0

        for _ in range(4):
            byte_2_raw = self.sock.recv(1)
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

    def _receive_loop(self):
        while self.connected:
            try:
                packet_type, flags, remaining_length = self._read_fixed_header()
                
                if packet_type is None:
                    self.after(0, lambda: self._log("error", "Connection lost (Broker closed)."))
                    self.connected = False
                    break
                    
                payload_data = b''
                while len(payload_data) < remaining_length:
                    chunk = self.sock.recv(remaining_length - len(payload_data))
                    if not chunk:
                        break
                    payload_data += chunk
                
                if packet_type == 2:
                    self.after(0, lambda: self._log("in", "CONNACK received"))
                
                elif packet_type == 9:
                    self.after(0, lambda: self._log("in", "SUBACK received"))

                elif packet_type == 3:
                    qos = (flags & 0x06) >> 1
                    topic_len = int.from_bytes(payload_data[0:2], byteorder='big')
                    topic_name = payload_data[2:2+topic_len].decode('utf-8')
                    
                    offset = 2 + topic_len
                    if qos > 0:
                        offset += 2
                        
                    message_bytes = payload_data[offset:]
                    decoded_msg = message_bytes.decode('utf-8')
                    
                    self.after(0, lambda t=topic_name, d=decoded_msg: self._log("in", f"[{t}] {d}"))
                    
                    try:
                        payload = json.loads(decoded_msg)
                        
                        if topic_name == "greenhouse/temp":
                            self.sensors["temp"] = float(payload.get("value"))
                        elif topic_name == "greenhouse/humidity":
                            self.sensors["rh"] = float(payload.get("value"))
                        elif topic_name == "greenhouse/light":
                            self.sensors["lux"] = float(payload.get("value"))
                        elif topic_name == "greenhouse/gas":
                            self.sensors["gas"] = float(payload.get("value"))
                            
                        self.after(0, self._refresh_ui)

                    except json.JSONDecodeError as e:
                        self.after(0, lambda err=e: self._log("error", f"JSON Decode: {err}"))
                    except KeyError as e:
                        self.after(0, lambda err=e: self._log("error", f"Key Missing: {err}"))
                        
            except Exception as e:
                self.after(0, lambda err=e: self._log("error", f"Receive Loop Exception: {err}"))

    def _ping_loop(self):
        while self.connected:
            time.sleep(45)
            try:
                self.sock.sendall(bytearray([0xC0, 0x00]))
            except Exception:
                break

    def _refresh_ui(self):
        self.sensor_labels["temp"].configure(text=f"{self.sensors['temp']:.1f}")
        self.sensor_labels["rh"].configure(text=f"{self.sensors['rh']:.1f}")
        self.sensor_labels["lux"].configure(text=f"{self.sensors['lux']:.1f}")
        self.sensor_labels["gas"].configure(text=f"{self.sensors['gas']:.1f}")
        
        chance_de_vida = EnvironmentalAI.predict_life_chance(
            temp=self.sensors["temp"],
            hum=self.sensors["rh"],
            gas=self.sensors["gas"],
            lux=self.sensors["lux"]
        )
        
        if chance_de_vida >= 70.0:
            color = "#22c55e"  
        elif chance_de_vida >= 50.0:
            color = "#eab308"  
        else:
            color = "#ef4444"  
            
        self.health_label.configure(text=f"{chance_de_vida:.1f}%", text_color=color)

    def _send_curtain(self):
        try:
            pos = int(self.curtain_entry.get())
            if not (0 <= pos <= 100):
                raise ValueError
            self._publish("greenhouse/actuators/curtain", {"position": pos})
            self._log("system", f"Command queued: curtain {pos}")
        except ValueError:
            self._log("error", "Curtain value must be 0-100")

    def _send_irrigation(self):
        try:
            sec = int(self.irrig_entry.get())
            if sec <= 0:
                raise ValueError
            self._publish("greenhouse/actuators/irrigation", {"duration_sec": sec})
            self._log("system", f"Command queued: irrigation {sec}")
        except ValueError:
            self._log("error", "Irrigation value must be > 0")

    def _publish(self, topic, payload_dict):
        if not self.connected:
            self._log("error", "Not connected to broker.")
            return
        pkt = self._build_publish_packet(topic, payload_dict)
        self._log("out", f"PUBLISH '{topic}' -> {json.dumps(payload_dict)}")
        try:
            self.sock.sendall(pkt)
        except Exception as e:
            self._log("error", f"Send failed: {e}")

    @staticmethod
    def _encode_remaining_length(length):
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

    @staticmethod
    def _build_connect_packet(client_id):
        proto = "MQTT".encode('utf-8')
        var_h = bytearray([0x00, 0x04]) + proto + bytearray([0x04, 0x02, 0x00, 0x3C])
        cid = client_id.encode('utf-8')
        payload = bytearray([len(cid) >> 8, len(cid) & 0xFF]) + cid
        
        rl_bytes = GreenhouseDashboard._encode_remaining_length(len(var_h) + len(payload))
        return bytearray([0x10]) + rl_bytes + var_h + payload

    @staticmethod
    def _build_publish_packet(topic, payload_dict):
        payload = json.dumps(payload_dict).encode('utf-8')
        tb = topic.encode('utf-8')
        th = bytearray([len(tb) >> 8, len(tb) & 0xFF])
        
        var_h_and_payload = th + tb + payload
        rl_bytes = GreenhouseDashboard._encode_remaining_length(len(var_h_and_payload))
        
        return bytearray([0x30]) + rl_bytes + var_h_and_payload

    @staticmethod
    def _build_subscribe_packet(topic):
        tb = topic.encode('utf-8')
        pid = bytearray([0x00, 0x01])
        payload = bytearray([len(tb) >> 8, len(tb) & 0xFF]) + tb + b'\x00'
        
        var_h_and_payload = pid + payload
        rl_bytes = GreenhouseDashboard._encode_remaining_length(len(var_h_and_payload))
        
        return bytearray([0x82]) + rl_bytes + var_h_and_payload

if __name__ == "__main__":
    app = GreenhouseDashboard()
    app.mainloop()