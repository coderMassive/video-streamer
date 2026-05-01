import cv2
import socket
import pickle
import sys
import threading
import time

import sounddevice as sd
from collections import deque

def stringed_videos(videos: list[str], start_index: int=0):
    output = ""

    for i, video in enumerate(videos):
        output += f"{start_index + i + 1}: {video}\n"
    output += f"Got {start_index + 1} to {start_index + len(videos)} video names."
    return output

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

    stream: sd.OutputStream = None

    def receive_frames():
        nonlocal running

        while running:
            try:
                data, _ = sock.recvfrom(65536)
                raw_payload = pickle.loads(data)
                payload = raw_payload[:2]
                audio_payload = raw_payload[2]

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
                    cache.append((frame_index, frame, audio_payload))

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

        frame_index, frame, audio_payload = cache.popleft()

        if frame_index is not None and last_frame_index is not None:
            if frame_index != last_frame_index + 1:
                print(f"frame jump: {last_frame_index} -> {frame_index}")

        last_frame_index = frame_index

        print("cache size:", len(cache))
        cv2.imshow("Frame", frame)
        if stream is not None and (stream.samplerate != audio_payload[1] or stream.channels != audio_payload[2]):
            stream.stop()
            stream.close()
            stream = None
        if stream is None:
            stream = sd.OutputStream(samplerate=audio_payload[1], channels=audio_payload[2])
            stream.start()
        stream.write(audio_payload[0])

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
            sock.sendto(b"stop", (host_ip, host_port))
            running = False

    cv2.destroyAllWindows()

    if stream is not None:
        stream.stop()
        stream.close()


def main(host_ip, host_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host_ip, host_port))

    try:
        while True:
            command = input("> ")
            match command.strip().split():
                case ["GET", *args]:
                    sock.send(pickle.dumps(("GET", ' '.join(args))))
                    port = int(pickle.loads(sock.recv(1024)))
                    video_playback(host_ip, port)
                case ["DIR", *args]:
                    index = args[0] if len(args) > 0 else 0
                    count = args[1] if len(args) > 1 else 64
                    sock.send(pickle.dumps(("DIR", index, count)))
                    message = pickle.loads(sock.recv(65536))
                    print(stringed_videos(message, index))
                case ["EXIT"]:
                    break
                case _:
                    print("Invalid command.")
    except KeyboardInterrupt:
        pass

    sock.close()


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
