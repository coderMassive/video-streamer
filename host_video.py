import cv2
import socket
import pickle
import sys
import threading
from pathlib import Path
import time

def stream_video(sock, client_addr, directory, video_name):
    paused = False
    cap = cv2.VideoCapture(str((Path(directory) / video_name).absolute()))
    cap_lock = threading.Lock()

    def handle_messages():
        nonlocal paused
        while True:
            data, addr = sock.recvfrom(1024)
            if addr == client_addr:
                command = data.decode("utf-8")
                if command == "pause":
                    paused = True
                elif command == "resume":
                    paused = False
                elif command == "back":
                    with cap_lock:
                        current = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, current - 60))
                elif command == "forward":
                    with cap_lock:
                        current = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, current + 60)

    threading.Thread(target=handle_messages, daemon=True).start()

    frame_index = 0
    while True:
        if paused:
            time.sleep(0.01)
            continue

        with cap_lock:
            ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.resize(frame, (640, 360))
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 30])
        if not success:
            continue

        sock.sendto(pickle.dumps((frame_index, encoded)), client_addr)
        frame_index += 1

def handle_client(client_sock, address, video_sock, videos_directory):
    try:
        while True:
            data = client_sock.recv(1024)
            if not data:
                break
            command, arg = pickle.loads(data)
            if command == "GET":
                port = video_sock.getsockname()[1]
                client_sock.send(pickle.dumps(port))
                client_addr = (address[0], None)
                def wait_and_stream():
                    while True:
                        data, addr = video_sock.recvfrom(1024)
                        if addr[0] == address[0]:
                            stream_video(video_sock, addr, videos_directory, arg)
                            break
                threading.Thread(target=wait_and_stream, daemon=True).start()
            else:
                client_sock.send(pickle.dumps("INVALID"))
    except:
        pass
    client_sock.close()

def main(port, directory):
    control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    control_sock.bind(("", port))
    control_sock.listen(5)
    video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    video_sock.bind(("0.0.0.0", 0))
    while True:
        client_sock, addr = control_sock.accept()
        threading.Thread(target=handle_client, args=(client_sock, addr, video_sock, directory), daemon=True).start()

if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
