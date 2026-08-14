#!/usr/bin/env python3
"""Build deterministic ASS subtitle tracks from a validated private plan."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


STYLE_KEYS = {
    "dialogue": "Dialogue",
    "worldview": "Worldview",
    "character_intro": "CharacterIntro",
}


def ass_time(milliseconds: int) -> str:
    centiseconds = max(0, milliseconds // 10)
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def ass_escape(value: str) -> str:
    value = value.replace("\\", r"\\")
    value = value.replace("{", r"\{").replace("}", r"\}")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return value.replace("\n", r"\N")


def verticalize(value: str) -> str:
    lines: list[str] = []
    for raw_line in value.splitlines():
        compact = re.sub(r"\s+", "", raw_line)
        if compact:
            lines.extend(list(compact))
            lines.append("")
    while lines and not lines[-1]:
        lines.pop()
    return r"\N".join(ass_escape(item) for item in lines)


def event_text(event: dict[str, Any], language_mode: str) -> str:
    text = str(event.get("text", "")).strip()
    translation = str(event.get("translation", "")).strip()
    if event.get("kind") == "character_intro":
        identity = str(event.get("character_identity", "")).strip()
        chinese = (
            ass_escape(str(event["vertical_text"]))
            if event.get("vertical_text")
            else verticalize(f"{text}\n{identity}")
        )
        if language_mode == "zh":
            return chinese
        translated_name = str(event.get("character_name_translation", "")).strip()
        translated_identity = str(
            event.get("character_identity_translation", "")
        ).strip()
        translated = " · ".join(
            part for part in (translated_name, translated_identity) if part
        )
        return f"{chinese}\\N{ass_escape(translated)}"
    if language_mode == "zh":
        return ass_escape(text)
    if language_mode == "other_only":
        return ass_escape(translation)
    return f"{ass_escape(text)}\\N{ass_escape(translation)}"


def style_line(
    name: str,
    font_name: str,
    font_size: int,
    alignment: int,
    margin_l: int,
    margin_r: int,
    margin_v: int,
    *,
    bold: int = 0,
    outline: float = 2.5,
    shadow: float = 0.0,
) -> str:
    return (
        f"Style: {name},{font_name},{font_size},"
        "&H00FFFFFF,&H000000FF,&H00111111,&HFF000000,"
        f"{bold},0,0,0,100,100,0,0,1,{outline},{shadow},"
        f"{alignment},{margin_l},{margin_r},{margin_v},1"
    )


def build_ass(plan: dict[str, Any], video: dict[str, Any]) -> str:
    settings = plan["settings"]
    width = int(video["width"])
    height = int(video["height"])
    font_name = str(settings["font_name"])
    base_size = max(28, round(height * 0.052))
    worldview_size = max(26, round(base_size * 0.86))
    character_size = max(30, round(base_size * 0.95))
    default_margin_lr = max(24, round(width * 0.06))
    default_margin_v = max(24, round(height * 0.06))

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        style_line(
            "Dialogue",
            font_name,
            base_size,
            2,
            default_margin_lr,
            default_margin_lr,
            default_margin_v,
        ),
        style_line(
            "Worldview",
            font_name,
            worldview_size,
            8,
            default_margin_lr,
            default_margin_lr,
            default_margin_v,
            outline=2.0,
            shadow=0.0,
        ),
        style_line(
            "CharacterIntro",
            font_name,
            character_size,
            6,
            default_margin_lr,
            default_margin_lr,
            default_margin_v,
            bold=1,
            outline=2.0,
            shadow=0.0,
        ),
        "",
        "[Events]",
        (
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
            "MarginV, Effect, Text"
        ),
    ]

    language_mode = str(settings["language_mode"])
    events = sorted(
        video.get("events", []),
        key=lambda event: (int(event["start_ms"]), int(event["end_ms"]), event["event_id"]),
    )
    for event in events:
        position = event["position"]
        alignment = int(position["alignment"])
        overrides = f"{{\\an{alignment}}}"
        if "x" in position and "y" in position:
            overrides += f"{{\\pos({int(position['x'])},{int(position['y'])})}}"
        style = STYLE_KEYS[event["kind"]]
        text = event_text(event, language_mode)
        lines.append(
            "Dialogue: 0,"
            f"{ass_time(int(event['start_ms']))},"
            f"{ass_time(int(event['end_ms']))},"
            f"{style},,"
            f"{int(position['margin_l'])},"
            f"{int(position['margin_r'])},"
            f"{int(position['margin_v'])},,"
            f"{overrides}{text}"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Build without running validate_subtitle_plan.py first.",
    )
    args = parser.parse_args()

    if not args.skip_validation:
        validator = Path(__file__).with_name("validate_subtitle_plan.py")
        validation = subprocess.run(
            [sys.executable, str(validator), str(args.plan)],
            check=False,
        )
        if validation.returncode:
            return validation.returncode

    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read plan: {exc}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for video in plan["videos"]:
        video_id = str(video["video_id"])
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", video_id).strip("-") or "video"
        destination = args.output_dir / f"{safe_name}.ass"
        destination.write_text(build_ass(plan, video), encoding="utf-8")
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
