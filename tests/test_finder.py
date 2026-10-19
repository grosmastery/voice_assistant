from commands.finder import _pick


def test_pick_prefers_shortest_containing_name():
    names = ["Opera GX Browser", "Opera GX Browser Beta", "Uninstall Opera GX"]
    assert _pick("Opera GX", names) == "Opera GX Browser"


def test_pick_fuzzy_match():
    assert _pick("Spotfy", ["Spotify", "Steam"]) == "Spotify"


def test_pick_no_match():
    assert _pick("Zzz", ["Spotify", "Steam"]) is None


def test_pick_skips_uninstallers():
    assert _pick("Steam", ["Uninstall Steam", "Видалити Steam"]) is None