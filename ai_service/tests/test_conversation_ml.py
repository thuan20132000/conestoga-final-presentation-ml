import pytest

from ai_service.services import conversation_ml_service as ml_svc


def test_conversation_to_text():
    t = [
        {"role": "user", "content": " Book me in "},
        {"role": "assistant", "content": "Sure."},
    ]
    assert "user: Book me" in ml_svc.conversation_to_text(t)


def test_analyze_conversation_ml_uses_models(monkeypatch):
    class Pipe:
        def __init__(self, val):
            self._val = val

        def predict(self, row):
            return [self._val]

    fake = {
        "category": Pipe("make_appointment"),
        "sentiment": Pipe("positive"),
        "outcome": Pipe("successful"),
    }
    monkeypatch.setattr(ml_svc, "_get_models", lambda: fake)

    convo = [
        {"role": "user", "content": "I want a pedicure tomorrow."},
        {"role": "assistant", "content": "Checking slots."},
    ]
    out = ml_svc.analyze_conversation_ml(convo)
    assert out["category"] == "make_appointment"
    assert out["sentiment"] == "positive"
    assert out["outcome"] == "successful"
    assert "pedicure" in out["summary"].lower()
