from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/claude-usage", tags=["claude-usage"])

DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"
PROJECTS_DIR = Path(os.environ.get("CLAUDE_PROJECTS_DIR", str(DEFAULT_PROJECTS_DIR)))

# A gap longer than this between two log lines is treated as the end of a live
# session rather than the user just thinking - matches Claude Code's own idle feel.
IDLE_GAP_MINUTES = 10

# Claude's usage limit resets on a rolling window that starts at your first
# message and expires a fixed number of hours later, regardless of idle gaps in
# between - unlike the "live" coding timer above, so it's tracked separately.
LIMIT_WINDOW_HOURS = 5
# Only need enough history to find the currently active window's start; look back
# further than one window so we don't miss it if the machine just woke up, etc.
BLOCK_LOOKBACK_HOURS = 24


class TokenTotals(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    messages: int = 0


class ClaudeUsage(BaseModel):
    available: bool
    message: str | None = None
    live: bool = False
    session_started_at: datetime | None = None
    session_last_activity_at: datetime | None = None
    session_elapsed_seconds: float | None = None
    session_project: str | None = None
    today: TokenTotals = TokenTotals()
    today_sessions: int = 0
    limit_window_active: bool = False
    limit_window_started_at: datetime | None = None
    limit_window_resets_at: datetime | None = None
    limit_window_remaining_seconds: float | None = None
    limit_window: TokenTotals = TokenTotals()


def _iter_session_files() -> list[Path]:
    if not PROJECTS_DIR.is_dir():
        return []
    return list(PROJECTS_DIR.glob("*/*.jsonl"))


def _read_lines(path: Path) -> list[dict]:
    records = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records


def _parse_ts(record: dict) -> datetime | None:
    raw = record.get("timestamp")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _project_label(records: list[dict], session_file: Path) -> str:
    # Folder names mangle the real path (slashes become dashes, ambiguous with
    # hyphens in actual names), so prefer the "cwd" field logged on each record.
    for record in records:
        cwd = record.get("cwd")
        if cwd:
            return Path(cwd).name
    return session_file.parent.name


def _find_live_session() -> tuple[Path | None, list[dict]]:
    latest_file: Path | None = None
    latest_ts: datetime | None = None

    for session_file in _iter_session_files():
        try:
            mtime = datetime.fromtimestamp(session_file.stat().st_mtime, tz=UTC)
        except OSError:
            continue
        if latest_ts is None or mtime > latest_ts:
            latest_ts = mtime
            latest_file = session_file

    if latest_file is None:
        return None, []
    return latest_file, _read_lines(latest_file)


def _compute_live_session(now: datetime) -> tuple[bool, datetime | None, datetime | None, str | None]:
    session_file, records = _find_live_session()
    if session_file is None:
        return False, None, None, None

    timestamps = sorted(ts for r in records if (ts := _parse_ts(r)) is not None)
    if not timestamps:
        return False, None, None, None

    last_activity = timestamps[-1]
    gap = timedelta(minutes=IDLE_GAP_MINUTES)

    # Walk backward from the newest event to find the start of the current
    # continuous streak of activity (no gap larger than IDLE_GAP_MINUTES).
    streak_start = timestamps[-1]
    for prev, curr in zip(reversed(timestamps[:-1]), reversed(timestamps[1:])):
        if curr - prev > gap:
            break
        streak_start = prev

    live = (now - last_activity) <= gap
    return live, streak_start, last_activity, _project_label(records, session_file)


def _add_usage(totals: TokenTotals, usage: dict) -> None:
    totals.messages += 1
    totals.input_tokens += usage.get("input_tokens") or 0
    totals.output_tokens += usage.get("output_tokens") or 0
    totals.cache_read_tokens += usage.get("cache_read_input_tokens") or 0
    totals.cache_creation_tokens += usage.get("cache_creation_input_tokens") or 0


@router.get("/status", response_model=ClaudeUsage)
def get_claude_usage() -> ClaudeUsage:
    if not PROJECTS_DIR.is_dir():
        return ClaudeUsage(
            available=False,
            message=f"Claude Code project logs not found at {PROJECTS_DIR}.",
        )

    now = datetime.now(UTC)
    today = now.date()
    lookback = now - timedelta(hours=BLOCK_LOOKBACK_HOURS)

    live, started_at, last_activity, project = _compute_live_session(now)
    elapsed = (last_activity - started_at).total_seconds() if started_at and last_activity else None

    today_totals = TokenTotals()
    sessions_today: set[Path] = set()

    # (timestamp, usage) for every logged message in the lookback window, across
    # all projects - the rolling limit window isn't scoped to one project.
    recent_usage_events: list[tuple[datetime, dict]] = []

    for session_file in _iter_session_files():
        for record in _read_lines(session_file):
            ts = _parse_ts(record)
            if ts is None:
                continue
            usage = (record.get("message") or {}).get("usage")
            if not usage:
                continue

            if ts.date() == today:
                _add_usage(today_totals, usage)
                sessions_today.add(session_file)

            if ts >= lookback:
                recent_usage_events.append((ts, usage))

    recent_usage_events.sort(key=lambda pair: pair[0])

    # Group into rolling limit windows: a new window starts whenever the gap since
    # the current window's start reaches LIMIT_WINDOW_HOURS, mirroring how Claude's
    # own 5-hour usage limit resets - it's anchored to when the window began, not
    # to idle time, so this must NOT reuse the idle-gap logic from the live timer.
    window_span = timedelta(hours=LIMIT_WINDOW_HOURS)
    window_start: datetime | None = None
    window_events: list[tuple[datetime, dict]] = []

    for ts, usage in recent_usage_events:
        if window_start is None or ts - window_start >= window_span:
            window_start = ts
            window_events = []
        window_events.append((ts, usage))

    limit_window = TokenTotals()
    limit_window_active = False
    resets_at: datetime | None = None
    remaining_seconds: float | None = None

    if window_start is not None and now - window_start < window_span:
        limit_window_active = True
        resets_at = window_start + window_span
        remaining_seconds = (resets_at - now).total_seconds()
        for _, usage in window_events:
            _add_usage(limit_window, usage)

    return ClaudeUsage(
        available=True,
        live=live,
        session_started_at=started_at,
        session_last_activity_at=last_activity,
        session_elapsed_seconds=elapsed,
        session_project=project,
        today=today_totals,
        today_sessions=len(sessions_today),
        limit_window_active=limit_window_active,
        limit_window_started_at=window_start if limit_window_active else None,
        limit_window_resets_at=resets_at,
        limit_window_remaining_seconds=remaining_seconds,
        limit_window=limit_window,
    )
