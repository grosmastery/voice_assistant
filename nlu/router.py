import re
from rapidfuzz import fuzz
from commands.registry import FIXED, PREFIX

def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s.]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" .")

def route(text: str, cfg: dict, threshold: int = 82):
    t = normalize(text)
    if not t:
        return None

    for verbs, fn in PREFIX:
        for v in sorted(verbs, key=len, reverse=True):
            if t.startswith(v):
                rest = t[len(v):].strip(" .")
                if rest:
                    return fn(cfg, rest)

    best_fn, best_score = None, 0
    for phrases, fn in FIXED:
        for p in phrases:
            score = fuzz.ratio(t, p)
            if score > best_score:
                best_fn, best_score = fn, score
    if best_score >= threshold:
        return best_fn(cfg)
    return None