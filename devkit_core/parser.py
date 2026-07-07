"""
Parses DevKit script syntax into a list of Operations.

SYNTAX:
  # Single-line ops:
    DELETE path/to/file.txt
    DELETE src/**/*.bak
    RENAME src/old.ts -> src/new.ts
    MKDIR src/new/folder
    RUN npm install lodash

  # Block ops (multi-line content):
    :CREATE path/to/file.ext
    <file contents here, verbatim>
    :END

    :WRITE path/to/file.ext
    <replaces entire file>
    :END

    :APPEND path/to/file.ext
    <appended to end>
    :END

    :PREPEND path/to/file.ext
    <inserted at start>
    :END

    :REPLACE path/to/file.ext
    FIND:
    <literal text to find>
    WITH:
    <replacement text>
    :END

    :REGEX_REPLACE path/to/file.ext
    FIND: pattern here
    WITH: replacement here
    :END

    :REPLACE_BLOCK path/to/file.ext
    FROM: start marker line
    TO:   end marker line
    WITH:
    <new content between markers, replaces both markers too>
    :END

    :INSERT_AFTER path/to/file.ext
    FIND:
    <literal anchor line>
    WITH:
    <content to insert after the anchor>
    :END

    :INSERT_BEFORE path/to/file.ext
    FIND:
    <anchor>
    WITH:
    <content>
    :END

    :MULTI_REPLACE path/to/file.ext
    FIND:
    <text 1>
    WITH:
    <replacement 1>
    ---
    FIND:
    <text 2>
    WITH:
    <replacement 2>
    :END

  # Read ops (dump to output):
    :TREE root_path [--depth N] [--include *.ts,*.tsx] [--exclude node_modules,dist]
    :READ path1 path2 path3
    :SEARCH "text to find" [--in src/] [--ext .ts,.tsx]
    :LIST pattern
    :INFO path

  # Comments start with #
  # Blank lines outside of blocks are ignored.
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Operation:
    kind: str                    # e.g. "CREATE", "REPLACE"
    target: str = ""             # main path or argument
    args: Dict[str, Any] = field(default_factory=dict)
    body: str = ""               # multi-line body content
    find: str = ""               # for REPLACE-type ops
    replace: str = ""            # for REPLACE-type ops
    parts: List[Dict[str, str]] = field(default_factory=list)  # for MULTI_REPLACE
    line_no: int = 0             # source line for errors


BLOCK_OPS = {
    "CREATE", "WRITE", "APPEND", "PREPEND",
    "REPLACE", "REGEX_REPLACE",
    "REPLACE_BLOCK", "INSERT_AFTER", "INSERT_BEFORE",
    "MULTI_REPLACE",
    "TREE", "READ", "SEARCH", "LIST", "INFO",
}

INLINE_OPS = {
    "DELETE", "RENAME", "MOVE", "MKDIR",
    "RUN", "INSTALL",
    "GITADD", "GITCOMMIT",
}


class ParseError(Exception):
    pass


def parse_script(text: str) -> List[Operation]:
    """Parse a full script into a list of Operations."""
    lines = text.splitlines()
    ops: List[Operation] = []
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        line = raw.strip()
        i += 1

        # Skip comments & blank lines outside blocks
        if not line or line.startswith("#"):
            continue

        # Block op — starts with ":"
        if line.startswith(":"):
            header = line[1:].strip()
            if not header:
                raise ParseError(f"Line {i}: empty ':' directive")

            parts = header.split(None, 1)
            op_name = parts[0].upper()
            rest = parts[1] if len(parts) > 1 else ""

            if op_name not in BLOCK_OPS:
                raise ParseError(f"Line {i}: unknown block op ':{op_name}'")

            # Read until :END (or a sentinel for one-liner read ops)
            body_lines: List[str] = []
            found_end = False
            block_start = i
            while i < n:
                bl = lines[i]
                if bl.strip() == ":END":
                    found_end = True
                    i += 1
                    break
                body_lines.append(bl)
                i += 1

            body = "\n".join(body_lines)

            # Read-only ops don't need :END if they're single-line, but we
            # still accept them for consistency.  If no :END and body is empty,
            # treat header alone as the op.
            if op_name in ("TREE", "READ", "SEARCH", "LIST", "INFO") and not found_end:
                pass

            op = _build_block_op(op_name, rest, body, block_start)
            ops.append(op)
            continue

        # Inline op
        parts = line.split(None, 1)
        op_name = parts[0].upper()
        rest = parts[1] if len(parts) > 1 else ""

        if op_name not in INLINE_OPS:
            raise ParseError(f"Line {i}: unknown inline op '{op_name}' (or missing ':' for block ops)")

        ops.append(_build_inline_op(op_name, rest, i))

    return ops


def _build_inline_op(op_name: str, rest: str, line_no: int) -> Operation:
    op = Operation(kind=op_name, line_no=line_no)

    if op_name == "DELETE":
        op.target = rest.strip()

    elif op_name in ("RENAME", "MOVE"):
        # RENAME src/foo.ts -> src/bar.ts
        if "->" not in rest:
            raise ParseError(f"Line {line_no}: {op_name} requires 'src -> dst'")
        src, dst = [s.strip() for s in rest.split("->", 1)]
        op.target = src
        op.args["dst"] = dst

    elif op_name == "MKDIR":
        op.target = rest.strip()

    elif op_name in ("RUN", "INSTALL"):
        op.args["cmd"] = rest.strip()

    elif op_name == "GITADD":
        op.target = rest.strip() or "."

    elif op_name == "GITCOMMIT":
        op.args["msg"] = rest.strip().strip('"').strip("'")

    return op


def _build_block_op(op_name: str, rest: str, body: str, line_no: int) -> Operation:
    op = Operation(kind=op_name, target=rest.strip(), body=body, line_no=line_no)

    # Ops whose body needs FIND/WITH parsing
    fw_ops = {"REPLACE", "REGEX_REPLACE", "INSERT_AFTER", "INSERT_BEFORE"}
    if op_name in fw_ops:
        find_text, with_text = _parse_find_with(body, line_no)
        op.find = find_text
        op.replace = with_text

    elif op_name == "REPLACE_BLOCK":
        # FROM: <marker>\nTO: <marker>\nWITH:\n<content>
        op.args["from"], op.args["to"], op.replace = _parse_from_to_with(body, line_no)

    elif op_name == "MULTI_REPLACE":
        op.parts = _parse_multi(body, line_no)

    elif op_name == "TREE":
        # Parse flags from `rest`
        op.args.update(_parse_flags(rest, {"--depth": int, "--include": list, "--exclude": list}))
        # target = the actual path (first non-flag token)
        op.target = _strip_flags(rest)

    elif op_name == "READ":
        # target is space-separated list of paths
        op.args["paths"] = rest.split() if rest else []

    elif op_name == "SEARCH":
        # :SEARCH "text" [--in path] [--ext .ts,.tsx]
        m = re.match(r'^"([^"]*)"(.*)$', rest.strip())
        if not m:
            raise ParseError(f"Line {line_no}: SEARCH needs quoted text, e.g. :SEARCH \"foo\"")
        op.args["query"] = m.group(1)
        flags = _parse_flags(m.group(2), {"--in": str, "--ext": list})
        op.args.update(flags)

    elif op_name == "LIST":
        op.target = rest.strip()

    elif op_name == "INFO":
        op.target = rest.strip()

    return op


def _parse_find_with(body: str, line_no: int) -> tuple:
    """Body format:
       FIND:
       <text>
       WITH:
       <text>
       Also supports single-line: FIND: xxx / WITH: yyy
    """
    # Try single-line style first
    lines = body.splitlines()
    find_lines: List[str] = []
    with_lines: List[str] = []
    mode = None
    for ln in lines:
        stripped = ln.rstrip("\r")
        if stripped.startswith("FIND:"):
            mode = "find"
            after = stripped[5:].lstrip(" ")
            if after:
                find_lines.append(after)
            continue
        if stripped.startswith("WITH:"):
            mode = "with"
            after = stripped[5:].lstrip(" ")
            if after:
                with_lines.append(after)
            continue
        if mode == "find":
            find_lines.append(stripped)
        elif mode == "with":
            with_lines.append(stripped)

    if mode is None:
        raise ParseError(f"Line {line_no}: expected FIND:/WITH: in body")
    return ("\n".join(find_lines).rstrip(), "\n".join(with_lines).rstrip())


def _parse_from_to_with(body: str, line_no: int) -> tuple:
    lines = body.splitlines()
    from_line = ""
    to_line = ""
    with_lines: List[str] = []
    mode = None
    for ln in lines:
        s = ln.rstrip("\r")
        if s.startswith("FROM:"):
            from_line = s[5:].strip()
            continue
        if s.startswith("TO:"):
            to_line = s[3:].strip()
            continue
        if s.startswith("WITH:"):
            mode = "with"
            after = s[5:].lstrip(" ")
            if after:
                with_lines.append(after)
            continue
        if mode == "with":
            with_lines.append(s)

    if not from_line or not to_line:
        raise ParseError(f"Line {line_no}: REPLACE_BLOCK requires FROM: and TO:")
    return (from_line, to_line, "\n".join(with_lines).rstrip())


def _parse_multi(body: str, line_no: int) -> List[Dict[str, str]]:
    """Body: repeated FIND:/WITH: pairs separated by lines of '---'."""
    chunks = re.split(r"^---\s*$", body, flags=re.MULTILINE)
    parts = []
    for idx, chunk in enumerate(chunks):
        chunk = chunk.strip("\n")
        if not chunk.strip():
            continue
        try:
            f, w = _parse_find_with(chunk, line_no)
        except ParseError as e:
            raise ParseError(f"MULTI_REPLACE chunk {idx+1}: {e}")
        parts.append({"find": f, "with": w})
    if not parts:
        raise ParseError(f"Line {line_no}: MULTI_REPLACE has no FIND/WITH pairs")
    return parts


def _parse_flags(text: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Very small flag parser. spec maps flag -> type (int/str/list)."""
    result: Dict[str, Any] = {}
    tokens = text.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in spec:
            if i + 1 >= len(tokens):
                i += 1
                continue
            val = tokens[i + 1]
            t = spec[tok]
            key = tok.lstrip("-")
            if t is int:
                result[key] = int(val)
            elif t is list:
                result[key] = [v.strip() for v in val.split(",") if v.strip()]
            else:
                result[key] = val
            i += 2
        else:
            i += 1
    return result


def _strip_flags(text: str) -> str:
    """Return non-flag tokens joined."""
    tokens = text.split()
    out = []
    skip_next = False
    known = {"--depth", "--include", "--exclude", "--in", "--ext"}
    for t in tokens:
        if skip_next:
            skip_next = False
            continue
        if t in known:
            skip_next = True
            continue
        if t.startswith("--"):
            continue
        out.append(t)
    return " ".join(out).strip()
