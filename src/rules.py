from pathlib import Path

import yaml

from .models import Rule


def load_rule_pack(path: str | Path) -> tuple[dict, list[Rule]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return payload["metadata"], [Rule.model_validate(item) for item in payload["rules"]]

