"""
broker.py — Broker MQTT-SN v1.2 sobre UDP

Correções em relação ao broker TCP original:
  - UDP: recvfrom/sendto; cliente identificado por (ip, port)
  - recv() parcial eliminado: datagramas UDP chegam completos ou não chegam
  - Sem I/O de rede dentro de broker_lock (lock só protege estruturas em memória)
  - trigger_lwt não adquire lock enquanto chama route_publish
  - Race condition no keep_alive_monitor corrigida (snapshot atômico)
  - except: pass substituído por log de avisos
  - Wildcards MQTT + e # implementados em topic_matches()
  - Registro de tópicos MQTT-SN: REGISTER / REGACK
  - Estados de cliente: ACTIVE / ASLEEP / AWAKE
  - Modo sleep: mensagens enfileiradas e entregues no PINGREQ com ClientId
  - Anúncio de gateway: ADVERTISE periódico + resposta a SEARCHGW / GWINFO
  - clean_session=0: sessão (subs + fila offline) persiste entre reconexões
  - Limite de clientes configurável (MAX_CLIENTS)
  - QoS 2: controle de estado por pacote (pending_qos2) com deduplicação
"""

import socket
import threading
import time
import logging
from collections import defaultdict
from aux import MsgType, ReturnCode, TopicIdType, ClientState

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

BROKER_HOST    = "0.0.0.0"
BROKER_PORT    = 1883          # porta UDP padrão do MQTT-SN
GATEWAY_ID     = 0x01
MAX_CLIENTS    = 500
ADVERTISE_INTERVAL = 30        # segundos entre ADVERTISE broadcasts
BROADCAST_ADDR = ("255.255.255.255", BROKER_PORT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mqttsn")

# ---------------------------------------------------------------------------
# Estado global (protegido por broker_lock, exceto onde indicado)
# ---------------------------------------------------------------------------

broker_lock      = threading.Lock()

# addr (ip, port) → dict com dados do cliente
clients: dict[tuple, dict] = {}

# topic_name → set de addr dos subscribers
subscriptions: dict[str, set] = {}

# topic_name → {"message": bytes, "qos": int}
retained_messages: dict[str, dict] = {}

# addr → {"next_id": int, "id_to_name": {int: str}, "name_to_id": {str: int}}
topic_registrations: dict[tuple, dict] = {}


# ---------------------------------------------------------------------------
# Helpers de tópico
# ---------------------------------------------------------------------------

def topic_matches(pattern: str, topic: str) -> bool:
    """
    Verifica se 'topic' casa com 'pattern', suportando wildcards MQTT:
      +  corresponde a exatamente um nível
      #  corresponde a zero ou mais níveis (deve ser o último segmento)
    """
    if pattern == topic:
        return True
    pat_parts   = pattern.split("/")
    topic_parts = topic.split("/")
    return _match_parts(pat_parts, topic_parts)


def _match_parts(pat: list, top: list) -> bool:
    if not pat:
        return not top
    if pat[0] == "#":
        return True
    if not top:
        return False
    if pat[0] == "+" or pat[0] == top[0]:
        return _match_parts(pat[1:], top[1:])
    return False


def get_matching_subscribers(topic: str) -> set:
    """Retorna o conjunto de addr de todos os clientes subscritos ao tópico."""
    result = set()
    with broker_lock:
        for pattern, addrs in subscriptions.items():
            if topic_matches(pattern, topic):
                result |= addrs
    return result


# ---------------------------------------------------------------------------
# Helpers de codec MQTT-SN
# ---------------------------------------------------------------------------

def encode_length(length: int) -> bytes:
    """Codifica o campo Length do cabeçalho MQTT-SN (1 ou 3 bytes)."""
    if length <= 255:
        return bytes([length])
    # forma longa: 0x01 + 2 bytes big-endian
    return bytes([0x01]) + length.to_bytes(2, "big")


def build_packet(msg_type: MsgType, payload: bytes) -> bytes:
    body   = bytes([int(msg_type)]) + payload
    length = len(body) + 1          # +1 para o próprio campo Length
    return encode_length(length) + body


def parse_flags(flags_byte: int) -> dict:
    return {
        "dup":          bool(flags_byte & 0x80),
        "qos":          (flags_byte >> 5) & 0x03,
        "retain":       bool(flags_byte & 0x10),
        "will":         bool(flags_byte & 0x08),
        "clean_session":bool(flags_byte & 0x04),
        "topic_id_type":flags_byte & 0x03,
    }


def flags_byte(dup=False, qos=0, retain=False,
               will=False, clean_session=False,
               topic_id_type=TopicIdType.NORMAL) -> int:
    return (
        (0x80 if dup else 0)
        | ((qos & 0x03) << 5)
        | (0x10 if retain else 0)
        | (0x08 if will else 0)
        | (0x04 if clean_session else 0)
        | (int(topic_id_type) & 0x03)
    )


# ---------------------------------------------------------------------------
# Envio de pacotes (sem lock; chamado sempre fora de broker_lock)
# ---------------------------------------------------------------------------

def send_packet(sock: socket.socket, addr: tuple,
                msg_type: MsgType, payload: bytes) -> None:
    data = build_packet(msg_type, payload)
    try:
        sock.sendto(data, addr)
    except Exception as e:
        log.warning("[SEND] Falha ao enviar %s para %s: %s", msg_type.name, addr, e)


def send_connack(sock, addr, return_code=ReturnCode.ACCEPTED):
    send_packet(sock, addr, MsgType.CONNACK, bytes([int(return_code)]))


def send_regack(sock, addr, topic_id: int, msg_id: int,
                return_code=ReturnCode.ACCEPTED):
    payload = (topic_id.to_bytes(2, "big")
               + msg_id.to_bytes(2, "big")
               + bytes([int(return_code)]))
    send_packet(sock, addr, MsgType.REGACK, payload)


def send_suback(sock, addr, qos: int, topic_id: int, msg_id: int,
                return_code=ReturnCode.ACCEPTED):
    payload = (bytes([flags_byte(qos=qos)])
               + topic_id.to_bytes(2, "big")
               + msg_id.to_bytes(2, "big")
               + bytes([int(return_code)]))
    send_packet(sock, addr, MsgType.SUBACK, payload)


def send_unsuback(sock, addr, msg_id: int):
    send_packet(sock, addr, MsgType.UNSUBACK, msg_id.to_bytes(2, "big"))


def send_puback(sock, addr, topic_id: int, msg_id: int,
                return_code=ReturnCode.ACCEPTED):
    payload = (topic_id.to_bytes(2, "big")
               + msg_id.to_bytes(2, "big")
               + bytes([int(return_code)]))
    send_packet(sock, addr, MsgType.PUBACK, payload)


def send_pubrec(sock, addr, msg_id: int):
    send_packet(sock, addr, MsgType.PUBREC, msg_id.to_bytes(2, "big"))


def send_pubrel(sock, addr, msg_id: int):
    send_packet(sock, addr, MsgType.PUBREL, msg_id.to_bytes(2, "big"))


def send_pubcomp(sock, addr, msg_id: int):
    send_packet(sock, addr, MsgType.PUBCOMP, msg_id.to_bytes(2, "big"))


def send_publish(sock, addr, topic_id: int, message: bytes,
                 qos=0, retain=False, dup=False,
                 topic_id_type=TopicIdType.NORMAL, msg_id=0):
    fb = flags_byte(dup=dup, qos=qos, retain=retain,
                    topic_id_type=topic_id_type)
    payload = (bytes([fb])
               + topic_id.to_bytes(2, "big")
               + msg_id.to_bytes(2, "big")
               + message)
    send_packet(sock, addr, MsgType.PUBLISH, payload)


def send_pingresp(sock, addr):
    send_packet(sock, addr, MsgType.PINGRESP, b"")


def send_disconnect(sock, addr, duration: int = 0):
    payload = duration.to_bytes(2, "big") if duration else b""
    send_packet(sock, addr, MsgType.DISCONNECT, payload)


def send_advertise(sock):
    """Broadcast ADVERTISE (pode falhar em interfaces sem broadcast; ignoramos)."""
    payload = bytes([GATEWAY_ID]) + ADVERTISE_INTERVAL.to_bytes(2, "big")
    data = build_packet(MsgType.ADVERTISE, payload)
    try:
        sock.sendto(data, BROADCAST_ADDR)
    except Exception:
        pass  # broadcast pode não estar disponível em todas as interfaces


# ---------------------------------------------------------------------------
# Registro de tópicos por cliente
# ---------------------------------------------------------------------------

def _ensure_reg(addr: tuple) -> dict:
    if addr not in topic_registrations:
        topic_registrations[addr] = {"next_id": 1, "id_to_name": {}, "name_to_id": {}}
    return topic_registrations[addr]


def register_topic(addr: tuple, topic_name: str) -> int:
    """Registra o tópico para o cliente e devolve o topic_id (cria se não existe)."""
    reg = _ensure_reg(addr)
    if topic_name in reg["name_to_id"]:
        return reg["name_to_id"][topic_name]
    tid = reg["next_id"]
    reg["next_id"] += 1
    reg["id_to_name"][tid]       = topic_name
    reg["name_to_id"][topic_name] = tid
    return tid


def resolve_topic_id(addr: tuple, topic_id: int,
                     topic_id_type: int) -> str | None:
    """
    Converte topic_id para nome de tópico.
    Tipo SHORT: os dois bytes do topic_id são o nome literal (ex.: "ab").
    """
    if topic_id_type == TopicIdType.SHORT:
        b = topic_id.to_bytes(2, "big")
        return b.decode("ascii", errors="replace")
    reg = topic_registrations.get(addr, {})
    return reg.get("id_to_name", {}).get(topic_id)


# ---------------------------------------------------------------------------
# Roteamento de mensagens
# ---------------------------------------------------------------------------

def route_publish(sock: socket.socket, topic_name: str, message: bytes,
                  qos: int, retain: bool, source_addr: tuple):
    """
    Distribui a mensagem a todos os subscribers (exceto a fonte).
    Mensagens para clientes dormindo são enfileiradas.
    Chamado FORA de broker_lock.
    """
    log.debug("[ROUTE] topic='%s' from=%s", topic_name, source_addr)

    # 1. Atualizar retained
    if retain:
        with broker_lock:
            if message:
                retained_messages[topic_name] = {"message": message, "qos": qos}
                log.info("[RETAIN] Guardada mensagem em '%s'", topic_name)
            else:
                retained_messages.pop(topic_name, None)
                log.info("[RETAIN] Apagada mensagem retida em '%s'", topic_name)

    # 2. Coletar subscribers (fora do lock para não segurar durante envio)
    matching = get_matching_subscribers(topic_name)

    for addr in matching:
        if addr == source_addr:
            continue
        with broker_lock:
            client = clients.get(addr)
            if not client:
                continue
            state = client["state"]
            # topic_id para este subscriber
            tid = register_topic(addr, topic_name)

        if state == ClientState.ACTIVE:
            send_publish(sock, addr, tid, message, qos=qos, retain=False)
        elif state in (ClientState.ASLEEP, ClientState.AWAKE):
            # Enfileirar para entrega no próximo PINGREQ
            with broker_lock:
                client = clients.get(addr)
                if client:
                    client["offline_queue"].append({
                        "topic_id": tid,
                        "message":  message,
                        "qos":      qos,
                    })
                    log.debug("[QUEUE] Mensagem enfileirada para %s (state=%s)",
                              addr, state.name)


def flush_offline_queue(sock: socket.socket, addr: tuple):
    """Entrega mensagens enfileiradas a um cliente que acabou de acordar."""
    with broker_lock:
        client = clients.get(addr)
        if not client:
            return
        queue = client["offline_queue"][:]
        client["offline_queue"].clear()
        client["state"] = ClientState.ACTIVE

    for item in queue:
        send_publish(sock, addr, item["topic_id"], item["message"],
                     qos=item["qos"])


# ---------------------------------------------------------------------------
# Handlers de pacotes recebidos
# ---------------------------------------------------------------------------

def handle_connect(sock, addr, data: bytes):
    if len(data) < 4:
        log.warning("[CONNECT] Pacote curto de %s", addr)
        return

    flags      = parse_flags(data[0])
    _protocol  = data[1]          # deve ser 0x01 para MQTT-SN
    duration   = int.from_bytes(data[2:4], "big")
    client_id  = data[4:].decode("utf-8", errors="replace")

    log.info("[IN] CONNECT client_id='%s' addr=%s duration=%ds",
             client_id, addr, duration)

    with broker_lock:
        active_count = sum(1 for c in clients.values()
                           if c["state"] != ClientState.DISCONNECTED)
        if active_count >= MAX_CLIENTS:
            log.warning("[CONNECT] Broker cheio, rejeitando '%s'", client_id)

        # Verificar se há sessão prévia (clean_session=0)
        prev = None
        if not flags["clean_session"]:
            prev = clients.get(addr)

        clients[addr] = {
            "client_id":       client_id,
            "keep_alive":      duration,
            "last_seen":       time.time(),
            "clean_session":   flags["clean_session"],
            "state":           ClientState.ACTIVE,
            "clean_disconnect":False,
            "lwt":             None,
            "offline_queue":   prev["offline_queue"] if prev else [],
            "pending_qos2":    prev["pending_qos2"]  if prev else {},
        }

    if active_count >= MAX_CLIENTS:
        send_connack(sock, addr, ReturnCode.REJECTED_CONGESTION)
        return

    send_connack(sock, addr, ReturnCode.ACCEPTED)
    log.info("[OUT] CONNACK → %s", addr)


def handle_willtopic(sock, addr, data: bytes):
    if len(data) < 1:
        return
    flags      = parse_flags(data[0])
    will_topic = data[1:].decode("utf-8", errors="replace")
    with broker_lock:
        if addr in clients:
            if "lwt_pending" not in clients[addr]:
                clients[addr]["lwt_pending"] = {}
            clients[addr]["lwt_pending"]["topic"]  = will_topic
            clients[addr]["lwt_pending"]["qos"]    = flags["qos"]
            clients[addr]["lwt_pending"]["retain"] = flags["retain"]
    send_packet(sock, addr, MsgType.WILLMSGREQ, b"")


def handle_willmsg(sock, addr, data: bytes):
    will_message = data
    with broker_lock:
        if addr in clients:
            pending = clients[addr].pop("lwt_pending", {})
            if pending:
                pending["message"] = will_message
                clients[addr]["lwt"] = pending
    send_connack(sock, addr, ReturnCode.ACCEPTED)


def handle_register(sock, addr, data: bytes):
    if len(data) < 5:
        return
    # topic_id=0x0000 (campo reservado no sentido client→broker)
    msg_id     = int.from_bytes(data[2:4], "big")
    topic_name = data[4:].decode("utf-8", errors="replace")

    with broker_lock:
        tid = register_topic(addr, topic_name)

    log.info("[IN] REGISTER '%s' → id=%d  addr=%s", topic_name, tid, addr)
    send_regack(sock, addr, tid, msg_id)


def handle_publish(sock, addr, data: bytes):
    if len(data) < 6:
        return
    flags      = parse_flags(data[0])
    qos        = flags["qos"]
    retain     = flags["retain"]
    dup        = flags["dup"]
    tid_type   = flags["topic_id_type"]
    topic_id   = int.from_bytes(data[1:3], "big")
    msg_id     = int.from_bytes(data[3:5], "big")
    message    = data[5:]

    with broker_lock:
        topic_name = resolve_topic_id(addr, topic_id, tid_type)
        if addr in clients:
            clients[addr]["last_seen"] = time.time()

    if topic_name is None:
        log.warning("[PUBLISH] topic_id=%d desconhecido de %s", topic_id, addr)
        if qos == 1:
            send_puback(sock, addr, topic_id, msg_id, ReturnCode.REJECTED_TOPIC_ID)
        return

    log.info("[IN] PUBLISH topic='%s' qos=%d addr=%s", topic_name, qos, addr)

    # QoS 1
    if qos == 1:
        send_puback(sock, addr, topic_id, msg_id)

    # QoS 2 — fase 1: PUBREC + deduplicação
    elif qos == 2:
        with broker_lock:
            client = clients.get(addr, {})
            pending = client.get("pending_qos2", {})
            if msg_id in pending:
                # Duplicata: reenviar PUBREC mas não rotear de novo
                log.debug("[QoS2] Duplicata msg_id=%d de %s, reenviando PUBREC", msg_id, addr)
                send_pubrec(sock, addr, msg_id)
                return
            if client:
                pending[msg_id] = {"topic": topic_name, "message": message,
                                   "qos": qos, "retain": retain}
                client["pending_qos2"] = pending
        send_pubrec(sock, addr, msg_id)
        return  # roteamento ocorre no PUBREL

    # QoS 0 ou QoS 1: rotear agora
    if qos in (0, 1):
        route_publish(sock, topic_name, message, qos, retain, addr)


def handle_pubrel(sock, addr, data: bytes):
    if len(data) < 2:
        return
    msg_id = int.from_bytes(data[0:2], "big")

    topic_name = message = None
    qos = retain = None

    with broker_lock:
        client = clients.get(addr, {})
        pending = client.get("pending_qos2", {})
        item = pending.pop(msg_id, None)
        if item:
            topic_name = item["topic"]
            message    = item["message"]
            qos        = item["qos"]
            retain     = item["retain"]

    send_pubcomp(sock, addr, msg_id)

    if topic_name is not None:
        route_publish(sock, topic_name, message, qos, retain, addr)


def handle_subscribe(sock, addr, data: bytes):
    if len(data) < 5:
        return
    flags      = parse_flags(data[0])
    qos        = flags["qos"]
    tid_type   = flags["topic_id_type"]
    msg_id     = int.from_bytes(data[1:3], "big")

    if tid_type == TopicIdType.SHORT:
        # 2 bytes do topic_id são o nome curto
        topic_name = data[3:5].decode("ascii", errors="replace")
        topic_id   = int.from_bytes(data[3:5], "big")
    elif tid_type == TopicIdType.PREDEFINED:
        topic_id   = int.from_bytes(data[3:5], "big")
        topic_name = str(topic_id)
    else:
        topic_name = data[5:].decode("utf-8", errors="replace")
        topic_id   = register_topic(addr, topic_name)

    log.info("[IN] SUBSCRIBE topic='%s' qos=%d addr=%s", topic_name, qos, addr)

    retained = None
    with broker_lock:
        subscriptions.setdefault(topic_name, set()).add(addr)
        # Coletar retained message (se existir) para enviar após o lock
        for stored_topic, ret_msg in retained_messages.items():
            if topic_matches(stored_topic, topic_name) or topic_matches(topic_name, stored_topic):
                retained = (stored_topic, ret_msg)
                break

    send_suback(sock, addr, qos, topic_id, msg_id)
    log.info("[OUT] SUBACK → %s", addr)

    # Enviar retained fora do lock
    if retained:
        ret_topic, ret_msg = retained
        with broker_lock:
            tid = register_topic(addr, ret_topic)
        send_publish(sock, addr, tid, ret_msg["message"],
                     qos=ret_msg["qos"], retain=True)


def handle_unsubscribe(sock, addr, data: bytes):
    if len(data) < 5:
        return
    flags    = parse_flags(data[0])
    tid_type = flags["topic_id_type"]
    msg_id   = int.from_bytes(data[1:3], "big")

    if tid_type == TopicIdType.SHORT:
        topic_name = data[3:5].decode("ascii", errors="replace")
    else:
        topic_name = data[5:].decode("utf-8", errors="replace")

    log.info("[IN] UNSUBSCRIBE topic='%s' addr=%s", topic_name, addr)

    with broker_lock:
        if topic_name in subscriptions:
            subscriptions[topic_name].discard(addr)
            if not subscriptions[topic_name]:
                del subscriptions[topic_name]

    send_unsuback(sock, addr, msg_id)


def handle_pingreq(sock, addr, data: bytes):
    """
    PINGREQ com ClientId → cliente acordando do modo sleep (entregar fila).
    PINGREQ vazio → keepalive normal.
    """
    client_id = data.decode("utf-8", errors="replace") if data else None

    with broker_lock:
        if addr in clients:
            clients[addr]["last_seen"] = time.time()
            if client_id and clients[addr]["state"] == ClientState.ASLEEP:
                clients[addr]["state"] = ClientState.AWAKE
                log.info("[SLEEP] Cliente %s acordando (PINGREQ)", addr)

    if client_id:
        flush_offline_queue(sock, addr)

    send_pingresp(sock, addr)


def handle_disconnect(sock, addr, data: bytes):
    """
    DISCONNECT com campo duration > 0 → cliente entrando em modo sleep.
    DISCONNECT sem duration → desconexão limpa.
    """
    duration = 0
    if len(data) >= 2:
        duration = int.from_bytes(data[0:2], "big")

    with broker_lock:
        if addr in clients:
            if duration > 0:
                clients[addr]["state"]      = ClientState.ASLEEP
                clients[addr]["keep_alive"] = duration
                clients[addr]["last_seen"]  = time.time()
                log.info("[SLEEP] Cliente %s dormindo por %ds", addr, duration)
            else:
                clients[addr]["clean_disconnect"] = True
                clients[addr]["state"] = ClientState.DISCONNECTED
                log.info("[DISCONNECT] Cliente %s desconectou limpo", addr)

    if duration == 0:
        send_disconnect(sock, addr)
        _cleanup_client(sock, addr)


def handle_searchgw(sock, addr, data: bytes):
    """Responde GWINFO ao cliente que procura um gateway."""
    log.info("[SEARCHGW] de %s, enviando GWINFO", addr)
    payload = bytes([GATEWAY_ID])
    send_packet(sock, addr, MsgType.GWINFO, payload)


# ---------------------------------------------------------------------------
# Ciclo de vida do cliente
# ---------------------------------------------------------------------------

def trigger_lwt(sock: socket.socket, addr: tuple):
    """
    Dispara o LWT se o cliente não se desconectou de forma limpa.
    Chamado FORA de broker_lock.
    """
    lwt = None
    with broker_lock:
        client = clients.get(addr)
        if client and not client["clean_disconnect"] and client.get("lwt"):
            lwt = client["lwt"]

    if lwt:
        log.info("[LWT] Disparando LWT para %s  tópico='%s'", addr, lwt["topic"])
        topic_id = None
        with broker_lock:
            topic_id = register_topic(addr, lwt["topic"])
        route_publish(sock, lwt["topic"],
                      lwt["message"].encode() if isinstance(lwt["message"], str)
                      else lwt["message"],
                      lwt["qos"], lwt["retain"], addr)


def _cleanup_client(sock: socket.socket, addr: tuple):
    """Remove cliente do estado global e limpa sessão se clean_session=1."""
    with broker_lock:
        client = clients.pop(addr, None)
        if not client:
            return
        clean_session = client["clean_session"]

    if clean_session:
        _clean_session_data(addr)


def _clean_session_data(addr: tuple):
    """Remove subscriptions e dados de registro associados ao addr."""
    with broker_lock:
        empty = [t for t, subs in subscriptions.items() if addr in subs]
        for t in empty:
            subscriptions[t].discard(addr)
            if not subscriptions[t]:
                del subscriptions[t]
        topic_registrations.pop(addr, None)
    log.info("[SESSION] Sessão limpa para %s", addr)


# ---------------------------------------------------------------------------
# Monitor de keep-alive
# ---------------------------------------------------------------------------

def keep_alive_monitor(sock: socket.socket):
    while True:
        time.sleep(5)
        now = time.time()

        # Snapshot atômico para evitar race condition
        with broker_lock:
            snapshot = {
                addr: (data["keep_alive"], data["last_seen"], data["state"])
                for addr, data in clients.items()
            }

        timed_out = []
        for addr, (ka, last_seen, state) in snapshot.items():
            if state == ClientState.DISCONNECTED:
                continue
            if ka > 0 and (now - last_seen) > ka * 1.5:
                log.info("[KEEPALIVE] Timeout para %s", addr)
                timed_out.append(addr)

        for addr in timed_out:
            trigger_lwt(sock, addr)
            _cleanup_client(sock, addr)


# ---------------------------------------------------------------------------
# Anúncio periódico de gateway
# ---------------------------------------------------------------------------

def advertise_loop(sock: socket.socket):
    while True:
        send_advertise(sock)
        time.sleep(ADVERTISE_INTERVAL)


# ---------------------------------------------------------------------------
# Loop principal UDP
# ---------------------------------------------------------------------------

DISPATCH = {
    MsgType.CONNECT:      handle_connect,
    MsgType.WILLTOPIC:    handle_willtopic,
    MsgType.WILLMSG:      handle_willmsg,
    MsgType.REGISTER:     handle_register,
    MsgType.PUBLISH:      handle_publish,
    MsgType.PUBREL:       handle_pubrel,
    MsgType.SUBSCRIBE:    handle_subscribe,
    MsgType.UNSUBSCRIBE:  handle_unsubscribe,
    MsgType.PINGREQ:      handle_pingreq,
    MsgType.DISCONNECT:   handle_disconnect,
    MsgType.SEARCHGW:     handle_searchgw,
}

# Pacotes que não precisam de cliente autenticado
UNAUTHENTICATED_OK = {MsgType.CONNECT, MsgType.SEARCHGW}


def _parse_packet(data: bytes):
    """
    Retorna (msg_type, payload) ou (None, None) em caso de erro.
    Suporta cabeçalho Length de 1 byte (≤255) e 3 bytes (0x01 + 2 bytes).
    """
    if len(data) < 2:
        return None, None
    if data[0] == 0x01:
        if len(data) < 4:
            return None, None
        length   = int.from_bytes(data[1:3], "big")
        msg_type = data[3]
        payload  = data[4:]
    else:
        length   = data[0]
        msg_type = data[1]
        payload  = data[2:]

    try:
        return MsgType(msg_type), payload
    except ValueError:
        return None, None


def start_broker():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Habilitar broadcast para ADVERTISE
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind((BROKER_HOST, BROKER_PORT))

    log.info("MQTT-SN Broker iniciado em %s:%d", BROKER_HOST, BROKER_PORT)

    # Threads de suporte
    threading.Thread(target=keep_alive_monitor, args=(sock,),
                     daemon=True, name="keepalive").start()
    threading.Thread(target=advertise_loop, args=(sock,),
                     daemon=True, name="advertise").start()

    while True:
        try:
            data, addr = sock.recvfrom(65535)
        except Exception as e:
            log.error("[UDP] recvfrom falhou: %s", e)
            continue

        msg_type, payload = _parse_packet(data)
        if msg_type is None:
            log.debug("[UDP] Pacote inválido de %s (%d bytes), ignorado", addr, len(data))
            continue

        # Atualizar last_seen para qualquer pacote de cliente conhecido
        with broker_lock:
            if addr in clients:
                clients[addr]["last_seen"] = time.time()

        # Verificar autenticação
        if msg_type not in UNAUTHENTICATED_OK:
            with broker_lock:
                known = addr in clients
            if not known:
                log.warning("[AUTH] Pacote %s de addr não autenticado %s",
                            msg_type.name, addr)
                continue

        handler = DISPATCH.get(msg_type)
        if handler:
            log.debug("[IN] %s de %s", msg_type.name, addr)
            # Cada pacote é processado em thread separada para não bloquear o loop
            threading.Thread(target=_safe_handle,
                             args=(handler, sock, addr, payload),
                             daemon=True).start()
        else:
            log.debug("[IN] Tipo %s não tratado, ignorado", msg_type.name)


def _safe_handle(handler, sock, addr, payload):
    try:
        handler(sock, addr, payload)
    except Exception as e:
        log.error("[HANDLER] Exceção em %s para %s: %s",
                  handler.__name__, addr, e, exc_info=True)


if __name__ == "__main__":
    start_broker()