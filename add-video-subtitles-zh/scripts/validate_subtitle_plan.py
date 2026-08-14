#!/usr/bin/env python3
"""Validate the private nextplay.video-subtitles.v1 execution plan."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT = "nextplay.video-subtitles.v1"
KINDS = {"dialogue", "worldview", "character_intro"}
STATUSES = {"waiting_user", "in_progress", "failed", "skipped", "completed"}
BACKGROUND_MODES = {"none"}
WORLDVIEW_PLACEMENT_MODES = {
    "existing_exclusive_segment",
    "generated_reference_shot",
    "existing_whitespace",
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def require_nonempty_string(
    value: Any, path: str, errors: list[str]
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        fail(errors, f"{path} must be a non-empty string")
        return None
    return value.strip()


def require_nonnegative_int(
    value: Any, path: str, errors: list[str], *, positive: bool = False
) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        fail(errors, f"{path} must be an integer")
        return None
    if positive and value <= 0:
        fail(errors, f"{path} must be greater than zero")
        return None
    if not positive and value < 0:
        fail(errors, f"{path} must be non-negative")
        return None
    return value


def require_bbox(
    value: Any,
    path: str,
    errors: list[str],
    *,
    width: int | None = None,
    height: int | None = None,
    enforce_safe_area: bool = False,
) -> dict[str, int] | None:
    if not isinstance(value, dict):
        fail(errors, f"{path} must be an object")
        return None
    result: dict[str, int] = {}
    for key in ("x1", "y1", "x2", "y2"):
        coordinate = require_nonnegative_int(value.get(key), f"{path}.{key}", errors)
        if coordinate is not None:
            result[key] = coordinate
    if len(result) != 4:
        return None
    if result["x2"] <= result["x1"] or result["y2"] <= result["y1"]:
        fail(errors, f"{path} must have x2>x1 and y2>y1")
        return None
    if width is not None and result["x2"] > width:
        fail(errors, f"{path}.x2 exceeds video width")
    if height is not None and result["y2"] > height:
        fail(errors, f"{path}.y2 exceeds video height")
    if enforce_safe_area and width is not None and height is not None:
        if result["x1"] < round(width * 0.05):
            fail(errors, f"{path} crosses left 5% safe boundary")
        if result["x2"] > round(width * 0.95):
            fail(errors, f"{path} crosses right 5% safe boundary")
        if result["y1"] < round(height * 0.05):
            fail(errors, f"{path} crosses top 5% safe boundary")
        if result["y2"] > round(height * 0.95):
            fail(errors, f"{path} crosses bottom 5% safe boundary")
    return result


def bboxes_intersect(left: dict[str, int], right: dict[str, int]) -> bool:
    return not (
        left["x2"] <= right["x1"]
        or right["x2"] <= left["x1"]
        or left["y2"] <= right["y1"]
        or right["y2"] <= left["y1"]
    )


def validate_plan(plan: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["root must be a JSON object"]

    if plan.get("contract") != CONTRACT:
        fail(errors, f"contract must equal {CONTRACT}")

    status = plan.get("status")
    if status not in STATUSES:
        fail(errors, f"status must be one of {sorted(STATUSES)}")

    settings = plan.get("settings")
    if not isinstance(settings, dict):
        fail(errors, "settings must be an object")
        settings = {}

    language_mode = settings.get("language_mode")
    if language_mode not in {"zh", "zh_en", "zh_other", "other_only"}:
        fail(
            errors,
            "settings.language_mode must be zh, zh_en, zh_other, or other_only",
        )
    if language_mode in {"zh_other", "other_only"}:
        require_nonempty_string(
            settings.get("target_language"),
            "settings.target_language",
            errors,
        )
    require_nonempty_string(settings.get("font_key"), "settings.font_key", errors)
    require_nonempty_string(settings.get("font_name"), "settings.font_name", errors)
    background_mode = settings.get("background_mode")
    if background_mode not in BACKGROUND_MODES:
        fail(
            errors,
            f"settings.background_mode must be one of {sorted(BACKGROUND_MODES)}",
        )
    worldview_placement_mode = settings.get("worldview_placement_mode")
    if settings.get("include_worldview") is True:
        if worldview_placement_mode not in WORLDVIEW_PLACEMENT_MODES:
            fail(
                errors,
                "settings.worldview_placement_mode must be one of "
                f"{sorted(WORLDVIEW_PLACEMENT_MODES)} when worldview is enabled",
            )

    routes = plan.get("routes")
    if not isinstance(routes, list) or not routes:
        fail(errors, "routes must be a non-empty array")
        routes = []

    route_ids: set[str] = set()
    route_video_ids: dict[str, list[str]] = {}
    for index, route in enumerate(routes):
        path = f"routes[{index}]"
        if not isinstance(route, dict):
            fail(errors, f"{path} must be an object")
            continue
        route_id = require_nonempty_string(route.get("route_id"), f"{path}.route_id", errors)
        videos = route.get("video_ids")
        if route_id:
            if route_id in route_ids:
                fail(errors, f"duplicate route_id: {route_id}")
            route_ids.add(route_id)
        if not isinstance(videos, list) or not videos:
            fail(errors, f"{path}.video_ids must be a non-empty array")
            continue
        cleaned: list[str] = []
        for video_index, video_id in enumerate(videos):
            cleaned_id = require_nonempty_string(
                video_id, f"{path}.video_ids[{video_index}]", errors
            )
            if cleaned_id:
                cleaned.append(cleaned_id)
        if route_id:
            route_video_ids[route_id] = cleaned

    videos = plan.get("videos")
    if not isinstance(videos, list) or not videos:
        fail(errors, "videos must be a non-empty array")
        videos = []

    video_ids: set[str] = set()
    event_ids: set[str] = set()
    character_events: list[tuple[str, str, str, int, set[str]]] = []
    character_event_details: dict[str, tuple[str, str, int, set[str]]] = {}
    worldview_events: list[tuple[str, int, int, set[str]]] = []

    for video_index, video in enumerate(videos):
        path = f"videos[{video_index}]"
        if not isinstance(video, dict):
            fail(errors, f"{path} must be an object")
            continue
        video_id = require_nonempty_string(video.get("video_id"), f"{path}.video_id", errors)
        if video_id:
            if video_id in video_ids:
                fail(errors, f"duplicate video_id: {video_id}")
            video_ids.add(video_id)
        require_nonempty_string(
            video.get("visible_name"), f"{path}.visible_name", errors
        )
        require_nonempty_string(video.get("source"), f"{path}.source", errors)
        require_nonempty_string(
            video.get("source_media_ref"), f"{path}.source_media_ref", errors
        )
        require_nonempty_string(
            video.get("source_media_version"), f"{path}.source_media_version", errors
        )
        require_nonnegative_int(
            video.get("render_revision"),
            f"{path}.render_revision",
            errors,
            positive=True,
        )
        require_nonempty_string(video.get("output_name"), f"{path}.output_name", errors)
        duration = require_nonnegative_int(
            video.get("duration_ms"), f"{path}.duration_ms", errors, positive=True
        )
        width = require_nonnegative_int(
            video.get("width"), f"{path}.width", errors, positive=True
        )
        height = require_nonnegative_int(
            video.get("height"), f"{path}.height", errors, positive=True
        )

        segments = video.get("segments")
        if not isinstance(segments, list) or not segments:
            fail(errors, f"{path}.segments must be a non-empty array")
            segments = []
        segment_map: dict[str, tuple[int, int]] = {}
        expected_offset = 0
        for segment_index, segment in enumerate(segments):
            segment_path = f"{path}.segments[{segment_index}]"
            if not isinstance(segment, dict):
                fail(errors, f"{segment_path} must be an object")
                continue
            segment_id = require_nonempty_string(
                segment.get("segment_id"), f"{segment_path}.segment_id", errors
            )
            require_nonempty_string(
                segment.get("source"), f"{segment_path}.source", errors
            )
            segment_duration = require_nonnegative_int(
                segment.get("duration_ms"),
                f"{segment_path}.duration_ms",
                errors,
                positive=True,
            )
            segment_offset = require_nonnegative_int(
                segment.get("concat_offset_ms"),
                f"{segment_path}.concat_offset_ms",
                errors,
            )
            if segment_offset is not None and segment_offset != expected_offset:
                fail(
                    errors,
                    f"{segment_path}.concat_offset_ms must equal cumulative "
                    f"prior duration {expected_offset}",
                )
            if segment_id and segment_duration is not None and segment_offset is not None:
                if segment_id in segment_map:
                    fail(errors, f"duplicate segment_id in {path}: {segment_id}")
                segment_map[segment_id] = (segment_duration, segment_offset)
            if segment_duration is not None:
                expected_offset += segment_duration
        if duration is not None and segments and expected_offset != duration:
            fail(
                errors,
                f"{path}.segments cumulative duration {expected_offset} "
                f"must equal video duration {duration}",
            )

        source_lines = video.get("dialogue_source_lines")
        if not isinstance(source_lines, list):
            fail(errors, f"{path}.dialogue_source_lines must be an array")
            source_lines = []
        source_line_map: dict[str, dict[str, Any]] = {}
        source_event_ids: set[str] = set()
        for line_index, line in enumerate(source_lines):
            line_path = f"{path}.dialogue_source_lines[{line_index}]"
            if not isinstance(line, dict):
                fail(errors, f"{line_path} must be an object")
                continue
            line_id = require_nonempty_string(
                line.get("line_id"), f"{line_path}.line_id", errors
            )
            require_nonempty_string(line.get("text"), f"{line_path}.text", errors)
            require_nonempty_string(line.get("speaker"), f"{line_path}.speaker", errors)
            status_value = line.get("status")
            if status_value not in {"spoken", "not_spoken_in_final"}:
                fail(
                    errors,
                    f"{line_path}.status must be spoken or not_spoken_in_final",
                )
            if status_value == "spoken":
                linked_event = require_nonempty_string(
                    line.get("event_id"), f"{line_path}.event_id", errors
                )
                if linked_event:
                    if linked_event in source_event_ids:
                        fail(errors, f"duplicate dialogue source event_id {linked_event}")
                    source_event_ids.add(linked_event)
            elif status_value == "not_spoken_in_final":
                require_nonempty_string(
                    line.get("evidence"), f"{line_path}.evidence", errors
                )
            if line_id:
                if line_id in source_line_map:
                    fail(errors, f"duplicate dialogue line_id in {path}: {line_id}")
                source_line_map[line_id] = line

        events = video.get("events")
        if not isinstance(events, list):
            fail(errors, f"{path}.events must be an array")
            continue

        dialogue_by_routes: list[tuple[int, int, set[str], str]] = []
        video_dialogue_event_ids: set[str] = set()
        local_worldview_events: list[
            tuple[int, int, set[str], str, dict[str, int] | None]
        ] = []
        local_non_world_events: list[
            tuple[int, int, set[str], str, dict[str, int] | None]
        ] = []
        for event_index, event in enumerate(events):
            event_path = f"{path}.events[{event_index}]"
            if not isinstance(event, dict):
                fail(errors, f"{event_path} must be an object")
                continue
            event_id = require_nonempty_string(
                event.get("event_id"), f"{event_path}.event_id", errors
            )
            if event_id:
                if event_id in event_ids:
                    fail(errors, f"duplicate event_id: {event_id}")
                event_ids.add(event_id)
            kind = event.get("kind")
            if kind not in KINDS:
                fail(errors, f"{event_path}.kind must be one of {sorted(KINDS)}")
            start = require_nonnegative_int(
                event.get("start_ms"), f"{event_path}.start_ms", errors
            )
            end = require_nonnegative_int(
                event.get("end_ms"), f"{event_path}.end_ms", errors
            )
            if start is not None and end is not None:
                if end <= start:
                    fail(errors, f"{event_path}.end_ms must be greater than start_ms")
                if duration is not None and end > duration:
                    fail(errors, f"{event_path} ends after video duration")
            require_nonempty_string(event.get("text"), f"{event_path}.text", errors)
            if (
                language_mode in {"zh_en", "zh_other", "other_only"}
                and kind != "character_intro"
            ):
                require_nonempty_string(
                    event.get("translation"), f"{event_path}.translation", errors
                )

            applies = event.get("applies_to_routes")
            applies_set: set[str] = set()
            if not isinstance(applies, list) or not applies:
                fail(errors, f"{event_path}.applies_to_routes must be a non-empty array")
            else:
                for route_index, route_id in enumerate(applies):
                    cleaned_route = require_nonempty_string(
                        route_id,
                        f"{event_path}.applies_to_routes[{route_index}]",
                        errors,
                    )
                    if cleaned_route:
                        applies_set.add(cleaned_route)
                        if cleaned_route not in route_ids:
                            fail(errors, f"{event_path} references unknown route {cleaned_route}")
                        elif video_id and video_id not in route_video_ids.get(cleaned_route, []):
                            fail(
                                errors,
                                f"{event_path} applies to route {cleaned_route} "
                                f"that does not contain video {video_id}",
                            )

            position = event.get("position")
            text_bbox: dict[str, int] | None = None
            if not isinstance(position, dict):
                fail(errors, f"{event_path}.position must be an object")
            else:
                alignment = position.get("alignment")
                if alignment not in range(1, 10):
                    fail(errors, f"{event_path}.position.alignment must be 1..9")
                for margin_name in ("margin_l", "margin_r", "margin_v"):
                    require_nonnegative_int(
                        position.get(margin_name),
                        f"{event_path}.position.{margin_name}",
                        errors,
                    )
                text_bbox = require_bbox(
                    position.get("text_bbox"),
                    f"{event_path}.position.text_bbox",
                    errors,
                    width=width,
                    height=height,
                    enforce_safe_area=True,
                )
                if "x" in position or "y" in position:
                    anchor_x = require_nonnegative_int(
                        position.get("x"), f"{event_path}.position.x", errors
                    )
                    anchor_y = require_nonnegative_int(
                        position.get("y"), f"{event_path}.position.y", errors
                    )
                    if (
                        text_bbox is not None
                        and anchor_x is not None
                        and anchor_y is not None
                        and alignment in range(1, 10)
                    ):
                        if alignment in {1, 4, 7}:
                            expected_x = text_bbox["x1"]
                        elif alignment in {2, 5, 8}:
                            expected_x = (text_bbox["x1"] + text_bbox["x2"]) / 2
                        else:
                            expected_x = text_bbox["x2"]
                        if alignment in {7, 8, 9}:
                            expected_y = text_bbox["y1"]
                        elif alignment in {4, 5, 6}:
                            expected_y = (text_bbox["y1"] + text_bbox["y2"]) / 2
                        else:
                            expected_y = text_bbox["y2"]
                        if abs(anchor_x - expected_x) > 24:
                            fail(
                                errors,
                                f"{event_path}.position.x contradicts text_bbox "
                                f"for alignment {alignment}",
                            )
                        if abs(anchor_y - expected_y) > 24:
                            fail(
                                errors,
                                f"{event_path}.position.y contradicts text_bbox "
                                f"for alignment {alignment}",
                            )

            if kind == "dialogue" and start is not None and end is not None:
                dialogue_by_routes.append((start, end, applies_set, event_id or event_path))
                local_non_world_events.append(
                    (start, end, applies_set, event_id or event_path, text_bbox)
                )
                if event_id:
                    video_dialogue_event_ids.add(event_id)
                if event.get("fade_in_ms", 0) or event.get("fade_out_ms", 0):
                    fail(errors, f"{event_path} dialogue must not use fade")
                source_line_id = require_nonempty_string(
                    event.get("source_line_id"),
                    f"{event_path}.source_line_id",
                    errors,
                )
                source_segment_id = require_nonempty_string(
                    event.get("source_segment_id"),
                    f"{event_path}.source_segment_id",
                    errors,
                )
                local_start = require_nonnegative_int(
                    event.get("segment_local_start_ms"),
                    f"{event_path}.segment_local_start_ms",
                    errors,
                )
                local_end = require_nonnegative_int(
                    event.get("segment_local_end_ms"),
                    f"{event_path}.segment_local_end_ms",
                    errors,
                )
                event_offset = require_nonnegative_int(
                    event.get("concat_offset_ms"),
                    f"{event_path}.concat_offset_ms",
                    errors,
                )
                require_nonempty_string(
                    event.get("audio_start_evidence"),
                    f"{event_path}.audio_start_evidence",
                    errors,
                )
                require_nonempty_string(
                    event.get("audio_end_evidence"),
                    f"{event_path}.audio_end_evidence",
                    errors,
                )
                speaker = require_nonempty_string(
                    event.get("speaker"), f"{event_path}.speaker", errors
                )
                rendered_text = str(event.get("text", "")).strip()
                rendered_translation = str(event.get("translation", "")).strip()
                if speaker and rendered_text.startswith((f"{speaker}：", f"{speaker}:")):
                    fail(
                        errors,
                        f"{event_path} rendered dialogue must not include speaker prefix",
                    )
                if re.match(
                    r"^[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){1,3}\s*[:：]\s*",
                    rendered_translation,
                ):
                    fail(
                        errors,
                        f"{event_path} translated dialogue must not include speaker prefix",
                    )
                segment_details = (
                    segment_map.get(source_segment_id) if source_segment_id else None
                )
                if source_segment_id and segment_details is None:
                    fail(
                        errors,
                        f"{event_path} references unknown segment {source_segment_id}",
                    )
                elif (
                    segment_details is not None
                    and local_start is not None
                    and local_end is not None
                    and event_offset is not None
                ):
                    segment_duration, segment_offset = segment_details
                    if local_end <= local_start:
                        fail(
                            errors,
                            f"{event_path}.segment_local_end_ms must exceed local start",
                        )
                    if local_end > segment_duration:
                        fail(errors, f"{event_path} local time exceeds segment duration")
                    if event_offset != segment_offset:
                        fail(
                            errors,
                            f"{event_path}.concat_offset_ms must equal segment offset "
                            f"{segment_offset}",
                        )
                    if start != local_start + segment_offset:
                        fail(
                            errors,
                            f"{event_path}.start_ms must equal local start plus offset",
                        )
                    if end != local_end + segment_offset:
                        fail(
                            errors,
                            f"{event_path}.end_ms must equal local end plus offset",
                        )
                line = source_line_map.get(source_line_id) if source_line_id else None
                if source_line_id and line is None:
                    fail(errors, f"{event_path} references unknown source line {source_line_id}")
                elif line is not None:
                    if line.get("status") != "spoken":
                        fail(errors, f"{event_path} source line is not marked spoken")
                    if line.get("event_id") != event_id:
                        fail(errors, f"{event_path} source line points to another event")
                    if str(line.get("text", "")).strip() != str(event.get("text", "")).strip():
                        fail(errors, f"{event_path} text differs from formal source line")
                    if speaker and str(line.get("speaker", "")).strip() != speaker:
                        fail(errors, f"{event_path} speaker differs from formal source line")
            elif kind == "worldview" and start is not None and end is not None:
                worldview_events.append((video_id or "", start, end, applies_set))
                local_worldview_events.append(
                    (start, end, applies_set, event_id or event_path, text_bbox)
                )
                if start < 0 or end > 5000:
                    fail(errors, f"{event_path} worldview must stay within first 5000ms")
                require_nonempty_string(
                    event.get("stable_whitespace_evidence"),
                    f"{event_path}.stable_whitespace_evidence",
                    errors,
                )
            elif kind == "character_intro" and start is not None:
                if end is not None:
                    local_non_world_events.append(
                        (start, end, applies_set, event_id or event_path, text_bbox)
                    )
                character_name = require_nonempty_string(
                    event.get("character_name"),
                    f"{event_path}.character_name",
                    errors,
                )
                require_nonempty_string(
                    event.get("character_identity"),
                    f"{event_path}.character_identity",
                    errors,
                )
                if language_mode in {"zh_en", "zh_other", "other_only"}:
                    require_nonempty_string(
                        event.get("character_name_translation"),
                        f"{event_path}.character_name_translation",
                        errors,
                    )
                    require_nonempty_string(
                        event.get("character_identity_translation"),
                        f"{event_path}.character_identity_translation",
                        errors,
                    )
                identity_evidence = event.get("identity_evidence")
                if not isinstance(identity_evidence, list) or len(identity_evidence) < 2:
                    fail(
                        errors,
                        f"{event_path}.identity_evidence must contain at least two anchors",
                    )
                else:
                    for evidence_index, evidence in enumerate(identity_evidence):
                        require_nonempty_string(
                            evidence,
                            f"{event_path}.identity_evidence[{evidence_index}]",
                            errors,
                        )
                first_clear = require_nonnegative_int(
                    event.get("first_clear_visible_ms"),
                    f"{event_path}.first_clear_visible_ms",
                    errors,
                )
                require_nonempty_string(
                    event.get("first_clear_frame"),
                    f"{event_path}.first_clear_frame",
                    errors,
                )
                character_side = event.get("character_side")
                if character_side not in {"left", "right"}:
                    fail(errors, f"{event_path}.character_side must be left or right")
                character_bbox = require_bbox(
                    event.get("character_bbox"),
                    f"{event_path}.character_bbox",
                    errors,
                    width=width,
                    height=height,
                )
                face_bbox = require_bbox(
                    event.get("face_bbox"),
                    f"{event_path}.face_bbox",
                    errors,
                    width=width,
                    height=height,
                )
                if first_clear is not None and start < first_clear:
                    fail(errors, f"{event_path} starts before first clear visible frame")
                if (
                    text_bbox is not None
                    and face_bbox is not None
                    and bboxes_intersect(text_bbox, face_bbox)
                ):
                    fail(errors, f"{event_path} text bbox overlaps face bbox")
                if (
                    text_bbox is not None
                    and character_bbox is not None
                    and width is not None
                    and character_side in {"left", "right"}
                ):
                    character_center = (character_bbox["x1"] + character_bbox["x2"]) / 2
                    text_center = (text_bbox["x1"] + text_bbox["x2"]) / 2
                    detected_side = "left" if character_center < width / 2 else "right"
                    text_side = "left" if text_center < width / 2 else "right"
                    if detected_side != character_side:
                        fail(errors, f"{event_path}.character_side contradicts character bbox")
                    if text_side != character_side:
                        fail(errors, f"{event_path} text is not on character side")
                    horizontal_gap = max(
                        0,
                        character_bbox["x1"] - text_bbox["x2"],
                        text_bbox["x1"] - character_bbox["x2"],
                    )
                    if horizontal_gap > width * 0.25:
                        fail(errors, f"{event_path} text is too far from character")
                if character_name and video_id:
                    character_events.append(
                        (video_id, character_name, event_id or event_path, start, applies_set)
                    )
                    if event_id:
                        character_event_details[event_id] = (
                            video_id,
                            character_name,
                            start,
                            applies_set,
                        )

        for left_index, left in enumerate(dialogue_by_routes):
            for right in dialogue_by_routes[left_index + 1 :]:
                left_start, left_end, left_routes, left_id = left
                right_start, right_end, right_routes, right_id = right
                if left_routes & right_routes and max(left_start, right_start) < min(
                    left_end, right_end
                ):
                    fail(
                        errors,
                        f"dialogue events {left_id} and {right_id} overlap on the same route",
                    )
        missing_dialogue_events = source_event_ids - video_dialogue_event_ids
        if missing_dialogue_events:
            fail(
                errors,
                f"{path} spoken source lines lack dialogue events: "
                + ", ".join(sorted(missing_dialogue_events)),
            )
        unlinked_dialogue_events = video_dialogue_event_ids - source_event_ids
        if unlinked_dialogue_events:
            fail(
                errors,
                f"{path} dialogue events lack spoken source lines: "
                + ", ".join(sorted(unlinked_dialogue_events)),
            )
        for world_index, world in enumerate(local_worldview_events):
            world_start, world_end, world_routes, world_id, world_bbox = world
            for other_world in local_worldview_events[world_index + 1 :]:
                (
                    other_world_start,
                    other_world_end,
                    other_world_routes,
                    other_world_id,
                    _,
                ) = other_world
                if world_routes & other_world_routes and max(
                    world_start, other_world_start
                ) < min(world_end, other_world_end):
                    fail(
                        errors,
                        f"worldview cards {world_id} and {other_world_id} overlap; "
                        "world rule and episode premise must display sequentially",
                    )
            for (
                other_start,
                other_end,
                other_routes,
                other_id,
                other_bbox,
            ) in local_non_world_events:
                if world_routes & other_routes and max(world_start, other_start) < min(
                    world_end, other_end
                ):
                    if worldview_placement_mode != "existing_whitespace":
                        fail(
                            errors,
                            f"worldview event {world_id} overlaps {other_id}; "
                            "selected placement mode requires an exclusive interval",
                        )
                    elif (
                        world_bbox is None
                        or other_bbox is None
                        or bboxes_intersect(world_bbox, other_bbox)
                    ):
                        fail(
                            errors,
                            f"worldview event {world_id} spatially overlaps {other_id} "
                            "in existing_whitespace mode",
                        )

    for route_id, route_videos in route_video_ids.items():
        for video_id in route_videos:
            if video_id not in video_ids:
                fail(errors, f"route {route_id} references unknown video {video_id}")

    include_worldview = settings.get("include_worldview")
    if include_worldview is True and not worldview_events:
        fail(errors, "settings.include_worldview is true but no worldview event exists")
    if include_worldview is False and worldview_events:
        fail(errors, "worldview events exist while settings.include_worldview is false")
    worldview_contexts = plan.get("worldview_contexts", [])
    if include_worldview is True:
        if not isinstance(worldview_contexts, list) or not worldview_contexts:
            fail(
                errors,
                "settings.include_worldview is true but worldview_contexts is empty",
            )
            worldview_contexts = []
        covered_routes: set[str] = set()
        for index, context in enumerate(worldview_contexts):
            path = f"worldview_contexts[{index}]"
            if not isinstance(context, dict):
                fail(errors, f"{path} must be an object")
                continue
            entry_video_id = require_nonempty_string(
                context.get("entry_video_id"), f"{path}.entry_video_id", errors
            )
            require_nonempty_string(
                context.get("entry_episode_id"), f"{path}.entry_episode_id", errors
            )
            require_nonempty_string(
                context.get("topology_evidence"), f"{path}.topology_evidence", errors
            )
            require_nonempty_string(
                context.get("world_rule_source"), f"{path}.world_rule_source", errors
            )
            require_nonempty_string(
                context.get("episode_context_source"),
                f"{path}.episode_context_source",
                errors,
            )
            require_nonempty_string(
                context.get("audience_prior_knowledge"),
                f"{path}.audience_prior_knowledge",
                errors,
            )
            require_nonempty_string(
                context.get("world_rule_text"), f"{path}.world_rule_text", errors
            )
            require_nonempty_string(
                context.get("episode_context_text"),
                f"{path}.episode_context_text",
                errors,
            )
            require_nonempty_string(
                context.get("episode_premise_text"),
                f"{path}.episode_premise_text",
                errors,
            )
            require_nonempty_string(
                context.get("opening_visual_evidence"),
                f"{path}.opening_visual_evidence",
                errors,
            )
            if worldview_placement_mode == "generated_reference_shot":
                if context.get("establishing_shot_generation_mode") != "reference_conditioned":
                    fail(
                        errors,
                        f"{path}.establishing_shot_generation_mode must be "
                        "reference_conditioned",
                    )
                style_references = context.get("style_reference_frames")
                if not isinstance(style_references, list) or not style_references:
                    fail(errors, f"{path}.style_reference_frames must be non-empty")
                else:
                    for ref_index, reference in enumerate(style_references):
                        require_nonempty_string(
                            reference,
                            f"{path}.style_reference_frames[{ref_index}]",
                            errors,
                        )
                require_nonempty_string(
                    context.get("style_continuity_evidence"),
                    f"{path}.style_continuity_evidence",
                    errors,
                )
            require_nonempty_string(
                context.get("causal_bridge_text"),
                f"{path}.causal_bridge_text",
                errors,
            )
            require_nonempty_string(
                context.get("causal_bridge_source"),
                f"{path}.causal_bridge_source",
                errors,
            )
            if context.get("causal_bridge_verified") is not True:
                fail(errors, f"{path}.causal_bridge_verified must be true")
            if context.get("frozen_input_acknowledged") is not True:
                fail(errors, f"{path}.frozen_input_acknowledged must be true")
            if context.get("upstream_regeneration_requested") is not False:
                fail(errors, f"{path}.upstream_regeneration_requested must be false")
            if context.get("zero_context_check") is not True:
                fail(errors, f"{path}.zero_context_check must be true")
            introduced_names = context.get("introduced_names")
            if not isinstance(introduced_names, list):
                fail(errors, f"{path}.introduced_names must be an array")
            else:
                if len(introduced_names) > 2:
                    fail(
                        errors,
                        f"{path}.introduced_names may contain at most place and protagonist",
                    )
                for name_index, name in enumerate(introduced_names):
                    require_nonempty_string(
                        name, f"{path}.introduced_names[{name_index}]", errors
                    )
            unexplained_terms = context.get("unexplained_terms")
            if not isinstance(unexplained_terms, list):
                fail(errors, f"{path}.unexplained_terms must be an array")
            elif unexplained_terms:
                fail(errors, f"{path}.unexplained_terms must be empty")
            context_routes = context.get("route_ids")
            cleaned_routes: set[str] = set()
            if not isinstance(context_routes, list) or not context_routes:
                fail(errors, f"{path}.route_ids must be a non-empty array")
            else:
                for route_index, route_id in enumerate(context_routes):
                    cleaned_route = require_nonempty_string(
                        route_id, f"{path}.route_ids[{route_index}]", errors
                    )
                    if cleaned_route:
                        cleaned_routes.add(cleaned_route)
                        if cleaned_route not in route_ids:
                            fail(errors, f"{path} references unknown route {cleaned_route}")
            covered_routes.update(cleaned_routes)
            if entry_video_id and entry_video_id not in video_ids:
                fail(errors, f"{path} references unknown video {entry_video_id}")
            for route_id in cleaned_routes:
                if entry_video_id and entry_video_id not in route_video_ids.get(route_id, []):
                    fail(errors, f"{path} entry video is not on route {route_id}")
                matching_events = [
                    event
                    for event in worldview_events
                    if event[0] == entry_video_id and route_id in event[3]
                ]
                if not matching_events:
                    fail(
                        errors,
                        f"{path} has no worldview event for route {route_id} "
                        f"on entry video {entry_video_id}",
                    )
        missing_routes = route_ids - covered_routes
        if missing_routes:
            fail(
                errors,
                "worldview_contexts do not cover routes: "
                + ", ".join(sorted(missing_routes)),
            )
    elif worldview_contexts:
        fail(
            errors,
            "worldview_contexts exist while settings.include_worldview is false",
        )

    first_appearances = plan.get("route_first_appearances")
    if not isinstance(first_appearances, list):
        fail(errors, "route_first_appearances must be an array")
        first_appearances = []

    appearance_keys: set[tuple[str, str]] = set()
    appearance_records: set[tuple[str, str, str, int]] = set()
    for index, appearance in enumerate(first_appearances):
        path = f"route_first_appearances[{index}]"
        if not isinstance(appearance, dict):
            fail(errors, f"{path} must be an object")
            continue
        route_id = require_nonempty_string(appearance.get("route_id"), f"{path}.route_id", errors)
        character_name = require_nonempty_string(
            appearance.get("character_name"), f"{path}.character_name", errors
        )
        identity_evidence = appearance.get("identity_evidence")
        if not isinstance(identity_evidence, list) or len(identity_evidence) < 2:
            fail(errors, f"{path}.identity_evidence must contain at least two anchors")
        else:
            for evidence_index, evidence in enumerate(identity_evidence):
                require_nonempty_string(
                    evidence,
                    f"{path}.identity_evidence[{evidence_index}]",
                    errors,
                )
        video_id = require_nonempty_string(appearance.get("video_id"), f"{path}.video_id", errors)
        first_visible = require_nonnegative_int(
            appearance.get("first_clear_visible_ms"),
            f"{path}.first_clear_visible_ms",
            errors,
        )
        require_nonempty_string(
            appearance.get("first_clear_frame"), f"{path}.first_clear_frame", errors
        )
        character_side = appearance.get("character_side")
        if character_side not in {"left", "right"}:
            fail(errors, f"{path}.character_side must be left or right")
        require_bbox(
            appearance.get("character_bbox"), f"{path}.character_bbox", errors
        )
        require_bbox(appearance.get("face_bbox"), f"{path}.face_bbox", errors)
        require_nonempty_string(appearance.get("evidence"), f"{path}.evidence", errors)
        intro_event_id = require_nonempty_string(
            appearance.get("intro_event_id"), f"{path}.intro_event_id", errors
        )
        if route_id and route_id not in route_ids:
            fail(errors, f"{path} references unknown route {route_id}")
        if video_id and video_id not in video_ids:
            fail(errors, f"{path} references unknown video {video_id}")
        if route_id and video_id and video_id not in route_video_ids.get(route_id, []):
            fail(errors, f"{path} video is not on route {route_id}")
        if route_id and character_name:
            key = (route_id, character_name)
            if key in appearance_keys:
                fail(errors, f"duplicate first appearance for route/character {key}")
            appearance_keys.add(key)
        if route_id and character_name and video_id and first_visible is not None:
            appearance_records.add((route_id, character_name, video_id, first_visible))
        if intro_event_id and intro_event_id not in event_ids:
            fail(errors, f"{path} references unknown intro event {intro_event_id}")

    if settings.get("include_character_intro") is True:
        if not first_appearances:
            fail(
                errors,
                "settings.include_character_intro is true but no first appearance records exist",
            )
        for video_id, character_name, event_id, start, applies in character_events:
            for route_id in applies:
                matching = [
                    record
                    for record in appearance_records
                    if record[0] == route_id
                    and record[1] == character_name
                    and record[2] == video_id
                ]
                if not matching:
                    fail(
                        errors,
                        f"character event {event_id} lacks a matching first appearance "
                        f"record for route {route_id}",
                    )
                elif start < matching[0][3]:
                    fail(
                        errors,
                        f"character event {event_id} starts before first visible evidence",
                    )
    elif character_events:
        fail(
            errors,
            "character intro events exist while settings.include_character_intro is false",
        )

    for index, appearance in enumerate(first_appearances):
        if not isinstance(appearance, dict):
            continue
        intro_event_id = appearance.get("intro_event_id")
        route_id = appearance.get("route_id")
        character_name = appearance.get("character_name")
        video_id = appearance.get("video_id")
        first_visible = appearance.get("first_clear_visible_ms")
        details = character_event_details.get(intro_event_id)
        if details is None:
            continue
        event_video, event_character, event_start, event_routes = details
        path = f"route_first_appearances[{index}]"
        if event_video != video_id:
            fail(errors, f"{path} intro event belongs to video {event_video}")
        if event_character != character_name:
            fail(errors, f"{path} intro event belongs to character {event_character}")
        if route_id not in event_routes:
            fail(errors, f"{path} intro event does not apply to route {route_id}")
        if isinstance(first_visible, int) and event_start < first_visible:
            fail(errors, f"{path} intro event starts before first visible evidence")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()

    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: plan not found: {args.plan}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON: {exc}", file=sys.stderr)
        return 2

    errors = validate_plan(plan)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"FAILED: {len(errors)} validation error(s)", file=sys.stderr)
        return 1

    print("OK: subtitle plan is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
