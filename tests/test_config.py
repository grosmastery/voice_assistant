from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
FILES = [p for p in (ROOT / "config.yaml", ROOT / "config.example.yaml") if p.exists()]

pytestmark = pytest.mark.skipif(not FILES, reason="no config.yaml / config.example.yaml")


@pytest.fixture(params=FILES, ids=lambda p: p.name)
def real_cfg(request):
    return yaml.safe_load(request.param.read_text(encoding="utf-8"))


def _entries(c):
    items = {}
    for group in ("apps", "games", "sites"):
        items.update({f"{group}.{k}": v for k, v in c.get(group, {}).items()})
    if "browser" in c:
        items["browser"] = c["browser"]
    return items


def test_all_entries_are_dicts(real_cfg):
    # broken indentation turns game fields into top-level keys
    for group in ("apps", "games", "sites"):
        for name, item in real_cfg.get(group, {}).items():
            assert isinstance(item, dict), f"{group}.{name} must be a mapping"


def test_every_entry_has_aliases(real_cfg):
    for name, item in _entries(real_cfg).items():
        assert item.get("aliases"), name


def test_aliases_are_not_too_short(real_cfg):
    for name, item in _entries(real_cfg).items():
        for a in item["aliases"]:
            assert len(str(a)) >= 4, f"{name}: alias '{a}' is too short for fuzzy matching"


def test_no_alias_collisions(real_cfg):
    seen = {}
    for name, item in _entries(real_cfg).items():
        for a in item["aliases"]:
            a = str(a).lower()
            assert a not in seen, f"'{a}' is in both {seen[a]} and {name}"
            seen[a] = name


def test_games_have_launcher_and_id(real_cfg):
    for name, g in real_cfg.get("games", {}).items():
        assert g["launcher"] in ("battlenet", "steam"), name
        key = "game_id" if g["launcher"] == "battlenet" else "app_id"
        assert key in g, f"{name}: missing {key}"


def test_process_names_look_like_executables(real_cfg):
    for name, item in _entries(real_cfg).items():
        procs = item.get("process")
        if procs is None:
            continue
        for p in ([procs] if isinstance(procs, str) else procs):
            assert p.lower().endswith(".exe"), f"{name}: '{p}'"


def test_say_is_text_or_list_of_text(real_cfg):
    for name, item in _entries(real_cfg).items():
        say = item.get("say")
        if say is None:
            continue
        values = say if isinstance(say, list) else [say]
        assert all(isinstance(v, str) and v.strip() for v in values), name


def test_games_launchers_have_matching_app(real_cfg):
    # the Battle.net launcher must be listed in apps so its path can be found
    if any(g["launcher"] == "battlenet" for g in real_cfg.get("games", {}).values()):
        assert "battlenet" in real_cfg.get("apps", {})