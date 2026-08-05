"""
qml_bridge.py — QML context property registration.

Extracted from main.py to keep the entry-point focused on startup wiring.
Call ``register_context_properties()`` after creating the engine and all
controller instances.
"""
from __future__ import annotations

from typing import Any


def register_context_properties(engine: Any, **props: Any) -> None:
    """
    Register all Python objects as QML context properties.

    Usage in main.py::

        from qml_bridge import register_context_properties
        register_context_properties(
            engine,
            app=controller,
            clientApp=client_controller,
            ...
        )
    """
    ctx = engine.rootContext()
    for name, value in props.items():
        ctx.setContextProperty(name, value)
