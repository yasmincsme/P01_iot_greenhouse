"""
aux.py — Constantes do protocolo MQTT-SN (v1.2)
"""
from enum import IntEnum


class MsgType(IntEnum):
    ADVERTISE     = 0x00
    SEARCHGW      = 0x01
    GWINFO        = 0x02
    CONNECT       = 0x04
    CONNACK       = 0x05
    WILLTOPICREQ  = 0x06
    WILLTOPIC     = 0x07
    WILLMSGREQ    = 0x08
    WILLMSG       = 0x09
    REGISTER      = 0x0A
    REGACK        = 0x0B
    PUBLISH       = 0x0C
    PUBACK        = 0x0D
    PUBCOMP       = 0x0E
    PUBREC        = 0x0F
    PUBREL        = 0x10
    SUBSCRIBE     = 0x12
    SUBACK        = 0x13
    UNSUBSCRIBE   = 0x14
    UNSUBACK      = 0x15
    PINGREQ       = 0x16
    PINGRESP      = 0x17
    DISCONNECT    = 0x18
    WILLTOPICUPD  = 0x1A
    WILLTOPICRESP = 0x1B
    WILLMSGUPD    = 0x1C
    WILLMSGRESP   = 0x1D


class ReturnCode(IntEnum):
    ACCEPTED            = 0x00
    REJECTED_CONGESTION = 0x01
    REJECTED_TOPIC_ID   = 0x02
    REJECTED_NOT_SUPP   = 0x03


class TopicIdType(IntEnum):
    NORMAL     = 0x00  # topic_id registrado via REGISTER
    PREDEFINED = 0x01  # topic_id pré-definido
    SHORT      = 0x02  # nome curto de 2 bytes embutido no campo topic_id


# Estados do cliente
class ClientState(IntEnum):
    ACTIVE       = 0
    ASLEEP       = 1
    AWAKE        = 2
    DISCONNECTED = 3