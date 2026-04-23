import cv2
import socket
import pickle
import sys
import json
import threading

from pathlib import Path
from itertools import islice

def stream_video(sock: socket.socket, client_ip: str, directory: str, video_name: str):
    cap = cv2.VideoCapture((Path(directory) / video_name).absolute())
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30

    while True:
        data, addr = sock.recvfrom(1024)
        data = json.loads(data.decode('utf-8'))

        if "stop" in data:
            break

        cap.set(cv2.CAP_PROP_POS_FRAMES, data["frame"])
        ok, frame = cap.read()
        if not ok:
            break

        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 40])
        if not success:
            continue

        payload = pickle.dumps(encoded)
        sock.sendto(payload, (client_ip, addr[1]))

    cap.release()

def get_videos(directory: str, index: int=0, limit: int=64) -> list[str]:
    videos = Path(directory)
    return [video.name for video in islice(videos.iterdir(), index, index + limit)]

def handle_client_requests(video_sock: socket.socket, client_sock: socket.socket, address, videos_directory: str):
    try:
        while True:
            data = client_sock.recv(1024)
            if not data: break

            message = pickle.loads(data)
            command, args = message[0], tuple(message[1:])

            output = None

            match command:
                case "DIR":
                    output = get_videos(videos_directory, int(args[0]), int(args[1]))
                case "GET":
                    playback_thread = threading.Thread(target=stream_video, args=(video_sock, address[0], videos_directory, args[0]), daemon=True)
                    playback_thread.start()
                    output = video_sock.getsockname()[1]
                case _:
                    output = "INVALID"

            client_sock.send(pickle.dumps(output))
    except:
        pass

    client_sock.close()
    print(f"Connection closed with {address}")

def main(host_listen_port: int, videos_directory: str):
    print("Starting server...")

    control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    control_sock.bind(("", host_listen_port))

    control_sock.listen(10)

    video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    video_sock.bind(('0.0.0.0', 0)) # Select random port
    print(f"Established video socket at {video_sock.getsockname()}")

    try:
        while True:
            client_sock, address = control_sock.accept()
            print(f"Accepted connection from {address}!")
            thread = threading.Thread(target=handle_client_requests, args=(video_sock, client_sock, address, videos_directory), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        pass

    control_sock.close()
    print("Server closed.")

if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
