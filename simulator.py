"""
eBells Wemos simulator.

Simulates one bell communicating with the eBells UDP server.
"""

import argparse
import socket

from protocol import (
    encode_register,
    decode_registered,
    encode_strike,
    decode_rejected,
    STROKE_HAND,
    STROKE_BACK,
)


# --------------------------------------------------
# Simulator configuration
# --------------------------------------------------

DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 5005


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Simulate an eBell Wemos"
    )

    parser.add_argument(
        "--mac",
        required=True,
        help="MAC address to simulate",
    )

    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help=f"UDP server address (default: {DEFAULT_SERVER})",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"UDP server port (default: {DEFAULT_PORT})",
    )

    args = parser.parse_args()

    server_address = (
        args.server,
        args.port,
    )

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    # Give recvfrom() a timeout so the simulator doesn't
    # wait forever if the server doesn't respond.
    sock.settimeout(3.0)

    print("eBell simulator")
    print("================")
    print()
    print(f"MAC:    {args.mac}")
    print(f"Server: {args.server}:{args.port}")
    print()

    # --------------------------------------------------
    # Registration
    # --------------------------------------------------

    packet = encode_register(args.mac)

    print("Sending REGISTER...")

    sock.sendto(
        packet,
        server_address,
    )

    try:
        data, address = sock.recvfrom(1024)

    except socket.timeout:
        print("ERROR: No response from server.")
        sock.close()
        return

    # --------------------------------------------------
    # Registration response
    # --------------------------------------------------

    try:
        bell_number = decode_registered(data)

        print(
            f"Registered as Bell {bell_number}"
        )

    except ValueError:

        try:
            reason = decode_rejected(data)

            print(
                f"Registration rejected "
                f"(reason {reason})"
            )

        except ValueError as error:
            print(
                f"Invalid response from server: {error}"
            )

        sock.close()
        return

    # --------------------------------------------------
    # Interactive mode
    # --------------------------------------------------

    print()
    print("Commands:")
    print("  h = handstroke")
    print("  b = backstroke")
    print("  q = quit")
    print()

    while True:
        try:
            command = input(
                f"Bell {bell_number}> "
            ).strip().lower()

        except EOFError:
            break

        if command == "q":
            break

        if command == "h":
            stroke = STROKE_HAND
            name = "HANDSTROKE"

        elif command == "b":
            stroke = STROKE_BACK
            name = "BACKSTROKE"

        else:
            print("Unknown command")
            continue

        packet = encode_strike(
            args.mac,
            stroke,
        )

        sock.sendto(
            packet,
            server_address,
        )

        print(
            f"Sent {name}"
        )

    sock.close()
    print("Simulator stopped.")


if __name__ == "__main__":
    main()

