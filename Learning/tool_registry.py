"""
SAFE TOOL REGISTRY WITH SANDBOX EXECUTION + USER VERIFICATION
============================================================

This version:
- NEVER imports untrusted Python code into the main program.
- Executes GitHub tools ONLY in a separate restricted subprocess.
- Scans repositories for dangerous code patterns.
- If repo appears suspicious, the agent asks the user for confirmation.
- Safe JSON-based tool contract.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

import requests

# -------------------------------------------------------------
# Paths
# -------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_ROOT = os.path.join(BASE_DIR, "tools")
DOWNLOADED_ROOT = os.path.join(TOOLS_ROOT, "downloaded")
SAFE_RUNNER = os.path.join(BASE_DIR, "safe_runner.py")   # NEW

os.makedirs(DOWNLOADED_ROOT, exist_ok=True)


# -------------------------------------------------------------
# Data Structures
# -------------------------------------------------------------

@dataclasses.dataclass
class RegisteredTool:
    name: str
    file_path: str
    description: str = ""
    source: str = ""  # e.g. "github:owner/repo"


_TOOL_REGISTRY: Dict[str, RegisteredTool] = {}


# -------------------------------------------------------------
# Register + List Tools
# -------------------------------------------------------------

def register_tool(name: str, file_path: str, description: str, source: str):
    """Register a sandboxed tool."""
    _TOOL_REGISTRY[name] = RegisteredTool(
        name=name,
        file_path=file_path,
        description=description,
        source=source,
    )


def list_tools() -> List[RegisteredTool]:
    return list(_TOOL_REGISTRY.values())


def get_tool(name: str) -> Optional[RegisteredTool]:
    return _TOOL_REGISTRY.get(name)


# -------------------------------------------------------------
# RUN TOOL (in sandbox)
# -------------------------------------------------------------

def run_tool(name: str, **params) -> Any:
    """
    Run a tool in a strict sandbox subprocess, not in the agent.
    """
    tool = get_tool(name)
    if not tool:
        raise ValueError(f"Tool '{name}' not found.")

    cmd = [
        sys.executable,
        SAFE_RUNNER,
        tool.file_path,
        json.dumps(params),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10  # prevent infinite loops
        )
    except subprocess.TimeoutExpired:
        return {"error": "Tool execution timeout"}

    if result.returncode != 0:
        return {"error": "Tool crashed", "details": result.stderr.strip()}

    try:
        return json.loads(result.stdout.strip())
    except Exception:
        return {"error": "Invalid tool output", "raw": result.stdout.strip()}


# -------------------------------------------------------------
# GitHub Search
# -------------------------------------------------------------

GITHUB_API_SEARCH = "https://api.github.com/search/repositories"

def search_github_repos(task_description: str, language="python", per_page=5) -> List[dict]:
    query = f"{task_description} language:{language}"

    try:
        resp = requests.get(GITHUB_API_SEARCH, params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
        }, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        return [{"error": f"GitHub search failed: {e}", "query": query}]

    items = resp.json().get("items", [])
    results = []

    for item in items:
        results.append({
            "full_name": item.get("full_name"),
            "description": item.get("description") or "",
            "html_url": item.get("html_url"),
            "clone_url": item.get("clone_url"),
        })

    return results


# -------------------------------------------------------------
# Clone repo safely
# -------------------------------------------------------------

def clone_repo(clone_url: str, target_name: str) -> str:
    """
    Clone repo to downloaded directory.
    DOES NOT import or run code.
    """
    dest = os.path.join(DOWNLOADED_ROOT, target_name)

    if os.path.exists(dest):
        return dest

    cmd = ["git", "clone", "--depth", "1", clone_url, dest]

    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return dest


# -------------------------------------------------------------
# SAFETY SCANNING (core of safe mode)
# -------------------------------------------------------------

DANGEROUS_PATTERNS = [
    r"os\.system",
    r"subprocess",
    r"shutil",
    r"socket",
    r"requests",
    r"eval",
    r"exec",
    r"open\(.*w",          # writing files
    r"__import__",
    r"base64.b64decode",
    r"pickle",
]

def scan_file_for_risk(path: str) -> List[str]:
    """Return a list of reasons the file may be unsafe."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return ["File could not be read"]

    issues = []
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, content):
            issues.append(f"Matches dangerous pattern: {pattern}")

    return issues


# -------------------------------------------------------------
# Discover tools (SAFE MODE)
# -------------------------------------------------------------

def discover_tools(repo_path: str, source_label: str) -> List[RegisteredTool]:
    """
    SAFE discovery:
    - detect `tool_*.py` files
    - scan for malicious code
    - require user confirmation if suspicious
    """

    found_tools = []

    for root, _, files in os.walk(repo_path):
        for fname in files:
            if not fname.startswith("tool_") or not fname.endswith(".py"):
                continue

            file_path = os.path.join(root, fname)
            tool_name = fname.replace("tool_", "").replace(".py", "")

            # -------- SAFETY CHECK --------
            issues = scan_file_for_risk(file_path)

            if issues:
                # Ask user to approve
                found_tools.append({
                    "tool_name": tool_name,
                    "file_path": file_path,
                    "source": source_label,
                    "unsafe": True,
                    "issues": issues,
                })
            else:
                # Safe enough → register
                register_tool(
                    name=tool_name,
                    file_path=file_path,
                    description=f"Tool from {source_label}",
                    source=source_label
                )
                found_tools.append({
                    "tool_name": tool_name,
                    "file_path": file_path,
                    "source": source_label,
                    "unsafe": False,
                })

    return found_tools


# -------------------------------------------------------------
# Acquire tools for a repo
# -------------------------------------------------------------

def github_acquire_tools(task_description: str, repo: dict) -> List[dict]:
    """
    Clone repo, scan tools, return list of tool info.
    Does NOT auto-enable unsafe ones.
    """
    clone_url = repo.get("clone_url")
    full_name = repo.get("full_name", "unknown_repo")

    target_name = full_name.replace("/", "_")
    repo_path = clone_repo(clone_url, target_name)

    tools = discover_tools(repo_path, f"github:{full_name}")

    return tools