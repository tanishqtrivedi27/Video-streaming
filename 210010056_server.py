import cv2
import os
import pickle
import socket
import struct
import threading
import configparser

VIDEO_DIRECTORY = "videos"
CHUNKS_DIRECTORY = "chunks" ### Q3a
SERVER_HOST = socket.gethostname()
SERVER_PORT = 9999

# Global dictionary to store client sockets, public_keys and video
client_sockets = {}
client_public_keys = {} ### Q1b
video_files = []

client_lock = threading.Lock()

# Function to handle client connections
def handle_client(client_socket, addr):
    try:
        ### Q1a
        client_info = client_socket.recv(1024).decode().split()
        client_name = client_info[1]
        client_public_key = client_info[2]
        
        with client_lock:
            client_sockets[addr] = client_socket
            client_public_keys[client_socket] = [client_name, client_public_key]

        broadcast_dict() ### Q1c

        while True:
            message = client_socket.recv(1024).decode()
            if not message:
                break

            if message.startswith("LIST_VIDEOS"):
                send_video_list(client_socket)
            elif message.startswith("VIDEO_SELECTION"):
                video_selection = message.split(" ")[1]
                stream_video(client_socket, video_files[int(video_selection)])
            elif message.startswith("MESSAGE"):
                sender, message_content = extract_message(message)
                forward_message(message_content, sender)
            elif message.startswith("QUIT"):
                break # goes to finally block
    except Exception as e:
        print(f"Error handling client: {e}")  # Connection error or client closed socket w/o QUIT message
    finally:

        ### Q1d
        client_socket.close()
        with client_lock:
            del client_sockets[addr]
            del client_public_keys[client_socket]
        broadcast_dict()

def send_video_list(client_socket):
    video_list = str(video_files)
    client_socket.send(video_list.encode())

def stream_video(client_socket, video_file):
    ### Q3b
    print(f"Started Streaming Video for {client_public_keys[client_socket][0]}")
    try:
        suffix = ['_part1_low.mp4', '_part2_medium.mp4', '_part3_high.mp4']
        video_filename = video_file.split(".", 1)[0]
        chunks = [f'{video_filename}{ext}' for ext in suffix]
        for video_chunk in chunks:
            path = f'./{CHUNKS_DIRECTORY}/{video_chunk}'
            vid = cv2.VideoCapture(path)
            if not vid.isOpened():
                raise Exception(f"Failed to open video file: {path}")
            frameOver = 0
            while vid.isOpened():
                ret, frame = vid.read()
                if not ret: 
                    frameOver = 1
                    break
                encoded_frame = pickle.dumps(frame)
                message = struct.pack("Q", len(encoded_frame)) + encoded_frame

                client_socket.send(message)
            if (frameOver == 1):
                continue
    except Exception as e:
        print(f"Error while streaming video: {e}")
    finally:
        # Release video resources
        if 'vid' in locals() and vid.isOpened():
            vid.release()
    print("Video Streaming Ended")

def extract_message(message):
    parts = message.split(" ", 2)
    sender = parts[1]
    message_content = parts[2]
    return sender, message_content

def forward_message(message, sender):
    ### Q2
    message = f'ENCRYPTED_MESSAGE {sender} {message}'
    for addr, socket in client_sockets.items():
        socket.send(message.encode())

def broadcast_dict():
    with client_lock:
        client_dict = {}
        for _, val in client_public_keys.items():
            client_dict[val[0]] = val[1]

        updated_dict = str(client_dict)
    print(list(client_dict.keys()))
    message = f'UPDATED_DICT {updated_dict}'
    for addr, socket in client_sockets.items():
        socket.send(message.encode())

def populate_videos_list():
    video_files.clear()
    for filename in os.listdir(VIDEO_DIRECTORY):
        if (filename.endswith(".mp4")):
            video_files.append(filename)

def cut_video(video_file):
    output_prefix = video_file.split(".", 1)[0]
    cap = cv2.VideoCapture(f'./{VIDEO_DIRECTORY}/{video_file}')
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    part1_end = total_frames // 3
    part2_end = 2 * (total_frames // 3)
    
    resolutions = []
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')   
        resolutions = [eval(config['resolutions']['low']), eval(config['resolutions']['medium']), eval(config['resolutions']['high'])]
    except Exception as e:
        resolutions = [(256, 144), (1280, 720), (2560, 1440)]

    suffix = ['_part1_low.mp4', '_part2_medium.mp4', '_part3_high.mp4']
    cutOff = [(0, part1_end), (part1_end, part2_end), (part2_end, total_frames)]
    
    codec = cv2.VideoWriter_fourcc(*'mp4v')
    for i in range(3):
        cap.set(cv2.CAP_PROP_POS_FRAMES, cutOff[i][0])
        out = cv2.VideoWriter(f'./{CHUNKS_DIRECTORY}/{output_prefix}{suffix[i]}', codec, 30, resolutions[i])
        for j in range(cutOff[i][0], cutOff[i][1]):
            ret, frame = cap.read()
            if ret:
                frame = cv2.resize(frame, resolutions[i])
                out.write(frame)
        out.release()

    cap.release()
    cv2.destroyAllWindows()

def generate_video_chunks():
    for video_file in video_files:
        cut_video(video_file)

def main():
    print("Setting up server...")
    populate_videos_list()
    generate_video_chunks()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(20)
    print(f"Server is now up and running on port {SERVER_PORT}")
    while True:
        client_socket, addr = server_socket.accept()

        client_thread = threading.Thread(target=handle_client, args=(client_socket, addr))
        client_thread.start()

if __name__ == "__main__":
    main()