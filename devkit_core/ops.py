"""All operation executors. Each takes an Operation + context and returns a Result."""
import os
import re
import glob
import shutil
import subprocess
import fnmatch
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

from .parser import Operation
from . import backup


@dataclass
class OpResult:
    op: Operation
    ok: bool = True
    message: str = ""
    files_changed: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    diff: str = ""
    output: str = ""            # for read ops (TREE, READ, SEARCH...)


class OpContext:
    def __init__(self, cwd: str, dry_run: bool = False):
        self.cwd = str(Path(cwd).resolve())
        self.dry_run = dry_run
        self.session: Optional[str] = None

    def ensure_session(self):
        if self.session is None and not self.dry_run:
            self.session = backup.make_session(self.cwd)
        return self.session

    def resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return Path(self.cwd) / p

    def rel(self, path) -> str:
        p = Path(path).resolve()
        try:
            return str(p.relative_to(self.cwd))
        except ValueError:
            return str(p)


# ─────────────────────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────────────────────
def execute(op: Operation, ctx: OpContext) -> OpResult:
    handler = HANDLERS.get(op.kind)
    if not handler:
        return OpResult(op=op, ok=False, message=f"No handler for {op.kind}")
    try:
        return handler(op, ctx)
    except Exception as e:
        return OpResult(op=op, ok=False, message=f"{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────
# FILE OPS
# ─────────────────────────────────────────────────────────────
def _write_file(path: Path, content: str, ctx: OpContext, mode: str = "w"):
    if ctx.dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode, encoding="utf-8", newline="") as f:
        f.write(content)


def _diff(old: str, new: str, filename: str) -> str:
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=2,
    ))


def op_create(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    if path.exists():
        return OpResult(op=op, ok=False, message=f"File exists: {ctx.rel(path)} (use :WRITE to overwrite)")
    _write_file(path, op.body, ctx)
    return OpResult(op=op, message=f"Created {ctx.rel(path)}",
                    files_created=[ctx.rel(path)],
                    diff=_diff("", op.body, ctx.rel(path)))


def op_write(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    if path.exists():
        backup.backup_file(ctx.ensure_session(), ctx.cwd, str(path))
    _write_file(path, op.body, ctx)
    return OpResult(op=op, message=f"Wrote {ctx.rel(path)}",
                    files_changed=[ctx.rel(path)] if path.exists() or not ctx.dry_run else [],
                    files_created=[] if old else [ctx.rel(path)],
                    diff=_diff(old, op.body, ctx.rel(path)))


def op_append(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    new = old + op.body
    if path.exists():
        backup.backup_file(ctx.ensure_session(), ctx.cwd, str(path))
    _write_file(path, new, ctx)
    return OpResult(op=op, message=f"Appended to {ctx.rel(path)}",
                    files_changed=[ctx.rel(path)],
                    diff=_diff(old, new, ctx.rel(path)))


def op_prepend(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    new = op.body + old
    if path.exists():
        backup.backup_file(ctx.ensure_session(), ctx.cwd, str(path))
    _write_file(path, new, ctx)
    return OpResult(op=op, message=f"Prepended to {ctx.rel(path)}",
                    files_changed=[ctx.rel(path)],
                    diff=_diff(old, new, ctx.rel(path)))


def op_delete(op: Operation, ctx: OpContext) -> OpResult:
    pattern = op.target
    # Support globs (including **)
    matches = _glob_all(ctx.cwd, pattern)
    if not matches:
        return OpResult(op=op, ok=False, message=f"No files match: {pattern}")

    deleted = []
    for p in matches:
        if p.is_file():
            backup.backup_file(ctx.ensure_session(), ctx.cwd, str(p))
            if not ctx.dry_run:
                p.unlink()
            deleted.append(ctx.rel(p))
    return OpResult(op=op, message=f"Deleted {len(deleted)} file(s)",
                    files_deleted=deleted)


def op_rename(op: Operation, ctx: OpContext) -> OpResult:
    src = ctx.resolve(op.target)
    dst = ctx.resolve(op.args["dst"])
    if not src.exists():
        return OpResult(op=op, ok=False, message=f"Source not found: {ctx.rel(src)}")
    if src.is_file():
        backup.backup_file(ctx.ensure_session(), ctx.cwd, str(src))
    if not ctx.dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    return OpResult(op=op, message=f"Renamed {ctx.rel(src)} → {ctx.rel(dst)}",
                    files_changed=[ctx.rel(dst)],
                    files_deleted=[ctx.rel(src)])


def op_mkdir(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    if not ctx.dry_run:
        path.mkdir(parents=True, exist_ok=True)
    return OpResult(op=op, message=f"Directory ready: {ctx.rel(path)}")


# ─────────────────────────────────────────────────────────────
# CONTENT OPS
# ─────────────────────────────────────────────────────────────
def op_replace(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    if not path.exists():
        return OpResult(op=op, ok=False, message=f"File not found: {ctx.rel(path)}")
    old = path.read_text(encoding="utf-8", errors="replace")
    if op.find not in old:
        return OpResult(op=op, ok=False, message=f"FIND text not found in {ctx.rel(path)}")
    new = old.replace(op.find, op.replace)
    if new == old:
        return OpResult(op=op, ok=True, message=f"No change in {ctx.rel(path)}")
    backup.backup_file(ctx.ensure_session(), ctx.cwd, str(path))
    _write_file(path, new, ctx)
    return OpResult(op=op, message=f"Replaced in {ctx.rel(path)}",
                    files_changed=[ctx.rel(path)],
                    diff=_diff(old, new, ctx.rel(path)))


def op_regex_replace(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    if not path.exists():
        return OpResult(op=op, ok=False, message=f"File not found: {ctx.rel(path)}")
    old = path.read_text(encoding="utf-8", errors="replace")
    try:
        new, count = re.subn(op.find, op.replace, old, flags=re.MULTILINE)
    except re.error as e:
        return OpResult(op=op, ok=False, message=f"Regex error: {e}")
    if count == 0:
        return OpResult(op=op, ok=False, message=f"Pattern not matched in {ctx.rel(path)}")
    backup.backup_file(ctx.ensure_session(), ctx.cwd, str(path))
    _write_file(path, new, ctx)
    return OpResult(op=op, message=f"Regex-replaced {count} match(es) in {ctx.rel(path)}",
                    files_changed=[ctx.rel(path)],
                    diff=_diff(old, new, ctx.rel(path)))


def op_replace_block(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    if not path.exists():
        return OpResult(op=op, ok=False, message=f"File not found: {ctx.rel(path)}")
    old = path.read_text(encoding="utf-8", errors="replace")
    from_marker = op.args["from"]
    to_marker = op.args["to"]

    if from_marker not in old:
        return OpResult(op=op, ok=False, message=f"FROM marker not found: {from_marker!r}")
    start_idx = old.index(from_marker)
    tail = old[start_idx:]
    if to_marker not in tail:
        return OpResult(op=op, ok=False, message=f"TO marker not found after FROM")
    end_idx = start_idx + tail.index(to_marker) + len(to_marker)

    new = old[:start_idx] + op.replace + old[end_idx:]
    if new == old:
        return OpResult(op=op, ok=True, message=f"No change in {ctx.rel(path)}")
    backup.backup_file(ctx.ensure_session(), ctx.cwd, str(path))
    _write_file(path, new, ctx)
    return OpResult(op=op, message=f"Replaced block in {ctx.rel(path)}",
                    files_changed=[ctx.rel(path)],
                    diff=_diff(old, new, ctx.rel(path)))


def op_insert_after(op: Operation, ctx: OpContext) -> OpResult:
    return _insert(op, ctx, before=False)


def op_insert_before(op: Operation, ctx: OpContext) -> OpResult:
    return _insert(op, ctx, before=True)


def _insert(op: Operation, ctx: OpContext, before: bool) -> OpResult:
    path = ctx.resolve(op.target)
    if not path.exists():
        return OpResult(op=op, ok=False, message=f"File not found: {ctx.rel(path)}")
    old = path.read_text(encoding="utf-8", errors="replace")
    if op.find not in old:
        return OpResult(op=op, ok=False, message=f"Anchor text not found in {ctx.rel(path)}")

    anchor_len = len(op.find)
    idx = old.index(op.find)
    if before:
        new = old[:idx] + op.replace + ("\n" if not op.replace.endswith("\n") else "") + old[idx:]
    else:
        insert_at = idx + anchor_len
        prefix = "" if old[insert_at:insert_at+1] == "\n" else "\n"
        new = old[:insert_at] + prefix + op.replace + old[insert_at:]

    backup.backup_file(ctx.ensure_session(), ctx.cwd, str(path))
    _write_file(path, new, ctx)
    verb = "before" if before else "after"
    return OpResult(op=op, message=f"Inserted {verb} anchor in {ctx.rel(path)}",
                    files_changed=[ctx.rel(path)],
                    diff=_diff(old, new, ctx.rel(path)))


def op_multi_replace(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    if not path.exists():
        return OpResult(op=op, ok=False, message=f"File not found: {ctx.rel(path)}")
    old = path.read_text(encoding="utf-8", errors="replace")
    new = old
    misses = []
    hits = 0
    for i, pr in enumerate(op.parts):
        f, w = pr["find"], pr["with"]
        if f not in new:
            misses.append(i + 1)
            continue
        new = new.replace(f, w)
        hits += 1
    if hits == 0:
        return OpResult(op=op, ok=False, message=f"No replacements matched in {ctx.rel(path)}")
    if new == old:
        return OpResult(op=op, ok=True, message=f"No change in {ctx.rel(path)}")
    backup.backup_file(ctx.ensure_session(), ctx.cwd, str(path))
    _write_file(path, new, ctx)
    msg = f"Applied {hits}/{len(op.parts)} replacements in {ctx.rel(path)}"
    if misses:
        msg += f" (missed chunks: {misses})"
    return OpResult(op=op, message=msg,
                    files_changed=[ctx.rel(path)],
                    diff=_diff(old, new, ctx.rel(path)))


# ─────────────────────────────────────────────────────────────
# READ OPS
# ─────────────────────────────────────────────────────────────
DEFAULT_EXCLUDES = {
    "node_modules", ".git", "dist", "build", "__pycache__", ".next",
    ".devkit-backups", ".venv", "venv", ".idea", ".vscode", "coverage",
}


def op_tree(op: Operation, ctx: OpContext) -> OpResult:
    root = ctx.resolve(op.target or ".")
    depth = op.args.get("depth", 999)
    includes = op.args.get("include", [])
    excludes = set(op.args.get("exclude", []))
    excludes.update(DEFAULT_EXCLUDES)

    lines = [str(ctx.rel(root)) + "/"]

    def walk(path: Path, prefix: str, level: int):
        if level >= depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return
        entries = [e for e in entries if e.name not in excludes and not e.name.startswith(".") or e.name in (".env", ".gitignore")]
        if includes:
            entries = [e for e in entries if e.is_dir() or any(fnmatch.fnmatch(e.name, pat) for pat in includes)]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            branch = "└── " if is_last else "├── "
            lines.append(prefix + branch + entry.name + ("/" if entry.is_dir() else ""))
            if entry.is_dir():
                walk(entry, prefix + ("    " if is_last else "│   "), level + 1)

    walk(root, "", 0)
    output = "\n".join(lines)
    return OpResult(op=op, message=f"Tree of {ctx.rel(root)}", output=output)


def op_read(op: Operation, ctx: OpContext) -> OpResult:
    paths = op.args.get("paths", [])
    if not paths:
        return OpResult(op=op, ok=False, message="No paths given")
    chunks = []
    for pth in paths:
        p = ctx.resolve(pth)
        if not p.exists():
            chunks.append(f"===== {pth} =====\n[NOT FOUND]\n")
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            content = f"[READ ERROR: {e}]"
        chunks.append(f"===== {pth} =====\n{content}\n")
    output = "\n".join(chunks)
    return OpResult(op=op, message=f"Read {len(paths)} file(s)", output=output)


def op_search(op: Operation, ctx: OpContext) -> OpResult:
    query = op.args.get("query", "")
    root = ctx.resolve(op.args.get("in", "."))
    exts = op.args.get("ext", [])

    if not query:
        return OpResult(op=op, ok=False, message="Empty query")

    results = []
    total_hits = 0
    for path in _iter_files(root, exts):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if query in line:
                results.append(f"{ctx.rel(path)}:{i}: {line.strip()}")
                total_hits += 1
                if total_hits > 500:
                    results.append("... (truncated at 500 hits)")
                    return OpResult(op=op, message=f"Found {total_hits} hits", output="\n".join(results))
    output = "\n".join(results) if results else "(no matches)"
    return OpResult(op=op, message=f"Found {total_hits} hit(s) for {query!r}", output=output)


def op_list(op: Operation, ctx: OpContext) -> OpResult:
    pattern = op.target or "*"
    matches = _glob_all(ctx.cwd, pattern)
    output = "\n".join(ctx.rel(m) for m in matches)
    return OpResult(op=op, message=f"{len(matches)} match(es)", output=output or "(none)")


def op_info(op: Operation, ctx: OpContext) -> OpResult:
    path = ctx.resolve(op.target)
    if not path.exists():
        return OpResult(op=op, ok=False, message=f"Not found: {ctx.rel(path)}")
    st = path.stat()
    lines = [f"Path: {ctx.rel(path)}",
             f"Type: {'directory' if path.is_dir() else 'file'}",
             f"Size: {st.st_size:,} bytes",
             f"Modified: {_fmt_time(st.st_mtime)}"]
    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            lines.append(f"Lines: {len(text.splitlines()):,}")
        except Exception:
            pass
    return OpResult(op=op, message=f"Info: {ctx.rel(path)}", output="\n".join(lines))


# ─────────────────────────────────────────────────────────────
# UTILITY OPS
# ─────────────────────────────────────────────────────────────
def op_run(op: Operation, ctx: OpContext) -> OpResult:
    cmd = op.args.get("cmd", "")
    if not cmd:
        return OpResult(op=op, ok=False, message="Empty command")
    if ctx.dry_run:
        return OpResult(op=op, message=f"[dry-run] would run: {cmd}", output="")
    try:
        proc = subprocess.run(cmd, shell=True, cwd=ctx.cwd,
                              capture_output=True, text=True, timeout=300)
        output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        return OpResult(op=op, ok=proc.returncode == 0,
                        message=f"Exit {proc.returncode}: {cmd}",
                        output=output)
    except subprocess.TimeoutExpired:
        return OpResult(op=op, ok=False, message="Command timed out (300s)")


def op_install(op: Operation, ctx: OpContext) -> OpResult:
    # Detect package manager
    if (Path(ctx.cwd) / "package.json").exists():
        cmd = f"npm install {op.args['cmd']}"
    elif (Path(ctx.cwd) / "requirements.txt").exists() or (Path(ctx.cwd) / "pyproject.toml").exists():
        cmd = f"pip install {op.args['cmd']}"
    else:
        return OpResult(op=op, ok=False, message="Can't detect package manager (no package.json/requirements.txt)")
    op.args["cmd"] = cmd
    return op_run(op, ctx)


def op_gitadd(op: Operation, ctx: OpContext) -> OpResult:
    op2 = Operation(kind="RUN", args={"cmd": f"git add {op.target}"}, line_no=op.line_no)
    return op_run(op2, ctx)


def op_gitcommit(op: Operation, ctx: OpContext) -> OpResult:
    msg = op.args.get("msg", "devkit commit")
    op2 = Operation(kind="RUN", args={"cmd": f'git commit -m "{msg}"'}, line_no=op.line_no)
    return op_run(op2, ctx)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _glob_all(cwd: str, pattern: str) -> List[Path]:
    p = Path(cwd)
    # Support absolute paths too
    if os.path.isabs(pattern):
        return [Path(x) for x in glob.glob(pattern, recursive=True)]
    return [p / Path(x) for x in glob.glob(pattern, recursive=True, root_dir=str(p))] \
        if hasattr(glob, "glob") and "root_dir" in glob.glob.__code__.co_varnames \
        else [Path(x) for x in glob.glob(str(p / pattern), recursive=True)]


def _iter_files(root: Path, exts: List[str]):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # Skip excluded dirs
        if any(part in DEFAULT_EXCLUDES for part in path.parts):
            continue
        if exts and path.suffix not in exts and not any(path.name.endswith(e) for e in exts):
            continue
        yield path


def _fmt_time(ts: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


HANDLERS = {
    "CREATE":         op_create,
    "WRITE":          op_write,
    "APPEND":         op_append,
    "PREPEND":        op_prepend,
    "DELETE":         op_delete,
    "RENAME":         op_rename,
    "MOVE":           op_rename,
    "MKDIR":          op_mkdir,
    "REPLACE":        op_replace,
    "REGEX_REPLACE":  op_regex_replace,
    "REPLACE_BLOCK":  op_replace_block,
    "INSERT_AFTER":   op_insert_after,
    "INSERT_BEFORE":  op_insert_before,
    "MULTI_REPLACE":  op_multi_replace,
    "TREE":           op_tree,
    "READ":           op_read,
    "SEARCH":         op_search,
    "LIST":           op_list,
    "INFO":           op_info,
    "RUN":            op_run,
    "INSTALL":        op_install,
    "GITADD":         op_gitadd,
    "GITCOMMIT":      op_gitcommit,
}
