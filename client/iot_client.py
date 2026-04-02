"""
Dashboard IoT - Sistema de Monitoramento e Controle
Sensores: Luz, Temperatura, Umidade, Gás
Atuadores: Nebulizador, Cortina, Irrigação (Bomba d'água)
Conectividade: MQTT Broker

Requisitos: pip install paho-mqtt ttkbootstrap
Uso: python iot_dashboard.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random
import math
import json
import threading
from datetime import datetime
import socket

# ── Configurações MQTT ──────────────────────────────────────────
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPICS = {
    "temperatura": "iot/sensores/temperatura",
    "umidade": "iot/sensores/umidade",
    "luz": "iot/sensores/luz",
    "gas": "iot/sensores/gas",
}
MQTT_ACTUATOR_TOPICS = {
    "nebulizador": "iot/atuadores/nebulizador",
    "cortina": "iot/atuadores/cortina",
    "irrigacao": "iot/atuadores/irrigacao",
}

# ── Limiares para alertas ───────────────────────────────────────
THRESHOLDS = {
    "temperatura": {"min": 18, "max": 30, "crit_min": 10, "crit_max": 40},
    "umidade": {"min": 40, "max": 70, "crit_min": 20, "crit_max": 90},
    "luz": {"min": 200, "max": 800, "crit_min": 50, "crit_max": 1000},
    "gas": {"min": 0, "max": 400, "crit_min": 0, "crit_max": 700},
}


class SensorData:
    def __init__(self):
        self.temperatura = 25.0
        self.umidade = 55.0
        self.luz = 500.0
        self.gas = 150.0
        self.history = {"temperatura": [], "umidade": [], "luz": [], "gas": []}

    def update(self, sensor, value):
        setattr(self, sensor, value)
        hist = self.history[sensor]
        hist.append((datetime.now(), value))
        if len(hist) > 60:
            hist.pop(0)

    def conforto(self):
        scores = []
        for sensor in ["temperatura", "umidade", "luz", "gas"]:
            val = getattr(self, sensor)
            t = THRESHOLDS[sensor]
            ideal_center = (t["min"] + t["max"]) / 2
            ideal_range = (t["max"] - t["min"]) / 2
            dist = abs(val - ideal_center)
            score = max(0, 1 - (dist / (ideal_range * 2)))
            scores.append(score)
        weights = [0.3, 0.25, 0.2, 0.25]
        return sum(s * w for s, w in zip(scores, weights)) * 100


class MQTTManager:
    def __init__(self, on_message_cb, on_connect_cb, on_disconnect_cb):
        self.connected = False
        self.client_socket = None
        self.on_message_cb = on_message_cb
        self.on_connect_cb = on_connect_cb
        self.on_disconnect_cb = on_disconnect_cb

    def connect(self, broker, port):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(2.0) # Evita que a interface trave se o broker estiver off
            self.client_socket.connect((broker, port))
            
            # Monta o pacote CONNECT bruto (Tipo 1)
            protocol_name = b'\x00\x04MQTT'
            protocol_level = b'\x04'
            connect_flags = b'\x02' # Clean session ativado, sem login
            keep_alive = b'\x00\x3C'
            variable_header = protocol_name + protocol_level + connect_flags + keep_alive
            
            client_id = b'DashboardUI'
            payload = len(client_id).to_bytes(2, 'big') + client_id
            
            packet_type = 0x10 # 0001 0000 em binário
            remaining_length = len(variable_header) + len(payload)
            
            # Envia o pacote completo
            packet = bytes([packet_type, remaining_length]) + variable_header + payload
            self.client_socket.sendall(packet)

            # Finge que já estamos conectados (pois nosso broker ainda não responde o CONNACK)
            self.connected = True
            self.on_connect_cb()
            return True
        except Exception as e:
            print(f"Erro no Socket: {e}")
            self.connected = False
            return False

    def disconnect(self):
        if self.client_socket:
            try:
                # Pacote DISCONNECT bruto: Tipo 14 (0xE0) e Tamanho 0
                self.client_socket.sendall(b'\xE0\x00')
                self.client_socket.close()
            except:
                pass
        self.connected = False
        self.on_disconnect_cb()

    def publish(self, topic, payload):
        """Monta um pacote PUBLISH bruto (Tipo 3) e envia ao Broker"""
        if not self.connected or not self.client_socket:
            return
            
        try:
            topic_bytes = topic.encode('utf-8')
            vh_topic = len(topic_bytes).to_bytes(2, 'big') + topic_bytes
            payload_bytes = json.dumps(payload).encode('utf-8')
            
            rl = len(vh_topic) + len(payload_bytes)
            
            # Matemática base-128 para calcular o tamanho
            rl_bytes = bytearray()
            val = rl
            while True:
                byte = val % 128
                val = val // 128
                if val > 0:
                    byte |= 0x80
                rl_bytes.append(byte)
                if val == 0:
                    break
                    
            packet = b'\x30' + rl_bytes + vh_topic + payload_bytes
            self.client_socket.sendall(packet)
        except Exception as e:
            print(f"Erro ao enviar dados: {e}")
            self.disconnect()


class IoTDashboard:
    # ── Tema Roxo & Preto ───────────────────────────────────────
    BG          = "#0d0b12"
    BG_CARD     = "#16131f"
    BG_CARD_ALT = "#1e1a2b"
    BG_HOVER    = "#241f34"
    ACCENT      = "#a855f7"       # Roxo vibrante
    ACCENT_LIGHT= "#c084fc"       # Roxo claro
    ACCENT_DIM  = "#7c3aed"       # Roxo escuro
    ACCENT_GLOW = "#1f1535"
    PURPLE_SOFT = "#d8b4fe"       # Lavanda
    PINK        = "#f472b6"       # Rosa accent
    CYAN        = "#67e8f9"       # Ciano para contraste
    WARNING     = "#fbbf24"
    DANGER      = "#f87171"
    SUCCESS     = "#4ade80"
    TEXT        = "#ede9fe"       # Texto claro lavanda
    TEXT_DIM    = "#a78bfa"       # Texto roxo médio
    TEXT_MUTED  = "#6b5b95"       # Texto mais apagado
    BORDER      = "#2d2640"
    BORDER_GLOW = "#2a1f4a"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("✦ IoT Dashboard — Monitoramento Ambiental")
        self.root.geometry("1320x860")
        self.root.configure(bg=self.BG)
        self.root.minsize(1100, 700)

        self.data = SensorData()
        self.alerts = []
        self.actuator_states = {"nebulizador": False, "cortina": False, "irrigacao": False}
        self.simulation_mode = True

        self.mqtt = MQTTManager(
            on_message_cb=self._mqtt_message,
            on_connect_cb=self._mqtt_connected,
            on_disconnect_cb=self._mqtt_disconnected,
        )

        self._build_ui()
        self._start_simulation()
        self.root.mainloop()

    # ── Helpers de UI ───────────────────────────────────────────
    def _card(self, parent, bg=None, glow=False, **kw):
        color = bg or self.BG_CARD
        border = self.BORDER_GLOW if glow else self.BORDER
        f = tk.Frame(parent, bg=color, highlightbackground=border,
                     highlightthickness=1, **kw)
        return f

    def _label(self, parent, text="", font=("Segoe UI", 11), fg=None, **kw):
        return tk.Label(parent, text=text, font=font, fg=fg or self.TEXT,
                        bg=parent["bg"], **kw)

    def _styled_button(self, parent, text, command, primary=False, width=None):
        bg = self.ACCENT_DIM if primary else self.BG_CARD_ALT
        fg = "#fff" if primary else self.ACCENT_LIGHT
        abg = self.ACCENT if primary else self.BG_HOVER
        btn = tk.Button(
            parent, text=text, font=("Segoe UI", 9, "bold"),
            bg=bg, fg=fg, activebackground=abg, activeforeground="#fff",
            relief="flat", cursor="hand2", padx=14, pady=5,
            highlightbackground=self.ACCENT_DIM, highlightthickness=1,
            command=command, bd=0
        )
        if width:
            btn.config(width=width)
        return btn

    # ── Build UI ────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=self.BG, height=65)
        header.pack(fill="x", padx=24, pady=(18, 5))
        header.pack_propagate(False)

        # Title with gradient-like effect
        title_frame = tk.Frame(header, bg=self.BG)
        title_frame.pack(side="left")

        self._label(title_frame, "✦",
                    font=("Segoe UI", 24), fg=self.ACCENT).pack(side="left", padx=(0, 8))
        self._label(title_frame, "IoT Dashboard",
                    font=("Segoe UI Semibold", 22), fg=self.TEXT).pack(side="left")
        self._label(title_frame, "  ·  Monitoramento Ambiental",
                    font=("Segoe UI", 12), fg=self.TEXT_MUTED).pack(side="left", pady=(8, 0))

        # Divider line
        divider = tk.Canvas(self.root, height=2, bg=self.BG, highlightthickness=0)
        divider.pack(fill="x", padx=24, pady=(0, 8))
        divider.bind("<Configure>", lambda e: (
            divider.delete("all"),
            divider.create_rectangle(0, 0, e.width * 0.6, 2, fill=self.ACCENT_DIM, outline=""),
            divider.create_rectangle(e.width * 0.6, 0, e.width, 2, fill=self.BORDER, outline="")
        ))

        # Connection status (right side of header)
        self.conn_frame = tk.Frame(header, bg=self.BG)
        self.conn_frame.pack(side="right")

        self.conn_dot = tk.Canvas(self.conn_frame, width=14, height=14,
                                   bg=self.BG, highlightthickness=0)
        self.conn_dot.pack(side="left", padx=(0, 6))
        self._draw_conn_dot(self.WARNING)

        self.conn_label = self._label(self.conn_frame, "Simulação",
                                       font=("Segoe UI", 10), fg=self.WARNING)
        self.conn_label.pack(side="left", padx=(0, 14))

        self.btn_connect = self._styled_button(
            self.conn_frame, "⚡ Conectar Broker", self._toggle_connection
        )
        self.btn_connect.pack(side="left")

        # Main content
        main = tk.Frame(self.root, bg=self.BG)
        main.pack(fill="both", expand=True, padx=24, pady=10)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.columnconfigure(2, weight=2)
        main.rowconfigure(0, weight=1)

        # ─ Col 1: Sensores ──────────────────────────────────────
        col1 = tk.Frame(main, bg=self.BG)
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self._section_header(col1, "◈  SENSORES", self.ACCENT)

        self.sensor_widgets = {}
        sensors_info = [
            ("temperatura", "🌡  Temperatura", "°C", self.PINK),
            ("umidade", "💧  Umidade", "%", self.CYAN),
            ("luz", "☀  Luminosidade", "lux", self.WARNING),
            ("gas", "🔥  Gás (MQ-2)", "ppm", self.DANGER),
        ]

        for key, label, unit, color in sensors_info:
            card = self._card(col1, glow=True)
            card.pack(fill="x", pady=4)

            inner = tk.Frame(card, bg=self.BG_CARD)
            inner.pack(fill="x", padx=18, pady=14)

            top_row = tk.Frame(inner, bg=self.BG_CARD)
            top_row.pack(fill="x")

            self._label(top_row, label, font=("Segoe UI", 11), fg=self.TEXT_DIM).pack(side="left")

            val_label = self._label(top_row, "--", font=("Segoe UI Bold", 24), fg=color)
            val_label.pack(side="right")

            unit_label = self._label(top_row, f" {unit}", font=("Segoe UI", 10), fg=self.TEXT_MUTED)
            unit_label.pack(side="right")

            # Barra estilizada
            bar_frame = tk.Frame(inner, bg=self.BG_CARD)
            bar_frame.pack(fill="x", pady=(10, 0))

            bar_bg = tk.Canvas(bar_frame, height=6, bg=self.BORDER, highlightthickness=0)
            bar_bg.pack(fill="x")

            self.sensor_widgets[key] = {
                "value": val_label, "bar": bar_bg, "color": color, "card": card
            }

        # ─ Col 2: Conforto + Atuadores ──────────────────────────
        col2 = tk.Frame(main, bg=self.BG)
        col2.grid(row=0, column=1, sticky="nsew", padx=5)

        # Conforto
        self._section_header(col2, "◈  CONFORTO AMBIENTAL", self.ACCENT)

        comfort_card = self._card(col2, glow=True)
        comfort_card.pack(fill="x", pady=(4, 14))

        self.comfort_canvas = tk.Canvas(comfort_card, width=200, height=190,
                                         bg=self.BG_CARD, highlightthickness=0)
        self.comfort_canvas.pack(pady=(16, 4))

        self.comfort_label = self._label(comfort_card, "Ambiente Agradável",
                                          font=("Segoe UI Semibold", 11), fg=self.ACCENT_LIGHT)
        self.comfort_label.pack(pady=(0, 14))

        # Atuadores
        self._section_header(col2, "◈  ATUADORES", self.ACCENT)

        actuators_info = [
            ("nebulizador", "💨  Nebulizador"),
            ("cortina", "🪟  Cortina"),
            ("irrigacao", "🌱  Irrigação"),
        ]

        self.actuator_btns = {}
        for key, label in actuators_info:
            act_card = self._card(col2, glow=True)
            act_card.pack(fill="x", pady=4)

            inner = tk.Frame(act_card, bg=self.BG_CARD)
            inner.pack(fill="x", padx=16, pady=11)

            self._label(inner, label, font=("Segoe UI", 11)).pack(side="left")

            # Status badge
            status_frame = tk.Frame(inner, bg=self.BG_CARD)
            status_frame.pack(side="right")

            btn = self._styled_button(
                status_frame, "Ligar",
                lambda k=key: self._toggle_actuator(k),
                primary=False
            )
            btn.pack(side="right", padx=(8, 0))

            status_dot = tk.Canvas(status_frame, width=10, height=10,
                                    bg=self.BG_CARD, highlightthickness=0)
            status_dot.pack(side="right", padx=(0, 4))
            status_dot.create_oval(1, 1, 9, 9, fill=self.DANGER, outline="")

            status_lbl = self._label(status_frame, "OFF",
                                      font=("Segoe UI Bold", 10), fg=self.DANGER)
            status_lbl.pack(side="right")

            self.actuator_btns[key] = {"btn": btn, "status": status_lbl, "dot": status_dot}

        # ─ Col 3: Alertas ───────────────────────────────────────
        col3 = tk.Frame(main, bg=self.BG)
        col3.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        self._section_header(col3, "◈  ALERTAS", self.DANGER)

        alert_card = self._card(col3, glow=True)
        alert_card.pack(fill="both", expand=True, pady=4)

        self.alert_text = tk.Text(
            alert_card, bg=self.BG_CARD, fg=self.TEXT, font=("Consolas", 9),
            relief="flat", wrap="word", padx=14, pady=12,
            insertbackground=self.ACCENT, highlightthickness=0,
            state="disabled", cursor="arrow", selectbackground=self.ACCENT_DIM
        )
        self.alert_text.pack(fill="both", expand=True, padx=2, pady=2)

        self.alert_text.tag_configure("warning", foreground=self.WARNING)
        self.alert_text.tag_configure("danger", foreground=self.DANGER)
        self.alert_text.tag_configure("info", foreground=self.ACCENT_LIGHT)
        self.alert_text.tag_configure("time", foreground=self.TEXT_MUTED)

        # Footer
        footer = tk.Frame(self.root, bg=self.BG, height=35)
        footer.pack(fill="x", padx=24, pady=(0, 12))

        self.clock_label = self._label(footer, "", font=("Consolas", 9), fg=self.TEXT_MUTED)
        self.clock_label.pack(side="right")

        self._label(footer, "✦ IoT System v2.0",
                    font=("Segoe UI", 8), fg=self.BORDER).pack(side="left")

    # ── Section header helper ───────────────────────────────────
    def _section_header(self, parent, text, color):
        f = tk.Frame(parent, bg=self.BG)
        f.pack(fill="x", pady=(0, 6))
        self._label(f, text, font=("Segoe UI Semibold", 10), fg=color).pack(side="left")
        # Small decorative line
        c = tk.Canvas(f, height=1, bg=self.BG, highlightthickness=0)
        c.pack(side="left", fill="x", expand=True, padx=(10, 0), pady=(2, 0))
        c.bind("<Configure>", lambda e, cv=c, cl=color: (
            cv.delete("all"),
            cv.create_rectangle(0, 0, e.width, 1, fill=self.BORDER, outline="")
        ))

    # ── Connection dot ──────────────────────────────────────────
    def _draw_conn_dot(self, color):
        self.conn_dot.delete("all")
        # Outer glow
        self.conn_dot.create_oval(0, 0, 13, 13, fill="", outline=self.BORDER, width=2)
        self.conn_dot.create_oval(3, 3, 10, 10, fill=color, outline="")

    # ── Conforto gauge ──────────────────────────────────────────
    def _draw_comfort(self, percent):
        c = self.comfort_canvas
        c.delete("all")
        cx, cy, r = 100, 100, 75

        # Background arc (more segments for glow)
        c.create_arc(cx - r, cy - r, cx + r, cy + r, start=180, extent=180,
                     outline=self.BORDER, width=12, style="arc")

        # Colored arc
        extent = (percent / 100) * 180
        if percent >= 70:
            color = self.SUCCESS
            glow = "#1a3a20"
        elif percent >= 40:
            color = self.WARNING
            glow = "#3a3010"
        else:
            color = self.DANGER
            glow = "#3a1515"

        # Glow arc (wider, dimmer)
        c.create_arc(cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3,
                     start=180, extent=extent,
                     outline=glow, width=18, style="arc")

        # Main arc
        c.create_arc(cx - r, cy - r, cx + r, cy + r, start=180, extent=extent,
                     outline=color, width=12, style="arc")

        # Percentage text
        c.create_text(cx, cy - 12, text=f"{percent:.0f}%",
                      font=("Segoe UI Bold", 30), fill=color)
        c.create_text(cx, cy + 22, text="Conforto",
                      font=("Segoe UI", 10), fill=self.TEXT_MUTED)

    def _update_loop(self):
        self._tick_count += 1

        if self.simulation_mode:
            t = self._tick_count * 0.1
            self.data.update("temperatura", 24 + 4 * math.sin(t * 0.3) + random.uniform(-0.5, 0.5))
            self.data.update("umidade", 55 + 15 * math.sin(t * 0.2) + random.uniform(-1, 1))
            self.data.update("luz", 500 + 300 * math.sin(t * 0.15) + random.uniform(-20, 20))
            self.data.update("gas", 150 + 100 * math.sin(t * 0.1) + random.uniform(-10, 10))

            # === ADICIONE ESTE BLOCO AQUI ===
            if self.mqtt.connected:
                self.mqtt.publish(MQTT_TOPICS["temperatura"], {"value": round(self.data.temperatura, 2)})
                self.mqtt.publish(MQTT_TOPICS["umidade"], {"value": round(self.data.umidade, 2)})
                self.mqtt.publish(MQTT_TOPICS["luz"], {"value": round(self.data.luz, 2)})
                self.mqtt.publish(MQTT_TOPICS["gas"], {"value": round(self.data.gas, 2)})
            # =================================

        for key in ["temperatura", "umidade", "luz", "gas"]:
            val = getattr(self.data, key)
            self.sensor_widgets[key]["value"].config(text=f"{val:.1f}")
            self._update_sensor_bar(key, val)

    # ── Sensor bar update ───────────────────────────────────────
    def _update_sensor_bar(self, key, value):
        w = self.sensor_widgets[key]
        t = THRESHOLDS[key]
        bar = w["bar"]
        bar.delete("all")
        bar.update_idletasks()
        width = bar.winfo_width()
        total_range = t["crit_max"] - t["crit_min"]
        if total_range == 0:
            return
        fill = min(1, max(0, (value - t["crit_min"]) / total_range))
        # Draw rounded bar with gradient effect
        fill_w = width * fill
        bar.create_rectangle(0, 0, fill_w, 6, fill=w["color"], outline="")
        # Glow tip
        if fill_w > 2:
            bar.create_rectangle(max(0, fill_w - 8), 0, fill_w, 6,
                                fill=w["color"], outline="")

    # ── Alertas ─────────────────────────────────────────────────
    def _check_alerts(self):
        now = datetime.now().strftime("%H:%M:%S")
        for sensor in ["temperatura", "umidade", "luz", "gas"]:
            val = getattr(self.data, sensor)
            t = THRESHOLDS[sensor]
            names = {"temperatura": "Temperatura", "umidade": "Umidade",
                     "luz": "Luminosidade", "gas": "Gás"}
            name = names[sensor]

            if val >= t["crit_max"] or val <= t["crit_min"]:
                self._add_alert(f"⚠ CRÍTICO: {name} = {val:.1f}", "danger", now)
            elif val >= t["max"] or val <= t["min"]:
                self._add_alert(f"⚡ Atenção: {name} = {val:.1f}", "warning", now)

    def _add_alert(self, msg, tag, time_str):
        self.alert_text.config(state="normal")
        self.alert_text.insert("1.0", f"[{time_str}] ", "time")
        self.alert_text.insert("1.end", f"{msg}\n", tag)

        lines = int(self.alert_text.index("end-1c").split(".")[0])
        if lines > 50:
            self.alert_text.delete("50.0", "end")

        self.alert_text.config(state="disabled")

    # ── Atuadores ───────────────────────────────────────────────
    def _toggle_actuator(self, key):
        self.actuator_states[key] = not self.actuator_states[key]
        state = self.actuator_states[key]
        w = self.actuator_btns[key]

        if state:
            w["btn"].config(text="Desligar", bg=self.ACCENT, fg="#fff")
            w["status"].config(text="ON", fg=self.SUCCESS)
            w["dot"].delete("all")
            w["dot"].create_oval(1, 1, 9, 9, fill=self.SUCCESS, outline="")
        else:
            w["btn"].config(text="Ligar", bg=self.BG_CARD_ALT, fg=self.ACCENT_LIGHT)
            w["status"].config(text="OFF", fg=self.DANGER)
            w["dot"].delete("all")
            w["dot"].create_oval(1, 1, 9, 9, fill=self.DANGER, outline="")

        if self.mqtt.connected:
            topic = MQTT_ACTUATOR_TOPICS[key]
            self.mqtt.publish(topic, {"state": "on" if state else "off"})

        names = {"nebulizador": "Nebulizador", "cortina": "Cortina", "irrigacao": "Irrigação"}
        now = datetime.now().strftime("%H:%M:%S")
        action = "ligado" if state else "desligado"
        self._add_alert(f"● {names[key]} {action}", "info", now)

    # ── MQTT callbacks ──────────────────────────────────────────
    def _mqtt_message(self, topic, payload):
        value = payload.get("value", payload.get("valor", 0))
        for sensor, t in MQTT_TOPICS.items():
            if topic == t:
                self.data.update(sensor, float(value))
                break

    def _mqtt_connected(self):
        self.simulation_mode = False
        self.root.after(0, lambda: self._update_conn_status(True))
        now = datetime.now().strftime("%H:%M:%S")
        self.root.after(0, lambda: self._add_alert("● Conectado ao broker MQTT", "info", now))

    def _mqtt_disconnected(self):
        self.simulation_mode = True
        self.root.after(0, lambda: self._update_conn_status(False))

    def _update_conn_status(self, connected):
        if connected:
            self._draw_conn_dot(self.SUCCESS)
            self.conn_label.config(text="Conectado", fg=self.SUCCESS)
            self.btn_connect.config(text="⚡ Desconectar")
        else:
            self._draw_conn_dot(self.WARNING)
            self.conn_label.config(text="Simulação", fg=self.WARNING)
            self.btn_connect.config(text="⚡ Conectar Broker")

    def _toggle_connection(self):
        if self.mqtt.connected:
            self.mqtt.disconnect()
        else:
            dlg = tk.Toplevel(self.root)
            dlg.title("Conexão MQTT")
            dlg.geometry("380x220")
            dlg.configure(bg=self.BG_CARD)
            dlg.transient(self.root)
            dlg.grab_set()

            self._label(dlg, "⚡ Broker MQTT", font=("Segoe UI Semibold", 14),
                        fg=self.ACCENT_LIGHT).pack(pady=(20, 14))

            f1 = tk.Frame(dlg, bg=self.BG_CARD)
            f1.pack(fill="x", padx=28)
            self._label(f1, "Host:", font=("Segoe UI", 10), fg=self.TEXT_DIM).pack(anchor="w")
            host_entry = tk.Entry(f1, bg=self.BG, fg=self.TEXT, font=("Consolas", 11),
                                   insertbackground=self.ACCENT, relief="flat",
                                   highlightbackground=self.ACCENT_DIM, highlightthickness=1)
            host_entry.insert(0, MQTT_BROKER)
            host_entry.pack(fill="x", pady=(2, 10))

            f2 = tk.Frame(dlg, bg=self.BG_CARD)
            f2.pack(fill="x", padx=28)
            self._label(f2, "Porta:", font=("Segoe UI", 10), fg=self.TEXT_DIM).pack(anchor="w")
            port_entry = tk.Entry(f2, bg=self.BG, fg=self.TEXT, font=("Consolas", 11),
                                   insertbackground=self.ACCENT, relief="flat",
                                   highlightbackground=self.ACCENT_DIM, highlightthickness=1)
            port_entry.insert(0, str(MQTT_PORT))
            port_entry.pack(fill="x", pady=(2, 10))

            def do_connect():
                host = host_entry.get().strip()
                port = int(port_entry.get().strip())
                ok = self.mqtt.connect(host, port)
                if not ok:
                    now = datetime.now().strftime("%H:%M:%S")
                    self._add_alert("✖ Falha na conexão MQTT", "danger", now)
                dlg.destroy()

            self._styled_button(dlg, "✦ Conectar", do_connect, primary=True).pack(pady=12)

    # ── Simulação ───────────────────────────────────────────────
    def _start_simulation(self):
        self._tick_count = 0
        self._update_loop()

    def _update_loop(self):
        self._tick_count += 1

        if self.simulation_mode:
            t = self._tick_count * 0.1
            self.data.update("temperatura", 24 + 4 * math.sin(t * 0.3) + random.uniform(-0.5, 0.5))
            self.data.update("umidade", 55 + 15 * math.sin(t * 0.2) + random.uniform(-1, 1))
            self.data.update("luz", 500 + 300 * math.sin(t * 0.15) + random.uniform(-20, 20))
            self.data.update("gas", 150 + 100 * math.sin(t * 0.1) + random.uniform(-10, 10))

        for key in ["temperatura", "umidade", "luz", "gas"]:
            val = getattr(self.data, key)
            self.sensor_widgets[key]["value"].config(text=f"{val:.1f}")
            self._update_sensor_bar(key, val)

        comfort = self.data.conforto()
        self._draw_comfort(comfort)
        if comfort >= 70:
            self.comfort_label.config(text="Ambiente Agradável 😊", fg=self.SUCCESS)
        elif comfort >= 40:
            self.comfort_label.config(text="Ambiente Moderado 😐", fg=self.WARNING)
        else:
            self.comfort_label.config(text="Ambiente Desconfortável 😟", fg=self.DANGER)

        if self._tick_count % 5 == 0:
            self._check_alerts()

        self.clock_label.config(text=datetime.now().strftime("✦  %d/%m/%Y  %H:%M:%S"))

        self.root.after(1000, self._update_loop)


if __name__ == "__main__":
    IoTDashboard()
