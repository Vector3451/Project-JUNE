# Network/tool_gateway.py
# Central router for all network tools.
# Now strictly uses Docker to sandbox and execute Kali commands.

import subprocess

TERMINAL_OPENED = False

def execute_network_tool(input_data):
    """
    Receives either:
    1. A raw command string (e.g. "nmap -sV localhost") -> Executes via Docker.
    2. A legacy JSON object (e.g. {"tool": "nmap" ...}) -> Warning or basic conversion.

    Returns the raw output from the Docker container.
    """

    # 1. Direct Command Mode (Preferred)
    if isinstance(input_data, str):
        cmd = input_data.strip()
        
        # Basic Safety Blocklist
        blocked = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:", "shutdown", "reboot"]
        if any(b in cmd for b in blocked):
            return f"[SECURITY BLOCK] Command '{cmd}' contains dangerous patterns and was blocked."

        daemon_name = "june-kali-daemon"

        if cmd == "READ_TERMINAL":
            try:
                output = subprocess.check_output(["docker", "exec", daemon_name, "tmux", "capture-pane", "-pt", "netjune"], text=True)
                return output.strip()
            except subprocess.CalledProcessError:
                return "[ERROR] Could not read terminal. Is the tmux session active?"

        try:
            # 1. Ensure the persistent daemon container is running
            daemon_name = "june-kali-daemon"
            check_running = subprocess.run(["docker", "ps", "-q", "-f", f"name={daemon_name}"], capture_output=True, text=True)
            
            if not check_running.stdout.strip():
                # Clean up any stopped container first
                subprocess.run(["docker", "rm", "-f", daemon_name], capture_output=True)
                
                # Start persistent container
                subprocess.run([
                    "docker", "run", "-d", "-it", "--name", daemon_name,
                    "--network", "host", "--privileged",
                    "-v", "D:/College/AI Assistant/vpns:/vpns",
                    "june-kali-runner", "bash"
                ], check=True)
            
            # 2. Ensure TMUX session exists
            check_tmux = subprocess.run(["docker", "exec", daemon_name, "tmux", "has-session", "-t", "netjune"], capture_output=True)
            if check_tmux.returncode != 0:
                subprocess.run(["docker", "exec", daemon_name, "tmux", "new-session", "-d", "-s", "netjune"], check=True)
            
            global TERMINAL_OPENED
            if not TERMINAL_OPENED:
                # Open a standalone Command Prompt attached to the TMUX session exactly once per server run
                try:
                    subprocess.Popen(
                        'start "NetJune Terminal" cmd /c "docker exec -it june-kali-daemon tmux attach -t netjune"', 
                        shell=True
                    )
                    TERMINAL_OPENED = True
                except Exception as e:
                    pass # Ignore if it fails

            # 3. Send the command to the TMUX session
            # We add a clear command first so the screen is clean for the new tool
            subprocess.run([
                "docker", "exec", daemon_name, 
                "tmux", "send-keys", "-t", "netjune", "clear", "C-m"
            ], check=True)
            
            subprocess.run([
                "docker", "exec", daemon_name, 
                "tmux", "send-keys", "-t", "netjune", cmd, "C-m"
            ], check=True)

            return f"[COMMAND DISPATCHED] The command '{cmd}' is now running in your native Windows Terminal tab. Please check the terminal for live output."

        except subprocess.CalledProcessError as e:
            return f"[EXECUTION ERROR] Docker operation failed: {e.output if hasattr(e, 'output') else e}"
        except Exception as e:
            return f"[EXECUTION ERROR] {e}"

    # 2. Legacy JSON Fallback (if model reverts to JSON)
    elif isinstance(input_data, dict):
        tool = input_data.get("tool")
        if "custom_cmd" in input_data:
            return execute_network_tool(input_data["custom_cmd"])
        return f"[LEGACY ERROR] JSON mode is deprecated. Please request the agent to use Direct Command mode."

    else:
        return "[ERROR] Invalid input format for tool execution."
