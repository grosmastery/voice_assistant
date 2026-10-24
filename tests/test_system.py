import json
import re
import urllib.error
from types import SimpleNamespace

import pytest

from commands import system
from nlu.router import route


@pytest.fixture
def rate(monkeypatch):
    monkeypatch.setattr(system, "_usd_rate", lambda: 40.0)


# ---- time, date, load ----
def test_time(cfg):
    assert re.fullmatch(r"It's \d{2}:\d{2}", route("what time is it", cfg))
    assert re.fullmatch(r"It's \d{2}:\d{2}", route("котра година", cfg))


def test_date(cfg):
    assert route("what is the date", cfg).startswith("Today is")


def test_system_load(cfg, monkeypatch):
    monkeypatch.setattr(system.psutil, "cpu_percent", lambda interval=None: 12.0)
    monkeypatch.setattr(system.psutil, "virtual_memory",
                        lambda: SimpleNamespace(percent=50.0))
    assert route("system load", cfg) == "CPU 12 percent, memory 50 percent"


# ---- fetching the rate ----
class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def fresh_cache(monkeypatch):
    monkeypatch.setitem(system._rate_cache, "value", 0.0)
    monkeypatch.setitem(system._rate_cache, "at", 0.0)


def test_usd_rate_is_cached(monkeypatch, fresh_cache):
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        return FakeResponse([{"rate": 41.5}])

    monkeypatch.setattr(system.urllib.request, "urlopen", fake_urlopen)
    assert system._usd_rate() == 41.5
    assert system._usd_rate() == 41.5
    assert len(calls) == 1


def test_usd_rate_refetches_after_ttl(monkeypatch, fresh_cache):
    calls = []
    monkeypatch.setattr(system.urllib.request, "urlopen",
                        lambda url, timeout=None: (calls.append(1),
                                                   FakeResponse([{"rate": 40.0}]))[1])
    system._usd_rate()
    monkeypatch.setitem(system._rate_cache, "at", 0.0)   # cache is "expired"
    system._usd_rate()
    assert len(calls) == 2


def test_dollar_rate_command(cfg, rate):
    assert route("dollar rate", cfg) == "One dollar is 40.00 hryvnias"
    assert route("курс долара", cfg) == "One dollar is 40.00 hryvnias"


def test_rate_unavailable(cfg, monkeypatch):
    def boom():
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(system, "_usd_rate", boom)
    assert route("dollar rate", cfg) == "I couldn't get the exchange rate"
    assert route("how much is 100 dollars in hryvnias", cfg) == \
        "I couldn't get the exchange rate"


# ---- amount parsing ----
@pytest.mark.parametrize("tokens, expected", [
    (["100"], 100),
    (["100.5"], 100.5),
    (["1", "000"], 1000),
    (["a", "hundred"], 100),
    (["two", "thousand"], 2000),
    (["two", "thousand", "five", "hundred"], 2500),
    (["сто"], 100),
    (["foo"], None),
    ([], None),
])
def test_parse_amount(tokens, expected):
    assert system._parse_amount(tokens) == expected


def test_find_amount():
    assert system._find_amount("how much is 100 dollars".split()) == (100, "USD")
    assert system._find_amount("5000 гривень".split()) == (5000, "UAH")
    assert system._find_amount("my dollar store".split()) is None
    assert system._find_amount("dollar rate".split()) is None


def test_money_formatting():
    assert system._money(1, "USD") == "1 dollar"
    assert system._money(4000, "UAH") == "4,000 hryvnias"
    assert system._money(2.5125, "USD") == "2.51 dollars"
    assert system._money(100.5, "UAH") == "100.50 hryvnias"


# ---- conversion from phrases ----
@pytest.mark.parametrize("phrase, expected", [
    ("скільки буде гривень 100 доларів", "100 dollars is 4,000 hryvnias"),
    ("100 доларів це скільки гривень", "100 dollars is 4,000 hryvnias"),
    ("convert 100 dollars to hryvnia", "100 dollars is 4,000 hryvnias"),
    ("how many hryvnias is a hundred dollars", "100 dollars is 4,000 hryvnias"),
    ("скільки гривень 1 000 доларів", "1,000 dollars is 40,000 hryvnias"),
    ("How much is $100 in hryvnias?", "100 dollars is 4,000 hryvnias"),
    ("5000 гривень в доларах", "5,000 hryvnias is 125 dollars"),
    ("скільки доларів 100.50 гривень", "100.50 hryvnias is 2.51 dollars"),
    ("how much is one dollar", "1 dollar is 40 hryvnias"),
    ("how much is a dollar", "1 dollar is 40 hryvnias"),
])
def test_conversion(cfg, rate, phrase, expected):
    assert route(phrase, cfg) == expected


@pytest.mark.parametrize("phrase", [
    "my dollar store is open",
    "i have 100 dollars",
    "100 гривень",
])
def test_conversion_ignores_non_requests(cfg, rate, phrase):
    assert route(phrase, cfg) is None