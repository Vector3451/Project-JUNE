# Project JUNE

**Project JUNE** is a sophisticated, locally-hosted AI assistant designed for privacy, real-time voice interaction, and network security operations. It combines the power of local LLMs (Ollama) with a custom RAG (Retrieval-Augmented Generation) system and specialized network tools.

## 🚀 Key Features

*   **🎙️ Voice-First Interaction**: Integration with **Whisper (Faster-Whisper)** for lightning-fast Speech-to-Text and **Coqui TTS** for natural-sounding responses.
*   **🧠 Dual Persona**:
    *   **June**: Your friendly, witty general assistant. Capable of searching the web, checking the weather, and answering general queries with context-aware memory.
    *   **NetJune**: A specialized security agent equipped with Kali Linux tools. Can execute network scans (`nmap`), check for vulnerabilities (`nmap`), and assist with cybersecurity tasks.
*   **📚 Custom RAG System**: Ingests local documents and learns from user interactions using **ChromaDB** and **SentenceTransformers**.
*   **🌐 Web Interface**: A modern, dark-themed Flask web app with real-time streaming responses and WebSocket support.
*   **🔌 Hardware Integration**: Designed to run on a powerful PC server with a lightweight Raspberry Pi client for voice I/O.
*   **🔒 Privacy Focused**: All processing (LLM, STT, TTS, RAG) happens locally on your machine.

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

