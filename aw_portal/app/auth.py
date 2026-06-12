"""Placeholder auth dependency — V1 has no auth.

Routers depend on `current_user` so middleware can be added later without
touching every endpoint signature.
"""
from __future__ import annotations


def current_user():
    # V1: anonymous advisor. Replace with real auth when introduced.
    return {"id": "advisor", "role": "advisor"}
