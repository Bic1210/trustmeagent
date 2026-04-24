from dataclasses import dataclass, field


@dataclass
class Report:
    verified: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)
    suspicious: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
