import json
from contextlib import asynccontextmanager

import btcintel.runtime as runtime
from btcintel.cli import main
from tests.analysis_scenario import A, build_funded, ransomware_tag
from tests.fakes import FakeChain
from tests.scenario import scenario_tags


def use_fake_chain(monkeypatch, tmp_path):
    real = runtime.open_runtime

    @asynccontextmanager
    async def with_fake_chain(settings, chain=None):
        async with real(settings, FakeChain(build_funded().txs)) as rt:
            rt.tags.add_many([*scenario_tags(), ransomware_tag()])
            yield rt

    monkeypatch.setenv("BTCINTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(runtime, "open_runtime", with_fake_chain)


def test_analyze_prints_the_markdown_report(tmp_path, monkeypatch, capsys):
    use_fake_chain(monkeypatch, tmp_path)
    assert main(["analyze", A]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"# Address analysis: {A}\n") and "**Verdict: SEVERE**" in out


def test_analyze_json_and_bad_address(tmp_path, monkeypatch, capsys):
    use_fake_chain(monkeypatch, tmp_path)
    assert main(["analyze", A, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"]["level"] == "severe"
    assert main(["analyze", "nope"]) == 2
