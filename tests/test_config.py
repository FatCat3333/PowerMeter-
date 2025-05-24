import json
from pathlib import Path
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main


def test_load_save_config(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(main, "CONFIG_PATH", tmp_path / "config.json")
    cfg = {"always_on_top": False, "snap_enabled": False, "border_width": 3}
    main.save_config(cfg)
    loaded = main.load_config()
    assert loaded["border_width"] == 3
    assert loaded["always_on_top"] is False
    assert loaded["snap_enabled"] is False
