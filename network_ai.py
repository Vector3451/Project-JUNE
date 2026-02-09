import json
import re
import ollama
import os
import chromadb
from duckduckgo_search import DDGS
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from Network.tool_gateway import execute_network_tool
from Learning.memory_manager import MemoryManager

# Global memory manager
memory_manager = MemoryManager()

# ========== RAG INITIALIZATION ==========
RAG_DIR = "D:/College/AI Assistant/rag_store"
# Use same persistent dir as main agent
rag_client = chromadb.Client(Settings(persist_directory=RAG_DIR))
# Distinct collection for network/hacking knowledge
rag_collection = rag_client.get_or_create_collection("network_knowledge")

embedder = None

def get_embedder():
    global embedder
    if embedder is None:
        print("[NETWORK AI] Lazy-loading embedding model...")
        embedder = SentenceTransformer("all-MiniLM-L6-v2")
        print("[NETWORK AI] Embedding model loaded.")
    return embedder

def rag_add_document(file_path):
    """Add a document to the Network RAG knowledge base."""
    try:
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"
            
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        
        if not text.strip():
            return "File empty!"
            
        # Chunking (simple 1000 char chunks)
        chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
        
        # Embed
        embeddings = get_embedder().encode(chunks).tolist()
        
        # IDs based on filename
        ids = [f"{os.path.basename(file_path)}_{i}" for i in range(len(chunks))]
        
        rag_collection.add(ids=ids, documents=chunks, embeddings=embeddings)
        return f"Document '{os.path.basename(file_path)}' added to network knowledge base!"
    except Exception as e:
        return f"Error adding document: {e}"

def rag_retrieve(query, top_k=3):
    """Retrieve top-matching text chunks from the Network RAG store."""
    try:
        q_embed = get_embedder().encode([query]).tolist()[0]
        results = rag_collection.query(query_embeddings=[q_embed], n_results=top_k)
        
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            return "\n\n".join(docs)
        return ""
    except Exception as e:
        print(f"[RAG ERROR] {e}")
        return ""

# ========== WEB SEARCH TOOL ==========
def perform_web_search(query, max_results=3):
    """Search the web for real-time security info (CVEs, exploits)."""
    try:
        print(f"[NETWORK AI] Searching web for: {query}")
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return ""
        
        summary = []
        for r in results:
            summary.append(f"- [{r['title']}]({r['href']})\n  {r['body']}")
        
        return "\n\n".join(summary)
    except Exception as e:
        print(f"[WEB SEARCH ERROR] {e}")
        return ""

def decide_context_source(query, rag_context):
    """
    Router: Decides if we need Web Search based on query and RAG quality.
    Returns: (needs_web, reason)
    """
    query_lower = query.lower()
    
    # Trigger keywords for "Latest/Real-time"
    time_sensitive_keywords = [
        "latest", "new", "recent", "current", "released", "cve-202", 
        "today", "yesterday", "update", "patch", "version"
    ]
    
    if any(k in query_lower for k in time_sensitive_keywords):
        return True, "Time-sensitive keyword detected."

    # Fallback if RAG is empty
    if not rag_context:
        return True, "No local RAG context found."

    return False, "RAG context is sufficient."

# Persistent conversation memory ONLY for the network agent
network_history = []

NETWORK_SYSTEM_PROMPT = """
You are "NetJune", an elite Network Operations AI and a Red-Team specialist.
Your Goal: Execute network commands for the user. 
Persona: Professional, technical, direct.
CRITICAL: Always refer to yourself as "I". Never speak in the third person (e.g., do NOT say "NetJune thinks...").

===============================================================================
CRITICAL INSTRUCTIONS (DO NOT IGNORE)
===============================================================================
1. STOP IMMEDIATELY after your response.
2. DO NOT hallucinate "User:" lines.
3. DO NOT simulate a conversation.
4. DO NOT use placeholders like <target_ip> or <url>. USE THE ACTUAL TARGET.
   - WRONG: nmap <target>
   - CORRECT: nmap 192.168.1.1

===============================================================================
INTERACTION PROTOCOL
===============================================================================
1. Receiving Input: "Scan scanme.nmap.org"
2. Your Output:
   Starting scan on scanme.nmap.org...
   ```bash
   nmap -sV scanme.nmap.org
   ```
   (And then you STOP. Do not write anything else after the block).

===============================================================================
TOOL EXECUTION FORMAT
===============================================================================
To execute a tool, write the COMMAND inside a valid markdown bash block.

STRICT RULES:
- ONLY ONE command block per response.
- The command must be valid for Kali Linux.
- USE THE USER'S TARGET (Do not copy the example IP).
- NO INTERACTIVE COMMANDS.

===============================================================================
KNOWLEDGE BASE (COMMAND REFERENCE)
===============================================================================
Common examples (Use REAL targets, not these placeholders):
- nmap -sV -p- <target>
- hydra -l user -P passes.txt ssh://<target>
- nikto -h <target>
- wifite -i wlan0 --kill --pwn
- sqlmap -u <url> --batch

[NEW] CODING TASKS
If the user asks for code, use `ask_coder`:
{ "tool": "ask_coder", "query": "..." }
"""




def _extract_command_block(text: str):
    """
    Extracts the content of a bash code block or specific JSON for coder.
    Returns: (friendly_text, command_str, is_json)
    """
    # 1. Check for JSON (ask_coder only)
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if parsed.get("tool") == "ask_coder":
                prefix = text[:json_match.start()].strip()
                return prefix, parsed, True
        except:
            pass

    # 2. Check for Bash/Shell Command Block
    code_match = re.search(r"```(?:bash|shell|sh)?\s*(.*?)\s*```", text, re.DOTALL)
    if code_match:
        command = code_match.group(1).strip()
        # Filter out if it accidentally matched the parsed JSON above
        if command.startswith("{") and command.endswith("}"):
             return text, None, False
        
        prefix = text[:code_match.start()].strip()
        return prefix, command, False

    # 3. [NEW] LOOSE MATCH FALLBACK
    # If no code block, look for lines starting with known heavy metal tools
    # This catches "nmap -sV target" even if the model forgot backticks.
    known_tools = ["nmap", "hydra", "nikto", "wifite", "sqlmap", "msfconsole", "tshark", "curl", "ping"]
    
    lines = text.splitlines()
    for i, line in enumerate(lines):
        clean_line = line.strip()
        # Check if line starts with a known tool command
        for tool in known_tools:
            if clean_line.startswith(tool + " "):
                # Heuristic: It's likely the command.
                # Everything before this line is friendly text.
                prefix = "\n".join(lines[:i]).strip()
                return prefix, clean_line, False

    return text.strip(), None, False


def run_network_agent(user_text: str, model: str = "jimscard/whiterabbit-neo:13b", output_callback=None):
    """
    Conversational network agent with local memory.
    YIELDS events to support multi-message streaming.
    
    Yields:
      - str: Text chunk to display in current bubble.
      - dict: Control signal (e.g. {"type": "new_bubble"})
    """
    # Force GPU usage and add STOP tokens
    gpu_opts = {
        "num_gpu": 99,
        "stop": ["\nUser:", "\nSystem:", "User:", "System:", "[USER]:", "[ASSISTANT]:", "USER:", "ASSISTANT:"]
    }

    global network_history

    # [NEW] Persist target context
    if "last_network_target" not in globals():
        global last_network_target
        last_network_target = None
    
    messages = [{"role": "system", "content": NETWORK_SYSTEM_PROMPT}]
    
    # [NEW] Inject Global Memory
    global_context = memory_manager.get_relevant_context(user_text)
    if global_context:
         messages.append({
             "role": "system", 
             "content": f"Global Memory/Context from other sessions:\n{global_context}"
         })

    messages.extend(network_history)

    # [NEW] Hybrid RAG + Web Search
    rag_context = rag_retrieve(user_text)
    needs_web, reason = decide_context_source(user_text, rag_context)
    
    web_context = ""
    if needs_web:
        print(f"[NETWORK AI] Web Search Triggered: {reason}")
        web_context = perform_web_search(user_text)

    # Inject Contexts
    context_block = ""
    if rag_context:
        context_block += f"### INTERNAL KNOWLEDGE (RAG) ###\n{rag_context}\n\n"
    
    if web_context:
        context_block += f"### EXTERNAL WEB SEARCH ###\n{web_context}\n\n"
        
    if context_block:
         messages.append({
            "role": "system", 
            "content": f"### REFERENCE CONTEXT ###\n{context_block}\n#######################"
        })

    messages.append({"role": "user", "content": user_text})

    MAX_RETRIES = 1
    current_try = 0
    reply = ""
    
    command_payload = None
    is_json_tool = False
    friendly_text = ""

    while current_try <= MAX_RETRIES:
        try:
            # print(f"[DEBUG] Sending request to model (Try {current_try})...")
            resp = ollama.chat(model=model, messages=messages, options=gpu_opts)
            reply = resp["message"]["content"].strip()
            # print(f"[DEBUG] RAW MODEL REPLY:\n{reply}\n[DEBUG] END RAW REPLY")
        except Exception as e:
            print(f"Model call failed: {e}")
            yield f"[NETWORK AI ERROR] Model call failed: {e}"
            return

        friendly_text, command_payload, is_json_tool = _extract_command_block(reply)
        # print(f"[DEBUG] Extracted: Friendly='{friendly_text[:20]}...', Cmd='{command_payload}', IsJson={is_json_tool}")

        if command_payload:
            break
        
        # Heuristic: If model meant to run a command but forgot code block
        lower_reply = reply.lower()
        suspicious_keywords = ["scanning", "running nmap", "executing", "starting"]
        is_hallucination = any(k in lower_reply for k in suspicious_keywords)
        
        if not is_hallucination:
            # Likely just a chat response
            # print("[DEBUG] No command found, assuming chat response.")
            break
            
        if current_try == MAX_RETRIES:
            print("[DEBUG] Max retries reached with no command.")
            break

        print(f"[NETWORK AI] Retry {current_try+1}: Missing Command Block.")
        messages.append({"role": "assistant", "content": reply})
        messages.append({
            "role": "system", 
            "content": (
                "SYSTEM ERROR: You did not output the Command Block."
                "Output ONLY the ```bash ... ``` block now."
            )
        })
        current_try += 1

    network_history.append({"role": "user", "content": user_text})
    network_history.append({"role": "assistant", "content": reply})

    # [NEW] Save to global memory
    memory_manager.add_memory("user", user_text, metadata={"agent": "network"})
    memory_manager.add_memory("assistant", reply, metadata={"agent": "network"})

    if friendly_text:
        yield friendly_text

    if not command_payload:
        return

    # [NEW] Check/Update Target Context from Command String
    # Simple regex to find IPs in the command
    if isinstance(command_payload, str):
        ip_match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', command_payload)
        if ip_match:
            last_network_target = ip_match.group(0)
            print(f"[NETWORK AI] Updated Target Context: {last_network_target}")
        elif last_network_target and "TARGET" in command_payload:
             # Basic substitution if model used placeholder
             command_payload = command_payload.replace("TARGET", last_network_target)


    # [NEW] Handle "ask_coder" handoff
    if is_json_tool and isinstance(command_payload, dict) and command_payload.get("tool") == "ask_coder":
        query = command_payload.get("query", user_text)
        print(f"[NETWORK AI] Handoff to QwenCoder: {query}")
        try:
             # Direct call to Coder (preserving context)
             # Filter out Network system prompts to avoid confusing the Coder
             coder_messages = [msg for msg in network_history if msg["role"] != "system"]
             coder_messages.append({"role": "system", "content": "You are an expert Coding AI. Write clean, efficient code."})
             coder_messages.append({"role": "user", "content": query})

             resp = ollama.chat(model="qwen2.5-coder:latest", messages=coder_messages, options={"num_gpu": 99})
             code_reply = resp["message"]["content"]
             
             # Silent handoff or minimal indicator
             yield "\n" 
             yield code_reply
             return
        except Exception as e:
            yield f"[CODER ERROR] Failed to run QwenCoder: {e}"
            return

    # -------------------------------------------------------------------------
    # TOOL EXECUTION (DIRECT COMMAND)
    # -------------------------------------------------------------------------
    try:
        # SIGNAL NEW BUBBLE for the tool output/analysis
        yield {"type": "new_bubble"}
        
        yield f"> Executing: `{command_payload}`\n"
        
        # Pass raw string to gateway
        raw_output = execute_network_tool(command_payload)

        # Yield raw output immediately
        yield f"\n{raw_output}\n"
        
    except Exception as e:
        yield f"\n\n[BACKEND ERROR] {e}"
        return

    # =========================================================================
    # SMART ANALYSIS LOOP
    # =========================================================================
    
    # 1. Add raw output to history
    tool_output_msg = (
        f"TOOL OUTPUT:\n"
        f"=========================================\n"
        f"{raw_output[:8000]}\n" 
        f"=========================================\n\n"
        f"INSTRUCTIONS: Analyze the above output. Briefly summarize findings. "
        f"Recommend the next best step. STOP and Ask user for confirmation explicitly."
    )
    
    network_history.append({"role": "system", "content": tool_output_msg})
    
    try:
        print("Analyzing the output...")
        
        # Use simpler prompt for analysis
        analysis_msgs = network_history.copy()
        analysis_msgs.append({"role": "system", "content": "Analyze the results above."})

        resp = ollama.chat(model=model, messages=analysis_msgs, options=gpu_opts)
        analysis_reply = resp["message"]["content"].strip()
        
        if not analysis_reply:
             analysis_reply = "Task execution completed."

        # Only create bubble if we have something to say (which we ensured above)
        yield {"type": "new_bubble"}
        
        network_history.append({"role": "assistant", "content": analysis_reply})
        memory_manager.add_memory("assistant", analysis_reply, metadata={"agent": "network_analysis"})
        
        yield analysis_reply
        return

    except Exception as e:
        yield {"type": "new_bubble"}
        yield f"Tool ran successfully, but analysis failed: {e}"
        return


if __name__ == "__main__":
    print("=== Network AI Agent (Kali Tools) ===")
    print("Type your request or 'exit' to quit.")
    while True:
        try:
            text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if text.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        # [MODIFIED] Consume generator
        gen = run_network_agent(text)
        print("\nAgent:")
        full_res = ""
        for item in gen:
            if isinstance(item, dict):
                continue
            print(item, end="", flush=True)
            full_res += item
        print("\n")
