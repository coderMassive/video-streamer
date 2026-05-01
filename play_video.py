import cv2
import socket
import pickle
import sys
import threading
import time
from collections import deque
import json


def video_playback(host_ip, host_port):
    cache = deque()
    running = True
    paused = False
    sender_paused = False

    max_cache = 120
    min_cache = 30

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.bind(("0.0.0.0", 0))
    sock.sendto(b"start", (host_ip, host_port))

    def receive_frames():
        nonlocal running

        while running:
            try:
                data, _ = sock.recvfrom(65536)
                payload = pickle.loads(data)

                if isinstance(payload, tuple) and len(payload) == 2:
                    frame_index, encoded = payload
                else:
                    frame_index = None
                    encoded = payload

                frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                # Always drain the socket. If cache is full, drop newest arrivals.
                if len(cache) < max_cache:
                    cache.append((frame_index, frame))

            except OSError:
                break
            except Exception:
                continue

        sock.close()

    threading.Thread(target=receive_frames, daemon=True).start()

    while running and len(cache) < min_cache:
        time.sleep(0.001)

    last_frame_index = None

    while running:
        if len(cache) >= max_cache - 5 and not sender_paused:
            sock.sendto(b"pause", (host_ip, host_port))
            sender_paused = True
        elif len(cache) <= min_cache and sender_paused:
            sock.sendto(b"resume", (host_ip, host_port))
            sender_paused = False

        if paused:
            key = cv2.waitKey(30) & 0xFF
            if key == ord("k"):
                paused = False
            elif key == ord("j"):
                sock.sendto(b"back", (host_ip, host_port))
                cache.clear()
                last_frame_index = None
            elif key == ord("l"):
                sock.sendto(b"forward", (host_ip, host_port))
                cache.clear()
                last_frame_index = None
            elif key == ord("q"):
                running = False
            continue

        if not cache:
            key = cv2.waitKey(1) & 0xFF
            if key == ord("k"):
                paused = True
            elif key == ord("j"):
                sock.sendto(b"back", (host_ip, host_port))
                cache.clear()
                last_frame_index = None
            elif key == ord("l"):
                sock.sendto(b"forward", (host_ip, host_port))
                cache.clear()
                last_frame_index = None
            elif key == ord("q"):
                running = False
            time.sleep(0.001)
            continue

        frame_index, frame = cache.popleft()

        if frame_index is not None and last_frame_index is not None:
            if frame_index != last_frame_index + 1:
                print(f"frame jump: {last_frame_index} -> {frame_index}")

        last_frame_index = frame_index

        print("cache size:", len(cache))
        cv2.imshow("Frame", frame)

        key = cv2.waitKey(33) & 0xFF
        if key == ord("k"):
            paused = True
        elif key == ord("j"):
            sock.sendto(b"back", (host_ip, host_port))
            cache.clear()
            last_frame_index = None
        elif key == ord("l"):
            sock.sendto(b"forward", (host_ip, host_port))
            cache.clear()
            last_frame_index = None
        elif key == ord("q"):
            running = False

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
