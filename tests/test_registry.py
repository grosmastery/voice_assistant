import pytest

from commands import registry


@pytest.fixture
def isolated():
    saved = (list(registry.FIXED), list(registry.PREFIX), list(registry.FREEFORM))
    registry.clear()
    yield registry
    registry.clear()
    registry.FIXED.extend(saved[0])
    registry.PREFIX.extend(saved[1])
    registry.FREEFORM.extend(saved[2])


def test_command_normalizes_phrases(isolated):
    @isolated.command("Pause, The Music!", "STOP")
    def fn(cfg):
        return "x"

    assert isolated.FIXED[-1][0] == ("pause the music", "stop")
    assert fn({}) == "x"                       # decorator returns the function unchanged


def test_with_target_normalizes_verbs(isolated):
    isolated.with_target("Open", "Відкрий!")(lambda cfg, rest: None)
    assert isolated.PREFIX[-1][0] == ("open", "відкрий")


def test_freeform_registers(isolated):
    fn = lambda cfg, text: None  # noqa: E731
    assert isolated.freeform(fn) is fn
    assert isolated.FREEFORM == [fn]


def test_duplicate_phrase_warns(isolated, capsys):
    isolated.command("dup phrase")(lambda cfg: "a")
    isolated.command("dup phrase")(lambda cfg: "b")
    assert "dup phrase" in capsys.readouterr().out


def test_clear(isolated):
    isolated.command("abc")(lambda cfg: "a")
    isolated.with_target("zap")(lambda cfg, r: None)
    isolated.freeform(lambda cfg, t: None)
    isolated.clear()
    assert not isolated.FIXED and not isolated.PREFIX and not isolated.FREEFORM