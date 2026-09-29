from pathlib import Path

import yaml

from .models import Rule


class InactiveRulePackError(ValueError):
    """Raised when a rule pack has not been explicitly approved for deterministic use."""


def load_rule_pack(path: str | Path) -> tuple[dict, list[Rule]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict) or "metadata" not in payload or "rules" not in payload:
        raise ValueError(f"Invalid rule pack structure: {path}")

    metadata = payload["metadata"] or {}
    if metadata.get("activation_allowed") is not True:
        raise InactiveRulePackError(
            f"Rule pack '{Path(path).name}' is not activated for deterministic checking. "
            "It must be professionally reviewed and set to activation_allowed: true."
        )

    return metadata, [Rule.model_validate(item) for item in payload["rules"]]
