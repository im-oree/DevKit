"""Runs a parsed script and aggregates results."""
from typing import List, Callable, Optional
from .parser import parse_script, Operation, ParseError
from .ops import execute, OpContext, OpResult


def run_script(text: str, cwd: str, dry_run: bool = False,
               on_result: Optional[Callable[[OpResult], None]] = None) -> List[OpResult]:
    """Parse & execute a script. Returns list of results."""
    ops = parse_script(text)
    ctx = OpContext(cwd=cwd, dry_run=dry_run)
    results: List[OpResult] = []
    for op in ops:
        r = execute(op, ctx)
        results.append(r)
        if on_result:
            on_result(r)
    return results


def summarize(results: List[OpResult]) -> str:
    ok = sum(1 for r in results if r.ok)
    fail = len(results) - ok
    created = sum(len(r.files_created) for r in results)
    changed = sum(len(r.files_changed) for r in results)
    deleted = sum(len(r.files_deleted) for r in results)
    lines = [
        f"═══ DevKit Summary ═══",
        f"Operations: {len(results)} ({ok} ok, {fail} failed)",
        f"Files created: {created}",
        f"Files changed: {changed}",
        f"Files deleted: {deleted}",
    ]
    if fail > 0:
        lines.append("")
        lines.append("Failures:")
        for r in results:
            if not r.ok:
                lines.append(f"  ✗ {r.op.kind} {r.op.target} — {r.message}")
    return "\n".join(lines)
