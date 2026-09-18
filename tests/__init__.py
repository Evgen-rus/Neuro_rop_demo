"""Automated regression tests for the local ROP assistant."""

import os

# Локальный .env demo-репозитория не должен замораживать часы и блокировать Bitrix в suite.
os.environ.setdefault("DEMO_MODE", "false")
