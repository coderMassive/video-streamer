import cv2
import pickle

def main(dest_ip: str, port: int) -> None:
	cap = cv2.VideoCapture("input_video.mp4")
	while True:
		ret, frame = cap.read()
		_, encoded_repr = cv2.imencode(".jpg", frame)
		sent_data = pickle.dumps(encoded_repr)
		cv2.imshow('Frame', cv2.imdecode(pickle.loads(sent_data), cv2.IMREAD_COLOR))
		cv2.waitKey(1000//60)
		try:
			cv2.getWindowProperty('Frame', cv2.WND_PROP_VISIBLE)
		except:
			break

if __name__ == "__main__":
	main("0.0.0.0", 1024)