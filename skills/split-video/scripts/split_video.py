#!/usr/bin/env python3
"""Split local videos into precisely timed, sequentially numbered MP4 clips."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split videos into fixed-duration MP4 clips."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="Input video files")
    parser.add_argument(
        "--output-dir", required=True, type=Path, help="Directory for output clips"
    )
    parser.add_argument(
        "--segment-seconds",
        type=float,
        default=9.0,
        help="Target clip duration in seconds (default: 9)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing clips with the same names",
    )
    parser.add_argument("--crf", type=int, default=18, help="H.264 CRF (default: 18)")
    parser.add_argument(
        "--preset", default="medium", help="libx264 preset (default: medium)"
    )
    return parser.parse_args()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def probe(path: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,duration,avg_frame_rate,r_frame_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    data = json.loads(result.stdout)
    video_durations = []
    for stream in data.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        try:
            candidate = float(stream["duration"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(candidate) and candidate > 0:
            video_durations.append(candidate)
    try:
        duration = max(video_durations) if video_durations else float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"无法读取视频时长：{path}") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"视频时长无效：{path}")
    data["duration_seconds"] = duration
    return data


def video_fps(probe_data: dict) -> float | None:
    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        for key in ("avg_frame_rate", "r_frame_rate"):
            value = stream.get(key, "")
            if "/" not in value:
                continue
            numerator, denominator = value.split("/", 1)
            try:
                fps = float(numerator) / float(denominator)
            except (ValueError, ZeroDivisionError):
                continue
            if math.isfinite(fps) and fps > 0:
                return fps
    return None


def expected_outputs(input_path: Path, output_dir: Path, count: int) -> list[Path]:
    return [
        output_dir / f"{input_path.stem}-{index:03d}.mp4"
        for index in range(1, count + 1)
    ]


def segment_count(duration: float, segment_seconds: float, fps: float | None) -> int:
    """Avoid a nearly empty extra clip caused by container or frame rounding."""
    tolerance = max(0.05, 1.0 / fps if fps else 0.05)
    return max(1, math.ceil((duration - tolerance) / segment_seconds))


def split_one(
    input_path: Path,
    output_dir: Path,
    segment_seconds: float,
    overwrite: bool,
    crf: int,
    preset: str,
) -> list[tuple[Path, float]]:
    source_probe = probe(input_path)
    source_duration = source_probe["duration_seconds"]
    fps = video_fps(source_probe)
    count = segment_count(source_duration, segment_seconds, fps)
    outputs = expected_outputs(input_path, output_dir, count)

    conflicts = [path for path in outputs if path.exists()]
    if conflicts and not overwrite:
        joined = "\n".join(f"  - {path}" for path in conflicts)
        raise FileExistsError(f"以下输出已存在；未覆盖任何文件：\n{joined}")

    output_dir.mkdir(parents=True, exist_ok=True)
    completed: list[tuple[Path, float]] = []
    tolerance = max(0.05, 1.0 / fps if fps else 0.05)

    for zero_based_index, output_path in enumerate(outputs):
        start = zero_based_index * segment_seconds
        requested = min(segment_seconds, source_duration - start)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output_path.stem}.", suffix=".mp4", dir=output_dir
        )
        os.close(file_descriptor)
        temporary_path = Path(temporary_name)
        try:
            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(input_path),
                "-ss",
                f"{start:.9f}",
                "-t",
                f"{requested:.9f}",
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                preset,
                "-crf",
                str(crf),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(temporary_path),
            ]
            run(command)
            actual = probe(temporary_path)["duration_seconds"]
            if abs(actual - requested) > tolerance:
                raise RuntimeError(
                    f"切片时长校验失败：{output_path.name} "
                    f"预期 {requested:.3f} 秒，实际 {actual:.3f} 秒"
                )
            os.replace(temporary_path, output_path)
            completed.append((output_path, actual))
        finally:
            temporary_path.unlink(missing_ok=True)

    return completed


def main() -> int:
    args = parse_args()
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("错误：PATH 中需要可用的 ffmpeg 和 ffprobe。", file=sys.stderr)
        return 2
    if not math.isfinite(args.segment_seconds) or args.segment_seconds <= 0:
        print("错误：--segment-seconds 必须大于 0。", file=sys.stderr)
        return 2
    if not 0 <= args.crf <= 51:
        print("错误：--crf 必须介于 0 和 51。", file=sys.stderr)
        return 2

    inputs = [path.expanduser().resolve() for path in args.inputs]
    missing = [path for path in inputs if not path.is_file()]
    if missing:
        for path in missing:
            print(f"错误：输入文件不存在：{path}", file=sys.stderr)
        return 2

    output_dir = args.output_dir.expanduser().resolve()
    planned_paths: list[Path] = []
    try:
        for input_path in inputs:
            source_probe = probe(input_path)
            count = segment_count(
                source_probe["duration_seconds"],
                args.segment_seconds,
                video_fps(source_probe),
            )
            planned_paths.extend(expected_outputs(input_path, output_dir, count))
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    if len(set(planned_paths)) != len(planned_paths):
        print("错误：多个输入会生成同名切片，请分开输出或重命名源文件。", file=sys.stderr)
        return 1
    conflicts = [path for path in planned_paths if path.exists()]
    if conflicts and not args.overwrite:
        print("错误：以下输出已存在；未处理任何输入：", file=sys.stderr)
        for path in conflicts:
            print(f"  - {path}", file=sys.stderr)
        return 1

    all_results: list[tuple[Path, float]] = []
    try:
        for input_path in inputs:
            all_results.extend(
                split_one(
                    input_path,
                    output_dir,
                    args.segment_seconds,
                    args.overwrite,
                    args.crf,
                    args.preset,
                )
            )
    except (subprocess.CalledProcessError, ValueError, FileExistsError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr.strip(), file=sys.stderr)
        return 1

    print(f"输出文件夹：{output_dir}")
    print(f"共生成 {len(all_results)} 个切片：")
    for path, duration in all_results:
        print(f"{path.name}\t{duration:.3f} 秒")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
