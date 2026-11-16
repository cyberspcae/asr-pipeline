#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一条命令跑完全程：录音 -> 处理过的音频 + 文稿

    python run.py 我的录音.MP3
    python run.py 我的录音.MP3 --redo     # 忽略已有结果，全部重来

它只是按顺序执行 01~04 四个分步脚本，所有中间产物照旧落盘。
所以中断后再跑一次会自动从断点继续，已转写的段不会重复扣额度。

最终交付两样东西（都在 workspace/<录音名>/ 里）：
    01_prep.wav         处理过的音频（前处理后的 16kHz WAV）
    04_transcript.txt   文稿（纯文字）
    04_transcript.md    文稿（同内容，每段带时间码，方便回听）
"""
import subprocess
import sys
from pathlib import Path

from common import ROOT, WORKSPACE, check_ffmpeg, die, eprint, short_task_dir

STEPS = ["01_prepare.py", "02_split.py", "03_transcribe.py", "04_merge.py"]


def main():
    argv = sys.argv[1:]
    redo = "--redo" in argv
    argv = [a for a in argv if a != "--redo"]
    if not argv:
        die("用法：python run.py 录音.MP3")
    audio = Path(argv[0]).expanduser().resolve()
    if not audio.is_file():
        die("找不到录音文件：%s" % audio)

    check_ffmpeg()
    task = WORKSPACE / audio.stem
    eprint("录音：%s" % audio.name)
    eprint("任务目录：%s" % short_task_dir(task))
    eprint("")

    for i, script in enumerate(STEPS, 1):
        cmd = [sys.executable, str(ROOT / script)]
        cmd += [str(audio)] if i == 1 else [short_task_dir(task)]
        if redo and i < 4:          # 04 是无状态合并，不需要 --redo
            cmd += ["--redo"]
        eprint("========== 第 %d/4 步：%s ==========" % (i, script))
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            die("第 %d 步失败（exit %d）。已完成的产物都在任务目录里，"
                "修好后再跑一次 run.py 会自动从断点继续。" % (i, r.returncode))
        eprint("")

    eprint("=" * 46)
    eprint("全部完成，交付物：")
    eprint("  处理过的音频   -> %s" % (task / "01_prep.wav"))
    eprint("  文稿（纯文字） -> %s" % (task / "04_transcript.txt"))
    eprint("  文稿（带时间码）-> %s" % (task / "04_transcript.md"))
    eprint("中间产物（分段音频、每段文字）也在同一个目录里。")


if __name__ == "__main__":
    main()
