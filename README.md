# Project JUNE

**Project JUNE** is a sophisticated, locally-hosted AI assistant designed for privacy, real-time voice interaction, and network security operations. It combines the power of local LLMs (Ollama) with a custom RAG (Retrieval-Augmented Generation) system and specialized network tools.

🏗️ Core System

### 1. `web_app.py`
**Role**: The main entry point and HTTP/WebSocket server.
*   **Framework**: Flask + Flask-SocketIO.
*   **Key Functions**:
    *   `index()`: Renders the chat interface (`chat.html`).
    *   `chat()`: Primary API endpoint. Receives user text, classifies intent (using `intent_classifier`), and routes to either **June** (Standard Agent) or **NetJune** (Network Agent).
    *   `stream_chat_api()`: A generator-based endpoint that yields tokens in real-time. Used by the Raspberry Pi client.
    *   `voice_input()`: Handles audio file uploads, runs `faster-whisper` for STT, and returns transcription.
    *   `handle_connect()`: Manages WebSocket connections.
*   **Dependencies**: `Assistant.py`, `network_ai.py`, `Learning.intent_classifier`.

### 2. `Assistant.py`
**Role**: The brain of the "Standard" persona (June).
*   **Features**:
    *   **RAG (Retrieval-Augmented Generation)**: Uses `ChromaDB` and `SentenceTransformer` to store/retrieve local documents.
    *   **Voice I/O**:
        *   `speak_text()` / `speak_async()`: Uses **Coqui TTS** (VITS model) to generate speech.
        *   `listen_once()`: Records audio via `sounddevice` and detects voice activity (VAD).
    *   **Tool Execution**: `execute_tool()` handles local tools like `get_news`, `organize_files`, etc.
    *   **Ollama Integration**: communicate with local LLMs (Llama 3, Mistral).

---

## 🛡️ Network Intelligence Module (`Network/`)

### 3. `network_ai.py`
**Role**: The "NetJune" Persona logic.
*   **System Prompt**: Enforces a "Hacker" persona that outputs Bash commands inside markdown blocks.
*   **RAG**: Has a separate `network_knowledge` collection in ChromaDB for security-specific documents.
*   **Command Parsing**: `_extract_command_block()` parses the LLM output to find bash commands.
*   **Execution**: Sends parsed commands to `execute_network_tool()`.

### 4. `Network/ssh_client.py`
**Role**: A robust SSH wrapper for the Kali Linux VM.
*   **Class**: `SSHClient`
    *   **Circuit Breaker**: Stops trying to connect after `MAX_FAILURES` to prevent hanging the UI.
    *   **`run(command)`**: Executes command via SSH, handles stdout/stderr, and strips ANSI codes if needed.
    *   **`get_file()`**: SFTP downloader for retrieving loot/pcaps from the VM.
*   **Config**: Loads credentials from `Network/config.json`.

### 5. `Network/tool_gateway.py`
**Role**: Router/Firewall for network tools.
*   **Legacy Support**: Converts old JSON tool calls to direct string commands.
*   **Safety**: Basic blocklist (e.g., `rm -rf`, `reboot`) to prevent accidental destruction.

### 6. `kali_ssh.py`
**Role**: Lightweight SSH utility.
*   **Status**: Legacy/Simple script. Mostly superseded by `SSHClient` but useful for quick tests.

---

## 🧠 Learning & Safety Module (`Learning/`)

### 7. `Learning/intent_classifier.py`
**Role**: Router for user messages.
*   **Logic**: Uses keyword matching (heuristic) to classify messages into:
    *   `'system'` (Open app, draw, organize)
    *   `'coding'` (Write python, exploit, etc.)
    *   `'chat'` (General conversation)
    *   `'network'` (Hacking tasks - usually triggered by mode switch)

### 8. `Learning/tool_registry.py`
**Role**: Manages dynamic tool discovery and acquisition from GitHub.
*   **GitHub Integration**:
    *   `search_github_repos()`: Searches GitHub for repositories matching a task description (e.g., "python tool for weather").
    *   `github_acquire_tools()`: Clones a selected repository and scans it for compatible tools.
*   **Sandbox Safety**:
    *   `scan_file_for_risk()`: Regex scan for dangerous imports (`os.system`, `subprocess`) in downloaded tools.
    *   `discover_tools()`: Finds `tool_*.py` files in cloned repos.
    *   `run_tool()`: Spawns a **separate subprocess** using `safe_runner.py`.

### 9. `Learning/safe_runner.py`
**Role**: The Sandbox Environment.
*   **Mechanism**:
    *   Runs as a standalone script.
    *   **Stripped Globals**: Removes `open`, `exec`, `eval`, `import` from builtins.
    *   **Blocked Modules**: Prevents importing `os`, `sys`, `socket` inside the tool (unless whitelisted).
    *   **JSON IPC**: Communicates input/output via JSON string arguments only.

### 10. `Learning/memory_manager.py`
**Role**: Long-term memory storage.
*   **Class**: `MemoryManager`
    *   **Embeddings**: `all-MiniLM-L6-v2` (Fast, CPU-friendly).
    *   **Storage**: ChromaDB (`memory_store/` directory).
    *   **Methods**: `add_memory()`, `get_relevant_context()`.

---

## 📡 IoT Integration (Raspberry Pi)

### 11. `pi_client.py` (Runs on Pi)
**Role**: The lightweight terminal interface.
*   **Discovery**: Broadcasts `IAM:JUNE_PI_CLIENT` via UDP so the server finds it.
*   **I/O**: Accepts text input, sends to `API_ENDPOINT`, and streams the response text.
*   **Mode Switching**: Can switch the main server between "Standard" and "Network" modes remotely.

### 12. `pi_controller.py` (Runs on Server)
**Role**: Server-side handler for the Pi.
*   **Listener**: Background thread listens for UDP broadcasts to track the Pi's IP.
*   **`send_text_to_pi`**: Push notifications/alerts to the Pi's wall/terminal via SSH.

---

## 🔧 Utilities

### 13. `userpass_generator.py`
**Role**: Advanced password list generator.
*   **Features**:
    *   **GAN Noise**: Simulates random patterns.
    *   **Markov Chains**: Generates human-like pronounceable words.
    *   **Leetspeak**: Intelligent substitution (`e` -> `3`, `a` -> `@`).
    *   **Personal Info Mutation**: Mixes user details (name, birthdate) into password lists. Used for generating custom wordlists for Hydra interactions.

### 14. `ability_spec.json`
**Role**: Template schema for defining tool capabilities when importing from external sources.

---

## 🛠️ Architecture

*   **Backend**: Python (Flask, SocketIO)
*   **LLM Provider**: Ollama (supports Llama 3, Mistral, Qwen, etc.)
*   **Vector Database**: ChromaDB
*   **Speech Processing**: `faster-whisper` (STT) & `TTS` (Text-to-Speech)
*   **Network Intelligence**: Custom `NetworkAgent` with bash command execution capabilities.

## 📦 Installation

### Prerequisites
*   Python 3.10+
*   [Ollama](https://ollama.com/) running locally.
*   CUDA-enabled GPU (Highly recommended for TTS/STT performance).
*   `ffmpeg` installed and added to system PATH.

### Setup

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/Vector3451/Project-JUNE.git
    cd Project-JUNE
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Download Models**
    *   **Ollama**: Pull your preferred models (e.g., `ollama pull llama3`, `ollama pull qwen2.5-coder`).
    *   **NLTK Data**: The script will automatically download necessary NLTK data on first run.

## 🚀 Usage

### Starting the Server
Run the main web application:
```bash
python web_app.py
```
Open your browser and navigate to `http://localhost:5000`.

### Voice Mode
*   Click the **Mic** button in the UI or use the wake word (if configured) to speak to June.
*   The system will transcribe your speech and respond verbally.

### Network Mode (NetJune)
*   Ask June to "switch to network mode" or specifically ask for a network task (e.g., "Scan the network for open ports").
*   **⚠️ Disclaimer**: The network tools are powerful. Ensure you have permission to scan/test any network you target. This tool is for educational and authorized testing purposes only.

## 📂 Project Structure

*   `web_app.py`: Main Flask application entry point.
*   `Assistant.py`: Core logic for the main AI assistant (RAG, Voice, Tools).
*   `network_ai.py`: Specialized agent for network operations and security tools.
*   `templates/`: HTML templates for the web interface.
*   `static/`: CSS, JS, and assets.
*   `memory_store/`: Persistent storage for RAG and conversation history.

