import paramiko
import time
import socket
import threading

# CONFIGURATION
# Default fallbacks
PI_USER = "pi"
PI_PASS = "raspberry"
PI_PORT = 22

# Dynamic IP Storage
current_pi_ip = "192.168.1.2" # Default / Last known
ip_lock = threading.Lock()

def listen_for_pi_broadcasts():
    """Background thread to listen for Pi announcements"""
    global current_pi_ip
    udp_port = 5005
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', udp_port))
    sock.settimeout(None)
    
    print(f"[Discovery] Listening for Pi on UDP {udp_port}...")
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = data.decode('utf-8')
            if message == "IAM:JUNE_PI_CLIENT":
                new_ip = addr[0]
                with ip_lock:
                    if new_ip != current_pi_ip:
                        print(f"[Discovery] Found Pi at {new_ip}!")
                        current_pi_ip = new_ip
        except Exception as e:
            time.sleep(1)

# Start listener immediately when module is imported
t = threading.Thread(target=listen_for_pi_broadcasts, daemon=True)
t.start()

def send_text_to_pi(text: str, target_tty="wall"):
    """
    Sends text to the Raspberry Pi's terminal via SSH.
    """
    global current_pi_ip
    
    with ip_lock:
        target_host = current_pi_ip

    if not target_host:
        return "Error: Pi IP not found yet."

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(
            target_host,
            username=PI_USER,
            password=PI_PASS,
            port=PI_PORT,
            timeout=5
        )
        
        # Clean the text for bash safety (basic)
        safe_text = text.replace("'", "'\\''")
        
        if target_tty == "wall":
            # Wall sends to all logged in users
            command = f"echo '{safe_text}' | wall"
        else:
            command = f"echo '{safe_text}' > {target_tty}"

        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status != 0:
            err = stderr.read().decode().strip()
            return f"Error sending to Pi ({target_host}): {err}"
            
        return f"Message sent to Pi ({target_host}) successfully."
        
    except Exception as e:
        return f"Connection failed to {target_host}: {str(e)}"
    finally:
        client.close()

if __name__ == "__main__":
    print("Testing connection to Pi...")
    # Give listener a moment in case Pi is spamming right now
    time.sleep(1) 
    msg = "System initialized. Hello from Windows!"
    result = send_text_to_pi(msg)
    print(result)
