from dataclasses import dataclass


@dataclass
class Finding:
    level: str
    message: str
