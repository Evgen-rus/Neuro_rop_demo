"""Load the PraktikM manager playbook as bounded prompt-only knowledge."""

from __future__ import annotations

from pathlib import Path
import re

from app_clock import resolve_knowledge_dir


MANAGER_TACTICS_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "clients" / "praktikm" / "manager_tactics.md"
MAX_MANAGER_TACTICS_CHARS = 24000


def load_manager_tactics() -> str:
    # В DEMO_MODE читаем runtime-копию snapshot, tracked knowledge не перезаписываем.
    path = resolve_knowledge_dir() / "manager_tactics.md"
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("База практических тактик менеджера пуста")
    return text[:MAX_MANAGER_TACTICS_CHARS]


def manager_tactic_ids(text: str) -> tuple[str, ...]:
    """Extract stable tactic IDs from Markdown headings without a second config."""
    return tuple(dict.fromkeys(re.findall(r"^##\s+([A-Z][A-Z0-9-]+)\s+—", text, flags=re.MULTILINE)))
