import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "business-skill-track" / "episode-generator-biz" / "0.38" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "validate_mainline_projection", SCRIPTS / "validate_mainline_projection.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_decomposition_requires_verbatim_complete_ordered_coverage(tmp_path):
    mainline = {
        "complete_story": "第一段原文。\n\n第二段原文。",
        "expected_ending_title": "结束",
    }
    write_json(tmp_path / "mainline-story.json", mainline)
    decomposition = {
        "contract_version": "nextplay.mainline-decomposition.v1",
        "mainline_sha256": hashlib.sha256(canonical(mainline).encode("utf-8")).hexdigest(),
        "segments": [
            {"segment_id": "mainline-001", "title": "开端", "source_text": "第一段原文。"},
            {"segment_id": "mainline-002", "title": "结束", "source_text": "第二段原文。"},
        ],
    }
    write_json(tmp_path / "mainline-decomposition.json", decomposition)
    assert MODULE.decomposition_issues(tmp_path)[0] == []

    decomposition["segments"].pop()
    write_json(tmp_path / "mainline-decomposition.json", decomposition)
    assert "主线分解末尾遗漏冻结故事原文" in MODULE.decomposition_issues(tmp_path)[0]
