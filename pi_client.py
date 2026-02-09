import requests
import json
import sys
import time
import socket
import threading

# CONFIGURATION
# Replace this with your Windows PC's IP address (Static for now, or use broadcasting later)
SERVER_URL = "http://192.168.1.7:5000"  
API_ENDPOINT = f"{SERVER_URL}/api/chat/stream" # [UPDATED] Streaming endpoint
NETWORK_ENDPOINT = f"{SERVER_URL}/api/network"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def broadcast_presence():
    """Sends UDP broadcast so the Server knows our IP"""
    udp_ip = "<broadcast>"
    udp_port = 5005
    message = "IAM:JUNE_PI_CLIENT"
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    print(f"{YELLOW}[Discovery] Broadcasting presence to network...{RESET}")
    
    while True:
        try:
            sock.sendto(message.encode(), (udp_ip, udp_port))
            time.sleep(10) # Broadcast every 10 seconds
        except Exception as e:
            # print(f"Broadcast error: {e}")
            time.sleep(5)

# Start broadcaster in background
t = threading.Thread(target=broadcast_presence, daemon=True)
t.start()

def main():
    print(f"{BLUE}========================================")
    print(f"   JUNE AI TERMINAL CLIENT (RASPBERRY PI)")
    print(f"   Connected to: {SERVER_URL}")
    print(f"========================================{RESET}")

    # Check connection first
    try:
        # Check standard endpoint status
        requests.get(f"{SERVER_URL}/", timeout=2) 
        print(f"{GREEN}[+] Connection successful!{RESET}\n")
    except Exception as e:
        print(f"{RED}[-] Could not connect to server at {SERVER_URL}")
        print(f"    Error: {e}{RESET}")
        print(f"{YELLOW}    Make sure 'web_app.py' is running on your PC and firewall allows port 5000.{RESET}")
        return

    mode = "standard" # standard | network

    while True:
        try:
            # 1. Get User Input
            if mode == "network":
                prompt = f"{RED}root@NetJune:~#{RESET} "
            else:
                prompt = f"{GREEN}You:{RESET} "
            
            user_input = input(prompt).strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            # Local mode switching (mirroring server logic for UI)
            if user_input.lower() == "enter hacker mode":
                mode = "network"
                print(f"{RED}[!] HACKER MODE ACTIVATE{RESET}")
                continue
            if user_input.lower() == "exit hacker mode" and mode == "network":
                mode = "standard"
                print(f"{GREEN}[*] Returning to Standard Mode{RESET}")
                continue

            # 2. Send to Server
            payload = {"message": user_input}
            target_url = NETWORK_ENDPOINT if mode == "network" else API_ENDPOINT
            
            # Simple spinner
            sys.stdout.write(f"{YELLOW}Thinking...{RESET}\r")
            sys.stdout.flush()

            # STREAMING REQUEST
            try:
                response = requests.post(target_url, json=payload, stream=True, timeout=60)
                
                # Clear spinner matches the length of "Thinking..."
                sys.stdout.write("           \r") 
                
                if response.status_code == 200:
                    print(f"{BLUE}June:{RESET} ", end="")
                    
                    # Iterate over chunks
                    # Note: API now returns raw text stream, NOT JSON
                    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                        if chunk:
                            sys.stdout.write(chunk)
                            sys.stdout.flush()
                    print() # Newline at end
                    print("-" * 40)
                else:
                    print(f"\n{RED}[Error {response.status_code}]: {response.text}{RESET}")

            except requests.exceptions.Timeout:
                print(f"\n{RED}[Error]: Request timed out.{RESET}")
            except Exception as e:
                print(f"\n{RED}[Error]: {e}{RESET}")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n{RED}[Error]: {e}{RESET}")

if __name__ == "__main__":
    main()
