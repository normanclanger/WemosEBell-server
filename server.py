"""
eBells UDP server.

Receives registration packets from bells and assigns bell numbers
in the order that new bells are first seen.
"""

import socket
import struct
import time
from bellsound import BellSound

from protocol import (
    PROTOCOL_VERSION,
    MESSAGE_REGISTER,
    MESSAGE_REGISTERED,
    MESSAGE_STRIKE,
    MESSAGE_REJECTED,
    REJECT_REASON_MAX_BELLS,
    decode_register,
    decode_strike,
    encode_registered,
    encode_rejected,
)

# --------------------------------------------------
# Sound object
# --------------------------------------------------
sound = BellSound()

# --------------------------------------------------
# Server configuration
# --------------------------------------------------

SERVER_ADDRESS = "0.0.0.0"
SERVER_PORT = 5005

MAX_BELLS = 12


# --------------------------------------------------
# Bell registry
# --------------------------------------------------

bells = {}
STRIKE_SUPPRESSION_SECONDS = 0.350
last_strike_time = {}


# --------------------------------------------------
# Registration
# --------------------------------------------------

def register_bell(mac):
    """
    Register a new MAC address.

    Returns:
        bell number, or None if the server is full.
    """

    # Already registered?
    if mac in bells:
        return bells[mac]

    # Maximum number reached?
    if len(bells) >= MAX_BELLS:
        return None

    bell_number = len(bells) + 1

    bells[mac] = bell_number

    print()
    print(f"REGISTER  {mac}")
    print(f"Assigned Bell {bell_number}")

    return bell_number


# --------------------------------------------------
# Packet handling
# --------------------------------------------------

def handle_packet(data, address, sock):
    if len(data) < 2:
        print("Ignoring packet that is too short")
        return

    version = data[0]
    message_type = data[1]

    if version != PROTOCOL_VERSION:
        print(
            f"Ignoring packet from {address}: "
            f"unsupported protocol version {version}"
        )
        return

    if message_type == MESSAGE_REGISTER:
        handle_register(data, address, sock)

    elif message_type == MESSAGE_STRIKE:
        handle_strike(data, address)

    else:
        print(
            f"Ignoring unknown message type "
            f"{message_type} from {address}"
        )


def handle_register(data, address, sock):
    try:
        mac = decode_register(data)
    except ValueError as error:
        print(f"Invalid REGISTER from {address}: {error}")
        return

    bell_number = register_bell(mac)

    if bell_number is None:
        print(f"Registration rejected for {mac}: maximum bells reached")

        response = encode_rejected(
            REJECT_REASON_MAX_BELLS
        )

        sock.sendto(response, address)
        return

    response = encode_registered(bell_number)

    sock.sendto(response, address)


def handle_strike(data, address):
    try:
        mac, stroke = decode_strike(data)
    except ValueError as error:
        print(f"Invalid STRIKE from {address}: {error}")
        return

    # The bell must already be registered.
    if mac not in bells:
        print(
            f"Ignoring strike from unregistered bell {mac}"
        )
        return

    bell_number = bells[mac]
    now = time.monotonic()

    # Suppress bounce strikes from the same bell.
    previous = last_strike_time.get(mac)
    if (
        previous is not None
        and now - previous < STRIKE_SUPPRESSION_SECONDS
    ):
        print(
            f"SUPPRESSED Bell {bell_number} "
            f"({(now - previous) * 1000:.1f} ms since last strike)"
        )
        return

    # Record only accepted strikes.
    last_strike_time[mac] = now

    if stroke == 1:
        stroke_name = "HANDSTROKE"
    elif stroke == 2:
        stroke_name = "BACKSTROKE"
    else:
        stroke_name = f"UNKNOWN({stroke})"

    print(
        f"STRIKE    Bell {bell_number}    {stroke_name}"
    )
    print(f"Received UDP strike at {now:.6f}")
    sound.play_wav(bell_number, delay=0)



# --------------------------------------------------
# Main server
# --------------------------------------------------

def main():
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    sock.bind(
        (
            SERVER_ADDRESS,
            SERVER_PORT,
        )
    )

    print("eBells UDP server")
    print("=================")
    print()
    print(
        f"Listening on UDP port {SERVER_PORT}"
    )
    print(
        f"Maximum bells: {MAX_BELLS}"
    )
    print()
    
    sound.initialise_sound()
    
    print("Waiting for registrations...")

    try:
        while True:
            data, address = sock.recvfrom(1024)

            handle_packet(
                data,
                address,
                sock,
            )

    except KeyboardInterrupt:
        print()
        print("Server stopped.")

    finally:
        sock.close()


if __name__ == "__main__":
    main()

