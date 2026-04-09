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
        self.running = True

        self._build_ui()
        self._start_connection_manager()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        ctk.CTkLabel(header, text="GREENHOUSE DASHBOARD", font=("Consolas", 20, "bold")).pack(side="left")
        self.status_label = ctk.CTkLabel(header, text="OFFLINE", font=("Consolas", 12, "bold"), text_color="#ef4444")
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
        self.health_label = ctk.CTkLabel(health_card, text="0.0%", font=("Consolas", 48, "bold"), text_color="#22c55e")
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

    def _update_status(self, state):
        colors = {"ONLINE": "#22c55e", "OFFLINE": "#ef4444", "CONNECTING": "#f59e0b"}
        self.status_label.configure(text=state, text_color=colors.get(state, "white"))

    def _start_connection_manager(self):
        threading.Thread(target=self._connection_supervisor, daemon=True).start()

    def _connection_supervisor(self):
        while self.running:
            if not self.connected:
                self.after(0, lambda: self._update_status("CONNECTING"))
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(5)
                    self.sock.connect((BROKER_IP, PORT))
                    self.sock.settimeout(None)
                    
                    self.sock.sendall(self._build_connect_packet(CLIENT_ID))
                    
                    topics = ["greenhouse/temp", "greenhouse/humidity", "greenhouse/light", "greenhouse/gas"]
                    for t in topics:
                        self.sock.sendall(self._build_subscribe_packet(t))
                    
                    self.connected = True
                    self.after(0, lambda: self._update_status("ONLINE"))
                    self.after(0, lambda: self._log("system", "Broker connected"))

                    threading.Thread(target=self._ping_loop, daemon=True).start()
                    self._receive_loop()
                except Exception as e:
                    self.after(0, lambda: self._update_status("OFFLINE"))
                    self.after(0, lambda msg=str(e): self._log("error", f"Reconnection failed: {msg}"))
                    time.sleep(5)
            time.sleep(1)

    def _read_fixed_header(self):
        try:
            b1 = self.sock.recv(1)
            if not b1: return None, None, None
            
            packet_type = b1[0] >> 4
            flags = b1[0] & 0x0F

            multiplier = 1
            remaining_length = 0
            while True:
                b2 = self.sock.recv(1)
                if not b2: return None, None, None
                digit = b2[0]
                remaining_length += (digit & 127) * multiplier
                if (digit & 128) == 0: break
                multiplier *= 128
            return packet_type, flags, remaining_length
        except:
            return None, None, None

    def _receive_loop(self):
        while self.connected:
            packet_type, flags, remaining_length = self._read_fixed_header()
            if packet_type is None:
                self.connected = False
                break
            
            payload = b""
            while len(payload) < remaining_length:
                chunk = self.sock.recv(remaining_length - len(payload))
                if not chunk: break
                payload += chunk

            if packet_type == 3:
                self._handle_publish(flags, payload)

    def _handle_publish(self, flags, data):
        try:
            qos = (flags & 0x06) >> 1
            topic_len = int.from_bytes(data[0:2], 'big')
            topic = data[2:2+topic_len].decode('utf-8')
            
            offset = 2 + topic_len
            if qos > 0:
                offset += 2 # Skip Packet ID
                
            msg = data[offset:].decode('utf-8')
            self.after(0, lambda t=topic, m=msg: self._log("in", f"[{t}] {m}"))
            
            payload_dict = json.loads(msg)
            val = float(payload_dict.get("value", 0))
            
            mapping = {
                "greenhouse/temp": "temp",
                "greenhouse/humidity": "rh",
                "greenhouse/light": "lux",
                "greenhouse/gas": "gas"
            }
            
            if topic in mapping:
                self.sensors[mapping[topic]] = val
                self.after(0, self._refresh_ui)
        except Exception as e:
            print(f"Decode error: {e}")

    def _ping_loop(self):
        while self.connected:
            time.sleep(30)
            try:
                self.sock.sendall(bytearray([0xC0, 0x00]))
            except:
                self.connected = False

    def _refresh_ui(self):
        self.sensor_labels["temp"].configure(text=f"{self.sensors['temp']:.1f}")
        self.sensor_labels["rh"].configure(text=f"{self.sensors['rh']:.1f}")
        self.sensor_labels["lux"].configure(text=f"{self.sensors['lux']:.1f}")
        self.sensor_labels["gas"].configure(text=f"{self.sensors['gas']:.1f}")
        
        score = EnvironmentalAI.predict_life_chance(
            self.sensors["temp"], self.sensors["rh"], 
            self.sensors["gas"], self.sensors["lux"]
        )
        
        color = "#22c55e" if score >= 70 else "#eab308" if score >= 50 else "#ef4444"
        self.health_label.configure(text=f"{score:.1f}%", text_color=color)

    def _send_curtain(self):
        try:
            val = int(self.curtain_entry.get())
            self._publish("greenhouse/actuators/curtain", {"position": val})
        except: pass

    def _send_irrigation(self):
        try:
            val = int(self.irrig_entry.get())
            self._publish("greenhouse/actuators/irrigation", {"duration_sec": val})
        except: pass

    def _publish(self, topic, payload):
        if not self.connected: return
        try:
            pkt = self._build_publish_packet(topic, payload)
            self.sock.sendall(pkt)
            
            msg_str = json.dumps(payload)
            self.after(0, lambda: self._log("out", f"[{topic}] {msg_str}"))
            
        except: 
            self.connected = False
    
    @staticmethod
    def _encode_remaining_length(length):
        encoded = bytearray()
        while True:
            byte = length % 128
            length //= 128
            if length > 0: byte |= 0x80
            encoded.append(byte)
            if length == 0: break
        return encoded

    @staticmethod
    def _build_connect_packet(client_id):
        proto = "MQTT".encode('utf-8')
        var_h = bytearray([0x00, 0x04]) + proto + bytearray([0x04, 0x02, 0x00, 0x3C])
        cid = client_id.encode('utf-8')
        payload = bytearray([len(cid) >> 8, len(cid) & 0xFF]) + cid
        return bytearray([0x10]) + GreenhouseDashboard._encode_remaining_length(len(var_h) + len(payload)) + var_h + payload

    @staticmethod
    def _build_publish_packet(topic, payload_dict):
        payload = json.dumps(payload_dict).encode('utf-8')
        tb = topic.encode('utf-8')
        th = bytearray([len(tb) >> 8, len(tb) & 0xFF])
        content = th + tb + payload
        return bytearray([0x30]) + GreenhouseDashboard._encode_remaining_length(len(content)) + content

    @staticmethod
    def _build_subscribe_packet(topic):
        tb = topic.encode('utf-8')
        pid = bytearray([0x00, 0x01])
        payload = bytearray([len(tb) >> 8, len(tb) & 0xFF]) + tb + b'\x00'
        content = pid + payload
        return bytearray([0x82]) + GreenhouseDashboard._encode_remaining_length(len(content)) + content

if __name__ == "__main__":
    app = GreenhouseDashboard()
    app.mainloop()