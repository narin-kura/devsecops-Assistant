"""Tests for core.agents.specialists.exceptions_tracking's orchestration logic.

Mocks the Tool Runner boundary — see test_coordinator.py's module docstring
for why.
"""

from core.agents.specialists import exceptions_tracking


class FakeBlock:
    def __init__(self, type_, text=None):
        self.type = type_
        self.text = text


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeRunner:
    def __init__(self, messages):
        self._messages = messages

    def __iter__(self):
        return iter(self._messages)


class FakeMessagesAPI:
    def __init__(self, runner):
        self._runner = runner
        self.last_call_kwargs = None

    def tool_runner(self, **kwargs):
        self.last_call_kwargs = kwargs
        return self._runner


class FakeClient:
    def __init__(self, runner):
        self.beta = type("Beta", (), {"messages": FakeMessagesAPI(runner)})()


def test_run_returns_final_message_text(monkeypatch):
    final = FakeMessage([FakeBlock("text", text="Recorded exception abc123")])
    fake_client = FakeClient(FakeRunner([final]))
    monkeypatch.setattr(exceptions_tracking.anthropic, "Anthropic", lambda: fake_client)

    report = exceptions_tracking.run("record an exception for /tmp/foo")

    assert report == "Recorded exception abc123"


def test_run_joins_multiple_text_blocks(monkeypatch):
    final = FakeMessage([FakeBlock("text", text="line one"), FakeBlock("text", text="line two")])
    fake_client = FakeClient(FakeRunner([final]))
    monkeypatch.setattr(exceptions_tracking.anthropic, "Anthropic", lambda: fake_client)

    report = exceptions_tracking.run("task")

    assert report == "line one\nline two"


def test_run_passes_the_task_and_toolset_to_the_runner(monkeypatch):
    from core.modules.exceptions.agent_tools import EXCEPTIONS_TRACKING_TOOLS

    final = FakeMessage([FakeBlock("text", text="ok")])
    fake_client = FakeClient(FakeRunner([final]))
    monkeypatch.setattr(exceptions_tracking.anthropic, "Anthropic", lambda: fake_client)

    exceptions_tracking.run("list exceptions for /tmp/foo")

    kwargs = fake_client.beta.messages.last_call_kwargs
    assert kwargs["model"] == exceptions_tracking.MODEL_ID
    assert kwargs["tools"] == EXCEPTIONS_TRACKING_TOOLS
    assert kwargs["messages"] == [{"role": "user", "content": "list exceptions for /tmp/foo"}]
    assert "Exceptions Tracking specialist" in kwargs["system"]


def test_run_returns_fallback_message_when_runner_yields_nothing(monkeypatch):
    fake_client = FakeClient(FakeRunner([]))
    monkeypatch.setattr(exceptions_tracking.anthropic, "Anthropic", lambda: fake_client)

    report = exceptions_tracking.run("task")

    assert "no response" in report.lower()
