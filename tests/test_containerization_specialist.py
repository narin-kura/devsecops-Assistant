"""Tests for core.agents.specialists.containerization's orchestration logic.

Mocks the Tool Runner boundary — see test_coordinator.py's module docstring
for why.
"""

from core.agents.specialists import containerization


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
    final = FakeMessage([FakeBlock("text", text="Detected python, wrote Dockerfile")])
    fake_client = FakeClient(FakeRunner([final]))
    monkeypatch.setattr(containerization.anthropic, "Anthropic", lambda: fake_client)

    report = containerization.run("containerize /tmp/foo")

    assert report == "Detected python, wrote Dockerfile"


def test_run_joins_multiple_text_blocks(monkeypatch):
    final = FakeMessage([FakeBlock("text", text="line one"), FakeBlock("text", text="line two")])
    fake_client = FakeClient(FakeRunner([final]))
    monkeypatch.setattr(containerization.anthropic, "Anthropic", lambda: fake_client)

    report = containerization.run("task")

    assert report == "line one\nline two"


def test_run_passes_the_task_and_toolset_to_the_runner(monkeypatch):
    from core.modules.containerize.agent_tools import CONTAINERIZATION_TOOLS

    final = FakeMessage([FakeBlock("text", text="ok")])
    fake_client = FakeClient(FakeRunner([final]))
    monkeypatch.setattr(containerization.anthropic, "Anthropic", lambda: fake_client)

    containerization.run("containerize /tmp/foo with a compose file")

    kwargs = fake_client.beta.messages.last_call_kwargs
    assert kwargs["model"] == containerization.MODEL_ID
    assert kwargs["tools"] == CONTAINERIZATION_TOOLS
    assert kwargs["messages"] == [{"role": "user", "content": "containerize /tmp/foo with a compose file"}]
    assert "Containerization specialist" in kwargs["system"]


def test_run_returns_fallback_message_when_runner_yields_nothing(monkeypatch):
    fake_client = FakeClient(FakeRunner([]))
    monkeypatch.setattr(containerization.anthropic, "Anthropic", lambda: fake_client)

    report = containerization.run("task")

    assert "no response" in report.lower()
