from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/programming", tags=["programming"])

DEFAULT_REPO_PATH = r"C:\Users\Cooper\Programming\dashboard-of-my-life"
REPO_PATH = os.environ.get("GIT_REPO_PATH", DEFAULT_REPO_PATH)
GIT_TIMEOUT_SECONDS = 3.0


class ProgrammingStatus(BaseModel):
    available: bool
    message: str | None = None
    project_name: str | None = None
    branch: str | None = None
    commit_hash: str | None = None
    commit_message: str | None = None
    commit_author: str | None = None
    commit_date: str | None = None
    changed_files: int | None = None
    ahead: int | None = None
    behind: int | None = None


def _run_git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", REPO_PATH, *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def _parse_status_porcelain(output: str) -> tuple[str | None, int, int, int]:
    branch: str | None = None
    ahead = behind = changed_files = 0

    for line in output.splitlines():
        if line.startswith("# branch.head "):
            branch = line.removeprefix("# branch.head ")
        elif line.startswith("# branch.ab "):
            for part in line.removeprefix("# branch.ab ").split():
                if part.startswith("+"):
                    ahead = int(part[1:])
                elif part.startswith("-"):
                    behind = int(part[1:])
        elif not line.startswith("#"):
            changed_files += 1

    return branch, ahead, behind, changed_files


def _project_name() -> str:
    # A bind-mounted repo (e.g. Docker's /repo) has a meaningless folder name, so
    # prefer the actual GitHub repo name from the remote URL when one exists.
    remote_url = _run_git("remote", "get-url", "origin")
    if remote_url:
        name = remote_url.rstrip("/").rsplit("/", 1)[-1]
        return name.removesuffix(".git")
    return Path(REPO_PATH).name


@router.get("/status", response_model=ProgrammingStatus)
def get_programming_status() -> ProgrammingStatus:
    if not Path(REPO_PATH).is_dir():
        return ProgrammingStatus(available=False, message=f"Repo path not found: {REPO_PATH}")

    status_output = _run_git("status", "--porcelain=v2", "--branch")
    if status_output is None:
        return ProgrammingStatus(
            available=False,
            message=f"'{REPO_PATH}' isn't a git repository (or git isn't available here).",
        )

    branch, ahead, behind, changed_files = _parse_status_porcelain(status_output)

    log_output = _run_git("log", "-1", "--pretty=%s\x1f%an\x1f%cI")
    commit_message = commit_author = commit_date = None
    if log_output:
        parts = log_output.split("\x1f")
        if len(parts) == 3:
            commit_message, commit_author, commit_date = parts

    commit_hash = _run_git("rev-parse", "--short", "HEAD")
    project_name = _project_name()

    return ProgrammingStatus(
        available=True,
        project_name=project_name,
        branch=branch,
        commit_hash=commit_hash,
        commit_message=commit_message,
        commit_author=commit_author,
        commit_date=commit_date,
        changed_files=changed_files,
        ahead=ahead,
        behind=behind,
    )
