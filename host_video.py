import cv2
import socket
import pickle
import sys
import threading
import time

from pathlib import Path
from moviepy import VideoFileClip

def stream_video(sock, client_addr, directory, video_name):
    file_path = (Path(directory) / video_name).absolute()
    paused = False
    cap = cv2.VideoCapture(file_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 60
    cap_lock = threading.Lock()

    AUDIO_FREQUENCY = 32000
    audio_clip = VideoFileClip(file_path).audio
    audio = audio_clip.to_soundarray(fps=AUDIO_FREQUENCY).astype('float32')
    audio_fps_ratio = AUDIO_FREQUENCY // fps

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
        audio_segment = audio[frame_index * audio_fps_ratio:int(frame_index*audio_fps_ratio)]
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 30])
        if not success:
            continue

        sock.sendto(pickle.dumps((frame_index, encoded)), client_addr)
        sock.sendto(pickle.dumps((audio_segment, AUDIO_FREQUENCY)))
        frame_index += 1
    
    cap.release()

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
                def wait_and_stream():
                    while True:
                        _, addr = video_sock.recvfrom(1024)
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
