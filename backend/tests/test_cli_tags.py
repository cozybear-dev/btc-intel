from btcintel.cli import main
from tests.labels.test_importers import TAGPACK


def test_import_tagpack_file_then_query(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BTCINTEL_DATA_DIR", str(tmp_path / "data"))
    pack = tmp_path / "blender.yaml"
    pack.write_text(TAGPACK)
    assert main(["import-tags", "tagpack", str(pack), "--pack", "blender"]) == 0
    assert "3 tags" in capsys.readouterr().out
    assert main(["tags", "3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4"]) == 0
    out = capsys.readouterr().out
    assert "Blender.io" in out and "mixing_service" in out


def test_import_download_failure_is_reported_not_raised(tmp_path, monkeypatch, capsys):
    import httpx

    from btcintel.labels import importers

    def boom(url, proxy=None, timeout=300.0):
        raise httpx.ConnectError("offline")

    monkeypatch.setenv("BTCINTEL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(importers, "fetch", boom)
    assert main(["import-tags", "ofac"]) == 1
    assert "download failed" in capsys.readouterr().err
