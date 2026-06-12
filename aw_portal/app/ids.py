from __future__ import annotations

import uuid


def short() -> str:
    return uuid.uuid4().hex[:8]


def client_id() -> str:
    return f"c-{short()}"


def account_id() -> str:
    return f"a-{short()}"


def liability_id() -> str:
    return f"l-{short()}"


def report_id() -> str:
    return f"rep-{short()}"


def entry_id() -> str:
    return f"e-{short()}"
