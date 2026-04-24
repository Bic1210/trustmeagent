from __future__ import annotations

from html import escape


def _count(report: dict, key: str) -> int:
    return len(report.get(key, []))


def _confidence_score(report: dict) -> int:
    verified = _count(report, "verified")
    unverified = _count(report, "unverified")
    suspicious = _count(report, "suspicious")
    action_items = _count(report, "action_items")
    score = 100 - (unverified * 12) - (suspicious * 18) - max(0, action_items - verified) * 4
    return max(0, min(100, score))


def _headline(score: int) -> str:
    if score >= 80:
        return "Ready for human sign-off"
    if score >= 55:
        return "Needs focused review before merge"
    return "Do not trust this patch yet"


def _score_band(score: int) -> tuple[str, str]:
    if score >= 80:
        return ("high", "High confidence")
    if score >= 55:
        return ("guarded", "Guarded confidence")
    return ("low", "Low confidence")


def _ship_posture(report: dict, score: int) -> str:
    suspicious = _count(report, "suspicious")
    action_items = _count(report, "action_items")
    unverified = _count(report, "unverified")
    if suspicious or action_items >= 3:
        return "Hold merge until the suspicious findings and action queue are resolved."
    if unverified:
        return "Route this patch through targeted human review before you trust the result."
    if score >= 80:
        return "Signals are clean enough for sign-off, but the report is still evidence, not proof."
    return "Coverage is decent, but there is still enough uncertainty to justify manual inspection."


def _hero_copy(report: dict, score: int) -> str:
    detectors = len(report.get("detectors", []))
    verified = _count(report, "verified")
    unverified = _count(report, "unverified")
    suspicious = _count(report, "suspicious")
    return (
        f"trust me turns patch verification into an inspection page. "
        f"This run collected signals from {detectors} detectors, surfaced {verified} verified checks, "
        f"left {unverified} unverified gaps, and flagged {suspicious} suspicious signals."
    )


def _metric(label: str, value: int, tone: str, helper: str) -> str:
    return (
        f'<article class="metric metric-{escape(tone)}">'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-label">{escape(label)}</div>'
        f'<p class="metric-helper">{escape(helper)}</p>'
        "</article>"
    )


def _status_counts(report: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for detector in report.get("detectors", []):
        status = str(detector.get("status", "completed"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _status_chip(label: str, value: int, tone: str) -> str:
    return (
        f'<span class="status-chip tone-{escape(tone)}">'
        f"<strong>{value}</strong> {escape(label)}"
        "</span>"
    )


def _key_fact(label: str, value: str) -> str:
    return (
        '<div class="fact-row">'
        f'<div class="fact-label">{escape(label)}</div>'
        f'<div class="fact-value">{escape(value)}</div>'
        "</div>"
    )


def _list_items(items: list[str], empty_text: str) -> str:
    if not items:
        return f'<li class="empty">{escape(empty_text)}</li>'
    return "".join(f"<li>{escape(item)}</li>" for item in items)


def _list_card(title: str, items: list[str], tone: str, empty_text: str) -> str:
    return (
        f'<section class="panel list-card tone-{escape(tone)}">'
        '<div class="panel-header">'
        f'<div class="eyebrow">{escape(tone)} queue</div>'
        f"<h2>{escape(title)}</h2>"
        f'<span class="panel-count">{len(items)}</span>'
        "</div>"
        f"<ul>{_list_items(items, empty_text)}</ul>"
        "</section>"
    )


def _focus_items(report: dict) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    for entry in report.get("action_items", [])[:3]:
        items.append(("Action", entry, "accent"))
    for entry in report.get("suspicious", [])[:3]:
        items.append(("Risk", entry, "suspicious"))
    for entry in report.get("unverified", [])[:2]:
        items.append(("Gap", entry, "unverified"))
    return items[:6]


def _focus_grid(report: dict) -> str:
    items = _focus_items(report)
    if not items:
        return (
            '<div class="empty-panel">'
            "<strong>No urgent blockers surfaced.</strong>"
            "<p>The patch still needs human judgment, but this run did not produce an immediate escalation queue.</p>"
            "</div>"
        )

    cards = []
    for label, message, tone in items:
        cards.append(
            f'<article class="focus-card tone-{escape(tone)}">'
            f'<div class="focus-label">{escape(label)}</div>'
            f"<p>{escape(message)}</p>"
            "</article>"
        )
    return "".join(cards)


def _format_detector_name(name: str) -> str:
    trimmed = name
    if trimmed.startswith("detect_"):
        trimmed = trimmed[7:]
    for suffix in ("_check", "_status", "_risk"):
        if trimmed.endswith(suffix):
            trimmed = trimmed[: -len(suffix)]
    parts = [part for part in trimmed.replace("-", "_").split("_") if part]
    if not parts:
        return "Unknown detector"
    return " ".join(part.upper() if len(part) <= 3 else part.capitalize() for part in parts)


def _detector_card(detector: dict) -> str:
    verified = detector.get("verified", [])
    unverified = detector.get("unverified", [])
    suspicious = detector.get("suspicious", [])
    action_items = detector.get("action_items", [])
    status = str(detector.get("status", "completed"))
    counts = (
        _status_chip("verified", len(verified), "verified")
        + _status_chip("unverified", len(unverified), "unverified")
        + _status_chip("suspicious", len(suspicious), "suspicious")
        + _status_chip("actions", len(action_items), "accent")
    )

    note_items = suspicious[:1] + unverified[:1] + verified[:1]
    notes = "".join(f"<li>{escape(item)}</li>" for item in note_items) or "<li>No headline finding recorded.</li>"
    action = escape(action_items[0]) if action_items else "No follow-up action recorded."

    return (
        '<article class="detector-card">'
        '<div class="detector-top">'
        f"<h3>{escape(_format_detector_name(str(detector.get('detector', 'unknown'))))}</h3>"
        f'<span class="status status-{escape(status)}">{escape(status.replace("_", " "))}</span>'
        "</div>"
        f'<div class="detector-counts">{counts}</div>'
        '<div class="detector-section">'
        '<div class="mini-label">Headline finding</div>'
        f"<ul>{notes}</ul>"
        "</div>"
        '<div class="detector-section">'
        '<div class="mini-label">Next action</div>'
        f'<p class="detector-action">{action}</p>'
        "</div>"
        "</article>"
    )


def _detector_grid(report: dict) -> str:
    detectors = report.get("detectors", [])
    if not detectors:
        return (
            '<div class="empty-panel">'
            "<strong>No detector output available.</strong>"
            "<p>Run the harness again after detectors have emitted findings.</p>"
            "</div>"
        )
    return "".join(_detector_card(detector) for detector in detectors)


def _coverage_panel(report: dict) -> str:
    counts = _status_counts(report)
    order = [
        ("passed", "verified"),
        ("completed", "accent"),
        ("partial", "unverified"),
        ("failed", "suspicious"),
        ("error", "suspicious"),
        ("not_configured", "unverified"),
        ("skipped", "muted"),
    ]
    chips = "".join(
        _status_chip(status.replace("_", " "), counts[status], tone)
        for status, tone in order
        if counts.get(status)
    )
    if not chips:
        chips = _status_chip("detectors reported", len(report.get("detectors", [])), "accent")
    return chips


def _review_summary(report: dict) -> str:
    for detector in report.get("detectors", []):
        if detector.get("detector") != "review_summary_check":
            continue
        evidence = detector.get("evidence", {})
        change_summary = evidence.get("change_summary")
        if not isinstance(change_summary, str) or not change_summary.strip():
            return ""
        verdict = evidence.get("verdict", {})
        trust_level = verdict.get("trust_level", "unknown") if isinstance(verdict, dict) else "unknown"
        trust_reason = verdict.get("reason", "") if isinstance(verdict, dict) else ""
        return (
            '<section class="panel narrative">'
            '<div class="panel-header">'
            '<div class="eyebrow">review narrative</div>'
            "<h2>LLM Summary</h2>"
            f'<span class="panel-count">{escape(str(trust_level).title())}</span>'
            "</div>"
            f"<p>{escape(change_summary)}</p>"
            f'<p class="verdict-inline"><strong>{escape(str(trust_level).title())} trust.</strong> {escape(str(trust_reason))}</p>'
            "</section>"
        )
    return ""


def render_html(report: dict) -> str:
    score = _confidence_score(report)
    band_key, band_label = _score_band(score)
    detectors = report.get("detectors", [])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>trust me report</title>
  <style>
    :root {{
      --bg: #f6efe2;
      --bg-deep: #efe2cb;
      --surface: rgba(255, 250, 241, 0.86);
      --surface-strong: #fffaf1;
      --ink: #181512;
      --muted: #665f55;
      --border: rgba(42, 33, 24, 0.12);
      --border-strong: rgba(42, 33, 24, 0.2);
      --accent: #155eef;
      --accent-soft: rgba(21, 94, 239, 0.12);
      --verified: #157f55;
      --verified-soft: rgba(21, 127, 85, 0.12);
      --unverified: #9a6700;
      --unverified-soft: rgba(154, 103, 0, 0.12);
      --suspicious: #c4320a;
      --suspicious-soft: rgba(196, 50, 10, 0.12);
      --muted-soft: rgba(102, 95, 85, 0.1);
      --shadow: 0 24px 70px rgba(24, 21, 18, 0.08);
      --radius: 24px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "IBM Plex Sans", "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(21, 94, 239, 0.14), transparent 26%),
        radial-gradient(circle at top right, rgba(196, 50, 10, 0.08), transparent 22%),
        linear-gradient(180deg, #fbf6ed 0%, var(--bg) 46%, var(--bg-deep) 100%);
    }}
    h1, h2, h3 {{
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      letter-spacing: -0.03em;
    }}
    .shell {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 20px 56px;
    }}
    .masthead {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 22px;
      color: var(--muted);
      font-size: 0.86rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .brand {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
    }}
    .brand-mark {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: linear-gradient(135deg, var(--accent), #5cc1ff);
      box-shadow: 0 0 0 8px rgba(21, 94, 239, 0.12);
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.85fr);
      gap: 22px;
      align-items: stretch;
      margin-bottom: 22px;
    }}
    .hero-copy, .hero-panel, .panel, .metric {{
      border: 1px solid var(--border);
      background: var(--surface);
      backdrop-filter: blur(18px);
      box-shadow: var(--shadow);
    }}
    .hero-copy {{
      padding: 32px;
      border-radius: calc(var(--radius) + 4px);
      position: relative;
      overflow: hidden;
    }}
    .hero-copy::after {{
      content: "";
      position: absolute;
      inset: auto -60px -60px auto;
      width: 180px;
      height: 180px;
      background: radial-gradient(circle, rgba(21, 94, 239, 0.16), transparent 72%);
      pointer-events: none;
    }}
    .eyebrow {{
      margin-bottom: 12px;
      color: var(--muted);
      font-size: 0.74rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2.2rem, 5vw, 4.4rem);
      line-height: 0.95;
    }}
    .hero-copy p {{
      max-width: 62ch;
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 1.02rem;
      line-height: 1.7;
    }}
    .meta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .meta-chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.52);
      color: var(--muted);
      font-size: 0.84rem;
    }}
    .hero-panel {{
      padding: 28px;
      border-radius: calc(var(--radius) + 4px);
      display: grid;
      gap: 18px;
      align-content: start;
    }}
    .score-orb {{
      padding: 24px;
      border-radius: 28px;
      background: linear-gradient(160deg, rgba(255, 255, 255, 0.94), rgba(247, 240, 227, 0.9));
      border: 1px solid var(--border);
    }}
    .score-label {{
      display: block;
      color: var(--muted);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .score-value {{
      margin-top: 10px;
      font-size: clamp(3.4rem, 9vw, 5.4rem);
      line-height: 0.88;
      font-weight: 700;
      letter-spacing: -0.06em;
    }}
    .score-value small {{
      font-size: 1.2rem;
      color: var(--muted);
      font-weight: 600;
    }}
    .score-band {{
      display: inline-flex;
      margin-top: 14px;
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .score-band-high {{
      color: var(--verified);
      background: var(--verified-soft);
    }}
    .score-band-guarded {{
      color: var(--unverified);
      background: var(--unverified-soft);
    }}
    .score-band-low {{
      color: var(--suspicious);
      background: var(--suspicious-soft);
    }}
    .hero-panel-copy {{
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }}
    .scorecard {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 22px;
    }}
    .metric {{
      padding: 22px 18px;
      border-radius: 22px;
    }}
    .metric-value {{
      font-size: 2.2rem;
      line-height: 1;
      font-weight: 700;
      letter-spacing: -0.05em;
    }}
    .metric-label {{
      margin-top: 8px;
      font-size: 0.82rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--muted);
    }}
    .metric-helper {{
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.5;
    }}
    .metric-verified .metric-value {{ color: var(--verified); }}
    .metric-unverified .metric-value {{ color: var(--unverified); }}
    .metric-suspicious .metric-value {{ color: var(--suspicious); }}
    .metric-accent .metric-value {{ color: var(--accent); }}
    .metric-muted .metric-value {{ color: var(--ink); }}
    .triage-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 22px;
    }}
    .panel {{
      padding: 24px;
      border-radius: var(--radius);
    }}
    .panel-header {{
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }}
    .panel h2 {{
      margin: 0;
      font-size: 1.38rem;
      line-height: 1.05;
    }}
    .panel p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
    }}
    .panel-count {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 42px;
      height: 42px;
      padding: 0 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.74);
      border: 1px solid var(--border);
      color: var(--ink);
      font-weight: 700;
    }}
    .content-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr);
      gap: 18px;
      align-items: start;
    }}
    .stack {{
      display: grid;
      gap: 18px;
    }}
    .status-chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 12px;
      border-radius: 999px;
      border: 1px solid transparent;
      font-size: 0.82rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .tone-verified {{
      color: var(--verified);
      background: var(--verified-soft);
      border-color: rgba(21, 127, 85, 0.18);
    }}
    .tone-unverified {{
      color: var(--unverified);
      background: var(--unverified-soft);
      border-color: rgba(154, 103, 0, 0.2);
    }}
    .tone-suspicious {{
      color: var(--suspicious);
      background: var(--suspicious-soft);
      border-color: rgba(196, 50, 10, 0.18);
    }}
    .tone-accent {{
      color: var(--accent);
      background: var(--accent-soft);
      border-color: rgba(21, 94, 239, 0.2);
    }}
    .tone-muted {{
      color: var(--muted);
      background: var(--muted-soft);
      border-color: var(--border);
    }}
    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .focus-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .focus-card {{
      min-height: 144px;
      padding: 18px;
      border-radius: 20px;
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.62);
    }}
    .focus-card p {{
      margin-top: 8px;
      color: var(--ink);
      line-height: 1.6;
    }}
    .focus-label {{
      font-size: 0.74rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .empty-panel {{
      padding: 22px;
      border-radius: 20px;
      border: 1px dashed var(--border-strong);
      background: rgba(255, 255, 255, 0.34);
    }}
    .empty-panel strong {{
      display: block;
      margin-bottom: 8px;
    }}
    .detector-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .detector-card {{
      padding: 18px;
      border-radius: 22px;
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.58);
    }}
    .detector-top {{
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 12px;
    }}
    .detector-card h3 {{
      margin: 0;
      font-size: 1.14rem;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      padding: 7px 11px;
      border-radius: 999px;
      font-size: 0.76rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--border);
    }}
    .status-passed {{
      color: var(--verified);
      border-color: rgba(21, 127, 85, 0.18);
      background: var(--verified-soft);
    }}
    .status-failed, .status-error {{
      color: var(--suspicious);
      border-color: rgba(196, 50, 10, 0.18);
      background: var(--suspicious-soft);
    }}
    .status-not_configured, .status-skipped, .status-partial {{
      color: var(--unverified);
      border-color: rgba(154, 103, 0, 0.18);
      background: var(--unverified-soft);
    }}
    .status-completed {{
      color: var(--accent);
      border-color: rgba(21, 94, 239, 0.18);
      background: var(--accent-soft);
    }}
    .detector-counts {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }}
    .detector-section {{
      margin-top: 16px;
    }}
    .mini-label {{
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 0.74rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .detector-section ul, .list-card ul {{
      margin: 0;
      padding-left: 20px;
      display: grid;
      gap: 10px;
    }}
    .detector-section li, .list-card li {{
      line-height: 1.55;
    }}
    .detector-action {{
      color: var(--ink);
    }}
    .fact-grid {{
      display: grid;
      gap: 12px;
    }}
    .fact-row {{
      padding-top: 12px;
      border-top: 1px solid var(--border);
    }}
    .fact-row:first-child {{
      padding-top: 0;
      border-top: none;
    }}
    .fact-label {{
      margin-bottom: 4px;
      color: var(--muted);
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}
    .fact-value {{
      line-height: 1.55;
      word-break: break-word;
    }}
    .list-card {{
      border-top: 4px solid transparent;
    }}
    .list-card.tone-action, .list-card.tone-accent {{
      border-top-color: var(--accent);
    }}
    .list-card.tone-suspicious {{
      border-top-color: var(--suspicious);
    }}
    .list-card.tone-unverified {{
      border-top-color: var(--unverified);
    }}
    .list-card.tone-verified {{
      border-top-color: var(--verified);
    }}
    .list-card li.empty {{
      list-style: none;
      margin-left: -20px;
      color: var(--muted);
    }}
    .narrative {{
      background:
        linear-gradient(145deg, rgba(255, 255, 255, 0.74), rgba(247, 240, 227, 0.9)),
        var(--surface);
    }}
    .verdict-inline {{
      margin-top: 14px;
      color: var(--ink);
    }}
    .footer {{
      margin-top: 22px;
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.6;
      text-align: center;
    }}
    @media (max-width: 1080px) {{
      .hero,
      .content-grid,
      .triage-grid {{
        grid-template-columns: 1fr;
      }}
      .scorecard {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .detector-grid,
      .focus-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 680px) {{
      .shell {{
        padding-left: 14px;
        padding-right: 14px;
      }}
      .hero-copy,
      .hero-panel,
      .panel,
      .metric {{
        padding: 20px;
      }}
      .scorecard {{
        grid-template-columns: 1fr;
      }}
      .masthead {{
        flex-direction: column;
        align-items: start;
      }}
      .panel-header,
      .detector-top {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <div class="masthead">
      <div class="brand">
        <span class="brand-mark"></span>
        <span>trust me</span>
      </div>
      <span>patch confidence report</span>
    </div>

    <section class="hero">
      <div class="hero-copy">
        <div class="eyebrow">inspection summary</div>
        <h1>{escape(_headline(score))}</h1>
        <p>{escape(_hero_copy(report, score))}</p>
        <div class="meta-row">
          <span class="meta-chip">root: {escape(str(report.get("root", ".")))}</span>
          <span class="meta-chip">diff: {escape(str(report.get("diff_range") or "working tree"))}</span>
          <span class="meta-chip">patch: {escape(str(report.get("patch_path") or "none"))}</span>
          <span class="meta-chip">detectors: {len(detectors)}</span>
        </div>
      </div>

      <aside class="hero-panel">
        <div class="score-orb">
          <span class="score-label">Confidence score</span>
          <div class="score-value">{score}<small>/100</small></div>
          <div class="score-band score-band-{escape(band_key)}">{escape(band_label)}</div>
        </div>
        <p class="hero-panel-copy">{escape(_ship_posture(report, score))}</p>
      </aside>
    </section>

    <section class="scorecard">
      {_metric("Verified", _count(report, "verified"), "verified", "Evidence that actually passed or was confirmed.")}
      {_metric("Unverified", _count(report, "unverified"), "unverified", "Coverage gaps you still need to reason about.")}
      {_metric("Suspicious", _count(report, "suspicious"), "suspicious", "Signals that look risky or contradictory.")}
      {_metric("Action Items", _count(report, "action_items"), "accent", "Concrete follow-ups for the next reviewer.")}
      {_metric("Detectors", len(detectors), "muted", "Checks that contributed signal to this report.")}
    </section>

    <section class="triage-grid">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="eyebrow">ship posture</div>
            <h2>{escape(band_label)}</h2>
          </div>
          <span class="panel-count">{score}</span>
        </div>
        <p>{escape(_ship_posture(report, score))}</p>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="eyebrow">review load</div>
            <h2>Human attention</h2>
          </div>
          <span class="panel-count">{_count(report, "action_items") + _count(report, "suspicious")}</span>
        </div>
        <p>{escape(f'This patch has {_count(report, "action_items")} explicit action items and {_count(report, "suspicious")} suspicious signals competing for reviewer attention.')}</p>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="eyebrow">coverage</div>
            <h2>Detector status mix</h2>
          </div>
          <span class="panel-count">{len(detectors)}</span>
        </div>
        <div class="chip-row">{_coverage_panel(report)}</div>
      </section>
    </section>

    <section class="content-grid">
      <div class="stack">
        <section class="panel">
          <div class="panel-header">
            <div>
              <div class="eyebrow">priority queue</div>
              <h2>What needs attention before trust</h2>
            </div>
            <span class="panel-count">{len(_focus_items(report))}</span>
          </div>
          <div class="focus-grid">{_focus_grid(report)}</div>
        </section>

        {_review_summary(report)}

        <section class="panel">
          <div class="panel-header">
            <div>
              <div class="eyebrow">detector detail</div>
              <h2>Detector breakdown</h2>
            </div>
            <span class="panel-count">{len(detectors)}</span>
          </div>
          <div class="detector-grid">{_detector_grid(report)}</div>
        </section>
      </div>

      <aside class="stack">
        <section class="panel">
          <div class="panel-header">
            <div>
              <div class="eyebrow">run context</div>
              <h2>Scope of this report</h2>
            </div>
            <span class="panel-count">Run</span>
          </div>
          <div class="fact-grid">
            {_key_fact("Root", str(report.get("root", ".")))}
            {_key_fact("Diff range", str(report.get("diff_range") or "working tree"))}
            {_key_fact("Patch file", str(report.get("patch_path") or "none"))}
            {_key_fact("Detector count", str(len(detectors)))}
          </div>
        </section>

        {_list_card("Action Items", report.get("action_items", []), "accent", "No explicit next-step actions were recorded.")}
        {_list_card("Suspicious", report.get("suspicious", []), "suspicious", "No suspicious signals were recorded.")}
        {_list_card("Unverified", report.get("unverified", []), "unverified", "No unverified gaps were recorded.")}
        {_list_card("Verified", report.get("verified", []), "verified", "No verified checks were recorded.")}
      </aside>
    </section>

    <div class="footer">Generated by trust me. Use this page as a decision surface for review and triage, not as a proof that the patch is correct.</div>
  </main>
</body>
</html>"""
