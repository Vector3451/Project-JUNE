import paramiko

KALI_HOST = "127.0.0.1"
KALI_USER = "kali"
KALI_PASS = "fivenine"


def run_kali_command(command: str) -> str:
    """
    SSH into Kali VM and run the given command.
    Returns full raw terminal output exactly as Kali prints it.
    """
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            KALI_HOST,
            username=KALI_USER,
            password=KALI_PASS,
            port=2222,
            timeout=10
        )

        stdin, stdout, stderr = client.exec_command(command)

        out = stdout.read().decode(errors="ignore")
        err = stderr.read().decode(errors="ignore")

        client.close()

        return (out + "\n" + err).strip()

    except Exception as e:
        return f"[SSH ERROR] {str(e)}"