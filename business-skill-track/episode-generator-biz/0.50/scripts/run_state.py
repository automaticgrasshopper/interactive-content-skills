#!/usr/bin/env python3
"""Atomic controller for adaptation, writing, enhancement, structure and acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from action_contracts import GENERATIVE_ACTIONS, GENERATIVE_REFERENCES, TRANSITIONS, expected_outputs, generative_input
from dependency_binding import load_leaves, planning_content_sha256
from planning_acceptance import load_verified as load_planning
from validate_topology import parse


VERSION = "nextplay.episode-atomic-run.v5"
ACTIONS = tuple(sorted({action for group in TRANSITIONS.values() for action in group}))
DEFAULT_LEASE_SECONDS = 600


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate_hash(values: dict[str, str]) -> str:
    raw = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def state_path(cache_root: Path) -> Path:
    return cache_root / "run-state.json"


def load(cache_root: Path) -> dict[str, Any]:
    value = json.loads(state_path(cache_root).read_text(encoding="utf-8"))
    if value.get("contract_version") != VERSION:
        raise ValueError("运行状态合同不匹配")
    return value


def init(cache_root: Path) -> None:
    if state_path(cache_root).exists():
        raise ValueError("运行状态已存在；不得覆盖")
    planning = load_planning(cache_root)
    ids = list(parse(cache_root / "topology.md"))
    atomic_write(state_path(cache_root), {
        "contract_version": VERSION,
        "run_id": str(uuid.uuid4()),
        "status": "IN_PROGRESS",
        "planning_content_sha256": planning_content_sha256(cache_root),
        "planning_content_leaves": load_leaves(cache_root),
        "episode_order": ids,
        "episodes": {item: {"state": "QUEUED", "leases": {}, "outputs": {}, "execution_counts": {}, "content_failures": {}} for item in ids},
        "resolved_endings": planning["resolved_endings"],
    })


def require_current_planning(cache_root: Path, state: dict[str, Any]) -> None:
    load_planning(cache_root)
    if state.get("planning_content_sha256") != planning_content_sha256(cache_root):
        raise ValueError("规划内容发生变化；必须重新冻结受影响分集")


def available_actions(episode: dict[str, Any]) -> list[str]:
    return list((TRANSITIONS.get(str(episode.get("state"))) or {}).keys())


def claim(cache_root: Path, episode_id: str, action: str, owner: str, inputs: list[Path], lease_seconds: int) -> dict[str, Any]:
    state = load(cache_root)
    require_current_planning(cache_root, state)
    episode = (state.get("episodes") or {}).get(episode_id)
    if not isinstance(episode, dict) or action not in available_actions(episode):
        raise ValueError(f"非法状态转换：{episode_id}/{action}")
    if action == "ADAPT":
        nodes = parse(cache_root / "topology.md")
        predecessors = [source for source, node in nodes.items() if episode_id in node.get("successors", [])]
        blocked = [source for source in predecessors if state["episodes"][source].get("state") != "EPISODE_ACCEPTED"]
        if blocked:
            raise ValueError(f"直接前置尚未验收：{episode_id}/{blocked}")
    if action in (episode.get("leases") or {}):
        raise ValueError("动作已有活动租约")
    if not 60 <= lease_seconds <= 3600:
        raise ValueError("租约时长必须在60至3600秒之间")
    if action in GENERATIVE_ACTIONS:
        standard = generative_input(cache_root, action, episode_id)
        if inputs and [item.resolve() for item in inputs] != [standard]:
            raise ValueError(f"生成动作只接受标准输入：{standard}")
        inputs = [standard]
    hashes = {}
    for path in inputs:
        resolved = path.resolve()
        if not resolved.is_file():
            raise ValueError(f"原子动作输入不存在：{path}")
        hashes[str(resolved)] = sha256(resolved)
    issued = now()
    token = secrets.token_hex(24)
    episode.setdefault("leases", {})[action] = {
        "lease": token, "owner": owner, "input_hashes": hashes,
        "input_sha256": aggregate_hash(hashes), "issued_at": iso(issued),
        "expires_at": iso(issued + timedelta(seconds=lease_seconds)),
    }
    counts = episode.setdefault("execution_counts", {})
    counts[action] = int(counts.get(action) or 0) + 1
    atomic_write(state_path(cache_root), state)
    return {"lease": token, "episode_id": episode_id, "action": action, "input_sha256": aggregate_hash(hashes)}


def complete(cache_root: Path, episode_id: str, action: str, lease: str, outputs: list[Path], outcome: str = "PASS") -> None:
    state = load(cache_root)
    require_current_planning(cache_root, state)
    episode = state["episodes"][episode_id]
    active = (episode.get("leases") or {}).get(action)
    if not isinstance(active, dict) or active.get("lease") != lease:
        raise ValueError("原子动作租约无效")
    if parse_time(active["expires_at"]) <= now():
        raise ValueError("原子动作租约已过期")
    for name, expected in active.get("input_hashes", {}).items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            raise ValueError("动作执行期间输入发生变化")
    if outcome != "PASS":
        raise ValueError("动作提交只接受PASS；写作失败应走fail")
    required = expected_outputs(cache_root, action, episode_id, outcome)
    resolved = [item.resolve() for item in outputs]
    if set(resolved) != set(required) or len(resolved) != len(required):
        raise ValueError("原子动作输出合同错误")
    files = {}
    for path in resolved:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"原子动作输出不存在或为空：{path}")
        files[str(path)] = sha256(path)
    target = (TRANSITIONS.get(episode["state"]) or {}).get(action)
    if not target:
        raise ValueError("当前状态不接受该动作")
    episode["state"] = target
    episode.setdefault("outputs", {})[action] = {"outcome": outcome, "files": files}
    del episode["leases"][action]
    atomic_write(state_path(cache_root), state)


def fail(cache_root: Path, episode_id: str, action: str, lease: str, reason: str, failure_kind: str) -> None:
    state = load(cache_root)
    episode = state["episodes"][episode_id]
    active = (episode.get("leases") or {}).get(action)
    if not isinstance(active, dict) or active.get("lease") != lease:
        raise ValueError("原子动作租约无效")
    del episode["leases"][action]
    if failure_kind == "content":
        failures = episode.setdefault("content_failures", {})
        failures[action] = int(failures.get(action) or 0) + 1
    episode["last_failure"] = {"action": action, "kind": failure_kind, "reason": reason, "at": iso(now())}
    atomic_write(state_path(cache_root), state)


def technical_recover(cache_root: Path, episode_id: str, target: str, reason: str) -> None:
    allowed = {
        "REBUILD_ADAPTATION": ("QUEUED", set()),
        "REWRITE_COMPACT_DRAFT": ("ADAPTED", {"ADAPT"}),
        "RERUN_ENHANCE": ("COMPACT_DRAFT_VALIDATED", {"ADAPT", "WRITE_COMPACT_DRAFT", "VALIDATE_COMPACT_DRAFT"}),
        "RESEAL_STRUCTURE": ("ENHANCED", {"ADAPT", "WRITE_COMPACT_DRAFT", "VALIDATE_COMPACT_DRAFT", "ENHANCE"}),
        "REBIND_ACCEPTANCE": ("STRUCTURE_VALIDATED", {"ADAPT", "WRITE_COMPACT_DRAFT", "VALIDATE_COMPACT_DRAFT", "ENHANCE", "VALIDATE_STRUCTURE"}),
    }
    if target not in allowed or len(reason.strip()) < 8:
        raise ValueError("技术恢复边或原因无效")
    state = load(cache_root)
    episode = state["episodes"][episode_id]
    if episode.get("leases"):
        raise ValueError("技术恢复前必须结束活动租约")
    state_name, keep = allowed[target]
    episode["state"] = state_name
    episode["outputs"] = {k: v for k, v in (episode.get("outputs") or {}).items() if k in keep}
    episode["last_technical_recovery"] = {"edge": target, "reason": reason.strip(), "at": iso(now())}
    atomic_write(state_path(cache_root), state)


def expire_lease(cache_root: Path, episode_id: str, action: str, lease: str) -> None:
    state = load(cache_root)
    episode = state["episodes"][episode_id]
    active = (episode.get("leases") or {}).get(action)
    if not isinstance(active, dict) or active.get("lease") != lease:
        raise ValueError("原子动作租约无效")
    if parse_time(active["expires_at"]) > now():
        raise ValueError("活动租约尚未过期")
    del episode["leases"][action]
    episode["last_failure"] = {
        "action": action, "kind": "orchestration",
        "reason": "上下文切分后回收过期租约并自动重做当前动作", "at": iso(now()),
    }
    atomic_write(state_path(cache_root), state)


def next_action(cache_root: Path, state: dict[str, Any]) -> dict[str, Any] | None:
    nodes = parse(cache_root / "topology.md")
    for episode_id in state["episode_order"]:
        episode = state["episodes"][episode_id]
        if episode.get("state") == "EPISODE_ACCEPTED":
            continue
        leases = episode.get("leases") or {}
        if leases:
            action, active = next(iter(leases.items()))
            if parse_time(active["expires_at"]) <= now():
                return {
                    "action": "RECOVER_EXPIRED_LEASE", "episode_id": episode_id,
                    "leased_action": action, "lease": active["lease"],
                    "execution_mode": "current_task",
                    "instruction": "执行recover-expired-lease回收该租约，再读取run_state status自动重做动作。",
                }
            return {
                "action": action, "episode_id": episode_id, "lease": active["lease"],
                "resume": True, "execution_mode": "current_task",
                "instruction": "恢复当前租约对应动作；安全提交后再次读取run_state status。",
                **({"required_reference": GENERATIVE_REFERENCES[action]} if action in GENERATIVE_ACTIONS else {}),
            }
        actions = available_actions(episode)
        if not actions:
            raise ValueError(f"分集状态没有后续动作：{episode_id}/{episode.get('state')}")
        action = actions[0]
        if action == "ADAPT":
            predecessors = [source for source, node in nodes.items() if episode_id in node.get("successors", [])]
            if any(state["episodes"][source].get("state") != "EPISODE_ACCEPTED" for source in predecessors):
                continue
        result: dict[str, Any] = {
            "action": action, "episode_id": episode_id, "execution_mode": "current_task",
            "instruction": "按atomic-run-orchestration.md执行该原子动作；安全提交后再次读取run_state status。",
        }
        if action in GENERATIVE_ACTIONS:
            result["standard_input"] = str(generative_input(cache_root, action, episode_id))
            result["required_reference"] = GENERATIVE_REFERENCES[action]
        return result
    return None


def status(cache_root: Path) -> dict[str, Any]:
    state = load(cache_root)
    require_current_planning(cache_root, state)
    accepted = [key for key, value in state["episodes"].items() if value.get("state") == "EPISODE_ACCEPTED"]
    complete = len(accepted) == len(state["episodes"])
    state["status"] = "READY_FOR_CLOSURE" if complete else "IN_PROGRESS"
    state["next_actions"] = ([{
        "action": "ASSEMBLE_DELIVERABLE", "execution_mode": "current_task",
        "instruction": "按workflow-and-stage-gates.md完成组装并继续最终验证。",
    }] if complete else [next_action(cache_root, state)])
    if not all(isinstance(item, dict) for item in state["next_actions"]):
        raise ValueError("IN_PROGRESS状态缺少可执行的next_actions")
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("cache_root", type=Path)
    sub.add_parser("status").add_argument("cache_root", type=Path)
    claim_p = sub.add_parser("claim"); claim_p.add_argument("cache_root", type=Path); claim_p.add_argument("episode_id"); claim_p.add_argument("action", choices=ACTIONS); claim_p.add_argument("--owner", required=True); claim_p.add_argument("--input", action="append", type=Path, default=[]); claim_p.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS)
    complete_p = sub.add_parser("complete"); complete_p.add_argument("cache_root", type=Path); complete_p.add_argument("episode_id"); complete_p.add_argument("action", choices=ACTIONS); complete_p.add_argument("--lease", required=True); complete_p.add_argument("--output", action="append", type=Path, default=[]); complete_p.add_argument("--outcome", choices=("PASS", "FAIL"), default="PASS")
    fail_p = sub.add_parser("fail"); fail_p.add_argument("cache_root", type=Path); fail_p.add_argument("episode_id"); fail_p.add_argument("action", choices=ACTIONS); fail_p.add_argument("--lease", required=True); fail_p.add_argument("--reason", required=True); fail_p.add_argument("--kind", choices=("content", "orchestration"), required=True)
    recover_p = sub.add_parser("technical-recover"); recover_p.add_argument("cache_root", type=Path); recover_p.add_argument("episode_id"); recover_p.add_argument("recovery"); recover_p.add_argument("--reason", required=True)
    expire_p = sub.add_parser("recover-expired-lease"); expire_p.add_argument("cache_root", type=Path); expire_p.add_argument("episode_id"); expire_p.add_argument("action", choices=ACTIONS); expire_p.add_argument("--lease", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init": init(args.cache_root); print("RUN_STATE_INITIALIZED")
        elif args.command == "status": print(json.dumps(status(args.cache_root), ensure_ascii=False, indent=2))
        elif args.command == "claim": print(json.dumps(claim(args.cache_root, args.episode_id, args.action, args.owner, args.input, args.lease_seconds), ensure_ascii=False))
        elif args.command == "complete": complete(args.cache_root, args.episode_id, args.action, args.lease, args.output, args.outcome); print("ATOMIC_ACTION_COMMITTED")
        elif args.command == "fail": fail(args.cache_root, args.episode_id, args.action, args.lease, args.reason, args.kind); print("ATOMIC_ACTION_FAILED")
        elif args.command == "technical-recover": technical_recover(args.cache_root, args.episode_id, args.recovery, args.reason); print("TECHNICAL_RECOVERY_READY")
        else: expire_lease(args.cache_root, args.episode_id, args.action, args.lease); print("EXPIRED_LEASE_RECOVERED")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}"); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
