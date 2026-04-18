
import json

def test_reasoning_serialization():
    reasoning = {"check": True}
    text = json.dumps(reasoning)

    assert "check" in text
