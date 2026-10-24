from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

import psutil

from .registry import command, freeform

NBU_URL = ("https://bank.gov.ua/NBUStatService/v1/statdirectory/"
           "exchange?valcode=USD&json")
RATE_TTL = 600        # seconds to keep the rate in cache
RATE_TIMEOUT = 5      # seconds per request

# Currency words (EN/UK/RU) -> currency code
CURRENCY: dict[str, str] = {}
for _w in ("dollar", "dollars", "usd", "buck", "bucks", "долар", "долари",
           "доларів", "долара", "доларах", "доллар", "доллары", "долларов"):
    CURRENCY[_w] = "USD"
for _w in ("hryvnia", "hryvnias", "hryvna", "hryvnas", "hryvnya", "hrivna", "uah",
           "гривня", "гривні", "гривень", "гривню", "гривнях", "гривна", "гривен"):
    CURRENCY[_w] = "UAH"

# Number words for parsing amounts like "two hundred dollars"
UNITS = {
    "a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "один": 1, "одна": 1, "два": 2, "дві": 2, "три": 3, "чотири": 4,
    "десять": 10, "двадцять": 20, "тридцять": 30, "сорок": 40,
}
HUNDRED = {"hundred", "сто", "sto"}   # "sto" - Whisper sometimes writes it in Latin
THOUSAND = {"thousand", "тисяча", "тисячу", "тисячі", "тисяч"}
# Words that mark a conversion request even without the target currency
QUESTION = re.compile(r"\b(how much|how many|convert|скільки|конвертуй|переведи)\b")
NUMBER = re.compile(r"\d+(\.\d+)?")

_rate_cache: dict[str, float] = {"value": 0.0, "at": 0.0}


@command("what time is it", "current time", "котра година", "скільки часу")
def current_time(cfg: dict) -> str:
    return f"It's {datetime.now():%H:%M}"


@command("what is the date", "what day is it", "today's date",
         "яка дата", "яке сьогодні число")
def current_date(cfg: dict) -> str:
    now = datetime.now()
    return f"Today is {now:%A}, {now:%B} {now.day}"


@command("system load", "pc load", "how is the pc", "cpu usage",
         "навантаження системи", "як там комп'ютер")
def system_load(cfg: dict) -> str:
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    return f"CPU {cpu:.0f} percent, memory {ram:.0f} percent"


def _usd_rate() -> float:
    """Official NBU USD->UAH rate, cached for RATE_TTL seconds."""
    if time.time() - _rate_cache["at"] < RATE_TTL and _rate_cache["value"]:
        return _rate_cache["value"]
    with urllib.request.urlopen(NBU_URL, timeout=RATE_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    rate = float(data[0]["rate"])
    _rate_cache.update(value=rate, at=time.time())
    return rate


@command("dollar rate", "dollar exchange rate", "usd rate", "exchange rate",
         "dollar to hryvnia", "how much is a dollar",
         "курс долара", "курс долар", "скільки коштує долар", "курс валют")
def dollar_rate(cfg: dict) -> str:
    try:
        rate = _usd_rate()
    except (urllib.error.URLError, TimeoutError, OSError,
            ValueError, KeyError, IndexError):
        return "I couldn't get the exchange rate"
    return f"One dollar is {rate:.2f} hryvnias"


def _is_num_token(tok: str) -> bool:
    return bool(NUMBER.fullmatch(tok)) or tok in UNITS or tok in HUNDRED or tok in THOUSAND


def _parse_amount(tokens: list[str]) -> float | None:
    """'100' | '1 000' | 'a hundred' | 'two thousand' -> number."""
    total = cur = 0.0
    prev_digit = False
    for tok in tokens:
        if NUMBER.fullmatch(tok):
            if prev_digit and re.fullmatch(r"\d{3}", tok):   # "1 000" -> 1000
                cur = cur * 1000 + int(tok)
            else:
                cur += float(tok)
            prev_digit = True
            continue
        prev_digit = False
        if tok in HUNDRED:
            cur = max(cur, 1) * 100
        elif tok in THOUSAND:
            total += max(cur, 1) * 1000
            cur = 0
        elif tok in UNITS:
            cur += UNITS[tok]
        else:
            return None
    return (total + cur) or None


def _find_amount(tokens: list[str]) -> tuple[float, str] | None:
    """First "number + currency" occurrence; returns (amount, currency)."""
    for i, tok in enumerate(tokens):
        cur = CURRENCY.get(tok)
        if not cur:
            continue
        j = i
        # Walk back over the number words before the currency
        while j > 0 and _is_num_token(tokens[j - 1]):
            j -= 1
        amount = _parse_amount(tokens[j:i]) if j < i else None
        if amount:
            return amount, cur
    return None


def _money(value: float, cur: str) -> str:
    # "1,000 dollars" / "41.25 hryvnias"
    value = round(value, 2)
    num = f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"
    if cur == "USD":
        unit = "dollar" if value == 1 else "dollars"
    else:
        unit = "hryvnia" if value == 1 else "hryvnias"
    return f"{num} {unit}"


@freeform
def convert_currency(cfg: dict, text: str) -> str | None:
    tokens = text.split()
    found = _find_amount(tokens)
    if not found:
        return None
    amount, src = found
    dst = "UAH" if src == "USD" else "USD"
    mentioned = {CURRENCY[t] for t in tokens if t in CURRENCY}
    if dst not in mentioned and not QUESTION.search(text):
        return None                       # just a mention of money, not a conversion request
    try:
        rate = _usd_rate()
    except (urllib.error.URLError, TimeoutError, OSError,
            ValueError, KeyError, IndexError):
        return "I couldn't get the exchange rate"
    result = amount * rate if src == "USD" else amount / rate
    return f"{_money(amount, src)} is {_money(result, dst)}"