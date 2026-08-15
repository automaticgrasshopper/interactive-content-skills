#!/usr/bin/env python3
"""Atomic, resumable controller for one episode action at a time."""

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

from action_contracts import (
    CHILD_ACTIONS,
    REVIEW_ACTIONS,
    TRANSITIONS,
    child_input,
    expected_outputs,
)
from episode_artifact import predecessors
from dependency_binding import load_leaves, stage_two_content_sha256
from stage_two_acceptance import VERSION as STAGE_TWO_VERSION, load_verified as load_stage_two
from validate_topology import parse


VERSION = "nextplay.episode-atomic-run.v2"
ACTIONS = tuple(sorted({action for actions in TRANSITIONS.values() for action in actions}))
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
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    path = state_path(cache_root)
    if path.exists():
        raise ValueError("运行状态已存在；使用 status，不得覆盖")
    stage_two = load_stage_two(cache_root)
    episode_ids = list(parse(cache_root / "topology.md"))
    atomic_write(path, {
        "contract_version": VERSION,
        "run_id": str(uuid.uuid4()),
        "status": "IN_PROGRESS",
        "stage_two_content_sha256": stage_two_content_sha256(cache_root),
        "stage_two_content_leaves": load_leaves(cache_root),
        "episode_order": episode_ids,
        "episodes": {
            episode_id: {
                "state": "QUEUED",
                "leases": {},
                "execution_counts": {},
                "content_failures": {},
                "orchestration_failures": {},
                "outputs": {},
                "reviews": {},
            }
            for episode_id in episode_ids
        },
        "ending_plan": stage_two["ending_plan"],
    })


def require_current_stage_two(cache_root: Path, state: dict[str, Any]) -> None:
    path = cache_root / "stage-two-acceptance.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("contract_version") != STAGE_TWO_VERSION or receipt.get("status") != "PASS":
        raise ValueError("阶段二验收回执合同或状态错误")
    current = stage_two_content_sha256(cache_root)
    if state.get("stage_two_content_sha256") != current:
        raise ValueError("阶段二内容发生变化；先运行 rebase-stage-two 计算影响集，不得全量重置")


def record_orchestration_failure(episode: dict[str, Any], action: str, reason: str) -> None:
    failures = episode.setdefault("orchestration_failures", {})
    failures[action] = int(failures.get(action) or 0) + 1
    episode["last_failure"] = {
        "action": action,
        "kind": "orchestration",
        "reason": reason,
        "at": iso(now()),
    }
    if failures[action] >= 3:
        episode["fallback_required"] = {
            "action": action,
            "reason": "同一动作编排失败已达三次；下一次必须改用父端执行、消息传输或保存IN_PROGRESS",
        }


def sweep_expired(state: dict[str, Any]) -> bool:
    changed = False
    current = now()
    for episode in (state.get("episodes") or {}).values():
        for action, lease in list((episode.get("leases") or {}).items()):
            expires = str((lease or {}).get("expires_at") or "")
            if expires and parse_time(expires) <= current:
                del episode["leases"][action]
                record_orchestration_failure(episode, action, "租约过期，已自动回收")
                changed = True
    return changed


def available_actions(episode: dict[str, Any]) -> list[str]:
    state_name = str(episode.get("state"))
    actions = list((TRANSITIONS.get(state_name) or {}).keys())
    if state_name in {"REVIEWS_PREPARED", "REVIEWING"}:
        completed = set((episode.get("reviews") or {}).keys())
        actions = [action for action in actions if action not in completed]
    return actions


def claim(
    cache_root: Path,
    episode_id: str,
    action: str,
    owner: str,
    inputs: list[Path],
    lease_seconds: int,
) -> dict[str, Any]:
    state = load(cache_root)
    require_current_stage_two(cache_root, state)
    if sweep_expired(state):
        atomic_write(state_path(cache_root), state)
    episode = (state.get("episodes") or {}).get(episode_id)
    if not isinstance(episode, dict):
        raise ValueError("运行状态不存在该分集")
    breaker = episode.get("circuit_breaker") or {}
    if breaker.get("status") == "OPEN" and breaker.get("action") == action:
        raise ValueError("该内容动作已连续失败三次并熔断；必须改变策略后恢复")
    if action not in available_actions(episode):
        raise ValueError(f"非法状态转换：{episode.get('state')} -> {action}")
    if action == "ADAPT":
        incoming = predecessors(parse(cache_root / "topology.md"))[episode_id]
        blocked = [item for item in incoming if state["episodes"][item].get("state") != "EPISODE_ACCEPTED"]
        if blocked:
            raise ValueError(f"直接前置分集尚未验收：{blocked}")
    if action in (episode.get("leases") or {}):
        raise ValueError("该原子动作已有活动租约，不得重复调度")
    if not 60 <= lease_seconds <= 3600:
        raise ValueError("租约时长必须在60至3600秒之间")
    if action in CHILD_ACTIONS:
        expected_child_input = child_input(cache_root, action, episode_id)
        if inputs and [path.resolve() for path in inputs] != [expected_child_input]:
            raise ValueError(f"子Agent动作只接受标准输入：{expected_child_input}")
        inputs = [expected_child_input]
    input_hashes: dict[str, str] = {}
    for path in inputs:
        resolved = path.resolve()
        if not resolved.is_file():
            raise ValueError(f"原子动作输入不存在：{path}")
        input_hashes[str(resolved)] = sha256(resolved)
    issued = now()
    lease = secrets.token_hex(24)
    episode.setdefault("leases", {})[action] = {
        "lease": lease,
        "owner": owner,
        "input_hashes": input_hashes,
        "input_sha256": aggregate_hash(input_hashes),
        "issued_at": iso(issued),
        "expires_at": iso(issued + timedelta(seconds=lease_seconds)),
        "status": "RUNNING",
    }
    counts = episode.setdefault("execution_counts", {})
    counts[action] = int(counts.get(action) or 0) + 1
    atomic_write(state_path(cache_root), state)
    active = episode["leases"][action]
    return {
        "lease": lease,
        "episode_id": episode_id,
        "action": action,
        "input_hashes": input_hashes,
        "input_sha256": active["input_sha256"],
        "expires_at": active["expires_at"],
    }


def complete(
    cache_root: Path,
    episode_id: str,
    action: str,
    lease: str,
    outputs: list[Path],
    outcome: str = "PASS",
) -> None:
    state = load(cache_root)
    require_current_stage_two(cache_root, state)
    episode = state["episodes"].get(episode_id)
    active = (episode or {}).get("leases") or {}
    current_lease = active.get(action)
    if not isinstance(current_lease, dict) or current_lease.get("lease") != lease:
        raise ValueError("原子动作租约无效或已完成")
    if parse_time(str(current_lease["expires_at"])) <= now():
        raise ValueError("原子动作租约已过期；先执行abandon或重新claim")
    for name, expected in current_lease.get("input_hashes", {}).items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            raise ValueError("原子动作执行期间输入发生变化")
    if outcome not in {"PASS", "FAIL"}:
        raise ValueError("动作结果必须是PASS或FAIL")
    if action not in REVIEW_ACTIONS and outcome != "PASS":
        raise ValueError("只有独立复检动作可以用FAIL结果完成")
    resolved_outputs = [path.resolve() for path in outputs]
    required = expected_outputs(cache_root, action, episode_id, outcome)
    if set(resolved_outputs) != set(required) or len(resolved_outputs) != len(required):
        raise ValueError(
            "原子动作输出合同错误：expected="
            + json.dumps([str(path) for path in required], ensure_ascii=False)
        )
    output_hashes: dict[str, str] = {}
    for path in resolved_outputs:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"原子动作输出不存在或为空：{path}")
        output_hashes[str(path)] = sha256(path)
    target = (TRANSITIONS.get(str(episode.get("state"))) or {}).get(action)
    if not target:
        raise ValueError("当前状态不接受该原子动作完成")
    if action in REVIEW_ACTIONS:
        reviews = episode.setdefault("reviews", {})
        reviews[action] = {"outcome": outcome, "outputs": output_hashes}
        if set(reviews) == REVIEW_ACTIONS:
            target = (
                "REVIEWS_PASSED"
                if all(item.get("outcome") == "PASS" for item in reviews.values())
                else "REVIEWS_FAILED"
            )
        else:
            target = "REVIEWING"
    elif action == "REPAIR":
        episode["reviews"] = {}
    episode["state"] = target
    episode.setdefault("outputs", {})[action] = {
        "outcome": outcome,
        "files": output_hashes,
    }
    del active[action]
    episode.pop("fallback_required", None)
    atomic_write(state_path(cache_root), state)


def fail(
    cache_root: Path,
    episode_id: str,
    action: str,
    lease: str,
    reason: str,
    failure_kind: str,
) -> None:
    state = load(cache_root)
    episode = state["episodes"].get(episode_id)
    active = (episode or {}).get("leases") or {}
    current = active.get(action)
    if not isinstance(current, dict) or current.get("lease") != lease:
        raise ValueError("原子动作租约无效")
    del active[action]
    if failure_kind == "orchestration":
        record_orchestration_failure(episode, action, reason)
    else:
        failures = episode.setdefault("content_failures", {})
        failures[action] = int(failures.get(action) or 0) + 1
        episode["last_failure"] = {
            "action": action,
            "kind": "content",
            "reason": reason,
            "at": iso(now()),
        }
        if failures[action] >= 3:
            episode["circuit_breaker"] = {"action": action, "status": "OPEN"}
    state["status"] = "IN_PROGRESS"
    atomic_write(state_path(cache_root), state)


def abandon(cache_root: Path, episode_id: str, action: str, lease: str, reason: str) -> None:
    fail(cache_root, episode_id, action, lease, reason, "orchestration")


def recover(cache_root: Path, episode_id: str, action: str, strategy: str) -> None:
    state = load(cache_root)
    episode = state["episodes"].get(episode_id)
    breaker = (episode or {}).get("circuit_breaker") or {}
    if breaker.get("status") != "OPEN" or breaker.get("action") != action:
        raise ValueError("该内容动作没有打开的熔断器")
    if len(strategy.strip()) < 8:
        raise ValueError("恢复必须记录已改变的执行策略")
    episode["circuit_breaker"] = {
        "action": action,
        "status": "RECOVERED",
        "changed_strategy": strategy.strip(),
    }
    atomic_write(state_path(cache_root), state)


TECHNICAL_RECOVERY = {
    "REBUILD_ADAPTATION": ("QUEUED", set()),
    "RESEAL_STRUCTURE": ("ENHANCED", {"ADAPT", "WRITE_DRAFT", "VALIDATE_DRAFT", "ENHANCE"}),
    "REPREPARE_REVIEWS": ("STRUCTURE_VALIDATED", {"ADAPT", "WRITE_DRAFT", "VALIDATE_DRAFT", "ENHANCE", "VALIDATE_STRUCTURE"}),
    "REBIND_ACCEPTANCE": ("REVIEWS_PASSED", {"ADAPT", "WRITE_DRAFT", "VALIDATE_DRAFT", "ENHANCE", "VALIDATE_STRUCTURE", "PREPARE_REVIEWS", "REVIEW_DRAMA", "REVIEW_COLD_READ", "MERGE_FINDINGS", "REPAIR"}),
}


def technical_recover(cache_root: Path, episode_id: str, recovery: str, reason: str) -> None:
    state = load(cache_root)
    require_current_stage_two(cache_root, state)
    episode = (state.get("episodes") or {}).get(episode_id)
    if not isinstance(episode, dict):
        raise ValueError("运行状态不存在该分集")
    if episode.get("leases"):
        raise ValueError("技术恢复前必须结束当前集全部活动租约")
    if recovery not in TECHNICAL_RECOVERY:
        raise ValueError("未知技术恢复边")
    if len(reason.strip()) < 8:
        raise ValueError("技术恢复必须记录具体原因")
    target, keep = TECHNICAL_RECOVERY[recovery]
    episode["state"] = target
    episode["outputs"] = {key: value for key, value in (episode.get("outputs") or {}).items() if key in keep}
    if target not in {"REVIEWING", "REVIEWS_PASSED"}:
        episode["reviews"] = {}
    episode["last_technical_recovery"] = {"edge": recovery, "reason": reason.strip(), "at": iso(now())}
    state["status"] = "IN_PROGRESS"
    atomic_write(state_path(cache_root), state)


def rebase_stage_two(cache_root: Path, reason: str) -> list[str]:
    """Rebind receipt-only changes; invalidate only synopsis-changed nodes and descendants."""
    state = load(cache_root)
    if len(reason.strip()) < 8:
        raise ValueError("阶段二重绑必须记录具体原因")
    current = load_stage_two(cache_root).get("content_leaves") or {}
    previous = state.get("stage_two_content_leaves") or {}
    if previous.get("global") != current.get("global"):
        raise ValueError("阶段二全局故事、拓扑或情绪材料发生变化；不得伪装成局部技术重绑")
    old_episodes = previous.get("episodes") or {}
    new_episodes = current.get("episodes") or {}
    changed = {episode_id for episode_id in set(old_episodes) | set(new_episodes) if old_episodes.get(episode_id) != new_episodes.get(episode_id)}
    nodes = parse(cache_root / "topology.md")
    affected = set(changed)
    pending = list(changed)
    while pending:
        source = pending.pop()
        for target in nodes.get(source, {}).get("successors", []):
            if target not in affected:
                affected.add(target)
                pending.append(target)
    for episode_id in sorted(affected):
        episode = (state.get("episodes") or {}).get(episode_id)
        if not isinstance(episode, dict):
            continue
        episode.update({"state": "QUEUED", "leases": {}, "outputs": {}, "reviews": {}})
        episode["last_stage_two_rebase"] = {"reason": reason.strip(), "at": iso(now())}
    state["stage_two_content_sha256"] = str(current.get("content_sha256") or "")
    state["stage_two_content_leaves"] = current
    state["status"] = "IN_PROGRESS"
    atomic_write(state_path(cache_root), state)
    return sorted(affected)


def rewrite_episode(cache_root: Path, episode_id: str, reason: str) -> None:
    """Archive the failed writing attempt and return this episode to Screenwriter."""
    state = load(cache_root)
    require_current_stage_two(cache_root, state)
    episode = (state.get("episodes") or {}).get(episode_id)
    if not isinstance(episode, dict) or episode.get("state") != "FINDINGS_MERGED":
        raise ValueError("只有已合并且要求整集重写的问题单可以回到Screenwriter")
    if (episode.get("leases") or {}):
        raise ValueError("整集重写前必须结束当前集全部活动租约")
    merged_path = cache_root / "merged-review-findings" / f"{episode_id}.json"
    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    if merged.get("rewrite_required") is not True:
        raise ValueError("当前问题单允许局部修复，不得扩大为整集重写")
    if len(reason.strip()) < 8:
        raise ValueError("整集重写必须记录具体原因")

    archive = cache_root / "rewrite-history" / episode_id / str(uuid.uuid4())
    exact = [
        f"screenplay-drafts/{episode_id}.md",
        f"screenwriter-receipts/{episode_id}.json",
        f"enhancer-inputs/{episode_id}.txt",
        f"enhanced-screenplays/{episode_id}.md",
        f"episodes/{episode_id}.md",
        f"episode-structure-receipts/{episode_id}.json",
        f"dramatization-plans/{episode_id}.json",
        f"dramatization-receipts/{episode_id}.json",
        f"episode-quality-receipts/{episode_id}.json",
        f"merged-review-findings/{episode_id}.json",
        f"repair-baselines/{episode_id}.md",
        f"review-repair-inputs/{episode_id}.txt",
        f"review-repair-receipts/{episode_id}.json",
        f"episode-acceptance-receipts/{episode_id}.json",
    ]
    paths = [cache_root / relative for relative in exact]
    for pattern in (
        f"review-packets/{episode_id}.*.json",
        f"review-findings/{episode_id}.*.json",
        f"child-results/{episode_id}.*",
    ):
        paths.extend(cache_root.glob(pattern))
    moved: list[str] = []
    for source in sorted(set(paths)):
        if not source.is_file():
            continue
        relative = source.relative_to(cache_root)
        target = archive / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        moved.append(str(relative))
    atomic_write(archive / "rewrite-receipt.json", {
        "contract_version": "nextplay.episode-rewrite.v1",
        "episode_id": episode_id,
        "reason": reason.strip(),
        "archived_files": moved,
    })
    episode["state"] = "ADAPTED"
    episode["reviews"] = {}
    episode["leases"] = {}
    episode["outputs"] = {
        key: value
        for key, value in (episode.get("outputs") or {}).items()
        if key == "ADAPT"
    }
    episode["last_rewrite_archive"] = str(archive.relative_to(cache_root))
    state["status"] = "IN_PROGRESS"
    atomic_write(state_path(cache_root), state)


def status(cache_root: Path) -> dict[str, Any]:
    state = load(cache_root)
    require_current_stage_two(cache_root, state)
    changed = sweep_expired(state)
    accepted = [episode_id for episode_id, value in state["episodes"].items() if value.get("state") == "EPISODE_ACCEPTED"]
    state["status"] = "READY_FOR_CLOSURE" if len(accepted) == len(state["episodes"]) else "IN_PROGRESS"
    state["accepted_count"] = len(accepted)
    state["total_count"] = len(state["episodes"])
    next_episode = next(
        (episode_id for episode_id in state["episode_order"] if state["episodes"][episode_id].get("state") != "EPISODE_ACCEPTED"),
        None,
    )
    state["next_episode_id"] = next_episode
    state["next_actions"] = available_actions(state["episodes"][next_episode]) if next_episode else []
    if changed or state_path(cache_root).is_file():
        persisted = {key: value for key, value in state.items() if key not in {"accepted_count", "total_count", "next_episode_id", "next_actions"}}
        atomic_write(state_path(cache_root), persisted)
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("cache_root", type=Path)
    sub.add_parser("status").add_argument("cache_root", type=Path)
    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("cache_root", type=Path)
    claim_parser.add_argument("episode_id")
    claim_parser.add_argument("action", choices=ACTIONS)
    claim_parser.add_argument("--owner", required=True)
    claim_parser.add_argument("--input", action="append", type=Path, default=[])
    claim_parser.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS)
    complete_parser = sub.add_parser("complete")
    complete_parser.add_argument("cache_root", type=Path)
    complete_parser.add_argument("episode_id")
    complete_parser.add_argument("action", choices=ACTIONS)
    complete_parser.add_argument("--lease", required=True)
    complete_parser.add_argument("--output", action="append", type=Path, default=[])
    complete_parser.add_argument("--outcome", choices=("PASS", "FAIL"), default="PASS")
    fail_parser = sub.add_parser("fail")
    fail_parser.add_argument("cache_root", type=Path)
    fail_parser.add_argument("episode_id")
    fail_parser.add_argument("action", choices=ACTIONS)
    fail_parser.add_argument("--lease", required=True)
    fail_parser.add_argument("--reason", required=True)
    fail_parser.add_argument("--kind", choices=("content", "orchestration"), required=True)
    abandon_parser = sub.add_parser("abandon")
    abandon_parser.add_argument("cache_root", type=Path)
    abandon_parser.add_argument("episode_id")
    abandon_parser.add_argument("action", choices=ACTIONS)
    abandon_parser.add_argument("--lease", required=True)
    abandon_parser.add_argument("--reason", required=True)
    recover_parser = sub.add_parser("recover")
    recover_parser.add_argument("cache_root", type=Path)
    recover_parser.add_argument("episode_id")
    recover_parser.add_argument("action", choices=ACTIONS)
    recover_parser.add_argument("--strategy", required=True)
    rewrite_parser = sub.add_parser("rewrite")
    rewrite_parser.add_argument("cache_root", type=Path)
    rewrite_parser.add_argument("episode_id")
    rewrite_parser.add_argument("--reason", required=True)
    technical_parser = sub.add_parser("technical-recover")
    technical_parser.add_argument("cache_root", type=Path)
    technical_parser.add_argument("episode_id")
    technical_parser.add_argument("recovery", choices=tuple(TECHNICAL_RECOVERY))
    technical_parser.add_argument("--reason", required=True)
    rebase_parser = sub.add_parser("rebase-stage-two")
    rebase_parser.add_argument("cache_root", type=Path)
    rebase_parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            init(args.cache_root)
            print("RUN_STATE_INITIALIZED")
        elif args.command == "status":
            print(json.dumps(status(args.cache_root), ensure_ascii=False, indent=2))
        elif args.command == "claim":
            print(json.dumps(claim(args.cache_root, args.episode_id, args.action, args.owner, args.input, args.lease_seconds), ensure_ascii=False, indent=2))
        elif args.command == "complete":
            complete(args.cache_root, args.episode_id, args.action, args.lease, args.output, args.outcome)
            print("ATOMIC_ACTION_COMMITTED")
        elif args.command == "fail":
            fail(args.cache_root, args.episode_id, args.action, args.lease, args.reason, args.kind)
            print("ATOMIC_ACTION_FAILED")
        elif args.command == "abandon":
            abandon(args.cache_root, args.episode_id, args.action, args.lease, args.reason)
            print("ATOMIC_ACTION_ABANDONED")
        elif args.command == "recover":
            recover(args.cache_root, args.episode_id, args.action, args.strategy)
            print("CIRCUIT_BREAKER_RECOVERED")
        elif args.command == "rewrite":
            rewrite_episode(args.cache_root, args.episode_id, args.reason)
            print("EPISODE_RETURNED_TO_SCREENWRITER")
        elif args.command == "technical-recover":
            technical_recover(args.cache_root, args.episode_id, args.recovery, args.reason)
            print("TECHNICAL_RECOVERY_READY")
        else:
            print(json.dumps({"affected_episode_ids": rebase_stage_two(args.cache_root, args.reason)}, ensure_ascii=False))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
