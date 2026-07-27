from __future__ import annotations

import colorsys
import json
import os
import secrets
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from PIL import Image, ImageStat
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# spotify.py lives at app/backend/app/spotify/spotify.py, so this source tree
# layout only holds for a normal (non-frozen, non-container) run. Docker's
# image flattens app/backend's contents into /app - a different depth - and a
# frozen desktop .exe has no source tree at all, so both need their own path
# resolution rather than reusing this one blindly.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent.parent


def _is_containerized() -> bool:
    return os.path.exists("/.dockerenv")


def _resolve_env_file() -> Path:
    """Find app/backend/.env - including when frozen into a desktop .exe.

    A PyInstaller build has no source tree to resolve parents[2] against, so
    __file__-based lookup silently fails there. sys.executable still points
    at the real .exe on disk, so look next to it (and one level up, which is
    where the .exe already ends up relative to app/backend/.env today).
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for candidate in (exe_dir / ".env", exe_dir.parent / ".env"):
            if candidate.is_file():
                return candidate
        return exe_dir / ".env"
    return BACKEND_ROOT / ".env"


load_dotenv(_resolve_env_file())


def _resolve_data_dir() -> Path:
    """Where spotify_tokens.json/spotify_settings.json are stored.

    Overridable via SPOTIFY_DATA_DIR (Docker sets this to its bind-mounted
    /app/data, since the container's flattened layout breaks the parents[]
    math above). A frozen .exe has the same problem as _resolve_env_file - no
    source tree - so it's resolved from sys.executable instead, landing on
    the same repo-root/data folder a native run would use.
    """
    override = os.environ.get("SPOTIFY_DATA_DIR", "").strip()
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        # dist/DashboardOfMyLife.exe -> backend -> app -> repo root
        return Path(sys.executable).resolve().parents[3] / "data"
    return REPOSITORY_ROOT / "data"


DATA_DIR = _resolve_data_dir()
TOKEN_FILE = DATA_DIR / "spotify_tokens.json"
SETTINGS_FILE = DATA_DIR / "spotify_settings.json"


# ---------------------------------------------------------------------------
# Spotify URLs and requested permissions
# ---------------------------------------------------------------------------

SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_PLAYBACK_URL = "https://api.spotify.com/v1/me/player"

SPOTIFY_SCOPES = "user-read-currently-playing user-read-playback-state"

REQUEST_TIMEOUT_SECONDS = 10.0
STATE_LIFETIME_SECONDS = 10 * 60

DEFAULT_CARD_COLOR = "#18181B"
DEFAULT_TEXT_COLOR = "#FFFFFF"

router = APIRouter(prefix="/spotify", tags=["spotify"])


# ---------------------------------------------------------------------------
# Settings: .env provides the bootstrap defaults, but the client ID/secret can
# be changed at runtime (e.g. from the UI, if a Spotify app registration gets
# rotated) via /spotify/credentials. Runtime changes are saved to a small JSON
# file and take priority over .env on every subsequent request.
# ---------------------------------------------------------------------------


class SpotifySettings(NamedTuple):
    client_id: str
    client_secret: str
    redirect_uri: str
    frontend_url: str


def _default_redirect_uri() -> str:
    return (
        os.environ.get("SPOTIFY_REDIRECT_URI", "").strip()
        or "http://127.0.0.1:8000/spotify/callback"
    )


def _default_frontend_url() -> str:
    fallback = (
        "http://localhost:3000/spotify" if _is_containerized() else "http://127.0.0.1:8000/spotify"
    )
    return os.environ.get("SPOTIFY_FRONTEND_URL", "").strip() or fallback


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        tmp_path.replace(path)
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"Could not save {path.name}.") from error


def _get_settings() -> SpotifySettings:
    saved = _read_json(SETTINGS_FILE)
    env_client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    env_client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    return SpotifySettings(
        client_id=saved.get("client_id") or env_client_id,
        client_secret=saved.get("client_secret") or env_client_secret,
        redirect_uri=saved.get("redirect_uri") or _default_redirect_uri(),
        frontend_url=saved.get("frontend_url") or _default_frontend_url(),
    )


# ---------------------------------------------------------------------------
# Temporary in-memory caches
# ---------------------------------------------------------------------------

# Remembers valid Spotify login attempts, keyed by their CSRF state token.
_pending_states: dict[str, float] = {}

# Remembers colours already calculated for artwork, keyed by artwork URL.
_artwork_color_cache: dict[str, tuple[str, str]] = {}


# ---------------------------------------------------------------------------
# API response/request models
# ---------------------------------------------------------------------------


class SpotifyStatus(BaseModel):
    configured: bool
    connected: bool
    message: str
    login_url: str
    redirect_uri: str


class SpotifyCredentialsUpdate(BaseModel):
    client_id: str
    client_secret: str
    redirect_uri: str | None = None


class SpotifyItem(BaseModel):
    id: str | None = None
    type: str
    name: str
    artists: list[str]
    album: str | None = None
    artwork_url: str | None = None
    dominant_color: str
    text_color: str
    spotify_url: str | None = None
    duration_ms: int


class SpotifyDevice(BaseModel):
    id: str | None = None
    name: str
    type: str
    is_active: bool
    volume_percent: int | None = None


class SpotifyNowPlaying(BaseModel):
    connected: bool
    is_playing: bool
    progress_ms: int
    shuffle_state: bool
    repeat_state: str
    item: SpotifyItem | None = None
    device: SpotifyDevice | None = None


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _spotify_is_configured(settings: SpotifySettings) -> bool:
    return bool(settings.client_id and settings.client_secret and settings.redirect_uri)


def _require_spotify_configuration(settings: SpotifySettings) -> None:
    if _spotify_is_configured(settings):
        return

    missing = [
        name
        for name, value in (
            ("client ID", settings.client_id),
            ("client secret", settings.client_secret),
            ("redirect URI", settings.redirect_uri),
        )
        if not value
    ]
    raise HTTPException(
        status_code=503,
        detail=f"Spotify is not configured. Missing: {', '.join(missing)}.",
    )


# ---------------------------------------------------------------------------
# Token-file helpers
# ---------------------------------------------------------------------------


def _load_tokens() -> dict[str, Any] | None:
    tokens = _read_json(TOKEN_FILE)
    return tokens or None


def _save_tokens(token_data: dict[str, Any]) -> None:
    _write_json(TOKEN_FILE, token_data)


def _clear_tokens() -> None:
    try:
        TOKEN_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _spotify_is_connected() -> bool:
    tokens = _load_tokens()
    refresh_token = (tokens or {}).get("refresh_token")
    return bool(isinstance(refresh_token, str) and refresh_token)


# ---------------------------------------------------------------------------
# Authorization-state helpers (CSRF protection for the OAuth redirect)
# ---------------------------------------------------------------------------


def _remove_expired_states() -> None:
    now = time.time()
    expired = [state for state, expires_at in _pending_states.items() if expires_at < now]
    for state in expired:
        _pending_states.pop(state, None)


def _create_authorization_state() -> str:
    _remove_expired_states()
    state = secrets.token_urlsafe(32)
    _pending_states[state] = time.time() + STATE_LIFETIME_SECONDS
    return state


def _consume_authorization_state(state: str) -> bool:
    expires_at = _pending_states.pop(state, None)
    return expires_at is not None and expires_at >= time.time()


# ---------------------------------------------------------------------------
# Spotify token exchange and refresh
# ---------------------------------------------------------------------------


async def _exchange_authorization_code(code: str, settings: SpotifySettings) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                SPOTIFY_TOKEN_URL,
                auth=(settings.client_id, settings.client_secret),
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502, detail="The backend could not contact Spotify."
        ) from error

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=f"Spotify rejected the token exchange with status {response.status_code}.",
        )

    token_data = _parse_token_response(response)

    if not isinstance(token_data.get("access_token"), str) or not token_data["access_token"]:
        raise HTTPException(status_code=502, detail="Spotify did not return an access token.")
    if not isinstance(token_data.get("refresh_token"), str) or not token_data["refresh_token"]:
        raise HTTPException(status_code=502, detail="Spotify did not return a refresh token.")

    token_data["expires_at"] = time.time() + _expires_in_seconds(token_data)
    token_data["authorized_at"] = time.time()
    return token_data


def _parse_token_response(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=502, detail="Spotify returned an invalid token response."
        ) from error
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Spotify returned an invalid token response.")
    return data


def _expires_in_seconds(token_data: dict[str, Any], default: int = 3600) -> int:
    try:
        return int(token_data.get("expires_in", default))
    except (TypeError, ValueError):
        return default


async def _refresh_access_token(stored_tokens: dict[str, Any], settings: SpotifySettings) -> str:
    refresh_token = stored_tokens.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        _clear_tokens()
        raise HTTPException(status_code=401, detail="Spotify must be connected again.")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                SPOTIFY_TOKEN_URL,
                auth=(settings.client_id, settings.client_secret),
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502, detail="The backend could not refresh the Spotify token."
        ) from error

    if response.status_code == 400:
        error_data = _parse_token_response_safe(response)
        if error_data.get("error") == "invalid_grant":
            _clear_tokens()
            raise HTTPException(
                status_code=401, detail="Spotify authorization expired. Connect Spotify again."
            )

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=f"Spotify rejected the token refresh with status {response.status_code}.",
        )

    refreshed = _parse_token_response(response)
    access_token = refreshed.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=502, detail="Spotify did not return a refreshed access token."
        )

    # Spotify does not always return a new refresh token - keep the existing
    # one when the response does not include another.
    updated_tokens = {
        **stored_tokens,
        **refreshed,
        "refresh_token": refreshed.get("refresh_token", refresh_token),
        "expires_at": time.time() + _expires_in_seconds(refreshed),
    }
    _save_tokens(updated_tokens)
    return access_token


def _parse_token_response_safe(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


async def _get_access_token(settings: SpotifySettings) -> str:
    _require_spotify_configuration(settings)

    stored_tokens = _load_tokens()
    if stored_tokens is None:
        raise HTTPException(status_code=401, detail="Spotify is not connected.")

    access_token = stored_tokens.get("access_token")
    expires_at = stored_tokens.get("expires_at", 0)
    token_is_valid = (
        isinstance(access_token, str)
        and bool(access_token)
        and isinstance(expires_at, (int, float))
        and expires_at > time.time() + 30
    )
    if token_is_valid:
        return access_token

    return await _refresh_access_token(stored_tokens, settings)


# ---------------------------------------------------------------------------
# Artwork-colour helpers
# ---------------------------------------------------------------------------


def _rgb_to_hex(color: tuple[int, int, int]) -> str:
    red, green, blue = color
    return f"#{red:02X}{green:02X}{blue:02X}"


def _choose_text_color(background: tuple[int, int, int]) -> str:
    """Choose black or white text based on background brightness (WCAG relative luminance)."""

    def linearise(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = background
    luminance = 0.2126 * linearise(red) + 0.7152 * linearise(green) + 0.0722 * linearise(blue)
    return "#111111" if luminance > 0.42 else "#FFFFFF"


def _extract_dominant_color(image_bytes: bytes) -> tuple[str, str]:
    """Find a useful accent colour from downloaded album artwork."""
    try:
        with Image.open(BytesIO(image_bytes)) as source_image:
            image = source_image.convert("RGB")
            image.thumbnail((96, 96), Image.Resampling.LANCZOS)
            quantized = image.quantize(colors=12, method=Image.Quantize.MEDIANCUT)

            color_counts = quantized.getcolors()
            palette = quantized.getpalette()

            if color_counts and palette:
                candidates: list[tuple[float, tuple[int, int, int]]] = []
                for count, palette_index in color_counts:
                    offset = palette_index * 3
                    color = (palette[offset], palette[offset + 1], palette[offset + 2])
                    _, lightness, saturation = colorsys.rgb_to_hls(
                        *(channel / 255 for channel in color)
                    )

                    # Prefer colours that are common and visibly colourful;
                    # very dark/light colours are penalised so a useful album
                    # accent wins over background black/white when possible.
                    brightness_weight = 0.15 if lightness < 0.08 or lightness > 0.92 else 1.0
                    score = count * (0.5 + 2.0 * saturation) * brightness_weight
                    candidates.append((score, color))

                if candidates:
                    _, dominant_rgb = max(candidates, key=lambda candidate: candidate[0])
                    return _rgb_to_hex(dominant_rgb), _choose_text_color(dominant_rgb)

            # Fallback: the image's average colour.
            average = tuple(round(channel) for channel in ImageStat.Stat(image).mean[:3])
            if len(average) == 3:
                average_rgb = (int(average[0]), int(average[1]), int(average[2]))
                return _rgb_to_hex(average_rgb), _choose_text_color(average_rgb)
    except (OSError, ValueError):
        pass

    return DEFAULT_CARD_COLOR, DEFAULT_TEXT_COLOR


async def _get_artwork_colors(artwork_url: str | None) -> tuple[str, str]:
    if not artwork_url:
        return DEFAULT_CARD_COLOR, DEFAULT_TEXT_COLOR

    cached = _artwork_color_cache.get(artwork_url)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            response = await client.get(artwork_url)
    except httpx.RequestError:
        return DEFAULT_CARD_COLOR, DEFAULT_TEXT_COLOR

    if response.is_error:
        return DEFAULT_CARD_COLOR, DEFAULT_TEXT_COLOR

    colors = _extract_dominant_color(response.content)

    # Keep this in-memory cache from growing forever.
    if len(_artwork_color_cache) >= 100:
        _artwork_color_cache.pop(next(iter(_artwork_color_cache)), None)
    _artwork_color_cache[artwork_url] = colors

    return colors


# ---------------------------------------------------------------------------
# Spotify playback parsing
# ---------------------------------------------------------------------------


def _get_first_image_url(images: object) -> str | None:
    if not isinstance(images, list):
        return None
    for image in images:
        if isinstance(image, dict) and isinstance(image.get("url"), str) and image["url"]:
            return image["url"]
    return None


async def _parse_spotify_item(raw_item: dict[str, Any]) -> SpotifyItem:
    """Convert Spotify's track or episode object into our simpler format."""
    item_type = str(raw_item.get("type") or "track")

    artists: list[str] = []
    album_name: str | None = None
    artwork_url: str | None = None

    if item_type == "episode":
        show = raw_item.get("show")
        show = show if isinstance(show, dict) else {}

        publisher = show.get("publisher")
        show_name = show.get("name")
        if isinstance(publisher, str) and publisher:
            artists.append(publisher)
        elif isinstance(show_name, str) and show_name:
            artists.append(show_name)

        album_name = show_name if isinstance(show_name, str) and show_name else None
        artwork_url = _get_first_image_url(raw_item.get("images")) or _get_first_image_url(
            show.get("images")
        )
    else:
        for raw_artist in raw_item.get("artists") or []:
            if (
                isinstance(raw_artist, dict)
                and isinstance(raw_artist.get("name"), str)
                and raw_artist["name"]
            ):
                artists.append(raw_artist["name"])

        album = raw_item.get("album")
        album = album if isinstance(album, dict) else {}
        raw_album_name = album.get("name")
        album_name = raw_album_name if isinstance(raw_album_name, str) and raw_album_name else None
        artwork_url = _get_first_image_url(album.get("images"))

    dominant_color, text_color = await _get_artwork_colors(artwork_url)

    external_urls = raw_item.get("external_urls")
    external_urls = external_urls if isinstance(external_urls, dict) else {}
    spotify_url = (
        external_urls.get("spotify") if isinstance(external_urls.get("spotify"), str) else None
    )

    raw_id = raw_item.get("id")
    raw_name = raw_item.get("name")
    try:
        duration_ms = int(raw_item.get("duration_ms", 0))
    except (TypeError, ValueError):
        duration_ms = 0

    return SpotifyItem(
        id=raw_id if isinstance(raw_id, str) else None,
        type=item_type,
        name=raw_name if isinstance(raw_name, str) and raw_name else "Unknown",
        artists=artists,
        album=album_name,
        artwork_url=artwork_url,
        dominant_color=dominant_color,
        text_color=text_color,
        spotify_url=spotify_url,
        duration_ms=duration_ms,
    )


def _parse_spotify_device(raw_device: object) -> SpotifyDevice | None:
    if not isinstance(raw_device, dict):
        return None

    raw_id = raw_device.get("id")
    raw_name = raw_device.get("name")
    raw_type = raw_device.get("type")
    raw_volume = raw_device.get("volume_percent")

    return SpotifyDevice(
        id=raw_id if isinstance(raw_id, str) else None,
        name=raw_name if isinstance(raw_name, str) and raw_name else "Unknown device",
        type=raw_type if isinstance(raw_type, str) and raw_type else "Unknown",
        is_active=bool(raw_device.get("is_active")),
        volume_percent=raw_volume if isinstance(raw_volume, int) else None,
    )


async def _request_playback(access_token: str) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            return await client.get(
                SPOTIFY_PLAYBACK_URL,
                params={"additional_types": "track,episode"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502, detail="The backend could not contact Spotify."
        ) from error


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=SpotifyStatus)
def get_spotify_status() -> SpotifyStatus:
    """Report Spotify configuration and connection status."""
    settings = _get_settings()
    configured = _spotify_is_configured(settings)
    connected = configured and _spotify_is_connected()

    if not configured:
        message = "Spotify credentials are missing."
    elif connected:
        message = "Spotify is connected."
    else:
        message = "Spotify is configured but not connected."

    return SpotifyStatus(
        configured=configured,
        connected=connected,
        message=message,
        login_url="/spotify/login",
        redirect_uri=settings.redirect_uri,
    )


@router.post("/credentials", response_model=SpotifyStatus)
def update_spotify_credentials(payload: SpotifyCredentialsUpdate) -> SpotifyStatus:
    """Save a new Spotify client ID/secret (e.g. after rotating an app registration)."""
    client_id = payload.client_id.strip()
    client_secret = payload.client_secret.strip()
    redirect_uri = (payload.redirect_uri or "").strip()

    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Client ID and secret are required.")

    saved = _read_json(SETTINGS_FILE)
    saved["client_id"] = client_id
    saved["client_secret"] = client_secret
    if redirect_uri:
        saved["redirect_uri"] = redirect_uri
    _write_json(SETTINGS_FILE, saved)

    # Tokens issued under the previous app registration won't work with a
    # different client ID, so clear them and require a fresh connection.
    _clear_tokens()

    return get_spotify_status()


@router.get("/login")
def spotify_login() -> RedirectResponse:
    """Redirect the browser to Spotify's permission screen."""
    settings = _get_settings()
    _require_spotify_configuration(settings)

    query = {
        "client_id": settings.client_id,
        "response_type": "code",
        "redirect_uri": settings.redirect_uri,
        "state": _create_authorization_state(),
        "scope": SPOTIFY_SCOPES,
        "show_dialog": "true",
    }
    return RedirectResponse(url=f"{SPOTIFY_AUTHORIZE_URL}?{urlencode(query)}", status_code=302)


@router.get("/callback")
async def spotify_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Receive Spotify's callback, exchange the code for tokens, then redirect back to the app."""
    settings = _get_settings()
    _require_spotify_configuration(settings)

    if not state or not _consume_authorization_state(state):
        raise HTTPException(
            status_code=400,
            detail="The Spotify authorization state was invalid or expired. Start login again.",
        )

    if error:
        return RedirectResponse(
            url=f"{settings.frontend_url}?spotify_error={error}", status_code=302
        )

    if not code:
        raise HTTPException(status_code=400, detail="Spotify did not return an authorization code.")

    token_data = await _exchange_authorization_code(code, settings)
    _save_tokens(token_data)

    return RedirectResponse(url=f"{settings.frontend_url}?spotify_connected=1", status_code=302)


@router.get("/now-playing", response_model=SpotifyNowPlaying)
async def get_now_playing() -> SpotifyNowPlaying:
    """Return the user's current Spotify playback information."""
    settings = _get_settings()
    access_token = await _get_access_token(settings)
    response = await _request_playback(access_token)

    # The token may have been revoked before its saved expiry time - try
    # refreshing it once before reporting an authorization failure.
    if response.status_code == 401:
        stored_tokens = _load_tokens()
        if stored_tokens is None:
            raise HTTPException(status_code=401, detail="Spotify is not connected.")
        access_token = await _refresh_access_token(stored_tokens, settings)
        response = await _request_playback(access_token)

    # Spotify returns 204 when there is no active playback.
    if response.status_code == 204:
        return SpotifyNowPlaying(
            connected=True, is_playing=False, progress_ms=0, shuffle_state=False, repeat_state="off"
        )

    if response.status_code == 401:
        _clear_tokens()
        raise HTTPException(status_code=401, detail="Spotify must be connected again.")

    if response.status_code == 403:
        raise HTTPException(
            status_code=403, detail="Spotify did not grant the required playback permissions."
        )

    if response.status_code == 429:
        raise HTTPException(
            status_code=429, detail="Spotify's request limit was reached. Try again shortly."
        )

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=f"Spotify playback request failed with status {response.status_code}.",
        )

    try:
        playback = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=502, detail="Spotify returned invalid playback information."
        ) from error
    if not isinstance(playback, dict):
        raise HTTPException(
            status_code=502, detail="Spotify returned invalid playback information."
        )

    raw_item = playback.get("item")
    parsed_item = await _parse_spotify_item(raw_item) if isinstance(raw_item, dict) else None

    try:
        progress_ms = int(playback.get("progress_ms") or 0)
    except (TypeError, ValueError):
        progress_ms = 0

    raw_repeat_state = playback.get("repeat_state")

    return SpotifyNowPlaying(
        connected=True,
        is_playing=bool(playback.get("is_playing")),
        progress_ms=progress_ms,
        shuffle_state=bool(playback.get("shuffle_state")),
        repeat_state=raw_repeat_state if isinstance(raw_repeat_state, str) else "off",
        item=parsed_item,
        device=_parse_spotify_device(playback.get("device")),
    )
