#!/usr/bin/env python3
"""Bind a completed Biz run to its frozen planning and screenplay closure."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

CONTRACT_VERSION="nextplay.episode-completion.v18"; HANDOFF_VERSION="nextplay.episode-handoff.v1"
def sha_bytes(value: bytes)->str:return hashlib.sha256(value).hexdigest()

def dependency_files(root:Path,business:Path,assets:Path,introductions:Path,spine:Path)->dict[str,Path]:
    result={"business-json":business,"asset-catalog":assets,"character-introductions":introductions,"emotional-spine":spine,"cache/planning-acceptance.json":root/"planning-acceptance.json","cache/run-state.json":root/"run-state.json"}
    for name in ("user-request.md","user-intent-lock.json","creative-brief.json","complete-story.json","complete-story-review.json","mainline-decomposition.json","mainline-emotional-movement.json","mainline-path.json","decision-fissure-audit.json","decision-fissure-review.json","story-treatment.json","story-treatment-review.json","topology-draft-1.md","topology.md","route-duration.json","topology-review-a.json","topology-review-b.json","synopsis-set-review.json"):
        result[f"cache/{name}"]=root/name
    for directory,suffix in (("episode-synopses",".json"),("episode-adaptation-sources",".json"),("episode-story-materials",".json"),("episode-writing-inputs",".txt"),("screenplays",".md"),("episode-structure-receipts",".json"),("episode-review-packets",".json"),("episode-review-candidates",".json"),("episode-quality-receipts",".json"),("episode-acceptance-receipts",".json"),("episodes",".md")):
        for path in sorted((root/directory).glob(f"*{suffix}")):result[f"cache/{directory}/{path.name}"]=path
    return result

def artifact_hashes(paths:dict[str,Path])->dict[str,str]:
    result={}
    for label,path in sorted(paths.items()):
        if not path.is_file():raise ValueError(f"完成凭证缺少依赖：{label}")
        result[label]=sha_bytes(path.read_bytes())
    return result

def validate_episode_artifact_closure(root:Path)->None:
    from validate_execution_integrity import issues as execution_integrity_issues
    integrity=execution_integrity_issues(root)
    if integrity:raise ValueError("；".join(integrity))
    ids=sorted(path.stem for path in (root/"episode-synopses").glob("episode-*.json"))
    if not ids:raise ValueError("完成凭证缺少全体分集梗概")
    required={"episode-adaptation-sources":".json","episode-story-materials":".json","episode-writing-inputs":".txt","screenplays":".md","episode-structure-receipts":".json","episode-review-packets":".json","episode-review-candidates":".json","episode-quality-receipts":".json","episode-acceptance-receipts":".json","episodes":".md"}
    for directory,suffix in required.items():
        actual=sorted(path.stem for path in (root/directory).glob(f"episode-*{suffix}"))
        if actual!=ids:raise ValueError(f"分集产物闭包不完整：{directory}")

def make_receipt(root:Path,business:Path,assets:Path,introductions:Path,spine:Path,skill_version:str)->dict[str,Any]:return {"contract_version":CONTRACT_VERSION,"skill_version":skill_version,"artifacts":artifact_hashes(dependency_files(root,business,assets,introductions,spine))}
def validate_receipt(receipt:Path,root:Path,business:Path,assets:Path,introductions:Path,spine:Path,skill_version:str)->list[str]:
    try:return [] if json.loads(receipt.read_text(encoding="utf-8"))==make_receipt(root,business,assets,introductions,spine,skill_version) else ["完成凭证与当前冻结材料不一致"]
    except (OSError,ValueError,json.JSONDecodeError) as error:return [f"完成凭证不可用：{error}"]
def make_handoff(root:Path,business:Path,receipt:Path,skill_version:str)->dict[str,Any]:
    validate_episode_artifact_closure(root); data=json.loads(business.read_text(encoding="utf-8")); topology=(root/"topology.md").read_text(encoding="utf-8")
    return {"contract_version":HANDOFF_VERSION,"capability_id":"episode-generator-biz","skill_version":skill_version,"business_output":{"path":str(business.resolve()),"sha256":sha_bytes(business.read_bytes())},"completion_receipt":{"path":str(receipt.resolve()),"sha256":sha_bytes(receipt.read_bytes()),"contract_version":CONTRACT_VERSION},"resolved_counts":{"episodes":len(data.get("分集列表") or []),"main_endings":topology.count("主结局"),"expected_endings":topology.count("期望结局"),"failure_endings":topology.count("失败结局"),"small_endings":topology.count("小结局")},"status":{"business_schema":"passed","skill_acceptance":"verified","project_projection":"not_performed"}}
def validate_handoff(path:Path,root:Path,business:Path,receipt:Path,skill_version:str)->list[str]:
    try:return [] if json.loads(path.read_text(encoding="utf-8"))==make_handoff(root,business,receipt,skill_version) else ["交接清单不一致"]
    except (OSError,ValueError,json.JSONDecodeError) as error:return [f"交接清单不可用：{error}"]
