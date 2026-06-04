import argparse
import socket
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Simple UDP syslog listener for local testing.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5514)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))

    print(f"listening udp syslog on {args.host}:{args.port}")
    while True:
        data, address = sock.recvfrom(65535)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = data.decode("utf-8", errors="replace").strip()
        print(f"{timestamp} from={address[0]}:{address[1]} {message}")


if __name__ == "__main__":
    main()
