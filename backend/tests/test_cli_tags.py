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
