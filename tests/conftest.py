import pytest

import commands  # noqa: F401  (registers commands)


@pytest.fixture
def cfg():
    return {
        "browser": {"aliases": ["browser", "opera", "браузер"], "say": "Opera GX",
                    "process": "opera.exe"},
        "apps": {
            "spotify": {"aliases": ["spotify", "спотіфай"], "say": "Spotify",
                        "process": "Spotify.exe"},
            "steam": {"aliases": ["steam", "стім"], "say": "Steam",
                      "process": "steam.exe"},
            "battlenet": {"aliases": ["battle.net", "батлнет"], "say": "Battle.net",
                          "process": "Battle.net.exe"},
        },
        "games": {
            "warcraft": {"aliases": ["warcraft", "варкрафт"],
                         "say": ["Warcraft", "World of Warcraft"],
                         "launcher": "battlenet", "game_id": "WoW",
                         "process": ["Wow.exe"]},
            "dota": {"aliases": ["dota 2", "дота"], "say": "Dota 2",
                     "launcher": "steam", "app_id": 570, "process": "dota2.exe"},
        },
        "sites": {"youtube": {"aliases": ["youtube", "ютуб"],
                              "url": "https://www.youtube.com"}},
        "_resolved": {"spotify": r"C:\fake\Spotify.lnk", "steam": r"C:\fake\Steam.lnk",
                      "battlenet": r"C:\fake\Battle.net.lnk",
                      "browser": r"C:\fake\Opera.lnk"},
        "_browser_exe": None,
    }