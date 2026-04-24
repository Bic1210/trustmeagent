import json


def render_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)
