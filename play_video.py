import cv2
import pickle
import socket
import sys
import json

def main(host_ip, host_port, client_ip, client_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((client_ip, client_port))

    i = 0
    speed = 1
    paused = False

    while True:
        request = {"frame": int(i)}
        json_bytes = json.dumps(request).encode('utf-8')
        sock.sendto(json_bytes, (host_ip, host_port))

        data, _ = sock.recvfrom(65536)
        encoded = pickle.loads(data)
        frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

        if frame is None:
            continue

        cv2.imshow("Frame", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("k"):
            paused = not paused
        elif key == ord("j"):
            i -= 150
        elif key == ord("l"):
            i += 150
        elif key == ord("i"):
            speed = 2
        elif key == ord("m"):
            speed = 0.5
        elif key == ord(";"):
            speed = 1

        if not paused:
            i += speed

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
