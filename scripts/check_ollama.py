"""
Ollama Diagnostic Smoke Test Script
Reports environment-aware Ollama status (Local vs Cloud).
Never prints API keys, authorization headers, or secrets.
Usage:
    python -m scripts.check_ollama
"""

import sys
from app.config import get_settings
from services.ai.ollama import OllamaService


def main():
    settings = get_settings()

    print("=" * 45)
    print("      OLLAMA SERVICE DIAGNOSTICS      ")
    print("=" * 45)

    enabled_str = "yes" if getattr(settings, "ollama_enabled", True) else "no"
    print(f"Ollama enabled    : {enabled_str}")

    svc = OllamaService()
    print(f"Mode              : {svc.mode}")

    reachable = svc.check_health()
    print(f"Host reachable    : {'yes' if reachable else 'no'}")
    print(f"Configured model  : {svc.model}")

    model_avail = svc.check_model_available() if reachable else False
    print(f"Model available   : {'yes' if model_avail else 'no'}")
    print("=" * 45)

    if not reachable:
        sys.exit(1)


if __name__ == "__main__":
    main()
