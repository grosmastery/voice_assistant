import ctypes

import pytest

from commands import dictation
from nlu.router import route


@pytest.fixture
def sent(monkeypatch):
    events = []

    def fake_send(inputs):
        events.extend((i.u.ki.wScan, i.u.ki.dwFlags) for i in inputs)
        return len(inputs)

    monkeypatch.setattr(dictation, "_send", fake_send)
    return events


@pytest.fixture
def typed(monkeypatch):
    out = []
    monkeypatch.setattr(dictation, "type_text", lambda t: out.append(t) or len(t))
    return out


def test_input_struct_size():
    # Windows rejects SendInput if the struct size is wrong (40 bytes on 64-bit)
    assert ctypes.sizeof(dictation.INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)


def test_type_text_sends_down_and_up(sent):
    assert dictation.type_text("Hi") == 4
    down, up = dictation.KEYEVENTF_UNICODE, dictation.KEYEVENTF_UNICODE | dictation.KEYEVENTF_KEYUP
    assert sent == [(ord("H"), down), (ord("H"), up), (ord("i"), down), (ord("i"), up)]


def test_type_text_cyrillic_and_emoji(sent):
    dictation.type_text("ї😀")
    assert sent[0][0] == ord("ї")
    assert len(sent) == 6                     # emoji is a surrogate pair: 2 units x down/up


def test_type_text_empty(sent):
    assert dictation.type_text("") == 0 and sent == []


def test_dictation_keeps_case_and_punctuation(cfg, typed):
    assert route("Type hello, World!", cfg) == "Typed: Hello, World!"
    assert typed == ["Hello, World!"]


def test_dictation_ukrainian(cfg, typed):
    route("Напиши: привіт, як справи?", cfg)
    assert typed == ["Привіт, як справи?"]


def test_verb_must_be_a_whole_word(cfg, typed):
    route("typescript is cool", cfg)
    route("writer", cfg)
    assert typed == []


def test_failed_typing(cfg, monkeypatch):
    monkeypatch.setattr(dictation, "type_text", lambda t: 0)
    assert route("type hello", cfg) == "I couldn't type that"
