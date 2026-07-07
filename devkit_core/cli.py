"""Command-line interface."""
import sys
import os
from pathlib import Path

from .runner import run_script, summarize
from .parser import ParseError
from . import backup


def run_cli(args):
    if not args:
        _interactive()
        return

    cmd = args[0].lower()

    if cmd == "run":
        _run_file(args[1:], dry_run=False)
    elif cmd == "preview":
        _run_file(args[1:], dry_run=True)
    elif cmd == "undo":
        _undo(args[1:])
    elif cmd == "sessions":
        _list_sessions()
    elif cmd == "tree":
        _quick_tree(args[1:])
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: devkit.py [run|preview|undo|sessions|tree|--help] [args]")
        sys.exit(1)


def _run_file(args, dry_run: bool):
    if not args:
        print("Usage: devkit.py run <script.dk>   (or '-' for stdin)")
        sys.exit(1)
    script_path = args[0]
    if script_path == "-":
        text = sys.stdin.read()
    else:
        if not os.path.exists(script_path):
            print(f"Script not found: {script_path}")
            sys.exit(1)
        text = Path(script_path).read_text(encoding="utf-8")

    cwd = os.getcwd()
    print(f"{'[PREVIEW]' if dry_run else '[RUN]'} in {cwd}")
    print("─" * 60)

    def on_result(r):
        icon = "✓" if r.ok else "✗"
        print(f"{icon} {r.op.kind} {r.op.target} — {r.message}")
        if r.output:
            print(r.output)
            print()

    try:
        results = run_script(text, cwd=cwd, dry_run=dry_run, on_result=on_result)
    except ParseError as e:
        print(f"✗ PARSE ERROR: {e}")
        sys.exit(1)

    print("─" * 60)
    print(summarize(results))
    if any(not r.ok for r in results):
        sys.exit(2)


def _undo(args):
    cwd = os.getcwd()
    sessions = backup.list_sessions(cwd)
    if not sessions:
        print("No backup sessions found.")
        return

    if args:
        target = args[0]
        if target not in sessions:
            print(f"Session '{target}' not found.")
            sys.exit(1)
    else:
        target = sessions[0]

    print(f"Restoring session: {target}")
    restored = backup.restore_session(cwd, target)
    for r in restored:
        print(f"  ↺ {r}")
    print(f"Restored {len(restored)} file(s).")


def _list_sessions():
    cwd = os.getcwd()
    sessions = backup.list_sessions(cwd)
    if not sessions:
        print("(no backup sessions)")
        return
    print("Backup sessions (newest first):")
    for s in sessions:
        print(f"  • {s}")


def _quick_tree(args):
    from .parser import Operation
    from .ops import op_tree, OpContext
    op = Operation(kind="TREE", target=args[0] if args else ".")
    ctx = OpContext(cwd=os.getcwd())
    r = op_tree(op, ctx)
    print(r.output)


def _interactive():
    print("DevKit interactive CLI. Type ':help' for commands, ':quit' to exit.")
    print("Paste multi-line ops. Terminate a block with ':END'.")
    print("Enter a lone ':run' or blank line + ':run' to execute buffered ops.")
    buf = []
    while True:
        try:
            line = input("dk> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if line.strip() == ":quit":
            return
        if line.strip() == ":help":
            print("Commands: :run (execute buffer), :preview, :clear, :quit, :help")
            continue
        if line.strip() == ":clear":
            buf = []
            print("(buffer cleared)")
            continue
        if line.strip() in (":run", ":preview"):
            script = "\n".join(buf)
            if not script.strip():
                print("(empty buffer)")
                continue
            dry = line.strip() == ":preview"
            try:
                results = run_script(script, cwd=os.getcwd(), dry_run=dry,
                                     on_result=lambda r: print(f"  {'✓' if r.ok else '✗'} {r.op.kind} — {r.message}"))
                print(summarize(results))
            except ParseError as e:
                print(f"✗ PARSE: {e}")
            buf = []
            continue
        buf.append(line)
