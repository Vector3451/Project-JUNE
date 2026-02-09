# Network/tool_gateway.py
# Central router for all network tools.
# Now simplified to handle Direct Command Strings along with legacy JSON support.

from .ssh_client import SSHClient

ssh = SSHClient()

def execute_network_tool(input_data):
    """
    Receives either:
    1. A raw command string (e.g. "nmap -sV localhost") -> Executes directly.
    2. A legacy JSON object (e.g. {"tool": "nmap" ...}) -> Warning or basic conversion.

    Returns the raw output from the SSH client.
    """

    # 1. Direct Command Mode (Preferred)
    if isinstance(input_data, str):
        cmd = input_data.strip()
        
        # Basic Safety Blocklist
        blocked = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:", "shutdown", "reboot"]
        if any(b in cmd for b in blocked):
            return f"[SECURITY BLOCK] Command '{cmd}' contains dangerous patterns and was blocked."

        try:
            output = ssh.run(cmd)
            return output
        except Exception as e:
            return f"[EXECUTION ERROR] {e}"

    # 2. Legacy JSON Fallback (if model reverts to JSON)
    elif isinstance(input_data, dict):
        tool = input_data.get("tool")
        # Attempt to reconstruct a basic command if possible, or error out.
        # Since we refactored network_ai to ask for bash blocks, this shouldn't happen often.
        if "custom_cmd" in input_data:
            return execute_network_tool(input_data["custom_cmd"])
        
        return f"[LEGACY ERROR] JSON mode is deprecated. Please request the agent to use Direct Command mode."

    else:
        return "[ERROR] Invalid input format for tool execution."
