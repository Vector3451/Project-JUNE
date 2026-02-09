"""
safe_runner.py
A lightweight sandbox runner for executing untrusted GitHub tools.

This script is executed as a SEPARATE PROCESS.
It isolates untrusted code so it cannot harm the main assistant.

Usage (tool_registry handles this):
    python safe_runner.py <tool_file.py> "<json_params>"
"""

import json
import os
import sys
import builtins
import traceback

# -------------------------------------------------------------
# 1. Disable dangerous builtins
# -------------------------------------------------------------

FORBIDDEN_BUILTINS = {
    "open",             # blocks file writes / reads
    "exec",
    "eval",
    "__import__",       # restrict manual importing
    "compile",
    "input",
}

SAFE_BUILTINS = {}

for k, v in builtins.__dict__.items():
    if k in FORBIDDEN_BUILTINS:
        # Override forbidden functions with harmless stubs
        SAFE_BUILTINS[k] = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError(f"Forbidden function: {k}"))
    else:
        SAFE_BUILTINS[k] = v


# -------------------------------------------------------------
# 2. Block dangerous modules from importing
# -------------------------------------------------------------

FORBIDDEN_MODULES = {
    "os",
    "sys",
    "socket",
    "subprocess",
    "shutil",
    "requests",
    "urllib",
    "multiprocessing",
    "pathlib",
    "pickle",
    "base64",
    "ctypes",
    "resource",
}

def sandbox_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in FORBIDDEN_MODULES:
        raise ImportError(f"Forbidden module: {name}")
    return original_import(name, globals, locals, fromlist, level)

original_import = __import__


# -------------------------------------------------------------
# 3. Restricted execution environment
# -------------------------------------------------------------

SANDBOX_GLOBALS = {
    "__builtins__": SAFE_BUILTINS,
}

# Allowed minimal imports
ALLOWED_SAFE_LIBS = [
    "json",
    "math",
    "random",
    "time",
]

for lib in ALLOWED_SAFE_LIBS:
    SANDBOX_GLOBALS[lib] = __import__(lib)


# -------------------------------------------------------------
# 4. Load tool file safely
# -------------------------------------------------------------

def load_tool(path: str):
    """
    Reads the file content and returns the run_tool function defined inside.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception:
        raise RuntimeError("Could not read tool file.")

    # Intercept import attempts
    SAFE_BUILTINS["__import__"] = sandbox_import

    # Execute file inside sandbox
    tool_locals = {}
    try:
        exec(code, SANDBOX_GLOBALS, tool_locals)
    except Exception as e:
        raise RuntimeError(f"Tool import failed: {e}")

    if "run_tool" not in tool_locals:
        raise RuntimeError("Tool has no run_tool(params) function.")

    fn = tool_locals["run_tool"]
    if not callable(fn):
        raise RuntimeError("run_tool is not callable.")

    return fn


# -------------------------------------------------------------
# 5. Main execution
# -------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "safe_runner requires 2 arguments"}))
        return

    tool_path = sys.argv[1]
    raw_params = sys.argv[2]

    try:
        params = json.loads(raw_params)
    except Exception:
        print(json.dumps({"error": "Invalid JSON params"}))
        return

    try:
        fn = load_tool(tool_path)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        return

    try:
        result = fn(params)  # call tool
    except Exception:
        print(json.dumps({
            "error": "Tool raised exception",
            "trace": traceback.format_exc()
        }))
        return

    # Ensure result is JSON-safe
    try:
        print(json.dumps(result))
    except Exception:
        print(json.dumps({
            "error": "Tool returned non-JSON-serializable output",
            "raw": str(result)
        }))


if __name__ == "__main__":
    main()