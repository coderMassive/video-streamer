import cv2
import socket
import pickle
import sys
import json

def main(host_ip, host_port, client_ip, client_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host_ip, host_port))

    cap = cv2.VideoCapture("input_video.mp4")
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30

    while True:
        data, _ = sock.recvfrom(1024)
        data = json.loads(data.decode('utf-8'))

        cap.set(cv2.CAP_PROP_POS_FRAMES, data["frame"])
        ok, frame = cap.read()
        if not ok:
            break

        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 40])
        if not success:
            continue

        payload = pickle.dumps(encoded)
        sock.sendto(payload, (client_ip, client_port))

    cap.release()

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
