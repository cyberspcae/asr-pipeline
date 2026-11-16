#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 2 步：统一音频 -> 小段音频 + 分段清单（中间产物 02_）

按 60 秒网格切片，并把每个切点吸附到附近最近的停顿处，尽量不切断句子。
每一段都保留原始时间码，后面回听定位全靠它。

为什么用固定网格、而不是只按静音切：
  实测中「降噪 5 级」的录音后半段底噪较高，silencedetect 常常一处停顿都
  检不出来，只按静音切会切出上百秒的长段。所以必须以网格为主、静音点为辅。

用法：
    python 02_split.py workspace/我的录音
    python 02_split.py workspace/我的录音 --redo

产物：
    workspace/我的录音/02_segments.json   分段清单（含起止时间）
    workspace/我的录音/02_audio/*.wav     每段的小音频
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess

from common import (D_SEGAUDIO, F_PREP, F_SEGJSON, D_TEXT, FFMPEG,
                    check_ffmpeg, die, eprint, fmt_time, get_task_dir,
                    load_config, probe_duration, run, short_task_dir)


def find_silence_midpoints(wav, cfg) -> list:
    """silencedetect 的输出在 stderr，取每个静音区间的中点作为候选切点"""
    r = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(wav),
         "-af", "silencedetect=noise=%ddB:d=%s" % (cfg["silence_db"], cfg["silence_min_dur"]),
         "-f", "null", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log = r.stderr.decode("utf-8", "replace")
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", log)]
    return [round((a + b) / 2, 2) for a, b in zip(starts, ends) if b > a]


def make_bounds(total: float, cuts: list, cfg: dict) -> list:
    seg = float(cfg["seg_seconds"])
    snap = float(cfg["snap_window_sec"])
    min_seg = float(cfg["min_seg_sec"])
    grid = [seg * i for i in range(1, int(total // seg) + 1)]
    bounds = [0.0]
    for g in grid:
        near = [c for c in cuts if abs(c - g) <= snap and c > bounds[-1] + min_seg]
        cut = round(min(near, key=lambda x: abs(x - g)) if near else g, 2)
        if cut > bounds[-1] + 8 and cut < total - 8:
            bounds.append(cut)
    if bounds[-1] < total:
        bounds.append(total)
    return bounds


def main():
    ap = argparse.ArgumentParser(description="第2步：音频 -> 02_segments.json + 02_audio/")
    ap.add_argument("task", help="任务目录，例如 workspace/我的录音")
    ap.add_argument("--redo", action="store_true", help="重新切分（会覆盖已有分段）")
    args = ap.parse_args()

    task = get_task_dir(args.task)
    wav = task / F_PREP
    if not wav.is_file():
        die("找不到 %s，请先跑 01_prepare.py" % wav.name)

    check_ffmpeg()
    cfg = load_config()
    segjson = task / F_SEGJSON
    if segjson.exists() and not args.redo:
        eprint("已存在 %s，跳过切分（要重新切分请加 --redo）" % F_SEGJSON)
        eprint("")
        eprint("下一步：python 03_transcribe.py %s" % short_task_dir(task))
        return

    total = probe_duration(wav)
    cuts = [c for c in find_silence_midpoints(wav, cfg) if 0 < c < total]
    bounds = make_bounds(total, cuts, cfg)

    audio_dir = task / D_SEGAUDIO
    audio_dir.mkdir(exist_ok=True)
    (task / D_TEXT).mkdir(exist_ok=True)  # 03 步会往里写

    eprint("[2/4] 分片：共 %d 段，目标每段 %s 秒（检出 %d 个停顿候选）"
           % (len(bounds) - 1, cfg["seg_seconds"], len(cuts)))

    segments = []
    for i, (st, ed) in enumerate(zip(bounds, bounds[1:])):
        if ed - st < 1.0:
            continue
        name = "seg_%03d.wav" % i
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
             "-ss", "%.2f" % st, "-t", "%.2f" % (ed - st), "-i", str(wav),
             "-ar", str(cfg["sample_rate"]), "-ac", str(cfg["channels"]),
             "-c:a", "pcm_s16le", str(audio_dir / name)])
        segments.append({
            "idx": i,
            "start": st,
            "end": ed,
            "audio": "%s/%s" % (D_SEGAUDIO, name),
            "text": "%s/seg_%03d.txt" % (D_TEXT, i),
        })
        eprint("      [%02d] %s ~ %s  (%.1f 秒)"
               % (i, fmt_time(st), fmt_time(ed), ed - st))

    if not segments:
        die("分片失败：音频可能过短或格式异常")

    data = {
        "source": task.name,
        "prep": F_PREP,
        "engine": cfg["model"],
        "total": total,
        "segments": segments,
    }
    segjson.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    eprint("")
    eprint("完成：%s" % segjson)
    eprint("      %s/ 共 %d 个小音频" % (audio_dir, len(segments)))
    eprint("")
    eprint("下一步：python 03_transcribe.py %s" % short_task_dir(task))


if __name__ == "__main__":
    main()
