import socket
import json
import struct
import time

HOST = "0.0.0.0"
PORT = 12345

def send_message(sock, action):
    msg = json.dumps({"action": action})
    msg_bytes = msg.encode()
    length = struct.pack(">H", len(msg_bytes))
    sock.sendall(length + msg_bytes)

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((HOST, PORT))
        server_sock.listen(1)
        print(f"Server listening on {HOST}:{PORT}")
        while True:
            conn, addr = server_sock.accept()
            print(f"Client connected from {addr}")
            try:
                while True:
                    send_message(conn, "toggle_on")
                    print("Sent: toggle_on")
                    time.sleep(3)
                    send_message(conn, "toggle_off")
                    print("Sent: toggle_off")
                    time.sleep(3)
            except Exception as e:
                print("Client disconnected or error:", e)
            finally:
                conn.close()

if __name__ == "__main__":
    main()
