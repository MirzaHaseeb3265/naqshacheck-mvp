import json
from types import SimpleNamespace

import pytest
from PIL import Image

from src import ai_agent


class FakeCompletions:
    def __init__(self, contents):
        self.contents = iter(contents)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        content = next(self.contents)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeClient:
    def __init__(self, contents):
        self.chat = SimpleNamespace(completions=FakeCompletions(contents))


def test_plan_analysis_validates_structured_output(monkeypatch):
    payload = {
        "observations": [{
            "field": "front_setback_ft", "value": 5, "unit": "ft",
            "confidence": 0.91, "evidence": "Visible front dimension label"
        }],
        "uncertainties": ["Rear label unclear"],
    }
    fake = FakeClient([json.dumps(payload)])
    monkeypatch.setattr(ai_agent, "_client", lambda api_key=None: fake)
    result = ai_agent.analyze_plan_image(Image.new("RGB", (100, 100)), api_key="test")
    assert result.observations[0].field == "front_setback_ft"
    assert result.observations[0].confidence == pytest.approx(0.91)
    assert fake.chat.completions.calls == 1


def test_malformed_response_gets_one_retry(monkeypatch):
    good = json.dumps({"observations": [], "uncertainties": ["Unreadable"]})
    fake = FakeClient(["not-json", good])
    monkeypatch.setattr(ai_agent, "_client", lambda api_key=None: fake)
    result = ai_agent.analyze_plan_image(Image.new("RGB", (50, 50)), api_key="test")
    assert result.uncertainties == ["Unreadable"]
    assert fake.chat.completions.calls == 2


def test_no_key_keeps_ai_optional(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert ai_agent.resolve_api_key() is None
    with pytest.raises(ai_agent.AIUnavailableError):
        ai_agent._client()


def test_candidate_rules_are_forced_to_ai_draft(monkeypatch):
    payload = {
        "rules": [{
            "title": "Minimum front setback", "field": "front_setback_ft", "operator": ">=",
            "value": 5, "unit": "ft", "citation": "Page 3, section 2",
            "applicability": "5 marla residential", "exceptions": "None stated", "status": "ACTIVE"
        }],
        "uncertainties": [],
    }
    fake = FakeClient([json.dumps(payload)])
    monkeypatch.setattr(ai_agent, "_client", lambda api_key=None: fake)
    result = ai_agent.extract_candidate_rules("minimum 5 ft", authority="LDA", source_label="test.pdf, page 3", api_key="test")
    assert result.rules[0].status == "AI-DRAFT"
