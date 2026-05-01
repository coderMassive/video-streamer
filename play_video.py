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
        nonlocal sender_paused

        while running:
            try:
                data, _ = sock.recvfrom(65536)
                raw_payload = pickle.loads(data)
                payload = raw_payload[:3]
                audio_payload = raw_payload[3]

                if isinstance(payload, tuple) and len(payload) == 3:
                    frame_index, encoded, fps = payload
                else:
                    frame_index = None
                    encoded = payload
                    fps=60

                frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                # Always drain the socket. If cache is full, drop newest arrivals.
                if len(cache) < max_cache and (not sender_paused):
                    cache.append((frame_index, frame, fps, audio_payload))

            except OSError:
                break
            except Exception:
                continue

        sock.close()

    threading.Thread(target=receive_frames, daemon=True).start()

    while running and len(cache) < min_cache:
        time.sleep(0.001)

    last_frame_index = 0

    def encode_frame_index(offset: int=0):
        return bytes(str(last_frame_index + (offset if offset is not None else 0)), encoding="utf-8")

    def handle_input(key: int):
        nonlocal paused, last_frame_index, running
        if key == ord("k"):
            paused = not paused
        elif key == ord("j"):
            sock.sendto(b"back:" + encode_frame_index(), (host_ip, host_port))
            cache.clear()
        elif key == ord("l"):
            sock.sendto(b"forward:" + encode_frame_index(), (host_ip, host_port))
            cache.clear()
        elif key == ord("q"):
            sock.sendto(b"stop", (host_ip, host_port))
            running = False

    while running:
        if len(cache) >= max_cache - 10 and not sender_paused:
            sock.sendto(b"pause", (host_ip, host_port))
            sender_paused = True
        elif len(cache) <= min_cache and sender_paused:
            sock.sendto(b"resume:" + encode_frame_index(len(cache)), (host_ip, host_port))
            sender_paused = False

        if paused:
            handle_input(cv2.waitKey(17) & 0xFF)
            continue

        if not cache:
            handle_input(cv2.waitKey(17) & 0xFF)
            continue

        frame_index, frame, fps, audio_payload = cache.popleft()
        last_frame_index = frame_index

        if stream is not None and (stream.samplerate != audio_payload[1] or stream.channels != audio_payload[2]):
            stream.stop()
            stream.close()
            stream = None
        if stream is None:
            stream = sd.OutputStream(samplerate=audio_payload[1], channels=audio_payload[2])
            stream.start()
        stream.write(audio_payload[0])
        cv2.imshow("Frame", frame)

        handle_input(cv2.waitKey(max(1, int(1000/fps))) & 0xFF)

        try:
            if cv2.getWindowProperty("Frame", cv2.WND_PROP_VISIBLE) < 1:
                sock.sendto(b"stop", (host_ip, host_port))
                running = False
        except:
            break

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
