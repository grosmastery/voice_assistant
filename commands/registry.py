FIXED = []    # (фрази, обробник): команда цілком, напр. "pause the music"
PREFIX = []   # (дієслова, обробник): "open <щось>"


def command(*phrases):
    def deco(fn):
        FIXED.append((phrases, fn))
        return fn
    return deco


def with_target(*verbs):
    def deco(fn):
        PREFIX.append((verbs, fn))
        return fn
    return deco