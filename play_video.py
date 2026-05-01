import cv2
import pickle
import socket
import sys
import json

import sounddevice as sd

def stringed_videos(videos: list[str], start_index: int=0):
    output = ""

    for i, video in enumerate(videos):
        output += f"{start_index + i + 1}: {video}\n"
    output += f"Got {start_index + 1} to {start_index + len(videos)} video names."
    return output

def video_playback(host_ip, host_port):
    print("Playing video!")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 0))

    i = 0
    speed = 1
    paused = False
    just_fetch = False
    first_frame = False

    stream: sd.OutputStream = None

    while True:
        if not paused or just_fetch:
            request = {"frame": int(i)}
            json_bytes = json.dumps(request).encode()
            sock.sendto(json_bytes, (host_ip, host_port))

            data, _ = sock.recvfrom(65536)
            audio_data, _ = sock.recvfrom(65536)
            encoded = pickle.loads(data)
            audio_decoded = pickle.loads(audio_data)
            frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            just_fetch = False
            sd.stop()

            if stream is None:
                stream = sd.OutputStream(samplerate=audio_decoded[1], channels=audio_decoded[2])
                stream.start()
            stream.write(audio_decoded[0])

        if frame is None:
            continue

        cv2.imshow("Frame", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("k"):
            paused = not paused
        elif key == ord("j"):
            i -= 150
            just_fetch = True
        elif key == ord("l"):
            i += 150
            just_fetch = True
        elif key == ord("i"):
            speed = 2
        elif key == ord("m"):
            speed = 0.5
        elif key == ord(";"):
            speed = 1

        if not paused:
            i += speed

        if first_frame == False:
            first_frame = True
        else:
            try:
                cv2.getWindowProperty('Frame', cv2.WND_PROP_VISIBLE)
            except:
                break

    sock.sendto(json.dumps({"stop": True}).encode(), (host_ip, host_port))
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
