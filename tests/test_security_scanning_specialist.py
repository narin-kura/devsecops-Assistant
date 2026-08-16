"""Tests for core.agents.specialists.security_scanning's orchestration logic.

Mocks the Tool Runner boundary — see test_coordinator.py's module docstring
for why.
"""

from core.agents.specialists import security_scanning


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
    final = FakeMessage([FakeBlock("text", text="Found 2 high-severity issues")])
    fake_client = FakeClient(FakeRunner([final]))
    monkeypatch.setattr(security_scanning.anthropic, "Anthropic", lambda: fake_client)

    report = security_scanning.run("scan /tmp/foo for secrets")

    assert report == "Found 2 high-severity issues"


def test_run_joins_multiple_text_blocks(monkeypatch):
    final = FakeMessage([FakeBlock("text", text="line one"), FakeBlock("text", text="line two")])
    fake_client = FakeClient(FakeRunner([final]))
    monkeypatch.setattr(security_scanning.anthropic, "Anthropic", lambda: fake_client)

    report = security_scanning.run("task")

    assert report == "line one\nline two"


def test_run_passes_the_task_and_toolset_to_the_runner(monkeypatch):
    from core.modules.security_scan.agent_tools import SECURITY_SCAN_TOOLS

    final = FakeMessage([FakeBlock("text", text="ok")])
    fake_client = FakeClient(FakeRunner([final]))
    monkeypatch.setattr(security_scanning.anthropic, "Anthropic", lambda: fake_client)

    security_scanning.run("scan /tmp/foo for vulnerable dependencies")

    kwargs = fake_client.beta.messages.last_call_kwargs
    assert kwargs["model"] == security_scanning.MODEL_ID
    assert kwargs["tools"] == SECURITY_SCAN_TOOLS
    assert kwargs["messages"] == [{"role": "user", "content": "scan /tmp/foo for vulnerable dependencies"}]
    assert "Security Scanning specialist" in kwargs["system"]


def test_run_returns_fallback_message_when_runner_yields_nothing(monkeypatch):
    fake_client = FakeClient(FakeRunner([]))
    monkeypatch.setattr(security_scanning.anthropic, "Anthropic", lambda: fake_client)

    report = security_scanning.run("task")

    assert "no response" in report.lower()
