"""Auto-backup + undo support."""
import os
import shutil
import time
import json
from pathlib import Path
from typing import List


BACKUP_ROOT = ".devkit-backups"


def _project_root(cwd: str) -> Path:
    return Path(cwd).resolve()


def make_session(cwd: str) -> str:
    """Create a new backup session folder and return its path."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    session = _project_root(cwd) / BACKUP_ROOT / ts
    session.mkdir(parents=True, exist_ok=True)
    # Marker file
    (session / ".session").write_text(json.dumps({
        "created": ts,
        "cwd": str(_project_root(cwd)),
    }), encoding="utf-8")
    return str(session)


def backup_file(session: str, project_root: str, filepath: str) -> None:
    """Copy file into backup session, preserving relative path."""
    src = Path(filepath).resolve()
    if not src.exists():
        return
    proj = Path(project_root).resolve()
    try:
        rel = src.relative_to(proj)
    except ValueError:
        rel = Path(src.name)
    dst = Path(session) / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def list_sessions(cwd: str) -> List[str]:
    root = _project_root(cwd) / BACKUP_ROOT
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir()], reverse=True)


def restore_session(cwd: str, session_name: str) -> List[str]:
    """Copy every file from session back into the project. Returns list of restored files."""
    proj = _project_root(cwd)
    session = proj / BACKUP_ROOT / session_name
    if not session.exists():
        raise FileNotFoundError(f"Session '{session_name}' not found")

    restored = []
    for src in session.rglob("*"):
        if src.is_dir():
            continue
        if src.name == ".session":
            continue
        rel = src.relative_to(session)
        dst = proj / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored.append(str(rel))
    return restored


def prune_old(cwd: str, keep: int = 20) -> int:
    """Keep only the most recent N backup sessions. Returns count deleted."""
    sessions = list_sessions(cwd)
    if len(sessions) <= keep:
        return 0
    to_delete = sessions[keep:]
    root = _project_root(cwd) / BACKUP_ROOT
    for name in to_delete:
        shutil.rmtree(root / name, ignore_errors=True)
    return len(to_delete)
