import cv2
import socket
import pickle
import sys
import threading
import time

from pathlib import Path
from moviepy import VideoFileClip
from itertools import islice

class Flag:
    value: bool = False

def stream_video(sock, client_ip, file_path, force_halt: Flag):
    paused = False
    halt = False
    cap = cv2.VideoCapture(file_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 60
    cap_lock = threading.Lock()

    AUDIO_FREQUENCY = 44100
    audio_clip = VideoFileClip(file_path).audio
    audio = audio_clip.to_soundarray(fps=AUDIO_FREQUENCY).astype('float32')
    audio_fps_ratio = AUDIO_FREQUENCY // fps

    user_addr = None

    def handle_messages():
        nonlocal paused
        nonlocal user_addr
        nonlocal halt

        while True:
            try:
                data, addr = sock.recvfrom(1024)
            except TimeoutError:
                halt = True
                break
            if (user_addr is None and addr[0] == client_ip) or user_addr == addr:
                user_addr = addr
                command = data.decode("utf-8")
                if command[:5] == "pause":
                    paused = True
                elif command[:6] == "resume":
                    with cap_lock:
                        current = int(command[7:])
                        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, current))
                    paused = False
                elif command[:4] == "back":
                    with cap_lock:
                        request = int(command[5:])
                        current = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(request, current) - fps * 5))
                elif command[:7] == "forward":
                    with cap_lock:
                        request = int(command[8:])
                        current = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, min(max(request, current) + fps * 5, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))))
                elif command == "stop":
                    halt = True
                    break

    threading.Thread(target=handle_messages, daemon=True).start()
    while not halt:
        if force_halt.value:
            halt = True
            break

        if paused or not user_addr:
            time.sleep(0.01)
            continue

        with cap_lock:
            ok, frame = cap.read()
            frame_index = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if not ok:
                cap.set(cv2.CAP_PROP_POS_FRAMES, cap.get(cv2.CAP_PROP_FRAME_COUNT) - 1)
                ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.resize(frame, (640, 360))
        audio_segment = audio[frame_index * audio_fps_ratio:int((frame_index + 1)*audio_fps_ratio)]
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 30])
        if not success:
            continue

        sock.sendto(pickle.dumps((frame_index, encoded, fps, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), (audio_segment, AUDIO_FREQUENCY, audio_clip.nchannels))), user_addr)
    
    cap.release()

def get_videos(directory: str, index: int=0, limit: int=64) -> list[str]:
    videos = Path(directory)
    return [video.name for video in islice(videos.iterdir(), index, index + limit)]

def handle_client_requests(video_sock: socket.socket, client_sock: socket.socket, address, videos_directory: str):
    play_flag = Flag()
    play_flag.value = False
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
                    file_path: Path = (Path(videos_directory) / args[0]).absolute()
                    if file_path.exists() and file_path.is_file():
                        playback_thread = threading.Thread(target=stream_video, args=(video_sock, address[0], file_path, play_flag), daemon=True)
                        playback_thread.start()
                        output = video_sock.getsockname()[1]
                    else:
                        output = "File does not exist!"
                case _:
                    output = "INVALID"

            client_sock.send(pickle.dumps(output))
    except:
        pass

    play_flag.value = True
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

if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
