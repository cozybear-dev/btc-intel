from btcintel.analysis.report import to_markdown
from tests.analysis_scenario import A, build_funded, run_analysis
from tests.fakes import FakeChain


async def test_markdown_report_has_verdict_reasons_and_tables():
    report, _ = await run_analysis(FakeChain(build_funded().txs))
    md = report.markdown
    assert md == to_markdown(report)
    assert md.startswith(f"# Address analysis: {A}\n")
    assert "**Verdict: SEVERE**" in md
    assert "- **severe**: Received 0.015 BTC directly from LockBit (ransomware, ransomwhere)" in md
    assert "## Sources of funds" in md and "| LockBit | ransomware | 0.015 BTC | 100% | 1 | ransomwhere |" in md
    assert "## Destinations of funds" in md and "| Example Exchange | exchange | 0.01 BTC | 67% | 1 | test |" in md
    assert "| Wallet fingerprint | v2|" not in md  # pipes in values are escaped
    assert "v2\\|lt:zero" in md


async def test_markdown_for_an_unused_address():
    report, _ = await run_analysis(FakeChain([]))
    assert report.markdown.count("No funds to trace.") == 2
    assert "**Verdict: NONE**" in report.markdown
