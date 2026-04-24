from __future__ import annotations

import curses

from trust_me.render.text_report import _confidence_score, _count, _detector_rows, _headline, _review_block, _section


def build_tui_lines(report: dict, run_dir: str | None = None) -> list[str]:
    score = _confidence_score(report)
    lines = [
        "Patch Confidence TUI",
        f"Confidence: {score}% ({_headline(score)})",
        f"Root: {report.get('root', '.')}",
        f"Input: diff={report.get('diff_range') or 'working tree'} patch={report.get('patch_path') or 'none'}",
        f"Counts: verified={_count(report, 'verified')} unverified={_count(report, 'unverified')} suspicious={_count(report, 'suspicious')} action_items={_count(report, 'action_items')}",
        "",
        "Detector Breakdown",
    ]
    detector_rows = _detector_rows(report)
    lines.extend(detector_rows or ["- no detector output"])

    review_lines = _review_block(report)
    if review_lines:
        lines.extend(["", *review_lines])

    lines.extend(
        [
            "",
            *_section("Verified", report.get("verified", [])),
            "",
            *_section("Unverified", report.get("unverified", [])),
            "",
            *_section("Suspicious", report.get("suspicious", [])),
            "",
            *_section("Action Items", report.get("action_items", [])),
        ]
    )
    if run_dir is not None:
        lines.extend(["", f"Artifacts saved to {run_dir}"])
    return lines


def _line_attr(index: int, line: str) -> int:
    if index == 0:
        return curses.A_BOLD
    if line in {"Detector Breakdown", "Review Narrative", "Verified", "Unverified", "Suspicious", "Action Items"}:
        return curses.A_BOLD
    return curses.A_NORMAL


def _draw_screen(stdscr: curses.window, lines: list[str], offset: int) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    body_height = max(1, height - 1)
    visible_lines = lines[offset : offset + body_height]

    for row_index, line in enumerate(visible_lines):
        clipped = line[: max(1, width - 1)]
        stdscr.addnstr(row_index, 0, clipped, max(1, width - 1), _line_attr(offset + row_index, line))

    footer = "q quit  j/k or arrows scroll  g/G home/end  PgUp/PgDn page"
    stdscr.addnstr(height - 1, 0, footer[: max(1, width - 1)], max(1, width - 1), curses.A_REVERSE)
    stdscr.refresh()


def _run_tui(stdscr: curses.window, report: dict, run_dir: str | None = None) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    stdscr.keypad(True)
    lines = build_tui_lines(report, run_dir=run_dir)
    offset = 0

    while True:
        height, _width = stdscr.getmaxyx()
        body_height = max(1, height - 1)
        max_offset = max(0, len(lines) - body_height)
        offset = max(0, min(offset, max_offset))
        _draw_screen(stdscr, lines, offset)

        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return
        if key in (curses.KEY_DOWN, ord("j")):
            offset = min(max_offset, offset + 1)
            continue
        if key in (curses.KEY_UP, ord("k")):
            offset = max(0, offset - 1)
            continue
        if key == curses.KEY_NPAGE:
            offset = min(max_offset, offset + body_height)
            continue
        if key == curses.KEY_PPAGE:
            offset = max(0, offset - body_height)
            continue
        if key == ord("g"):
            offset = 0
            continue
        if key == ord("G"):
            offset = max_offset
            continue


def run_tui(report: dict, run_dir: str | None = None) -> None:
    curses.wrapper(_run_tui, report, run_dir)
