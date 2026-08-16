"""Tests for core.agents.coordinator's orchestration logic.

These mock the Tool Runner boundary (client.beta.messages.tool_runner)
rather than calling the real Claude API, so they run fast, free, and
deterministically — they verify *our* message-mirroring, printing, and
error-handling code, not the model's behavior. See test_live_chat.py for
opt-in tests against the real API.
"""

import anthropic
import httpx

from core.agents import coordinator


class FakeBlock:
    def __init__(self, type_, text=None, name=None, input=None):
        self.type = type_
        self.text = text
        self.name = name
        self.input = input


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeRunner:
    """Mimics client.beta.messages.tool_runner()'s iteration + tool-response contract."""

    def __init__(self, messages, tool_responses=()):
        self._messages = messages
        self._tool_responses = list(tool_responses)

    def __iter__(self):
        return iter(self._messages)

    def generate_tool_call_response(self):
        if self._tool_responses:
            return self._tool_responses.pop(0)
        return None


class FakeMessagesAPI:
    def __init__(self, runner):
        self._runner = runner

    def tool_runner(self, **kwargs):
        self.last_call_kwargs = kwargs
        return self._runner


class FakeBeta:
    def __init__(self, runner):
        self.messages = FakeMessagesAPI(runner)


class FakeClient:
    def __init__(self, runner):
        self.beta = FakeBeta(runner)


def test_send_turn_appends_user_message_first():
    runner = FakeRunner([FakeMessage([FakeBlock("text", text="hi")])])
    client = FakeClient(runner)
    messages = []

    coordinator.send_turn(client, messages, "hello")

    assert messages[0] == {"role": "user", "content": "hello"}


def test_send_turn_mirrors_tool_use_and_tool_result_into_history():
    tool_use_msg = FakeMessage([FakeBlock("tool_use", name="delegate_to_ci_onboarding", input={"task": "x"})])
    final_msg = FakeMessage([FakeBlock("text", text="done")])
    tool_result = {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "abc", "content": "ok"}]}

    runner = FakeRunner([tool_use_msg, final_msg], tool_responses=[tool_result])
    client = FakeClient(runner)
    messages = []

    final = coordinator.send_turn(client, messages, "onboard this project")

    assert messages == [
        {"role": "user", "content": "onboard this project"},
        {"role": "assistant", "content": tool_use_msg.content},
        tool_result,
        {"role": "assistant", "content": final_msg.content},
    ]
    assert final is final_msg


def test_send_turn_prints_text_and_delegation_notice(capsys):
    tool_use_msg = FakeMessage([FakeBlock("tool_use", name="delegate_to_ci_onboarding", input={"task": "onboard"})])
    final_msg = FakeMessage([FakeBlock("text", text="Pipeline written.")])
    runner = FakeRunner([tool_use_msg, final_msg], tool_responses=[None])
    client = FakeClient(runner)

    coordinator.send_turn(client, [], "onboard this project")

    out = capsys.readouterr().out
    assert "delegating to delegate_to_ci_onboarding" in out
    assert "Pipeline written." in out


def test_send_turn_returns_none_when_runner_yields_nothing():
    runner = FakeRunner([])
    client = FakeClient(runner)

    final = coordinator.send_turn(client, [], "hello")

    assert final is None


def test_delegate_to_ci_onboarding_calls_the_specialist(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "core.agents.coordinator.ci_onboarding.run",
        lambda task: calls.append(task) or f"handled: {task}",
    )

    result = coordinator.delegate_to_ci_onboarding("onboard /tmp/foo to github-actions")

    assert calls == ["onboard /tmp/foo to github-actions"]
    assert result == "handled: onboard /tmp/foo to github-actions"


def test_delegate_to_containerization_calls_the_specialist(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "core.agents.coordinator.containerization.run",
        lambda task: calls.append(task) or f"handled: {task}",
    )

    result = coordinator.delegate_to_containerization("containerize /tmp/foo")

    assert calls == ["containerize /tmp/foo"]
    assert result == "handled: containerize /tmp/foo"


def test_delegate_to_automation_calls_the_specialist(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "core.agents.coordinator.automation.run",
        lambda task: calls.append(task) or f"handled: {task}",
    )

    result = coordinator.delegate_to_automation("scaffold automation for /tmp/foo")

    assert calls == ["scaffold automation for /tmp/foo"]
    assert result == "handled: scaffold automation for /tmp/foo"


def test_repl_exits_immediately_on_exit_command(monkeypatch, capsys):
    monkeypatch.setattr("core.agents.coordinator.anthropic.Anthropic", lambda: FakeClient(FakeRunner([])))
    inputs = iter(["exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    assert coordinator.repl() == 0


def test_repl_reprompts_on_empty_input_then_exits(monkeypatch):
    monkeypatch.setattr("core.agents.coordinator.anthropic.Anthropic", lambda: FakeClient(FakeRunner([])))
    inputs = iter(["", "   ", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    assert coordinator.repl() == 0


def test_repl_handles_eof_as_clean_exit(monkeypatch):
    monkeypatch.setattr("core.agents.coordinator.anthropic.Anthropic", lambda: FakeClient(FakeRunner([])))

    def raise_eof(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    assert coordinator.repl() == 0


def test_repl_reports_missing_credentials_without_crashing(monkeypatch, capsys):
    class ExplodingMessagesAPI:
        def tool_runner(self, **kwargs):
            raise TypeError("Could not resolve authentication method. Expected either api_key or auth_token")

    class ExplodingClient:
        def __init__(self):
            self.beta = type("Beta", (), {"messages": ExplodingMessagesAPI()})()

    monkeypatch.setattr("core.agents.coordinator.anthropic.Anthropic", ExplodingClient)
    inputs = iter(["hello"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    exit_code = coordinator.repl()

    assert exit_code == 1
    assert "No API credentials found" in capsys.readouterr().out


def test_repl_recovers_from_a_transient_api_error(monkeypatch, capsys):
    class FlakyThenOkMessagesAPI:
        def __init__(self):
            self.calls = 0

        def tool_runner(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise anthropic.APIConnectionError(
                    request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
                )
            return FakeRunner([FakeMessage([FakeBlock("text", text="recovered")])])

    class FlakyClient:
        def __init__(self):
            self.beta = type("Beta", (), {"messages": FlakyThenOkMessagesAPI()})()

    monkeypatch.setattr("core.agents.coordinator.anthropic.Anthropic", FlakyClient)
    inputs = iter(["first (fails)", "second (recovers)", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    assert coordinator.repl() == 0
    assert "recovered" in capsys.readouterr().out
