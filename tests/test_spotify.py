import pytest
import requests
import spotipy

from commands import spotify
from nlu.router import route

HOST = "MY-PC"


class FakeSp:
    """Fake spotipy client that records playback calls."""

    def __init__(self, devices=None, artists=(), tracks=(), fail_collection=False,
                 error=None):
        self._devices = [{"id": "pc", "name": HOST, "type": "Computer", "is_active": False}] \
            if devices is None else devices
        self.artists, self.tracks = list(artists), list(tracks)
        self.fail_collection, self.error = fail_collection, error
        self.played, self.shuffled, self.queries = [], [], []

    def devices(self):
        return {"devices": self._devices}

    def search(self, q, type, limit):
        self.queries.append((q, type))
        out = {}
        if "artist" in type.split(","):
            out["artists"] = {"items": self.artists}
        if "track" in type.split(","):
            out["tracks"] = {"items": self.tracks}
        return out

    def start_playback(self, **kw):
        if self.error:
            raise self.error
        if self.fail_collection and "collection" in (kw.get("context_uri") or ""):
            raise spotipy.SpotifyException(400, -1, "bad context")
        self.played.append(kw)

    def shuffle(self, state, device_id):
        self.shuffled.append(state)

    def current_user(self):
        return {"id": "me", "display_name": "Me"}

    def current_user_saved_tracks(self, limit):
        return {"items": [{"track": {"uri": "spotify:track:a"}},
                          {"track": {"uri": "spotify:track:b"}}]}


LINKIN = {"name": "Linkin Park", "uri": "spotify:artist:lp"}
NUMB = {"name": "Numb", "uri": "spotify:track:numb", "album": {"uri": "spotify:album:meteora"},
        "artists": [LINKIN]}


@pytest.fixture
def sp(monkeypatch):
    def use(**kw):
        fake = FakeSp(**kw)
        monkeypatch.setattr(spotify, "_get_client", lambda cfg: fake)
        return fake
    monkeypatch.setattr(spotify.socket, "gethostname", lambda: HOST)
    return use


# ---- parsing ----
@pytest.mark.parametrize("rest, expected", [
    ("my liked songs", ("", "liked")),
    ("my favorite songs on spotify", ("", "liked")),
    ("улюблені треки", ("", "liked")),
    ("songs by linkin park", ("linkin park", "artist")),
    ("виконавця океан ельзи", ("океан ельзи", "artist")),
    ("музику linkin park", ("linkin park", "artist")),
    ("the song numb", ("numb", "track")),
    ("пісню обійми", ("обійми", "track")),
    ("numb by linkin park on spotify", ("numb by linkin park", "auto")),
    ("linkin park", ("linkin park", "auto")),
])
def test_parse_request(rest, expected):
    assert spotify.parse_request(rest) == expected


def test_media_phrases_are_not_searched():
    assert spotify._is_fixed_phrase("the music")
    assert spotify._is_fixed_phrase("на паузу")
    assert not spotify._is_fixed_phrase("numb")


# ---- playback ----
def test_artist_when_name_matches(cfg, sp):
    fake = sp(artists=[LINKIN], tracks=[NUMB])
    assert route("play Linkin Park", cfg) == "Playing Linkin Park"
    assert fake.played == [{"device_id": "pc", "context_uri": "spotify:artist:lp"}]
    assert fake.shuffled == [True]


def test_track_when_name_differs_from_artist(cfg, sp):
    fake = sp(artists=[LINKIN], tracks=[NUMB])
    assert route("play numb", cfg) == "Playing Numb by Linkin Park"
    assert fake.played[0]["context_uri"] == "spotify:album:meteora"
    assert fake.played[0]["offset"] == {"uri": "spotify:track:numb"}


def test_title_by_artist_uses_field_search(cfg, sp):
    fake = sp(tracks=[NUMB])
    assert route("Play Numb by Linkin Park", cfg) == "Playing Numb by Linkin Park"
    assert fake.queries[0] == ("track:numb artist:linkin park", "track")


def test_ukrainian_artist(cfg, sp):
    okean = {"name": "Океан Ельзи", "uri": "spotify:artist:oe"}
    fake = sp(artists=[okean])
    assert route("увімкни виконавця Океан Ельзи", cfg) == "Playing Океан Ельзи"
    assert fake.queries == [("океан ельзи", "artist")]


def test_liked_songs(cfg, sp):
    fake = sp()
    assert route("play my liked songs", cfg) == "Playing your liked songs"
    assert fake.played == [{"device_id": "pc", "context_uri": "spotify:user:me:collection"}]


def test_liked_songs_fallback_to_track_list(cfg, sp):
    fake = sp(fail_collection=True)
    assert route("увімкни улюблені", cfg) == "Playing your liked songs"
    assert sorted(fake.played[0]["uris"]) == ["spotify:track:a", "spotify:track:b"]


def test_nothing_found(cfg, sp):
    sp()
    assert route("play qwertyuiop", cfg) == "I couldn't find qwertyuiop on Spotify"


def test_media_commands_still_work(cfg, sp, monkeypatch):
    fake = sp()
    monkeypatch.setattr("commands.media.press", lambda k, times=1: None)
    assert route("play the music", cfg) == "Playing"
    assert route("постав на паузу", cfg) == "Paused"
    assert fake.queries == []


# ---- devices ----
def test_prefers_this_pc_over_active_phone(cfg, sp):
    fake = sp(artists=[LINKIN], devices=[
        {"id": "phone", "name": "Pixel", "type": "Smartphone", "is_active": True},
        {"id": "pc", "name": "my-pc", "type": "Computer", "is_active": False},
    ])
    route("play linkin park", cfg)
    assert fake.played[0]["device_id"] == "pc"


def test_starts_desktop_app_when_no_device(cfg, sp, monkeypatch):
    fake = sp(artists=[LINKIN], devices=[])
    started = []

    def startfile(target):
        started.append(target)
        fake._devices = [{"id": "pc", "name": HOST, "type": "Computer"}]

    monkeypatch.setattr(spotify.os, "startfile", startfile)
    monkeypatch.setattr(spotify.time, "sleep", lambda s: None)
    assert route("play linkin park", cfg) == "Playing Linkin Park"
    assert started == [cfg["_resolved"]["spotify"]]


def test_no_device_after_wait(cfg, sp, monkeypatch):
    sp(devices=[])
    monkeypatch.setattr(spotify.os, "startfile", lambda t: None)
    monkeypatch.setattr(spotify.time, "sleep", lambda s: None)
    monkeypatch.setattr(spotify, "DEVICE_WAIT", 0)
    assert route("play linkin park", cfg) == "I couldn't find Spotify on this computer"


# ---- errors / setup ----
@pytest.mark.parametrize("error, reply", [
    (spotipy.SpotifyException(403, -1, "premium"), "Spotify Premium is needed for that"),
    (spotipy.SpotifyException(404, -1, "no device"), "Spotify isn't open on any device"),
    (spotipy.SpotifyException(500, -1, "boom"), "Spotify returned an error"),
    (requests.ConnectionError(), "I couldn't reach Spotify"),
])
def test_errors(cfg, sp, error, reply):
    sp(artists=[LINKIN], error=error)
    assert route("play linkin park", cfg) == reply


def test_not_configured(cfg, monkeypatch):
    monkeypatch.setattr(spotify, "_client", None)
    assert route("play linkin park", cfg) == "Spotify is not connected yet"


def test_not_logged_in(cfg, monkeypatch, tmp_path):
    monkeypatch.setattr(spotify, "_client", None)
    monkeypatch.setattr(spotify, "CACHE_PATH", str(tmp_path / "none"))
    cfg["spotify"] = {"client_id": "abc"}
    assert spotify._get_client(cfg) is None
