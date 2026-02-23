
from Learning.intent_classifier import classify_intent
from Learning.agent_context import AGENT_CONTEXT
from network_ai import run_network_agent
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_socketio import SocketIO, emit
import requests
import threading
import json
from datetime import datetime
import os
import tempfile
import re
from Assistant import (
    execute_tool,
    speak_async,
    set_voice_enabled,
    is_voice_enabled,
    initialize_assistant,
    listen_once,
    transcribe_file,
    ask_ollama_chat,
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'june_ai_assistant_secret'
# Increase ping interval to reduce "looping" feeling and increase timeout for stability
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)
voice_enabled_global = True
ACTIVE_MODE = "standard" # "standard" | "network"

@app.route('/')
def index():
    """Main chat interface"""
    return render_template('chat.html')

def extract_tool_call(text: str):
    """
    Scans text for the first valid JSON object containing a "tool" key.
    Returns (natural_text, tool_name, tool_args).
    """
    if not isinstance(text, str) or not text.strip():
        return text, None, None

    # Find all opening braces
    start_indices = [m.start() for m in re.finditer(r'\{', text)]
    
    for start in start_indices:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{': 
                depth += 1
            elif text[i] == '}': 
                depth -= 1
            
            if depth == 0:
                # We have a balanced block [start : i+1]
                candidate = text[start : i+1]
                
                # Check if it looks like a tool call before heavy parsing
                if '"tool"' in candidate or "'tool'" in candidate:
                    try:
                        # Attempt parse
                        obj = json.loads(candidate)
                        if isinstance(obj, dict) and "tool" in obj:
                            # FOUND VALID TOOL CALL
                            # Return text BEFORE the block as the user-facing message
                            natural_text = text[:start].strip()
                            
                            # Clean up potential markdown wrapper around the text if present
                            # e.g. "```json" at the end of natural_text
                            natural_text = re.sub(r'```\w*\s*$', '', natural_text).strip()
                            
                            return natural_text, obj.get("tool"), obj.get("args", {})
                    except json.JSONDecodeError:
                        pass
                # Once we hit depth 0, this block is done. 
                # If it wasn't valid JSON, no bigger block starting at 'start' will work.
                break

    return text, None, None


@app.route('/api/network', methods=['POST'])
def network_chat():
    """
    Dedicated endpoint for network operations.
    Uses the separate NetJune agent and returns RAW tool output.
    """
    try:
        data = request.json or {}
        user_message = (data.get("message") or "").strip()
        model = data.get("model", "jimscard/whiterabbit-neo:13b")

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        result = run_network_agent(user_message, model=model)

        return jsonify({
            "response": result,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({"error": f"Network agent error: {e}"}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Multi-agent conversational endpoint.
    Uses intent classification + agent memory to route:

    - June → normal chat + system tools
    - NetJune → real network actions
    """
    try:
        data = request.json or {}
        user_message = (data.get("message") or "").strip()
        model = data.get("model", "june:latest")

        if not user_message:
            return jsonify({"error": "Empty message"}), 400

        intent = classify_intent(user_message)
        AGENT_CONTEXT["last_intent"] = intent


        # 2. CODING (Direct Bypass)
        if intent == "coding":
            # Direct routing to Coder to avoid "moralizing" refusal from main chat model
            # Pass full history to preserve context (e.g. "don't give solution")
            try:
                import Assistant as AssistantModule
                history_for_coder = list(AssistantModule.conversation_history) # Copy
                # Append current user msg
                history_for_coder.append({"role": "user", "content": user_message})
            except Exception:
                history_for_coder = [{"role": "user", "content": user_message}]

            code_result = execute_tool("run_code_model", {
                "prompt": user_message,
                "messages": history_for_coder
            })
            return jsonify({
                "response": code_result,
                "timestamp": datetime.now().isoformat(),
                "intent": "coding",
                 "voice_enabled": voice_enabled_global
            })

        # ------------- NETWORK QUESTION (June explains) -------------
        if intent == "network_question":
            AGENT_CONTEXT["last_agent"] = "june"
            reply = ask_ollama_chat(user_message, model)
            return jsonify({
                "response": reply,
                "timestamp": datetime.now().isoformat(),
                "voice_enabled": voice_enabled_global
            })

        # ------------- NETWORK ACTION (NetJune executes) -------------
        if intent == "network_action":
            AGENT_CONTEXT["last_agent"] = "netjune"
            gen = run_network_agent(user_message, model="jimscard/whiterabbit-neo:13b")
            # Consume generator (ignoring control signals since this is HTTP/JSON-once)
            result = ""
            for item in gen:
                if isinstance(item, str):
                    result += item
            return jsonify({
                "response": result,
                "timestamp": datetime.now().isoformat(),
                "voice_enabled": voice_enabled_global
            })

        # ------------- SYSTEM / CHAT (Unified Handler) -------------
        # We process 'system' and 'chat' intents together because the model
        # might decide to use a tool even if the classifier didn't predict it.
        if intent in ["system", "chat", "general", "unknown"]:
            AGENT_CONTEXT["last_agent"] = "june"

            reply = ask_ollama_chat(user_message, model)
            if not isinstance(reply, str):
                reply = str(reply)

            # ALWAYS check for tool calls
            natural_text, tool_name, tool_args = extract_tool_call(reply)

            # June emitted a tool call
            if tool_name:
                if tool_args is None:
                    tool_args = {}

                result = execute_tool(tool_name, tool_args)

                if tool_name in ["run_code_model", "search_github"]:
                    # For code and GitHub links, show raw Markdown
                    formatted = result.strip()
                else:
                    # For other tools, wrap in a code block for terminal look
                    formatted = f"```\n{result.strip()}\n```"

                final_msg = (
                    natural_text.strip() + "\n\n" + formatted
                    if natural_text else formatted
                )

                return jsonify({
                    "response": final_msg,
                    "timestamp": datetime.now().isoformat(),
                    "voice_enabled": voice_enabled_global
                })

            # No tool call → just return the natural text (cleaned of JSON if any was malformed but caught)
            return jsonify({
                "response": natural_text,
                "timestamp": datetime.now().isoformat(),
                "voice_enabled": voice_enabled_global
            })

    except Exception as e:
        print(f"[ERROR] Chat endpoint error: {e}")
        return jsonify({"error": f"Server error: {e}"}), 500


@app.route('/api/tool', methods=['POST'])
def tool():
    """Execute tools directly (manual UI-triggered)."""
    try:
        data = request.json or {}
        tool_name = data.get('tool', '') or ''
        args = data.get('args', {}) or {}

        if not tool_name:
            return jsonify({'error': 'No tool specified'}), 400

        # Execute tool using the backend dispatcher
        try:
            result = execute_tool(tool_name, args)
        except Exception as e:
            result = f"Tool execution exception: {e}"

        # Voice feedback for tool results (if enabled)
        if voice_enabled_global and isinstance(result, str) and result.strip():
            try:
                threading.Thread(target=speak_async, args=(result,), daemon=True).start()
            except Exception:
                pass

        return jsonify({
            'result': result,
            'tool': tool_name,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'error': f'Tool execution error: {str(e)}'}), 500


@app.route('/api/voice', methods=['POST', 'PUT'])
def voice_control():
    """Control voice on/off"""
    global voice_enabled_global

    if request.method == 'POST':
        # Set voice state
        data = request.json or {}
        enabled = data.get('enabled', True)
        voice_enabled_global = bool(enabled)

        # Sync with backend
        set_voice_enabled(voice_enabled_global)

        return jsonify({
            'voice_enabled': voice_enabled_global,
            'message': f'Voice {"enabled" if voice_enabled_global else "disabled"}'
        })

    elif request.method == 'PUT':
        # Toggle voice state
        voice_enabled_global = not voice_enabled_global
        set_voice_enabled(voice_enabled_global)

        return jsonify({
            'voice_enabled': voice_enabled_global,
            'message': f'Voice {"enabled" if voice_enabled_global else "disabled"}'
        })

    # GET current state
    return jsonify({
        'voice_enabled': voice_enabled_global
    })


@app.route('/api/status')
def status():
    """Get system status"""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        ollama_running = response.status_code == 200

        return jsonify({
            'status': 'online' if ollama_running else 'offline',
            'voice_enabled': voice_enabled_global,
            'timestamp': datetime.now().isoformat(),
            'models': response.json().get('models', []) if ollama_running else []
        })
    except:
        return jsonify({
            'status': 'offline',
            'voice_enabled': voice_enabled_global,
            'timestamp': datetime.now().isoformat(),
            'models': []
        })


@app.route('/api/voice-input', methods=['POST'])
def voice_input():
    """Process voice input using Whisper STT"""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # Save temporarily
        temp_dir = os.path.join(tempfile.gettempdir(), "june_voice_upload")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"voice_{int(datetime.now().timestamp())}.webm")
        audio_file.save(temp_path)

        # Transcribe using Assistant.py's new function
        user_text = transcribe_file(temp_path)
        
        # Cleanup
        try:
            os.remove(temp_path)
        except:
            pass

        if not user_text:
            return jsonify({'error': 'No speech detected'}), 400

        return jsonify({
            'text': user_text,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'error': f'Voice input error: {str(e)}'}), 500


@app.route('/api/models')
def get_models():
    """Get available Ollama models"""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return jsonify({'models': models})
        else:
            return jsonify({'models': []})
    except:
        return jsonify({'models': []})


@app.route('/api/conversation', methods=['GET', 'POST', 'DELETE'])
def conversation():
    """Manage conversation history"""
    conversation_file = 'conversation_history.json'

    if request.method == 'GET':
        try:
            if os.path.exists(conversation_file):
                with open(conversation_file, 'r', encoding='utf-8') as f:
                    return jsonify(json.load(f))
            return jsonify({'messages': []})
        except:
            return jsonify({'messages': []})

    elif request.method == 'POST':
        try:
            data = request.json or {}
            messages = data.get('messages', [])
            with open(conversation_file, 'w', encoding='utf-8') as f:
                json.dump({'messages': messages}, f, indent=2, ensure_ascii=False)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            if os.path.exists(conversation_file):
                os.remove(conversation_file)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload file for RAG ingestion"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        upload_dir = "D:/College/AI Assistant/documents"
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename)
        file.save(filepath)

        # Add to RAG knowledge base
        from Assistant import rag_add_document
        result = rag_add_document(filepath)

        return jsonify({
            'success': True,
            'message': result,
            'filename': file.filename
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/system-stats')
def system_stats():
    """Get system monitoring statistics"""
    try:
        import psutil

        stats = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory': psutil.virtual_memory()._asdict(),
            'disk': psutil.disk_usage('/')._asdict(),
            'timestamp': datetime.now().isoformat()
        }

        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tools')
def list_tools():
    """List available tools"""
    tools = [
        {
            'name': 'open_path',
            'description': 'Open files, folders, or applications',
            'template': 'Open <path>'
        },
        {
            'name': 'learn_from_url',
            'description': 'Learn content from a website URL',
            'template': 'Learn from <url>'
        },
        {
            'name': 'draw_image',
            'description': 'Generate images using AI',
            'template': 'Draw <description>'
        },
        {
            'name': 'run_command',
            'description': 'Execute system commands',
            'template': 'Run command: <command>'
        },
        {
            'name': 'diagnose_system',
            'description': 'Check system health and performance',
            'template': 'Diagnose: <issue>'
        },
        {
            'name': 'get_news',
            'description': 'Get latest news on topics',
            'template': 'Get news about <topics>'
        },
        {
            'name': 'summarize_day',
            'description': 'Summarize daily activities',
            'template': 'Summarize my day'
        },
        {
            'name': 'organize_files',
            'description': 'Organize files in folders',
            'template': 'Organize files in: <path>'
        },
        {
            'name': 'recall_diagnostics',
            'description': 'View system diagnostic history',
            'template': 'Show system diagnostics'
        },
        {
            'name' : 'run_code_model',
            'description' : 'Codes for you',
            'template' : 'Coder'
        },
    ]

    return jsonify({'tools': tools})


@app.route('/api/network/reset', methods=['POST'])
def reset_network_memory():
    from network_ai import network_history
    network_history.clear()
    return jsonify({"message": "Network AI memory reset."})


@socketio.on('connect')
def handle_connect():
    emit('status', {'message': 'Connected to June AI Assistant'})


@socketio.on('stream_chat')
def handle_stream_chat(data):
    """Handle streaming chat responses with tool detection"""
    try:
        user_message = data.get('message', '').strip()
        model = data.get('model', 'june:latest')

        if not user_message:
            emit('error', {'message': 'Empty message'})
            return

        # 0. HANDLE MODE SWITCHING & PERSISTENCE
        global ACTIVE_MODE
        lower_msg = user_message.lower().strip()

        # Enter Hacker Mode
        if ACTIVE_MODE == "standard" and ("enter hacker mode" in lower_msg):
            ACTIVE_MODE = "network"
            emit('mode_change', {'mode': 'network'})
            msg = "Initializing Network Operations Center...\n\n**HACKER MODE ACTIVE**\n\nDirect shell access to Network AI established. Type 'exit' to return."
            emit('stream_complete', {'response': msg, 'timestamp': datetime.now().isoformat()})
            return

        # Exit Hacker Mode
        if ACTIVE_MODE == "network" and ("exit hacker mode" in lower_msg or "exit" in lower_msg):
            ACTIVE_MODE = "network" # This looks like a bug in original code too, setting mode to network instead of standard? No wait, original code said ACTIVE_MODE = "network" then emitted "standard"?
            # Ah, wait. The original code (lines 551-553) looked suspicious. Let's fix it.
            ACTIVE_MODE = "standard"
            emit('mode_change', {'mode': 'standard'})
            msg = "Deactivating Network Agent.\nReturning to standard user interface."
            emit('stream_complete', {'response': msg, 'timestamp': datetime.now().isoformat()})
            return

        # 1. PERSISTENT MODE ROUTING
        if ACTIVE_MODE == "network":
             AGENT_CONTEXT["last_agent"] = "netjune"
             
             # run_network_agent is now a generator
             gen = run_network_agent(user_message, model="jimscard/whiterabbit-neo:13b")
             full_response = ""
             
             for item in gen:
                 if isinstance(item, dict):
                     # Control signal
                     if item.get("type") == "new_bubble":
                         # Finalize current bubble with accumulated text
                         emit('stream_complete', {'response': full_response, 'timestamp': datetime.now().isoformat()})
                         # Signal frontend to start fresh bubble
                         emit('stream_new_bubble', {})
                         full_response = ""
                 else:
                     # String chunk
                     full_response += item
                     emit('stream_chunk', {'chunk': item})
                     
             emit('stream_complete', {'response': full_response, 'timestamp': datetime.now().isoformat()})
             return

        # Send an initial empty chunk to start UI stream safely
        emit('stream_chunk', {'chunk': '', 'full_response': ''})

        # 2. CLASSIFY INTENT (Standard Mode)
        intent = classify_intent(user_message)
        print(f"[DEBUG][Socket] Message: '{user_message}' | Intent: '{intent}'")
        AGENT_CONTEXT["last_intent"] = intent

        # 3. ROUTING
        
        # --- CODING (Bypass June) ---
        if intent == "coding":
            # [NEW] Handoff Confirmation
            emit('stream_complete', {'response': "Redirecting to QwenCoder for code generation...", 'timestamp': datetime.now().isoformat()})
            emit('stream_new_bubble', {})

            # Direct routing to QwenCoder
            code_result = execute_tool("run_code_model", {"prompt": user_message})
            emit('stream_complete', {'response': code_result, 'timestamp': datetime.now().isoformat()})
            return

        # --- NETWORK AGENT ---
        if intent in ["network_question", "network_action"]:
            if intent == "network_action":
                # [NEW] Handoff Confirmation
                emit('stream_complete', {'response': "Redirecting to Network Agent (NetJune)...", 'timestamp': datetime.now().isoformat()})
                emit('stream_new_bubble', {})
                
                AGENT_CONTEXT["last_agent"] = "netjune"
                
                # run_network_agent is now a generator
                gen = run_network_agent(user_message, model="jimscard/whiterabbit-neo:13b")
                full_response = ""
                
                for item in gen:
                    if isinstance(item, dict):
                        # Control signal
                        if item.get("type") == "new_bubble":
                            # Finalize current bubble with accumulated text
                            emit('stream_complete', {'response': full_response, 'timestamp': datetime.now().isoformat()})
                            # Signal frontend to start fresh bubble
                            emit('stream_new_bubble', {})
                            full_response = ""
                    else:
                        # String chunk
                        full_response += item
                        emit('stream_chunk', {'chunk': item})
                        
                # Ensure the final bubble is closed properly
                emit('stream_complete', {'response': full_response, 'timestamp': datetime.now().isoformat()})
                return
            else:
                AGENT_CONTEXT["last_agent"] = "june"
                # Use standard Assistant but stream it?
                # For network questions, we can use the main assistant if it knows about network tools (via RAG or system prompt)
                pass # Use fallback below

        # --- SYSTEM / CHAT (Unified SocketIO Handler) ---
        # Covers both explicit 'system' intent AND 'chat' intent fallback
        # to ensure tool calls are caught even if misclassified.
        if intent in ["system", "chat", "general", "unknown", "network_question"]:
            AGENT_CONTEXT["last_agent"] = "june"
            
            # Use the new streaming `ask_ollama_chat`
            # It yields chunks of text (and tool outputs)
            gen = ask_ollama_chat(user_message, model, stream=True)
            full_response = ""
            suppress_stream = False

            for chunk in gen:
                if isinstance(chunk, str):
                    full_response += chunk
                    
                    # Detect start of JSON block (usually \n{ or just { near the end)
                    if not suppress_stream:
                        # More aggressive check for JSON opening
                        if "{" in chunk and ("tool" in chunk or "tool" in full_response or '"' in chunk):
                            # Start buffering/suppressing once we see the brace if it looks like JSON
                            suppress_stream = True
                            pre_json = chunk.split("{")[0]
                            if pre_json:
                                emit('stream_chunk', {'chunk': pre_json})
                        else:
                            emit('stream_chunk', {'chunk': chunk})
                
            # Stream complete
            emit('stream_complete', {'response': full_response, 'timestamp': datetime.now().isoformat()})
            
            # [NEW] Voice feedback for streaming responses
            if voice_enabled_global and full_response:
                try:
                    # Clean the full response of any tool calls before speaking
                    clean_response, _, _ = extract_tool_call(full_response)
                    if clean_response:
                        speak_async(clean_response)
                except Exception as e:
                    print(f"[ERROR] speak_async failed: {e}")

    except Exception as e:
        print(f"[ERROR][Socket] Stream error: {e}")
        emit('error', {'message': f"Server error: {str(e)}"})


@app.route('/api/chat/stream', methods=['POST'])
def stream_chat_api():
    """
    Streaming endpoint for Raspberry Pi or other external clients.
    Yields chunks of text as they are generated.
    """
    data = request.json
    user_message = data.get('message', '').strip()
    model = data.get('model', 'june:latest')

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    def generate():
        # Call the generator from Assistant.py
        gen = ask_ollama_chat(user_message, model, stream=True)
        for chunk in gen:
            if isinstance(chunk, str):
                yield chunk

    return Response(stream_with_context(generate()), mimetype='text/plain')


if __name__ == '__main__':
    # Initialize assistant
    # initialize_assistant()

    print("\n\nOpen http://localhost:5000 in your browser")
    print("WebSocket support enabled for real-time streaming")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False)