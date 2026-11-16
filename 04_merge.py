#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 4 步：每段的 txt -> 合成一份文稿（终点）

这是本项目唯一对外交付的东西，输出两份等价文稿：
  - 04_transcript.md   每段前带 [mm:ss~mm:ss]，方便回听定位
  - 04_transcript.txt  纯文字，段间空行，没有任何标记

到此为止。本项目不做大纲、纠错、可疑段标记、自测卡——那是「一步到位」
的部分，需要时另写 05_xxx.py 读这份文稿即可，不必改动前面四步。

用法：
    python 04_merge.py workspace/我的录音

产物：workspace/我的录音/04_transcript.md 与 .txt
"""
from __future__ import annotations

import argparse
import json

from common import (F_MD, F_SEGJSON, F_TXT, die, eprint, fmt_time,
                    get_task_dir, load_config)


def main():
    ap = argparse.ArgumentParser(description="第4步：03_text/*.txt -> 文稿")
    ap.add_argument("task", help="任务目录，例如 workspace/我的录音")
    args = ap.parse_args()

    task = get_task_dir(args.task)
    segjson = task / F_SEGJSON
    if not segjson.is_file():
        die("找不到 %s，请先跑 02_split.py" % F_SEGJSON)

    data = json.loads(segjson.read_text(encoding="utf-8"))
    segs = data["segments"]
    # 引擎名以「当前 config」为准：分片时记录的 engine 可能已被换掉，
    # 文稿头部要标注的其实是本次转写所用的模型。
    engine = load_config().get("model") or data.get("engine", "?")

    rows, missing = [], 0
    for s in segs:
        p = task / s["text"]
        if p.is_file():
            text = p.read_text(encoding="utf-8").strip()
        else:
            text = ""
            missing += 1
        if not text:
            text = "（本段没有识别结果，请重跑第 3 步或回听原录音）"
        rows.append((s["start"], s["end"], text))

    # 纯文字版
    plain = "\n\n".join(t for _, _, t in rows) + "\n"
    (task / F_TXT).write_text(plain, encoding="utf-8")

    # 带时间码版
    lines = [
        "# 逐字稿 · %s" % data.get("source", task.name),
        "",
        "> 引擎：%s ｜ 共 %d 段 / %s"
        % (engine, len(rows), fmt_time(data.get("total", 0))),
        "> 这是**转写半成品**：可能有错字、漏句或把旁人说话混进来。",
        "> 关键内容请按下面的时间戳回听原录音，不要直接照抄当笔记。",
        "",
    ]
    for st, ed, t in rows:
        lines.append("**[%s ~ %s]** %s" % (fmt_time(st), fmt_time(ed), t))
        lines.append("")
    (task / F_MD).write_text("\n".join(lines), encoding="utf-8")

    total_chars = sum(len(t) for _, _, t in rows)
    eprint("[4/4] 合并文稿：%d 段 / 约 %d 字" % (len(rows), total_chars))
    if missing:
        eprint("      注意：%d 段还没有转写结果，已在文稿中标出；重跑第 3 步后再跑本步即可。"
               % missing)
    eprint("")
    eprint("完成（终点）：")
    eprint("  %s" % (task / F_MD))
    eprint("  %s" % (task / F_TXT))


if __name__ == "__main__":
    main()
