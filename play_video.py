import cv2
import pickle
import socket
import sys

def main(bind_ip: str, port: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((bind_ip, port))

    while True:
        data, _ = sock.recvfrom(65536)
        encoded = pickle.loads(data)
        frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

        if frame is None:
            continue

        cv2.imshow("Frame", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
