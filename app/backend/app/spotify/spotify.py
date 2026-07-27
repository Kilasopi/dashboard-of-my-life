from __future__ import annotations

import colorsys
import json
import os
import secrets
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from PIL import Image, ImageStat
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------

# spotify.py is located at:
# app/backend/app/spotify/spotify.py
#
# parents[2] points to:
# app/backend
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

load_dotenv(ENV_FILE)


SPOTIFY_CLIENT_ID = os.environ.get(
    "SPOTIFY_CLIENT_ID",
    "",
).strip()

SPOTIFY_CLIENT_SECRET = os.environ.get(
    "SPOTIFY_CLIENT_SECRET",
    "",
).strip()

SPOTIFY_REDIRECT_URI = os.environ.get(
    "SPOTIFY_REDIRECT_URI",
    "http://127.0.0.1:8000/spotify/callback",
).strip()


# ---------------------------------------------------------------------------
# Spotify URLs and requested permissions
# ---------------------------------------------------------------------------

SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_PLAYBACK_URL = "https://api.spotify.com/v1/me/player"

SPOTIFY_SCOPES = " ".join(
    [
        "user-read-currently-playing",
        "user-read-playback-state",
    ]
)


# ---------------------------------------------------------------------------
# Local token storage
# ---------------------------------------------------------------------------

# spotify.py is located at:
# repository/app/backend/app/spotify/spotify.py
#
# parents[4] points to the repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]

TOKEN_FILE = (
    REPOSITORY_ROOT
    / "data"
    / "spotify_tokens.json"
)


# ---------------------------------------------------------------------------
# General settings
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT_SECONDS = 10.0
STATE_LIFETIME_SECONDS = 10 * 60

DEFAULT_CARD_COLOR = "#18181B"
DEFAULT_TEXT_COLOR = "#FFFFFF"


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/spotify",
    tags=["spotify"],
)


# ---------------------------------------------------------------------------
# Temporary in-memory caches
# ---------------------------------------------------------------------------

# Remembers valid Spotify login attempts.
_pending_states: dict[str, float] = {}

# Remembers colours that have already been calculated for artwork.
#
# Example:
# {
#     "https://i.scdn.co/image/example": ("#7A4338", "#FFFFFF")
# }
_artwork_color_cache: dict[str, tuple[str, str]] = {}


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class SpotifyStatus(BaseModel):
    configured: bool
    connected: bool
    message: str
    login_url: str


class SpotifyCallbackResult(BaseModel):
    success: bool
    connected: bool
    message: str


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
# Spotify configuration helpers
# ---------------------------------------------------------------------------

def _spotify_is_configured() -> bool:
    """Return True when all required Spotify settings exist."""

    return bool(
        SPOTIFY_CLIENT_ID
        and SPOTIFY_CLIENT_SECRET
        and SPOTIFY_REDIRECT_URI
    )


def _require_spotify_configuration() -> None:
    """Stop a request when required Spotify settings are missing."""

    if _spotify_is_configured():
        return

    missing_settings: list[str] = []

    if not SPOTIFY_CLIENT_ID:
        missing_settings.append("SPOTIFY_CLIENT_ID")

    if not SPOTIFY_CLIENT_SECRET:
        missing_settings.append("SPOTIFY_CLIENT_SECRET")

    if not SPOTIFY_REDIRECT_URI:
        missing_settings.append("SPOTIFY_REDIRECT_URI")

    raise HTTPException(
        status_code=503,
        detail=(
            "Spotify is not configured. Missing: "
            + ", ".join(missing_settings)
        ),
    )


# ---------------------------------------------------------------------------
# Token-file helpers
# ---------------------------------------------------------------------------

def _load_tokens() -> dict[str, Any] | None:
    """Read saved Spotify tokens from the local token file."""

    try:
        with TOKEN_FILE.open(
            "r",
            encoding="utf-8",
        ) as token_file:
            token_data = json.load(token_file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None

    if not isinstance(token_data, dict):
        return None

    return token_data


def _save_tokens(token_data: dict[str, Any]) -> None:
    """Safely save Spotify tokens to the local data directory."""

    TOKEN_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = TOKEN_FILE.with_name(
        f"{TOKEN_FILE.name}.tmp"
    )

    try:
        with temporary_file.open(
            "w",
            encoding="utf-8",
        ) as token_file:
            json.dump(
                token_data,
                token_file,
                indent=2,
            )

        temporary_file.replace(TOKEN_FILE)
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail="The Spotify token file could not be saved.",
        ) from error


def _clear_tokens() -> None:
    """Remove locally stored Spotify authorization."""

    try:
        TOKEN_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _spotify_is_connected() -> bool:
    """Return True when a saved Spotify refresh token exists."""

    token_data = _load_tokens()

    if token_data is None:
        return False

    refresh_token = token_data.get("refresh_token")

    return bool(
        isinstance(refresh_token, str)
        and refresh_token
    )


# ---------------------------------------------------------------------------
# Authorization-state helpers
# ---------------------------------------------------------------------------

def _remove_expired_states() -> None:
    """Remove Spotify login attempts older than ten minutes."""

    current_time = time.time()

    expired_states = [
        state
        for state, expires_at in _pending_states.items()
        if expires_at < current_time
    ]

    for state in expired_states:
        _pending_states.pop(state, None)


def _create_authorization_state() -> str:
    """Create and remember a secure state for one login attempt."""

    _remove_expired_states()

    state = secrets.token_urlsafe(32)

    _pending_states[state] = (
        time.time() + STATE_LIFETIME_SECONDS
    )

    return state


def _consume_authorization_state(state: str) -> bool:
    """Validate a state value and prevent it from being reused."""

    expires_at = _pending_states.pop(state, None)

    if expires_at is None:
        return False

    return expires_at >= time.time()


# ---------------------------------------------------------------------------
# Spotify token exchange and refresh
# ---------------------------------------------------------------------------

async def _exchange_authorization_code(
    code: str,
) -> dict[str, Any]:
    """Exchange Spotify's temporary code for access and refresh tokens."""

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as client:
            response = await client.post(
                SPOTIFY_TOKEN_URL,
                auth=(
                    SPOTIFY_CLIENT_ID,
                    SPOTIFY_CLIENT_SECRET,
                ),
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": SPOTIFY_REDIRECT_URI,
                },
                headers={
                    "Content-Type": (
                        "application/x-www-form-urlencoded"
                    ),
                },
            )
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail="The backend could not contact Spotify.",
        ) from error

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Spotify rejected the token exchange "
                f"with status {response.status_code}."
            ),
        )

    try:
        token_data = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="Spotify returned an invalid token response.",
        ) from error

    if not isinstance(token_data, dict):
        raise HTTPException(
            status_code=502,
            detail="Spotify returned an invalid token response.",
        )

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=502,
            detail="Spotify did not return an access token.",
        )

    if not isinstance(refresh_token, str) or not refresh_token:
        raise HTTPException(
            status_code=502,
            detail="Spotify did not return a refresh token.",
        )

    expires_in = token_data.get("expires_in", 3600)

    try:
        expires_in_seconds = int(expires_in)
    except (TypeError, ValueError):
        expires_in_seconds = 3600

    token_data["expires_at"] = (
        time.time() + expires_in_seconds
    )
    token_data["authorized_at"] = time.time()

    return token_data


async def _refresh_access_token(
    stored_tokens: dict[str, Any],
) -> str:
    """Use the refresh token to obtain a new access token."""

    refresh_token = stored_tokens.get("refresh_token")

    if not isinstance(refresh_token, str) or not refresh_token:
        _clear_tokens()

        raise HTTPException(
            status_code=401,
            detail="Spotify must be connected again.",
        )

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as client:
            response = await client.post(
                SPOTIFY_TOKEN_URL,
                auth=(
                    SPOTIFY_CLIENT_ID,
                    SPOTIFY_CLIENT_SECRET,
                ),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={
                    "Content-Type": (
                        "application/x-www-form-urlencoded"
                    ),
                },
            )
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail="The backend could not refresh the Spotify token.",
        ) from error

    if response.status_code == 400:
        try:
            error_data = response.json()
        except ValueError:
            error_data = {}

        if error_data.get("error") == "invalid_grant":
            _clear_tokens()

            raise HTTPException(
                status_code=401,
                detail=(
                    "Spotify authorization expired. "
                    "Connect Spotify again."
                ),
            )

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Spotify rejected the token refresh "
                f"with status {response.status_code}."
            ),
        )

    try:
        refreshed_tokens = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="Spotify returned an invalid refresh response.",
        ) from error

    if not isinstance(refreshed_tokens, dict):
        raise HTTPException(
            status_code=502,
            detail="Spotify returned an invalid refresh response.",
        )

    access_token = refreshed_tokens.get("access_token")

    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=502,
            detail="Spotify did not return a refreshed access token.",
        )

    # Spotify does not always return a new refresh token.
    # Keep the existing one when the response does not include another.
    new_refresh_token = refreshed_tokens.get(
        "refresh_token",
        refresh_token,
    )

    expires_in = refreshed_tokens.get("expires_in", 3600)

    try:
        expires_in_seconds = int(expires_in)
    except (TypeError, ValueError):
        expires_in_seconds = 3600

    updated_tokens = {
        **stored_tokens,
        **refreshed_tokens,
        "refresh_token": new_refresh_token,
        "expires_at": time.time() + expires_in_seconds,
    }

    _save_tokens(updated_tokens)

    return access_token


async def _get_access_token() -> str:
    """Return a working access token, refreshing it when needed."""

    _require_spotify_configuration()

    stored_tokens = _load_tokens()

    if stored_tokens is None:
        raise HTTPException(
            status_code=401,
            detail="Spotify is not connected.",
        )

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

    return await _refresh_access_token(stored_tokens)


# ---------------------------------------------------------------------------
# Artwork-colour helpers
# ---------------------------------------------------------------------------

def _rgb_to_hex(color: tuple[int, int, int]) -> str:
    """Convert an RGB colour such as (122, 67, 56) into #7A4338."""

    red, green, blue = color

    return f"#{red:02X}{green:02X}{blue:02X}"


def _choose_text_color(
    background: tuple[int, int, int],
) -> str:
    """Choose black or white text based on background brightness."""

    def linearise(channel: int) -> float:
        value = channel / 255

        if value <= 0.04045:
            return value / 12.92

        return ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = background

    luminance = (
        0.2126 * linearise(red)
        + 0.7152 * linearise(green)
        + 0.0722 * linearise(blue)
    )

    if luminance > 0.42:
        return "#111111"

    return "#FFFFFF"


def _extract_dominant_color(
    image_bytes: bytes,
) -> tuple[str, str]:
    """Find a useful dominant colour from downloaded album artwork."""

    try:
        with Image.open(BytesIO(image_bytes)) as source_image:
            image = source_image.convert("RGB")

            image.thumbnail(
                (96, 96),
                Image.Resampling.LANCZOS,
            )

            quantized = image.quantize(
                colors=12,
                method=Image.Quantize.MEDIANCUT,
            )

            color_counts = quantized.getcolors()
            palette = quantized.getpalette()

            if color_counts and palette:
                candidates: list[
                    tuple[float, tuple[int, int, int]]
                ] = []

                for count, palette_index in color_counts:
                    palette_position = palette_index * 3

                    color = (
                        palette[palette_position],
                        palette[palette_position + 1],
                        palette[palette_position + 2],
                    )

                    red, green, blue = color

                    _, lightness, saturation = colorsys.rgb_to_hls(
                        red / 255,
                        green / 255,
                        blue / 255,
                    )

                    # Prefer colours that are common and visibly colourful.
                    # Very dark or very light colours receive a penalty so
                    # that a useful album accent is preferred when available.
                    brightness_weight = 1.0

                    if lightness < 0.08 or lightness > 0.92:
                        brightness_weight = 0.15

                    score = (
                        count
                        * (0.5 + 2.0 * saturation)
                        * brightness_weight
                    )

                    candidates.append((score, color))

                if candidates:
                    _, dominant_rgb = max(
                        candidates,
                        key=lambda candidate: candidate[0],
                    )

                    return (
                        _rgb_to_hex(dominant_rgb),
                        _choose_text_color(dominant_rgb),
                    )

            # Fallback: calculate the image's average colour.
            statistics = ImageStat.Stat(image)

            average_rgb = tuple(
                round(channel)
                for channel in statistics.mean[:3]
            )

            if len(average_rgb) == 3:
                typed_average = (
                    int(average_rgb[0]),
                    int(average_rgb[1]),
                    int(average_rgb[2]),
                )

                return (
                    _rgb_to_hex(typed_average),
                    _choose_text_color(typed_average),
                )
    except (OSError, ValueError):
        pass

    return DEFAULT_CARD_COLOR, DEFAULT_TEXT_COLOR


async def _get_artwork_colors(
    artwork_url: str | None,
) -> tuple[str, str]:
    """Download artwork and return its dominant and readable text colours."""

    if not artwork_url:
        return DEFAULT_CARD_COLOR, DEFAULT_TEXT_COLOR

    cached_colors = _artwork_color_cache.get(artwork_url)

    if cached_colors is not None:
        return cached_colors

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = await client.get(artwork_url)
    except httpx.RequestError:
        return DEFAULT_CARD_COLOR, DEFAULT_TEXT_COLOR

    if response.is_error:
        return DEFAULT_CARD_COLOR, DEFAULT_TEXT_COLOR

    colors = _extract_dominant_color(response.content)

    # Avoid allowing this small in-memory cache to grow forever.
    if len(_artwork_color_cache) >= 100:
        oldest_key = next(iter(_artwork_color_cache))
        _artwork_color_cache.pop(oldest_key, None)

    _artwork_color_cache[artwork_url] = colors

    return colors


# ---------------------------------------------------------------------------
# Spotify playback parsing
# ---------------------------------------------------------------------------

def _get_first_image_url(
    images: object,
) -> str | None:
    """Return the first valid URL from a Spotify image list."""

    if not isinstance(images, list):
        return None

    for image in images:
        if not isinstance(image, dict):
            continue

        image_url = image.get("url")

        if isinstance(image_url, str) and image_url:
            return image_url

    return None


async def _parse_spotify_item(
    raw_item: dict[str, Any],
) -> SpotifyItem:
    """Convert Spotify's track or episode object into our simpler format."""

    item_type = str(raw_item.get("type") or "track")

    artists: list[str] = []
    album_name: str | None = None
    artwork_url: str | None = None

    if item_type == "episode":
        show = raw_item.get("show")

        if not isinstance(show, dict):
            show = {}

        publisher = show.get("publisher")
        show_name = show.get("name")

        if isinstance(publisher, str) and publisher:
            artists.append(publisher)
        elif isinstance(show_name, str) and show_name:
            artists.append(show_name)

        if isinstance(show_name, str) and show_name:
            album_name = show_name

        artwork_url = _get_first_image_url(
            raw_item.get("images")
        )

        if artwork_url is None:
            artwork_url = _get_first_image_url(
                show.get("images")
            )
    else:
        raw_artists = raw_item.get("artists")

        if isinstance(raw_artists, list):
            for raw_artist in raw_artists:
                if not isinstance(raw_artist, dict):
                    continue

                artist_name = raw_artist.get("name")

                if isinstance(artist_name, str) and artist_name:
                    artists.append(artist_name)

        album = raw_item.get("album")

        if not isinstance(album, dict):
            album = {}

        raw_album_name = album.get("name")

        if isinstance(raw_album_name, str) and raw_album_name:
            album_name = raw_album_name

        artwork_url = _get_first_image_url(
            album.get("images")
        )

    dominant_color, text_color = await _get_artwork_colors(
        artwork_url
    )

    external_urls = raw_item.get("external_urls")

    if not isinstance(external_urls, dict):
        external_urls = {}

    raw_spotify_url = external_urls.get("spotify")

    spotify_url = (
        raw_spotify_url
        if isinstance(raw_spotify_url, str)
        else None
    )

    raw_id = raw_item.get("id")

    item_id = (
        raw_id
        if isinstance(raw_id, str)
        else None
    )

    raw_name = raw_item.get("name")

    item_name = (
        raw_name
        if isinstance(raw_name, str) and raw_name
        else "Unknown"
    )

    raw_duration = raw_item.get("duration_ms", 0)

    try:
        duration_ms = int(raw_duration)
    except (TypeError, ValueError):
        duration_ms = 0

    return SpotifyItem(
        id=item_id,
        type=item_type,
        name=item_name,
        artists=artists,
        album=album_name,
        artwork_url=artwork_url,
        dominant_color=dominant_color,
        text_color=text_color,
        spotify_url=spotify_url,
        duration_ms=duration_ms,
    )


def _parse_spotify_device(
    raw_device: object,
) -> SpotifyDevice | None:
    """Convert Spotify's device object into our response format."""

    if not isinstance(raw_device, dict):
        return None

    raw_id = raw_device.get("id")
    raw_name = raw_device.get("name")
    raw_type = raw_device.get("type")
    raw_volume = raw_device.get("volume_percent")

    device_id = (
        raw_id
        if isinstance(raw_id, str)
        else None
    )

    device_name = (
        raw_name
        if isinstance(raw_name, str) and raw_name
        else "Unknown device"
    )

    device_type = (
        raw_type
        if isinstance(raw_type, str) and raw_type
        else "Unknown"
    )

    volume_percent = (
        raw_volume
        if isinstance(raw_volume, int)
        else None
    )

    return SpotifyDevice(
        id=device_id,
        name=device_name,
        type=device_type,
        is_active=bool(raw_device.get("is_active")),
        volume_percent=volume_percent,
    )


# ---------------------------------------------------------------------------
# Spotify playback request
# ---------------------------------------------------------------------------

async def _request_playback(
    access_token: str,
) -> httpx.Response:
    """Request the user's current Spotify playback state."""

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as client:
            return await client.get(
                SPOTIFY_PLAYBACK_URL,
                params={
                    "additional_types": "track,episode",
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
            )
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail="The backend could not contact Spotify.",
        ) from error


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    response_model=SpotifyStatus,
)
def get_spotify_status() -> SpotifyStatus:
    """Report Spotify configuration and connection status."""

    configured = _spotify_is_configured()
    connected = (
        configured
        and _spotify_is_connected()
    )

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
    )


@router.get("/login")
def spotify_login() -> RedirectResponse:
    """Redirect the browser to Spotify's permission screen."""

    _require_spotify_configuration()

    state = _create_authorization_state()

    query_parameters = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "state": state,
        "scope": SPOTIFY_SCOPES,
        "show_dialog": "true",
    }

    authorization_url = (
        f"{SPOTIFY_AUTHORIZE_URL}?"
        f"{urlencode(query_parameters)}"
    )

    return RedirectResponse(
        url=authorization_url,
        status_code=302,
    )


@router.get(
    "/callback",
    response_model=SpotifyCallbackResult,
)
async def spotify_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> SpotifyCallbackResult:
    """Receive Spotify's callback and exchange its code for tokens."""

    _require_spotify_configuration()

    if not state:
        raise HTTPException(
            status_code=400,
            detail="Spotify did not return an authorization state.",
        )

    if not _consume_authorization_state(state):
        raise HTTPException(
            status_code=400,
            detail=(
                "The Spotify authorization state was invalid or expired. "
                "Start the login process again."
            ),
        )

    if error:
        return SpotifyCallbackResult(
            success=False,
            connected=False,
            message=(
                "Spotify authorization was declined: "
                f"{error}"
            ),
        )

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Spotify did not return an authorization code.",
        )

    token_data = await _exchange_authorization_code(code)

    _save_tokens(token_data)

    return SpotifyCallbackResult(
        success=True,
        connected=True,
        message=(
            "Spotify authorization succeeded and the tokens "
            "were saved locally."
        ),
    )


@router.get(
    "/now-playing",
    response_model=SpotifyNowPlaying,
)
async def get_now_playing() -> SpotifyNowPlaying:
    """Return the user's current Spotify playback information."""

    access_token = await _get_access_token()
    response = await _request_playback(access_token)

    # The token may have been revoked before its saved expiry time.
    # Try refreshing it once before reporting an authorization failure.
    if response.status_code == 401:
        stored_tokens = _load_tokens()

        if stored_tokens is None:
            raise HTTPException(
                status_code=401,
                detail="Spotify is not connected.",
            )

        access_token = await _refresh_access_token(stored_tokens)
        response = await _request_playback(access_token)

    # Spotify returns 204 when there is no active playback information.
    if response.status_code == 204:
        return SpotifyNowPlaying(
            connected=True,
            is_playing=False,
            progress_ms=0,
            shuffle_state=False,
            repeat_state="off",
            item=None,
            device=None,
        )

    if response.status_code == 401:
        _clear_tokens()

        raise HTTPException(
            status_code=401,
            detail="Spotify must be connected again.",
        )

    if response.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail=(
                "Spotify did not grant the required "
                "playback permissions."
            ),
        )

    if response.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail=(
                "Spotify's request limit was reached. "
                "Try again shortly."
            ),
        )

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Spotify playback request failed "
                f"with status {response.status_code}."
            ),
        )

    try:
        playback = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="Spotify returned invalid playback information.",
        ) from error

    if not isinstance(playback, dict):
        raise HTTPException(
            status_code=502,
            detail="Spotify returned invalid playback information.",
        )

    raw_item = playback.get("item")

    parsed_item = (
        await _parse_spotify_item(raw_item)
        if isinstance(raw_item, dict)
        else None
    )

    raw_progress = playback.get("progress_ms", 0)

    try:
        progress_ms = int(raw_progress or 0)
    except (TypeError, ValueError):
        progress_ms = 0

    raw_repeat_state = playback.get("repeat_state")

    repeat_state = (
        raw_repeat_state
        if isinstance(raw_repeat_state, str)
        else "off"
    )

    return SpotifyNowPlaying(
        connected=True,
        is_playing=bool(playback.get("is_playing")),
        progress_ms=progress_ms,
        shuffle_state=bool(playback.get("shuffle_state")),
        repeat_state=repeat_state,
        item=parsed_item,
        device=_parse_spotify_device(
            playback.get("device")
        ),
    )