"""
garak_bridge.py
---------------
Wrapper around the NVIDIA garak LLM vulnerability scanner CLI.
Exposes run_garak_scan() for use by the June AI assistant's tool system.

Supported model_type values:
  - "ollama"       → local Ollama REST endpoint (http://localhost:11434/api/generate)
  - "huggingface"  → HuggingFace Hub (requires HF_TOKEN env var for gated models)
  - "openai"       → OpenAI API (requires OPENAI_API_KEY env var)
  - "replicate"    → Replicate API (requires REPLICATE_API_TOKEN env var)
  - "litellm"      → LiteLLM proxy (any model via litellm)
  - "cohere"       → Cohere API (requires COHERE_KEY env var)
  - "groq"         → Groq API (requires GROQ_API_KEY env var)
  - "test"         → Garak's built-in test generator — no real model, runs instantly
  - "rest"         → Generic REST endpoint (requires GARAK_REST_URL env var or pass uri arg)
"""

import subprocess
import sys
import os
import re
import time
import json
import tempfile


# ─── Internal constants ──────────────────────────────────────────────────────

# Maps June-facing model_type strings to garak generator module paths.
_GENERATOR_MAP = {
    "ollama":       "rest.RestGenerator",   # Ollama via REST
    "huggingface":  "huggingface",
    "openai":       "openai",
    "replicate":    "replicate",
    "litellm":      "litellm",
    "cohere":       "cohere",
    "groq":         "groq",
    "rest":         "rest.RestGenerator",
    "test":         "test.Blank",
}

# Ollama REST config for garak (used when model_type == "ollama")
_OLLAMA_REST_ENV = {
    "GARAK_REST_URI":    "http://localhost:11434/api/generate",
    "GARAK_REST_MDLNAME": "",   # Will be filled with model_name at runtime
}

# Default probe set if none specified — a small, representative set
_DEFAULT_PROBES = "dan,encoding,promptinject"

# Hard cap on scan duration (seconds). Full scans can take 30+ minutes.
SCAN_TIMEOUT = 600  # 10 minutes


def _build_command(model_type: str, model_name: str, probes: str) -> list[str]:
    """Build the garak CLI command list."""
    generator = _GENERATOR_MAP.get(model_type.lower())
    if not generator:
        supported = ", ".join(_GENERATOR_MAP.keys())
        raise ValueError(
            f"Unknown model_type '{model_type}'. Supported: {supported}"
        )

    cmd = [sys.executable, "-m", "garak"]

    # Generator / model flags
    cmd += ["--model_type", generator]

    # Only pass --model_name if the generator actually needs one.
    # test.Blank does not need a model name.
    if generator != "test.Blank" and model_name:
        cmd += ["--model_name", model_name]

    # Probes
    if probes:
        cmd += ["--probes", probes]
    else:
        cmd += ["--probes", _DEFAULT_PROBES]

    return cmd


def _parse_output(raw: str, elapsed: float) -> str:
    """Extract a readable summary from garak stdout/stderr."""
    lines = raw.splitlines()

    summary_lines = []
    hit_section = False

    for line in lines:
        # Garak prints per-probe results like "  encoding.InjectBase64: PASS (840/840)"
        if re.search(r'(PASS|FAIL|ok|SKIP)', line, re.IGNORECASE):
            summary_lines.append(line.strip())
            hit_section = True

    # If we couldn't parse structured output, just return last N lines
    if not summary_lines:
        tail = [l.strip() for l in lines[-30:] if l.strip()]
        body = "\n".join(tail) if tail else raw[:1200]
        return (
            f"⏱ Scan completed in {elapsed:.1f}s\n\n"
            f"📋 Raw Output (last section):\n{body}"
        )

    body = "\n".join(summary_lines)
    return (
        f"⏱ Scan completed in {elapsed:.1f}s\n\n"
        f"📊 Garak Probe Results:\n{body}"
    )


def run_garak_scan(
    model_type: str = "ollama",
    model_name: str = "june:latest",
    probes: str = "",
) -> str:
    """
    Run a garak vulnerability scan against a model.

    Args:
        model_type : Generator type (see module docstring for supported values).
        model_name : Model identifier (e.g. "june:latest", "gpt-4o-mini", "gpt2").
        probes     : Comma-separated probe names (e.g. "dan,encoding").
                     Empty string → runs the default probe set.

    Returns:
        A human-readable scan result string for June to relay to the user.
    """
    try:
        cmd = _build_command(model_type, model_name, probes)
    except ValueError as e:
        return f"❌ Garak configuration error: {e}"

    # For Ollama we inject the model name into the REST env vars
    env = os.environ.copy()
    if model_type.lower() == "ollama":
        env["GARAK_REST_URI"]     = _OLLAMA_REST_ENV["GARAK_REST_URI"]
        env["GARAK_REST_MDLNAME"] = model_name

    probe_display = probes or _DEFAULT_PROBES
    print(
        f"[GARAK] Starting scan | model_type={model_type} | "
        f"model_name={model_name} | probes={probe_display}"
    )
    print(f"[GARAK] CMD: {' '.join(cmd)}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SCAN_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return (
            f"⏰ Garak scan timed out after {elapsed:.0f}s "
            f"(limit: {SCAN_TIMEOUT}s). "
            f"Try specifying a narrower probe set."
        )
    except FileNotFoundError:
        return (
            "❌ Garak not found. Make sure it is installed:\n"
            "  pip install garak"
        )
    except Exception as e:
        return f"❌ Unexpected error running garak: {e}"

    elapsed = time.time() - start
    combined = (result.stdout or "") + (result.stderr or "")

    if result.returncode != 0 and not combined.strip():
        return (
            f"❌ Garak exited with code {result.returncode} and produced no output.\n"
            f"Possible causes: wrong model_name, missing API key, or network issue."
        )

    summary = _parse_output(combined, elapsed)

    # Find and surface the report file path if garak printed it
    report_match = re.search(r'report file.*?:\s*(.+\.jsonl)', combined, re.IGNORECASE)
    if report_match:
        report_path = report_match.group(1).strip()
        summary += f"\n\n📁 Full report: `{report_path}`"

    return summary


def list_available_probes() -> str:
    """Return the list of all available garak probes as a string."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "garak", "--list_probes"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return output[:3000] if output else "No probe list returned."
    except Exception as e:
        return f"Error listing probes: {e}"


def list_available_generators() -> str:
    """Return the list of all available garak generators as a string."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "garak", "--list_generators"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return output[:3000] if output else "No generator list returned."
    except Exception as e:
        return f"Error listing generators: {e}"


# ─── Quick self-test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running quick garak self-test (test.Blank generator)...")
    result = run_garak_scan(model_type="test", model_name="", probes="test.Test")
    print(result)
