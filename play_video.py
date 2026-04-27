import cv2
import socket
import pickle
import sys
import threading
import time
from collections import deque

def video_playback(host_ip, host_port):
    cache = deque()
    running = True
    max_cache = 120
    min_cache = 30

    def receive_frames():
        nonlocal running
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", 0))
        sock.sendto(b"start", (host_ip, host_port))

        while running:
            if len(cache) >= max_cache:
                time.sleep(0.002)
                continue

            data, _ = sock.recvfrom(65536)
            encoded = pickle.loads(data)
            frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            if frame is not None:
                cache.append(frame)
        sock.close()

    threading.Thread(target=receive_frames, daemon=True).start()

    while len(cache) < min_cache:
        time.sleep(0.001)

    while True:
        if not cache:
            time.sleep(0.001)
            continue

        frame = cache.popleft()
        cv2.imshow("Frame", frame)
        key = cv2.waitKey(60) & 0xFF
        if key == ord("q"):
            running = False
            break

    cv2.destroyAllWindows()

def main(host_ip, host_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host_ip, host_port))

    while True:
        cmd = input("> ")
        if cmd.startswith("GET "):
            sock.send(pickle.dumps(("GET", cmd[4:])))
            port = pickle.loads(sock.recv(1024))
            video_playback(host_ip, port)
        elif cmd == "EXIT":
            break

    sock.close()

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
