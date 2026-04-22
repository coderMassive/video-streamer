import cv2
import socket
import pickle
import sys
import time

def main(host: str, port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cap = cv2.VideoCapture("input_video.mp4")
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 40])
        if not success:
            continue

        payload = pickle.dumps(encoded)
        sock.sendto(payload, (host, port))

        time.sleep(1/fps)

    cap.release()

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
