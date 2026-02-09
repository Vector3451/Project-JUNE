import paramiko
import json
import os
import socket


class SSHClient:
    """
    Secure SSH wrapper for connecting to the Kali VM.

    Features:
        - run(command: str) -> str
        - test_connection() -> bool
        - get_file(remote_path, local_path)  (added)
        - Supports long-running commands cleanly
        - Clean output, no prints
    """

    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "config.json")

        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"config.json not found at expected path: {config_path}\n"
                "Make sure it exists in the Network/ folder."
            )

        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
        except json.JSONDecodeError:
            raise ValueError(
                f"config.json is not valid JSON.\nCheck: {config_path}"
            )

        required = ["kali_host", "kali_user", "ssh_port"]
        for param in required:
            if param not in cfg:
                raise KeyError(
                    f"Missing '{param}' in config.json. Required fields: {required}"
                )

        self.host = cfg["kali_host"]
        self.user = cfg["kali_user"]
        self.port = cfg["ssh_port"]

        self.password = cfg.get("kali_password")
        self.ssh_key_path = cfg.get("ssh_key_path")

        self.client = None
        
        # Circuit breaker settings
        self.failure_count = 0
        self.MAX_FAILURES = 3

    # ----------------------------------------
    # Internal: connect safely
    # ----------------------------------------
    def _connect(self):
        # 1. Check circuit breaker
        if self.failure_count >= self.MAX_FAILURES:
             raise ConnectionAbortedError(
                 f"[SSH BLOCKED] Too many failed attempts ({self.failure_count}). "
                 "The VM appears to be offline. Please start it and restart the agent to try again."
             )

        if self.client:
            return

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            if self.ssh_key_path:
                pkey = paramiko.RSAKey.from_private_key_file(self.ssh_key_path)
                self.client.connect(
                    self.host,
                    port=self.port,
                    username=self.user,
                    pkey=pkey,
                    timeout=12,
                )
            else:
                self.client.connect(
                    self.host,
                    port=self.port,
                    username=self.user,
                    password=self.password,
                    timeout=12,
                )
            
            # Connection successful -> Reset counter
            self.failure_count = 0

        except socket.timeout:
            self.failure_count += 1
            raise TimeoutError(
                f"[SSH ERROR] Connection to {self.host}:{self.port} timed out. "
                f"(Attempt {self.failure_count}/{self.MAX_FAILURES})"
            )
        except paramiko.ssh_exception.NoValidConnectionsError:
            self.failure_count += 1
            raise ConnectionError(
                f"[SSH ERROR] Unable to reach {self.host}:{self.port}. "
                f"(Attempt {self.failure_count}/{self.MAX_FAILURES})"
            )
        except paramiko.AuthenticationException:
            # Authentication failure might not mean the host is down, but likely configuration error.
            # We count it as failure to prevent spamming bad auth.
            self.failure_count += 1
            raise PermissionError(
                "[SSH ERROR] Authentication failed."
            )
        except Exception as e:
            self.failure_count += 1
            raise Exception(f"[SSH ERROR] SSH connection failed: {e}")

    # ----------------------------------------
    # Internal: disconnect
    # ----------------------------------------
    def _disconnect(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = None

    # ----------------------------------------
    # PUBLIC: Execute shell commands
    # ----------------------------------------
    def run(self, command: str) -> str:
        """
        Execute a shell command on Kali and return all output.
        Handles:
            - multiline / chained commands
            - large stdout (Metasploit, SQLMap)
            - stderr merging
        """
        if not isinstance(command, str) or not command.strip():
            return "[ERROR] Invalid command."

        try:
            self._connect()
        except Exception as e:
            return str(e)

        try:
            stdin, stdout, stderr = self.client.exec_command(
                command, get_pty=False
            )

            out = stdout.read().decode(errors="ignore")
            err = stderr.read().decode(errors="ignore")

            self._disconnect()

            if not out.strip() and not err.strip():
                return "[NO OUTPUT]"

            if out and err:
                return out.strip() + "\n\n[ERROR]\n" + err.strip()
            if out:
                return out.strip()
            return "[ERROR]\n" + err.strip()

        except Exception as e:
            self._disconnect()
            return f"[SSH ERROR] Failed to run command: {e}"

    # ----------------------------------------
    # PUBLIC: download files (pcap, loot, etc.)
    # ----------------------------------------
    def get_file(self, remote_path: str, local_path: str) -> str:
        """
        Download a file from the Kali VM.

        Useful for:
            - tshark .pcap output
            - loot files
            - captured credentials
        """
        try:
            self._connect()
            sftp = self.client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            self._disconnect()
            return "OK"
        except Exception as e:
            self._disconnect()
            return f"[SSH ERROR] Failed to download file: {e}"

    # ----------------------------------------
    # Test SSH connectivity
    # ----------------------------------------
    def test_connection(self) -> bool:
        try:
            self._connect()
            stdin, stdout, stderr = self.client.exec_command("echo OK")
            result = stdout.read().decode().strip()
            self._disconnect()
            return result == "OK"
        except Exception:
            return False