import json


def render_json(report: dict) -> str:
    payload = dict(report)
    detectors = payload.get("detectors", [])
    payload["timing"] = {
        "total_seconds": payload.get("duration_seconds"),
        "detectors": [
            {
                "detector": detector.get("detector"),
                "status": detector.get("status"),
                "duration_seconds": detector.get("duration_seconds"),
            }
            for detector in detectors
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
