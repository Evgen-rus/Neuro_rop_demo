"""Единые бизнес-часы приложения: живое московское время или замороженный DEMO_NOW.

Технические timestamp (логи, timeout, perf) этот модуль не подменяет.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time
from pathlib import Path

from dotenv import load_dotenv

from setup import BASE_DIR, MSK_TZ


load_dotenv(BASE_DIR / ".env")

_TRUE = {"1", "true", "yes", "on"}
_PRODUCTION_DB_RELATIVE = Path("reports") / "rop_assistant" / "rop_assistant.sqlite"
_CONTAINER_ROOT = "/app"
_CONTAINER_KNOWLEDGE_PREFIX = "/app/knowledge"


def _read_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in _TRUE


def is_demo_mode() -> bool:
    """True только при явном DEMO_MODE=true. Production по умолчанию не меняется."""
    return _read_bool_env("DEMO_MODE", False)


def parse_demo_now(raw: str | None = None) -> datetime | None:
    """Разобрать DEMO_NOW. Дата без времени — 18:00 МСК; naive datetime — московское время."""
    value = str(raw if raw is not None else os.getenv("DEMO_NOW", "")).strip()
    if not value:
        return None
    if len(value) == 10:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError:
            return None
        return datetime.combine(parsed_date, time(18, 0), tzinfo=MSK_TZ)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MSK_TZ)
    return parsed.astimezone(MSK_TZ)


def app_now() -> datetime:
    """Текущий бизнес-момент: DEMO_NOW в demo, иначе живое московское время."""
    if not is_demo_mode():
        return datetime.now(MSK_TZ)
    parsed = parse_demo_now()
    if parsed is None:
        raise RuntimeError(
            "DEMO_MODE=true требует корректный DEMO_NOW, например 2026-09-18T18:00:00+03:00"
        )
    return parsed


def business_date(value: date | datetime | str | None = None) -> date:
    """Московская бизнес-дата для value или для app_now()."""
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if len(text) >= 10:
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                pass
        parsed = parse_demo_now(text)
        if parsed is not None:
            return parsed.date()
        raise ValueError(f"Некорректная бизнес-дата: {value}")
    if isinstance(value, datetime):
        current = value if value.tzinfo else value.replace(tzinfo=MSK_TZ)
        return current.astimezone(MSK_TZ).date()
    if isinstance(value, date):
        return value
    return app_now().date()


def resolve_db_path() -> Path:
    """Путь SQLite: ROP_DB_PATH из env или обычный production-файл."""
    raw = os.getenv("ROP_DB_PATH", "").strip()
    if not raw:
        return BASE_DIR / _PRODUCTION_DB_RELATIVE
    path = Path(raw)
    return path if path.is_absolute() else BASE_DIR / path


def resolve_knowledge_dir() -> Path:
    """OKF/tactics: в demo берём runtime-копию snapshot, иначе tracked knowledge."""
    tracked = BASE_DIR / "knowledge" / "clients" / "praktikm"
    if not is_demo_mode():
        return tracked
    runtime_dir = BASE_DIR / "runtime" / "knowledge" / "clients" / "praktikm"
    return runtime_dir if runtime_dir.is_dir() else tracked


def resolve_persisted_path(value: str | Path | None) -> Path:
    """Открыть сохранённый путь. В DEMO_MODE ``/app/...`` указывает на локальное дерево."""
    text = str(value or "").strip()
    if not text:
        return Path("__missing_persisted_path__")
    path = Path(text)
    if not is_demo_mode():
        return path
    posix = text.replace("\\", "/")
    if posix == _CONTAINER_KNOWLEDGE_PREFIX or posix.startswith(_CONTAINER_KNOWLEDGE_PREFIX + "/"):
        suffix = posix[len(_CONTAINER_KNOWLEDGE_PREFIX) :].lstrip("/")
        root = BASE_DIR / "runtime" / "knowledge"
        if not root.is_dir():
            root = BASE_DIR / "knowledge"
        return root / suffix if suffix else root
    if posix == _CONTAINER_ROOT:
        return BASE_DIR
    if posix.startswith(_CONTAINER_ROOT + "/"):
        return BASE_DIR / posix[len(_CONTAINER_ROOT) + 1 :]
    return path


def runtime_info() -> dict[str, object]:
    current = app_now()
    return {
        "demo_mode": is_demo_mode(),
        "current_business_datetime": current.isoformat(timespec="seconds"),
        "business_date": current.date().isoformat(),
        "timezone": "Europe/Moscow",
    }
