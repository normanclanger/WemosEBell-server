"""
eBells multi-bell simulator.

Registers eight simulated bells with the eBells UDP server.
Press 1-8 to ring a bell; each press alternates its stroke.
"""

import argparse
import socket
import sys
import termios
import tty

from protocol import (
    encode_register,
    decode_registered,
    encode_strike,
    decode_rejected,
    STROKE_HAND,
    STROKE_BACK,
)

DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 5005
BELL_COUNT = 8


def make_mac(base_mac, offset):
    """Return a MAC address incremented by offset."""
    compact = base_mac.replace(":", "").replace("-", "").replace(".", "")

    if len(compact) != 12:
        raise ValueError("MAC must contain 12 hexadecimal digits")

    try:
        value = int(compact, 16) + offset
    except ValueError:
        raise ValueError("MAC must contain hexadecimal digits") from None

    if value > 0xFFFFFFFFFFFF:
        raise ValueError("MAC address range overflow")

    value = f"{value:012x}"
    return ":".join(value[i:i + 2] for i in range(0, 12, 2))


def register_bell(sock, server_address, mac):
    """Register one simulated bell and return its assigned number."""
    print(f"Registering {mac}...", flush=True)
    sock.sendto(encode_register(mac), server_address)

    try:
        data, address = sock.recvfrom(1024)
    except socket.timeout:
        print(f"ERROR: No registration response for {mac}")
        return None

    try:
        bell_number = decode_registered(data)
        print(f"  Registered as Bell {bell_number}")
        return bell_number
    except ValueError:
        try:
            reason = decode_rejected(data)
            print(f"  Registration rejected (reason {reason})")
        except ValueError as error:
            print(f"  Invalid response: {error}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Simulate eight eBells"
    )
    parser.add_argument(
        "--mac",
        required=True,
        help="Base MAC address; seven consecutive addresses are derived from it",
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

    server_address = (args.server, args.port)
    bells = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)

    print("eBells multi-bell simulator")
    print("===========================")
    print(f"Server: {args.server}:{args.port}")
    print()

    try:
        # Register all eight simulated devices.
        for i in range(BELL_COUNT):
            mac = make_mac(args.mac, i)
            bell_number = register_bell(sock, server_address, mac)

            if bell_number is None:
                print("\nRegistration failed; stopping.")
                return

            # Start each bell with a handstroke.
            bells[bell_number] = {
                "mac": mac,
                "next_stroke": STROKE_HAND,
            }

        print()
        print("All bells registered.")
        print("Press 1-8 to ring the corresponding bell.")
        print("Each bell alternates handstroke/backstroke.")
        print("Press q to quit.")
        print()

        # Read individual key presses without requiring Enter.
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setcbreak(fd)

            while True:
                key = sys.stdin.read(1)

                if key.lower() == "q":
                    break

                if key not in "12345678":
                    continue

                requested_bell = int(key)

                if requested_bell not in bells:
                    print(f"Bell {requested_bell} is not registered")
                    continue

                bell = bells[requested_bell]
                stroke = bell["next_stroke"]

                if stroke == STROKE_HAND:
                    name = "HANDSTROKE"
                    bell["next_stroke"] = STROKE_BACK
                else:
                    name = "BACKSTROKE"
                    bell["next_stroke"] = STROKE_HAND

                packet = encode_strike(bell["mac"], stroke)
                sock.sendto(packet, server_address)

                print(f"Bell {requested_bell}: {name}", flush=True)

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    except (KeyboardInterrupt, EOFError):
        pass
    except ValueError as error:
        print(f"ERROR: {error}")
    finally:
        sock.close()
        print("\nSimulator stopped.")


if __name__ == "__main__":
    main()
