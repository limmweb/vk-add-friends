import vk_api
import time
import threading
import os
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

tokens_file = 'tokens.txt'
running = True
executor = None

def current_time():
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")

def read_tokens(file):
    try:
        print(f"{current_time()} - Attempting to read tokens from {file}")
        if os.path.exists(file):
            with open(file, 'r') as f:
                tokens = [line.strip() for line in f.readlines() if line.strip()]
                print(f"{current_time()} - Found {len(tokens)} tokens.")
                return tokens
        else:
            print(f"{current_time()} - File not found: {file}")
            return []
    except Exception as e:
        print(f"{current_time()} - Failed to read tokens from file: {e}")
        return []

def get_user_info(vk):
    try:
        user_info = vk.users.get()[0]
        return user_info['id'], user_info['first_name']
    except vk_api.exceptions.ApiError as e:
        print(f"{current_time()} - An error occurred while getting user info: {e}")
        return None, None

def set_online_status(vk):
    while running:
        try:
            vk.account.setOnline()
            print(f"{current_time()} - Set online status.")
        except vk_api.exceptions.ApiError as e:
            print(f"{current_time()} - An error occurred while setting online status: {e}")
        time.sleep(300)  # Sleep for 5 minutes

def accept_friend_requests(vk, user_id, user_name):
    while running:
        try:
            requests = vk.friends.getRequests(out=0)
            if len(requests['items']) == 0:
                print(f"{current_time()} - No more incoming friend requests for {user_name} ({user_id}).")
            else:
                print(f"{current_time()} - Found {len(requests['items'])} incoming friend requests for {user_name} ({user_id}).")

                for request_user_id in requests['items']:
                    try:
                        user_info = vk.users.get(user_ids=request_user_id)
                        if 'deactivated' not in user_info[0]:
                            vk.friends.add(user_id=request_user_id)
                            print(f"{current_time()} - Accepted friend request from user {request_user_id} for {user_name} ({user_id}).")
                        else:
                            vk.friends.delete(user_id=request_user_id)
                            print(f"{current_time()} - Rejected friend request from deactivated user {request_user_id} for {user_name} ({user_id}).")
                    except vk_api.exceptions.ApiError as e:
                        if e.code == 177:
                            print(f"{current_time()} - Skipped request from user {request_user_id} as user not found for {user_name} ({user_id}).")
                            vk.friends.delete(user_id=request_user_id)
                        else:
                            print(f"{current_time()} - An error occurred while accepting: {e}")
                            vk.friends.delete(user_id=request_user_id)
                            print(f"{current_time()} - Rejected friend request from user {request_user_id} for {user_name} ({user_id}).")
                    time.sleep(0.3)  # Delay of 0.3 seconds
        except vk_api.exceptions.ApiError as e:
            print(f"{current_time()} - An error occurred for {user_name} ({user_id}): {e}")
        
        time.sleep(300)  # Sleep for 5 minutes before checking again

def send_friend_requests(vk, user_id, user_name):
    while running:
        try:
            suggestions = vk.friends.getSuggestions(filter='mutual')
            if not suggestions['items']:
                print(f"{current_time()} - No friend suggestions available for {user_name} ({user_id}).")
            else:
                for suggestion in suggestions['items']:
                    try:
                        vk.friends.add(user_id=suggestion['id'])
                        print(f"{current_time()} - Sent friend request to user {suggestion['id']} for {user_name} ({user_id}).")
                        time.sleep(0.3)  # Delay of 0.3 seconds
                    except vk_api.exceptions.ApiError as e:
                        if e.code in (1, 2, 4, 5, 6, 9, 10, 14, 15):
                            print(f"{current_time()} - Friend request error for {user_name} ({user_id}): {e}")
                            time.sleep(10300)  # Sleep for 30 minutes on error
                            continue

        except vk_api.exceptions.ApiError as e:
            print(f"{current_time()} - An error occurred for {user_name} ({user_id}): {e}")
            time.sleep(10300)  # Sleep for 30 minutes on error
            continue

def account_operations(token):
    try:
        vk_session = vk_api.VkApi(token=token)
        vk = vk_session.get_api()

        user_id, user_name = get_user_info(vk)
        if not user_id or not user_name:
            print(f"{current_time()} - Failed to get user info for token: {token}")
            return

        print(f"{current_time()} - Starting operations for {user_name} ({user_id})")

        threads = [
            threading.Thread(target=set_online_status, args=(vk,)),
            threading.Thread(target=accept_friend_requests, args=(vk, user_id, user_name)),
            threading.Thread(target=send_friend_requests, args=(vk, user_id, user_name))
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

    except vk_api.exceptions.ApiError as e:
        print(f"{current_time()} - An error occurred with token {token}: {e}")

def monitor_tokens():
    tokens = read_tokens(tokens_file)
    for token in tokens:
        print(f"{current_time()} - Starting operations for token: {token}")
        executor.submit(account_operations, token)

def signal_handler(sig, frame):
    global running
    print(f"{current_time()} - Termination signal received. Exiting gracefully...")
    running = False
    executor.shutdown(wait=True)
    sys.exit(0)

if __name__ == "__main__":
    print(f"{current_time()} - Current working directory: {os.getcwd()}")
    print(f"{current_time()} - Checking for tokens file at: {os.path.abspath(tokens_file)}")

    if not os.path.exists(tokens_file):
        print(f"{current_time()} - tokens.txt not found in the current directory: {os.getcwd()}")
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    with ThreadPoolExecutor(max_workers=10) as exec:
        executor = exec
        monitor_tokens_thread = threading.Thread(target=monitor_tokens)
        monitor_tokens_thread.start()
        monitor_tokens_thread.join()
