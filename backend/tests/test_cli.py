from btcintel import __version__
from btcintel.cli import main


def test_version_command_prints_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_unknown_command_exits_nonzero():
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["no-such-command"])
    assert exc.value.code == 2
