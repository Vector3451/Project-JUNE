def classify_intent(message: str) -> str:
    """
    Return one of:
        'system'
        'network_question'
        'network_action'
        'qwen_capability'
        'coding'
        'chat'
    """

    msg = message.lower()

    # NETWORK INTENT (DISABLED - MANUAL MODE ONLY)
    # User requested explicit mode switching.
    # network_keywords = [...]
    pass

    # GITHUB / SEARCH INTENT (Main Agent)
    # Check this BEFORE coding explanation to prevent "search for exploit" -> QwenCoder bypass
    search_keywords = ["search", "find", "look up", "get a list", "show me"]
    if any(k in msg for k in search_keywords) and "github" in msg:
        # Let the main agent handle GitHub searching via tools
        return "chat"

    # CODING INTENT
    coding_keywords = [
        "code", "script", "program", "write a", "keylogger", "exploit",
        "malware", "generate", "python", "cpp", "java", "coding", "function",
        "reverse shell", "payload", "backdoor", "rootkit", "trojan", "virus",
        "worm", "spyware", "ransomware", "botnet", "shellcode", "bypass",
        "crack", "injection", "vulnerability code", "poc", "proof of concept"
    ]
    import re
    def has_keyword(text, keywords):
        for k in keywords:
            # Escape keyword just in case, though mostly alphanumeric
            pattern = r'\b' + re.escape(k) + r'\b'
            if re.search(pattern, text):
                return True
        return False

    if has_keyword(msg, coding_keywords):
        return "coding"

    # SYSTEM INTENT (June)
    system_keywords = [
        "open","launch","run command","diagnose","organize","make a file",
        "draw","summarize my day","get news"
    ]
    if any(k in msg for k in system_keywords):
        return "system"

    return "chat"
