#!/usr/bin/env python3
"""Validate a subtitle plan and burn its ASS tracks into new MP4 files."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any


CONTRACT = "nextplay.video-subtitles.render.v1"
NOTO_SANS_SC_URL = (
    "https://raw.githubusercontent.com/notofonts/noto-cjk/main/"
    "Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
)


def safe_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._") or "video"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"Command failed: {detail[-4000:]}") from exc


def supports_ass(ffmpeg: str) -> bool:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-filters"],
        check=False,
        text=True,
        capture_output=True,
    )
    return bool(re.search(r"^\s*\.\.\.\s+ass\s+V->V", result.stdout, re.MULTILINE))


def resolve_ffmpeg() -> str:
    system = shutil.which("ffmpeg")
    if system and supports_ass(system):
        return system
    try:
        import imageio_ffmpeg  # type: ignore
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if supports_ass(bundled):
            return bundled
    except ImportError:
        pass

    venv_dir = Path(tempfile.mkdtemp(prefix="nextplay-subtitle-ffmpeg-"))
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        venv_python = venv_dir / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        run([str(venv_python), "-m", "pip", "install", "imageio-ffmpeg", "-q"])
        bundled = run(
            [
                str(venv_python),
                "-c",
                "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())",
            ]
        ).stdout.strip()
    except Exception as exc:
        raise RuntimeError(
            "No FFmpeg build with the ASS/libass filter is available, and the private "
            "imageio-ffmpeg fallback could not be installed."
        ) from exc
    if not supports_ass(bundled):
        raise RuntimeError("The fallback FFmpeg build does not provide the ASS filter")
    return bundled


def probe(ffmpeg: str, source: Path) -> dict[str, Any]:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(source)],
        check=False,
        text=True,
        capture_output=True,
    )
    details = result.stderr
    duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", details)
    size = re.search(r"Video:.*?\s(\d{2,5})x(\d{2,5})(?:[\s,])", details)
    fps = re.search(r"(\d+(?:\.\d+)?)\s+fps", details)
    if not duration or not size:
        raise RuntimeError(f"Cannot probe video: {source}")
    hours, minutes, seconds = duration.groups()
    return {
        "duration_ms": round(
            (int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000
        ),
        "width": int(size.group(1)),
        "height": int(size.group(2)),
        "fps": float(fps.group(1)) if fps else None,
    }


def local_source(value: str, download_root: Path, video_id: str) -> Path:
    if value.startswith(("https://", "http://")):
        destination = download_root / f"{safe_stem(video_id)}-master.mp4"
        urllib.request.urlretrieve(value, destination)
        return destination
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Source video not found: {path}")
    return path


def resolve_font(
    font_key: str,
    requested_name: str,
    explicit_file: Path | None,
    explicit_name: str | None,
) -> tuple[str, Path]:
    if explicit_file:
        path = explicit_file.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Font file not found: {path}")
        return explicit_name or requested_name, path

    candidates: dict[str, list[tuple[str, str]]] = {
        "source_han_sans": [
            ("/System/Library/Fonts/STHeiti Light.ttc", "Heiti SC"),
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", "Hiragino Sans GB"),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "Noto Sans CJK SC"),
            ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "WenQuanYi Zen Hei"),
        ],
        "source_han_serif": [
            ("/System/Library/Fonts/ヒラギノ明朝 ProN.ttc", "Hiragino Mincho ProN"),
            ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", "Noto Serif CJK SC"),
        ],
        "lxgw_wenkai": [],
    }
    ordered = candidates.get(font_key, []) + candidates["source_han_sans"]
    for value, family in ordered:
        path = Path(value)
        if path.is_file():
            return family, path

    font_root = Path(tempfile.mkdtemp(prefix="nextplay-subtitle-font-"))
    downloaded = font_root / "NotoSansCJKsc-Regular.otf"
    try:
        urllib.request.urlretrieve(NOTO_SANS_SC_URL, downloaded)
    except Exception as exc:
        raise RuntimeError("No usable CJK font is available and fallback download failed") from exc
    if downloaded.stat().st_size < 1_000_000:
        raise RuntimeError("Downloaded CJK fallback font is invalid")
    return "Noto Sans CJK SC", downloaded


def ass_filter(ass_path: Path, font_file: Path | None) -> str:
    escaped = str(ass_path).replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")
    value = f"ass=filename='{escaped}'"
    if font_file:
        fonts = str(font_file.parent).replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")
        value += f":fontsdir='{fonts}'"
    return value


def render_one(
    ffmpeg: str,
    video: dict[str, Any],
    ass_path: Path,
    output: Path,
    font_file: Path | None,
    download_root: Path,
) -> dict[str, Any]:
    video_id = str(video["video_id"])
    source = local_source(str(video["source"]), download_root, video_id)
    if source.resolve() == output.resolve():
        raise RuntimeError("Output must not overwrite the subtitle-free master")
    before = probe(ffmpeg, source)
    render_process = run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vf",
            ass_filter(ass_path, font_file),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    if re.search(r"Glyph 0x|failed to find any fallback with glyph", render_process.stderr):
        raise RuntimeError(f"Missing glyphs while rendering {video_id}")
    after = probe(ffmpeg, output)
    if before["width"] != after["width"] or before["height"] != after["height"]:
        raise RuntimeError(f"Frame size changed for {video_id}: {before} -> {after}")
    if abs(before["duration_ms"] - after["duration_ms"]) > 120:
        raise RuntimeError(f"Duration drift for {video_id}: {before} -> {after}")
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Rendered output is empty: {output}")
    return {
        "video_id": video_id,
        "visible_name": video["visible_name"],
        "source": str(source),
        "output": str(output),
        "bytes": output.stat().st_size,
        "source_probe": before,
        "result_probe": after,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--font-file", type=Path)
    parser.add_argument("--font-name")
    parser.add_argument("--skip-validation", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    if not args.skip_validation:
        validation = subprocess.run(
            [sys.executable, str(script_dir / "validate_subtitle_plan.py"), str(args.plan)],
            check=False,
        )
        if validation.returncode:
            return validation.returncode

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ass_dir = args.output_dir / "ass"
    ass_dir.mkdir(exist_ok=True)
    actual_font_name, font_file = resolve_font(
        str(plan["settings"]["font_key"]),
        str(plan["settings"]["font_name"]),
        args.font_file,
        args.font_name,
    )
    run(
        [
            sys.executable,
            str(script_dir / "build_ass_subtitles.py"),
            str(args.plan),
            "--output-dir",
            str(ass_dir),
            "--skip-validation",
            "--font-name",
            actual_font_name,
        ]
    )

    ffmpeg = resolve_ffmpeg()
    download_root = Path(tempfile.mkdtemp(prefix="nextplay-subtitle-masters-"))
    rendered: list[dict[str, Any]] = []
    for video in plan["videos"]:
        video_id = str(video["video_id"])
        ass_path = ass_dir / f"{safe_stem(video_id)}.ass"
        output_name = Path(str(video["output_name"])).name
        if not output_name.lower().endswith(".mp4"):
            output_name += ".mp4"
        rendered.append(
            render_one(
                ffmpeg,
                video,
                ass_path,
                args.output_dir / output_name,
                font_file,
                download_root,
            )
        )

    print(
        json.dumps(
            {
                "status": "rendered",
                "contract": CONTRACT,
                "ffmpeg": ffmpeg,
                "requested_font": plan["settings"]["font_name"],
                "actual_font": actual_font_name,
                "font_file": str(font_file),
                "videos": rendered,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failed", "contract": CONTRACT, "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)
