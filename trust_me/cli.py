import argparse
import json
import sys
from pathlib import Path

from trust_me.artifacts import persist_run_artifacts
from trust_me.harness import run_harness
from trust_me.render.text_report import render_text
from trust_me.render.tui import run_tui


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="trust me: patch confidence harness")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Run checks against a repo or patch")
    run_parser.add_argument("--root", default=".", help="Project root to inspect")
    run_parser.add_argument("--diff", default=None, help="Optional git diff range")
    run_parser.add_argument("--patch", default=None, help="Optional patch file path")
    run_parser.add_argument("--format", choices=["json", "text", "tui"], default="text")
    run_parser.add_argument("--scope", choices=["all", "changed"], default="all", help="Scope checks to the full project or changed files only")
    run_parser.add_argument("--with-review", action="store_true", help="Ask Claude CLI for a tester-style review summary")
    run_parser.add_argument("--no-save", action="store_true", help="Do not persist run artifacts under runs/")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    result = run_harness(
        root=root,
        diff_range=args.diff,
        patch_path=args.patch,
        scope=args.scope,
        with_review=args.with_review,
    )
    run_dir = None
    if not args.no_save:
        run_dir = persist_run_artifacts(
            root,
            result,
            diff_range=args.diff,
            patch_path=args.patch,
            scope=args.scope,
            with_review=args.with_review,
            argv=sys.argv,
        )
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.format == "tui":
        run_tui(result, run_dir=str(run_dir) if run_dir is not None else None)
        return

    print(render_text(result, run_dir=str(run_dir) if run_dir is not None else None), end="")


if __name__ == "__main__":
    main()
