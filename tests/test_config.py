from pathlib import Path

import yaml

CFG = yaml.safe_load(
    (Path(__file__).parent.parent / "config.yaml").read_text(encoding="utf-8"))


def test_every_entry_has_aliases():
    entries = list(CFG.get("apps", {}).values()) + list(CFG.get("games", {}).values())
    entries += list(CFG.get("sites", {}).values()) + [CFG.get("browser", {})]
    for item in entries:
        assert item.get("aliases"), item


def test_games_have_launcher_and_id():
    for name, g in CFG.get("games", {}).items():
        assert g["launcher"] in ("battlenet", "steam"), name
        key = "game_id" if g["launcher"] == "battlenet" else "app_id"
        assert key in g, f"{name}: немає {key}"


def test_no_alias_collisions():
    seen = {}
    groups = [CFG.get("apps", {}), CFG.get("games", {}), CFG.get("sites", {})]
    for group in groups:
        for name, item in group.items():
            for a in item["aliases"]:
                a = a.lower()
                assert a not in seen, f"'{a}' є і в {seen[a]}, і в {name}"
                seen[a] = name