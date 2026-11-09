"""
eBells UDP protocol.

The protocol is deliberately small so that it can eventually be
implemented on an ESP8266 using WiFiUDP.
"""

import struct


# --------------------------------------------------
# Protocol version
# --------------------------------------------------

PROTOCOL_VERSION = 1


# --------------------------------------------------
# Message types
# --------------------------------------------------

MESSAGE_REGISTER = 1
MESSAGE_REGISTERED = 2
MESSAGE_STRIKE = 3
MESSAGE_REJECTED = 4


# --------------------------------------------------
# Stroke types
# --------------------------------------------------

STROKE_HAND = 1
STROKE_BACK = 2


# --------------------------------------------------
# Packet formats
# --------------------------------------------------

# REGISTER
#
#   byte 0       protocol version
#   byte 1       message type
#   bytes 2-7    MAC address
#
REGISTER_FORMAT = "!BB6s"

# REGISTERED
#
#   byte 0       protocol version
#   byte 1       message type
#   byte 2       bell number
#
REGISTERED_FORMAT = "!BBB"

# REJECTED
#
#   byte 0       protocol version
#   byte 1       message type
#   byte 2       reason
#
REJECTED_FORMAT = "!BBB"

# STRIKE
#
#   byte 0       protocol version
#   byte 1       message type
#   bytes 2-7    MAC address
#   byte 8       stroke type
#
STRIKE_FORMAT = "!BB6sB"


# --------------------------------------------------
# Registration
# --------------------------------------------------

def encode_register(mac):
    mac_bytes = mac_string_to_bytes(mac)

    return struct.pack(
        REGISTER_FORMAT,
        PROTOCOL_VERSION,
        MESSAGE_REGISTER,
        mac_bytes,
    )


def decode_register(data):
    if len(data) != struct.calcsize(REGISTER_FORMAT):
        raise ValueError("Invalid REGISTER packet length")

    version, message_type, mac_bytes = struct.unpack(
        REGISTER_FORMAT,
        data,
    )

    if version != PROTOCOL_VERSION:
        raise ValueError("Unsupported protocol version")

    if message_type != MESSAGE_REGISTER:
        raise ValueError("Not a REGISTER packet")

    return bytes_to_mac_string(mac_bytes)


# --------------------------------------------------
# Registration response
# --------------------------------------------------

def encode_registered(bell_number):
    return struct.pack(
        REGISTERED_FORMAT,
        PROTOCOL_VERSION,
        MESSAGE_REGISTERED,
        bell_number,
    )


def decode_registered(data):
    if len(data) != struct.calcsize(REGISTERED_FORMAT):
        raise ValueError("Invalid REGISTERED packet length")

    version, message_type, bell_number = struct.unpack(
        REGISTERED_FORMAT,
        data,
    )

    if version != PROTOCOL_VERSION:
        raise ValueError("Unsupported protocol version")

    if message_type != MESSAGE_REGISTERED:
        raise ValueError("Not a REGISTERED packet")

    return bell_number


# --------------------------------------------------
# Rejection
# --------------------------------------------------

REJECT_REASON_MAX_BELLS = 1


def encode_rejected(reason):
    return struct.pack(
        REJECTED_FORMAT,
        PROTOCOL_VERSION,
        MESSAGE_REJECTED,
        reason,
    )


def decode_rejected(data):
    if len(data) != struct.calcsize(REJECTED_FORMAT):
        raise ValueError("Invalid REJECTED packet length")

    version, message_type, reason = struct.unpack(
        REJECTED_FORMAT,
        data,
    )

    if version != PROTOCOL_VERSION:
        raise ValueError("Unsupported protocol version")

    if message_type != MESSAGE_REJECTED:
        raise ValueError("Not a REJECTED packet")

    return reason


# --------------------------------------------------
# Strike
# --------------------------------------------------

def encode_strike(mac, stroke):
    mac_bytes = mac_string_to_bytes(mac)

    return struct.pack(
        STRIKE_FORMAT,
        PROTOCOL_VERSION,
        MESSAGE_STRIKE,
        mac_bytes,
        stroke,
    )


def decode_strike(data):
    if len(data) != struct.calcsize(STRIKE_FORMAT):
        raise ValueError("Invalid STRIKE packet length")

    version, message_type, mac_bytes, stroke = struct.unpack(
        STRIKE_FORMAT,
        data,
    )

    if version != PROTOCOL_VERSION:
        raise ValueError("Unsupported protocol version")

    if message_type != MESSAGE_STRIKE:
        raise ValueError("Not a STRIKE packet")

    return bytes_to_mac_string(mac_bytes), stroke


# --------------------------------------------------
# MAC address conversion
# --------------------------------------------------

def mac_string_to_bytes(mac):
    parts = mac.split(":")

    if len(parts) != 6:
        raise ValueError("Invalid MAC address")

    try:
        return bytes(int(part, 16) for part in parts)
    except ValueError:
        raise ValueError("Invalid MAC address")


def bytes_to_mac_string(mac_bytes):
    return ":".join(
        f"{byte:02X}"
        for byte in mac_bytes
    )

