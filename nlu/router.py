from __future__ import annotations

import re

from rapidfuzz import fuzz

from commands.registry import FIXED, PREFIX, FREEFORM

OK = "ok"   # handler succeeded but has nothing to say


def normalize(text: str) -> str:
    # Keep in sync with registry._norm, phrases are stored normalized the same way
    text = text.lower().strip()
    # Whisper writes "one hundred dollars" as "$100", keep the currency as a word
    text = re.sub(r"\$\s*(\d[\d,.]*)", r"\1 dollars", text)
    text = re.sub(r"[^\w\s.]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" .")


def _raw_rest(raw: str, verb: str) -> str | None:
    """Text after the verb in the original (not normalized) phrase."""
    m = re.match(rf"\W*{re.escape(verb)}\b\W*", raw, re.IGNORECASE)
    return raw[m.end():].strip() if m else None


def _try_prefix(t: str, cfg: dict, raw: str = "") -> str | None:
    for verbs, fn in PREFIX:
        # Longest verb first, so "запусти" wins over a shorter prefix
        for v in sorted(verbs, key=len, reverse=True):
            if not t.startswith(v):   # no space needed: Whisper sometimes glues "OpenWarcraft"
                continue
            rest = t[len(v):].strip(" .")
            if not rest:
                continue
            if getattr(fn, "wants_raw", False):
                # Dictation needs a whole word, "type" must not match "typescript"
                if not t.startswith(v + " "):
                    continue
                rest = _raw_rest(raw, v) or rest
            reply = fn(cfg, rest)
            if reply is not None:
                return reply
    return None


def _try_fixed(t: str, cfg: dict, threshold: int) -> str | None:
    best_fn, best_score = None, 0
    for phrases, fn in FIXED:
        for p in phrases:
            score = fuzz.ratio(t, p)
            if score > best_score:
                best_fn, best_score = fn, score
    if best_fn and best_score >= threshold:
        return best_fn(cfg)
    return None


def _try_freeform(t: str, cfg: dict) -> str | None:
    for fn in FREEFORM:
        reply = fn(cfg, t)
        if reply is not None:
            return reply
    return None


def route(text: str, cfg: dict, threshold: int = 82) -> str | None:
    """Order: "verb + target" commands, then free-form parsers, then fuzzy fixed phrases."""
    t = normalize(text)
    if not t:
        return None
    reply = _try_prefix(t, cfg, text)
    if reply is not None:
        return reply
    reply = _try_freeform(t, cfg)
    if reply is not None:
        return reply
    return _try_fixed(t, cfg, threshold)