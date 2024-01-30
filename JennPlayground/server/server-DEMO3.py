from threading import Thread, Event
import socket
import cv2
from picamera.array import PiRGBArray
from picamera import PiCamera

'''
Define a threaded camera "PiVideoStream" class
'''

class PiVideoStream:
    def __init__(self, resolution=(160, 128), framerate=90):
        # initialize the camera and stream
        print("Initializing Video Steam")
        self.camera = PiCamera()
        self.camera.resolution = resolution
        self.camera.framerate = framerate
        self.rawCapture = PiRGBArray(self.camera, size=resolution)
        self.stream = self.camera.capture_continuous(self.rawCapture,
            format="rgb", use_video_port=True)
        # initialize the frame and the variable used to indicate
        # if the thread should be stopped
        self.frame = None
        self.stopped = False
        self.newframe = True
        
    def start(self):
        # start the thread to read frames from the video stream
        # ======= BEGIN CAMERA THREAD: UPDATE LOOP ============
        Thread(target=self.__update, args=()).start()
        return self
    
    def __update(self):
        # ==== UPDATE LOOP PULLING FRAMES FROM THE STREAM ====
        # keeps looping infinitely until the Thread is stopped
        for f in self.stream:
            # grab the frame from the stream and clear the stream in
            # preparation for the next frame
            self.frame = f.array
            self.rawCapture.truncate(0)
            self.newframe = True #indicate new frame
            # if the thread indicator variable is set, stop the thread
            # and resource camera resources
            if self.stopped:
                self.stream.close()
                self.rawCapture.close()
                self.camera.close()
                return
            
    
    def read(self):
        # return the frame most recently read by update loop
        new = self.newframe
        self.newframe = False #indicate frame already read
        return self.frame, new
    
    def stop(self):
        # indicate that the Thread (update loop) should be stopped
        self.stopped = True
        


'''
Server function to send motion data to client
'''
stop_event = Event()

def detect_motion_in_segment(thresh, x_start, x_end):
    segment = thresh[:, x_start:x_end]
    return 1 if cv2.countNonZero(segment) > 5 else 0


def client_handler(connection, stop_event):
    # Initialize variables for motion detection
    print("Started Client Handler")
    prev_frame = None
    video_stream = PiVideoStream(resolution=(320, 240), framerate=32).start()
    motion_level = 0
    
    #Prepare Image Quadrants
    w=video_stream.camera.resolution[0]
    h=video_stream.camera.resolution[1]
    total_pixels = w * h
    max_motion_pixels = total_pixels
    segment_width = w // 10
        
    try:
        
        while not stop_event.is_set():
            # Read the current frame from the video stream
            frame, new = video_stream.read()
            if new and frame is not None:
                # Convert frame to grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                # Initialize prev_frame
                if prev_frame is None:
                    prev_frame = gray
                    continue

                # Compute the absolute difference between the current frame and previous frame
                frame_delta = cv2.absdiff(prev_frame, gray)
                thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]


                
                # Sum up all the non-zero pixels in the threshold image to detect motion
                motion_level = cv2.countNonZero(thresh)
                
                # Divide Image into Quadrants
                top_left = int(cv2.countNonZero(thresh[:h//2, :w//2])>5)
                top_right = int(cv2.countNonZero(thresh[:h//2, w//2:])>5)
                bottom_left  = int(cv2.countNonZero(thresh[h//2:, :w//2])>5)
                bottom_right = int(cv2.countNonZero(thresh[h//2:, w//2:])>5)
                
                segments = [detect_motion_in_segment(thresh, i * segment_width, (i + 1) * segment_width) for i in range(10)]
                motion_data = ''.join(map(str, segments))
                
                print(motion_data)
                prev_frame = gray

                # Send motion level to the client

                try:
                    connection.sendall(str(motion_data).encode())
                except BrokenPipeError:
                    # Client has disconnected
                    break
            if video_stream.stopped:
                stop_event.set()

        # Cleanup resources
        video_stream.stop()
        print("Video Stream Stopped")
    finally:
        connection.close()
        print("Close Connection")

def server(host, port, stop_event):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((host, port))
        server_socket.listen()
        print("Server is listening on: ", port)

        while not stop_event.is_set():
            # Accept new connections
            connection, client_addr = server_socket.accept()
            print("Accepted a new connection from", client_addr)

            # Check for exit command from client
            data = connection.recv(1024).decode()
            if data.lower() == 'exit':
                print("EXIT received")
                stop_event.set()
                break
            elif data.lower() == 'start':
                print("START received")  
                print("Start Client Thread")
                # Start a new thread to handle the client
                client_thread = Thread(target=client_handler, args=(connection, stop_event))
                client_thread.start()           
                
        # Shutdown server code
        print("Server is shutting down.")




'''
Main function to start the server
'''
def main():
    server_ip = '0.0.0.0'
    port = 5560
    server_thread = Thread(target=server, args=(server_ip, port, stop_event))
    server_thread.start()

    # Wait for the server thread to finish
    server_thread.join()

if __name__ == '__main__':
    main()