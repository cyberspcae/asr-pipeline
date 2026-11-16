#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 1 步：录音 -> 统一格式的音频（中间产物 01_prep.wav）

只做一件事：把任意格式的录音转成 ASR 好吃的 16kHz / 单声道 WAV，
顺手做高通 + 响度归一化（这是几轮实测里单项收益最大的一步）。

用法：
    python 01_prepare.py 我的录音.MP3
    python 01_prepare.py 我的录音.MP3 --redo     # 强制重做

产物：workspace/<录音名>/01_prep.wav
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import (FFMPEG, ROOT, WORKSPACE, F_PREP, check_ffmpeg, die, eprint,
                    load_config, probe_duration, fmt_time, run, short_task_dir)


def main():
    ap = argparse.ArgumentParser(description="第1步：录音 -> 01_prep.wav")
    ap.add_argument("audio", help="录音文件路径（MP3 / WAV / M4A 等 ffmpeg 能读的都行）")
    ap.add_argument("--redo", action="store_true", help="已存在也重新生成")
    args = ap.parse_args()

    src = Path(args.audio).expanduser().resolve()
    if not src.is_file():
        die("找不到录音文件：%s" % src)

    check_ffmpeg()
    cfg = load_config()

    task = WORKSPACE / src.stem
    task.mkdir(parents=True, exist_ok=True)
    dst = task / F_PREP

    if dst.exists() and not args.redo:
        eprint("已存在，跳过：%s（要重做请加 --redo）" % dst)
    else:
        eprint("[1/4] 前处理：%s" % cfg["preprocess_filter"])
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(src),
             "-af", cfg["preprocess_filter"],
             "-ar", str(cfg["sample_rate"]), "-ac", str(cfg["channels"]),
             "-c:a", "pcm_s16le", str(dst)])

    total = probe_duration(dst)
    eprint("")
    eprint("完成：%s" % dst)
    eprint("时长：%s ｜ 格式：%d Hz / %d 声道 WAV"
           % (fmt_time(total), cfg["sample_rate"], cfg["channels"]))
    eprint("")
    eprint("下一步：python 02_split.py %s" % short_task_dir(task))


if __name__ == "__main__":
    main()
