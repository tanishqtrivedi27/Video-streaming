from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import cv2
import os
import pickle
import queue
import socket
import struct
import threading

SERVER_HOST = socket.gethostname()
SERVER_PORT = 9999

client_dict = {} ### dictionary containing public keys
message_queue = queue.Queue()

# handles dict updates and incoming messages from server
def receive_messages():
    global client_dict
    while True:
        try:
            message = server_socket.recv(256 * 1024)
            if message.startswith(b"UPDATED_DICT"):
                message = message.decode().split(" ", 1)[1]
                updated_dict = eval(message)
                client_dict = updated_dict  # Update local dictionary
            elif message.startswith(b"ENCRYPTED_MESSAGE"):
                message = message.decode().split(" ", 2)
                sender = message[1]
                received_message = message[2]
                decrypt_message(received_message, sender)
            else:
                message_queue.put(message)
        except Exception as e:
            print(f"Error while receiving message {e}")
            break

def send_message(message):
    server_socket.send(message.encode())

def generateRSA():
    key = RSA.generate(2048)

    public_key = key.publickey().export_key()
    private_key = key.export_key()

    private_cipher = PKCS1_OAEP.new(RSA.import_key(private_key))

    return public_key, private_cipher

def decrypt_message(ciphertext, sender):
    global private_cipher
    ciphertext = bytes.fromhex(ciphertext)
    try:
        decrypted_message = private_cipher.decrypt(ciphertext).decode()
        print(f"\nRECEIVED MESSAGE FROM {sender}:  {decrypted_message}") ### Q2b
    except ValueError: # message not for this client
        pass

def encrpyt_message(message, public_key):
    public_key = bytes.fromhex(public_key)
    public_cipher = PKCS1_OAEP.new(RSA.import_key(public_key))
    ciphertext = public_cipher.encrypt(message.encode())
    ciphertext = ciphertext.hex()
    return ciphertext

def stream_video():
    data = b""
    payload_size = struct.calcsize("Q")
    try:
        while True:
            while len(data) < payload_size:
                packet = message_queue.get(timeout=1)
                if not packet: 
                    break
                data += packet
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("Q", packed_msg_size)[0]
            
            while len(data) < msg_size:
                data += message_queue.get(timeout=1)
            frame_data = data[:msg_size]
            data  = data[msg_size:]
            frame = pickle.loads(frame_data)
            cv2.imshow("Streaming Video", frame)
            cv2.waitKey(1)
    except queue.Empty:
        pass          
    except Exception as e:
        print(f"Error while streaming video: {e}")
    finally:
        cv2.destroyAllWindows()

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.connect((SERVER_HOST, SERVER_PORT)) ### Q1a

# name w/o spaces
client_name = input("Enter your name (w/o spaces): ")

public_key, private_cipher = generateRSA()

send_message(f"CONNECT {client_name} {public_key.hex()}") ### Q1b

receive_thread = threading.Thread(target=receive_messages)
receive_thread.start()

while True:
    command = input("Enter command (LIST_VIDEOS, MESSAGE, QUIT): ")
    
    if command == "LIST_VIDEOS": ### Q3
        send_message("LIST_VIDEOS")
        video_list = message_queue.get(timeout=1)
        video_list = eval(video_list.decode())
        print("Available videos:")
        for idx, video_name in enumerate(video_list):
            print(f"{idx}: {video_name}")

        while True:
            selection = input("Enter video number (index starting from 0): ")
            if not selection.isdigit():
                print("Invalid input. Please enter a number.")
                continue
            selection = int(selection)
            if 0 <= selection < len(video_list):
                break
            else:
                print("Index should be between 0 and", len(video_list) - 1)
            
        send_message(f"VIDEO_SELECTION {selection}")

        stream_video()
    elif command == "MESSAGE":
        if (len(client_dict.keys()) == 1):
            print("No other clients are connected.")
            continue

        print(f"OTHER CONNECTED CLIENTS: {[c_name for c_name in client_dict.keys() if c_name != client_name]}")

        recipient = input("Enter recipient name: ")
        message_content = input("Enter message: ")
        try:
            encrpyted_message = encrpyt_message(message_content, client_dict[recipient]) ### Q2a
            send_message(f"MESSAGE {client_name} {encrpyted_message}")
        except KeyError:
            print(f"Recipient {recipient} not found in CLIENT_DICT")
    elif command == "QUIT":
        # Disconnect from server
        send_message("QUIT")
        os._exit(os.EX_OK)
    else:
        print("Invalid command")
