from __future__ import annotations

import re
from typing import Callable

FixedHandler = Callable[..., "str | None"]

FIXED: list[tuple[tuple[str, ...], FixedHandler]] = []    # whole phrases: "pause the music"
PREFIX: list[tuple[tuple[str, ...], FixedHandler]] = []   # verb + target: "open <something>"
FREEFORM: list[FixedHandler] = []                         # get the whole text, return None if not theirs


def _norm(text: str) -> str:
    # Same normalization as nlu.router.normalize
    text = re.sub(r"[^\w\s.]", " ", text.lower().strip())
    return re.sub(r"\s+", " ", text).strip(" .")


def _warn_duplicates(phrases: tuple[str, ...], registry: list) -> None:
    existing = {p for ps, _ in registry for p in ps}
    for p in phrases:
        if p in existing:
            print(f"[registry] warning: phrase '{p}' registered repeatedly")


def command(*phrases: str) -> Callable[[FixedHandler], FixedHandler]:
    """Register a handler fn(cfg) for fixed phrases."""
    normalized = tuple(_norm(p) for p in phrases)

    def deco(fn: FixedHandler) -> FixedHandler:
        _warn_duplicates(normalized, FIXED)
        FIXED.append((normalized, fn))
        return fn
    return deco


def with_target(*verbs: str, raw: bool = False) -> Callable[[FixedHandler], FixedHandler]:
    """Register a handler fn(cfg, rest) for "<verb> <rest>" commands.

    raw=True: rest keeps the original case and punctuation (for dictation).
    """
    normalized = tuple(_norm(v) for v in verbs)

    def deco(fn: FixedHandler) -> FixedHandler:
        fn.wants_raw = raw
        _warn_duplicates(normalized, PREFIX)
        PREFIX.append((normalized, fn))
        return fn
    return deco


def freeform(fn: FixedHandler) -> FixedHandler:
    """Register a handler fn(cfg, text) that parses the text itself."""
    FREEFORM.append(fn)
    return fn


def clear() -> None:
    # Used by tests
    FIXED.clear()
    PREFIX.clear()
    FREEFORM.clear()