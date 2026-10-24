"""Spotify playback through the Web API (needs Spotify Premium).

One-time setup:
  1. developer.spotify.com/dashboard -> Create app, Redirect URI: REDIRECT_URI,
     API: "Web API". Copy the Client ID into config.yaml -> spotify.client_id
  2. python spotify_login.py   (opens the browser once, the token is cached)
"""
from __future__ import annotations

import os
import random
import socket
import time

import requests
import spotipy
from rapidfuzz import fuzz, process
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyPKCE

from . import registry
from .registry import with_target

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "user-modify-playback-state user-read-playback-state user-library-read"
CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          ".spotify_cache")
DEVICE_WAIT = 15      # seconds to wait for the desktop app to appear as a device
ARTIST_SCORE = 85     # query this close to an artist name -> play the artist

VERBS = ("play", "увімкни", "включи", "постав")
LIKED = (
    "my liked songs", "liked songs", "my likes", "my favorites", "my favourites",
    "my favorite songs", "my favourite songs", "favorite songs", "my favorite music",
    "my music", "улюблені", "улюблені пісні", "улюблені треки", "мої улюблені",
    "мої улюблені пісні", "мої улюблені треки", "мою музику", "мої вподобані",
)
ARTIST_MARKERS = ("songs by", "music by", "something by", "the artist", "artist",
                  "виконавця", "пісні", "музику")
TRACK_MARKERS = ("the song", "song", "the track", "track", "пісню", "трек")
SUFFIXES = ("on spotify", "in spotify", "from spotify", "на спотіфай", "в спотіфай",
            "у спотіфай", "на spotify", "в spotify", "у spotify")

_client: spotipy.Spotify | None = None


def _auth(cfg: dict) -> SpotifyPKCE:
    s = cfg.get("spotify", {})
    return SpotifyPKCE(client_id=s["client_id"],
                       redirect_uri=s.get("redirect_uri", REDIRECT_URI),
                       scope=SCOPES, cache_handler=CacheFileHandler(cache_path=CACHE_PATH))


def _get_client(cfg: dict) -> spotipy.Spotify | None:
    """Client with a cached login, or None if Spotify isn't set up yet."""
    global _client
    if _client is None:
        if not cfg.get("spotify", {}).get("client_id"):
            return None
        auth = _auth(cfg)
        if not auth.cache_handler.get_cached_token():
            return None   # never block the main loop on a browser login
        _client = spotipy.Spotify(auth_manager=auth, retries=1)
    return _client


def _is_fixed_phrase(rest: str) -> bool:
    # "play the music", "постав на паузу" belong to media.py, not to a search
    full = [f"{v} {rest}" for v in VERBS]
    return any(fuzz.ratio(f, p) >= 90
               for phrases, _ in registry.FIXED for p in phrases for f in full)


def parse_request(rest: str) -> tuple[str, str]:
    """'numb by linkin park' -> (query, mode), mode: liked | artist | track | auto."""
    q = rest
    for s in SUFFIXES:
        if q.endswith(" " + s):
            q = q[:-len(s)].strip()
    if process.extractOne(q, LIKED, scorer=fuzz.ratio, score_cutoff=85):
        return "", "liked"
    for mode, markers in (("artist", ARTIST_MARKERS), ("track", TRACK_MARKERS)):
        for m in sorted(markers, key=len, reverse=True):
            if q.startswith(m + " "):
                return q[len(m):].strip(), mode
    return q, "auto"


def _pick_device(sp: spotipy.Spotify, cfg: dict) -> str | None:
    devices = sp.devices().get("devices", [])
    if not devices:
        # Desktop app closed: start it and wait until it registers
        try:
            os.startfile(cfg.get("_resolved", {}).get("spotify") or "spotify:")
        except OSError:
            return None
        deadline = time.time() + DEVICE_WAIT
        while not devices and time.time() < deadline:
            time.sleep(1)
            devices = sp.devices().get("devices", [])
    if not devices:
        return None
    # This PC first (desktop app uses the computer name), then the active one
    host = socket.gethostname().lower()
    for d in devices:
        if d.get("type") == "Computer" and d.get("name", "").lower() == host:
            return d["id"]
    for d in devices:
        if d.get("is_active"):
            return d["id"]
    return devices[0]["id"]


def _shuffle(sp: spotipy.Spotify, device: str, on: bool) -> None:
    try:
        sp.shuffle(on, device_id=device)
    except spotipy.SpotifyException:
        pass   # not critical, playback already started


def _play_liked(sp: spotipy.Spotify, device: str) -> str:
    user = sp.current_user()["id"]
    try:
        sp.start_playback(device_id=device, context_uri=f"spotify:user:{user}:collection")
    except spotipy.SpotifyException:
        # Some accounts reject the collection context, play the latest likes instead
        items = sp.current_user_saved_tracks(limit=50).get("items", [])
        uris = [i["track"]["uri"] for i in items if i.get("track")]
        if not uris:
            return "Your liked songs are empty"
        random.shuffle(uris)
        sp.start_playback(device_id=device, uris=uris)
    _shuffle(sp, device, True)
    return "Playing your liked songs"


def _play_artist(sp: spotipy.Spotify, device: str, artist: dict) -> str:
    sp.start_playback(device_id=device, context_uri=artist["uri"])
    _shuffle(sp, device, True)
    return f"Playing {artist['name']}"


def _play_track(sp: spotipy.Spotify, device: str, track: dict) -> str:
    # Album as the context, so music keeps going after the song ends
    sp.start_playback(device_id=device, context_uri=track["album"]["uri"],
                      offset={"uri": track["uri"]})
    _shuffle(sp, device, False)
    return f"Playing {track['name']} by {track['artists'][0]['name']}"


def _search(sp: spotipy.Spotify, query: str, mode: str) -> tuple[str, dict] | None:
    if mode != "artist" and " by " in query:
        title, artist = query.split(" by ", 1)
        found = sp.search(q=f"track:{title} artist:{artist}", type="track", limit=1)
        items = found["tracks"]["items"]
        if items:
            return "track", items[0]
    types = {"artist": "artist", "track": "track"}.get(mode, "artist,track")
    found = sp.search(q=query, type=types, limit=1)
    artists = found.get("artists", {}).get("items", [])
    tracks = found.get("tracks", {}).get("items", [])
    if artists and (mode == "artist"
                    or fuzz.ratio(query, artists[0]["name"].lower()) >= ARTIST_SCORE):
        return "artist", artists[0]
    if tracks:
        return "track", tracks[0]
    if artists:
        return "artist", artists[0]
    return None


@with_target(*VERBS)
def play_spotify(cfg: dict, rest: str) -> str | None:
    if _is_fixed_phrase(rest):
        return None
    query, mode = parse_request(rest)
    if mode != "liked" and not query:
        return None

    sp = _get_client(cfg)
    if sp is None:
        print("[spotify] not set up: add spotify.client_id to config.yaml "
              "and run: python spotify_login.py")
        return "Spotify is not connected yet"
    try:
        device = _pick_device(sp, cfg)
        if device is None:
            return "I couldn't find Spotify on this computer"
        if mode == "liked":
            return _play_liked(sp, device)
        found = _search(sp, query, mode)
        if found is None:
            return f"I couldn't find {query} on Spotify"
        kind, item = found
        return _play_artist(sp, device, item) if kind == "artist" else _play_track(sp, device, item)
    except spotipy.SpotifyException as exc:
        if exc.http_status == 403:
            return "Spotify Premium is needed for that"
        if exc.http_status == 404:
            return "Spotify isn't open on any device"
        return "Spotify returned an error"
    except requests.RequestException:
        return "I couldn't reach Spotify"


def login(config_path: str = "config.yaml") -> None:
    """Interactive one-time login, run from spotify_login.py."""
    import yaml
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg.get("spotify", {}).get("client_id"):
        raise SystemExit("Put your app's Client ID into config.yaml -> spotify.client_id")
    sp = spotipy.Spotify(auth_manager=_auth(cfg))
    print(f"Logged in to Spotify as {sp.current_user()['display_name']}")
