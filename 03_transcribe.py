#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第 3 步：小段音频 -> 每段一个 txt（中间产物 03_text/）

一段一个文件，这个文件本身就是缓存：
  - 已存在的 txt 默认跳过，不重复扣额度；
  - 想重转某一段，删掉那一个 txt 再跑本步即可；
  - 想全部重转，加 --redo。

转写失败不会写空文件，下次重跑会自动重试那几段。

用法：
    export SILICONFLOW_API_KEY="sk-xxxx"
    python 03_transcribe.py workspace/我的录音
    python 03_transcribe.py workspace/我的录音 --redo

产物：workspace/我的录音/03_text/seg_000.txt ...
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import uuid

from common import (D_TEXT, F_SEGJSON, api_key, die, eprint, fmt_time,
                    get_task_dir, load_config, short_task_dir)


def http_json(url: str, key: str, data: bytes, content_type: str,
              timeout: int, retries: int) -> dict:
    """只做 POST + 有限重试，不解析业务字段"""
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", content_type)
    last = "请求失败"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as ex:
            body = ex.read().decode("utf-8", "replace")[:300]
            last = "HTTP %d：%s" % (ex.code, body)
            if ex.code not in (429, 500, 502, 503, 504):
                break  # 4xx 客户端错误，重试没意义
        except Exception as ex:
            last = str(ex)
        time.sleep(2 ** attempt)
    raise RuntimeError(last)


def transcribe(wav_path, cfg: dict, key: str) -> str:
    """手写 multipart/form-data，避免任何第三方依赖"""
    boundary = "----AsrPipeline" + uuid.uuid4().hex
    parts = []
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n%s\r\n"
                  % (boundary, cfg["model"])).encode("utf-8"))
    # 部分模型（XingChenASR-V3.2-Ultra）必须显式带 response_format，
    # 否则接口直接返回 HTTP 500。config.json 里清空这一项就不发送该字段。
    rf = str(cfg.get("response_format") or "").strip()
    if rf:
        parts.append(("--%s\r\nContent-Disposition: form-data; "
                      "name=\"response_format\"\r\n\r\n%s\r\n"
                      % (boundary, rf)).encode("utf-8"))
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; "
                  "filename=\"%s\"\r\nContent-Type: audio/wav\r\n\r\n"
                  % (boundary, wav_path.name)).encode("utf-8"))
    parts.append(wav_path.read_bytes())
    parts.append(("\r\n--%s--\r\n" % boundary).encode("utf-8"))

    resp = http_json(cfg["api_url"], key, b"".join(parts),
                     "multipart/form-data; boundary=" + boundary,
                     int(cfg["api_timeout_sec"]), int(cfg["api_retries"]))
    return (resp.get("text") or "").strip()


def main():
    ap = argparse.ArgumentParser(description="第3步：分段音频 -> 03_text/*.txt")
    ap.add_argument("task", help="任务目录，例如 workspace/我的录音")
    ap.add_argument("--redo", action="store_true", help="忽略已有 txt，全部重新转写")
    args = ap.parse_args()

    task = get_task_dir(args.task)
    segjson = task / F_SEGJSON
    if not segjson.is_file():
        die("找不到 %s，请先跑 02_split.py" % F_SEGJSON)

    cfg = load_config()
    key = api_key(cfg)
    data = json.loads(segjson.read_text(encoding="utf-8"))
    segs = data["segments"]
    text_dir = task / D_TEXT
    text_dir.mkdir(exist_ok=True)

    eprint("[3/4] 转写：%d 段，引擎 %s" % (len(segs), cfg["model"]))
    done, skipped, failed = 0, 0, []
    for n, s in enumerate(segs, 1):
        out = task / s["text"]
        audio = task / s["audio"]
        if not audio.is_file():
            failed.append((s["idx"], "音频文件缺失：%s" % s["audio"]))
            eprint("      [%d/%d] 音频缺失，跳过" % (n, len(segs)))
            continue
        if out.exists() and not args.redo:
            skipped += 1
            eprint("      [%d/%d] %s 已转写，跳过" % (n, len(segs), fmt_time(s["start"])))
            continue
        try:
            text = transcribe(audio, cfg, key)
            out.write_text(text, encoding="utf-8")  # 逐段落盘，中断不丢
            done += 1
            eprint("      [%d/%d] %s  %d 字" % (n, len(segs), fmt_time(s["start"]), len(text)))
        except Exception as ex:
            failed.append((s["idx"], str(ex)))
            eprint("      [%d/%d] %s 失败：%s" % (n, len(segs), fmt_time(s["start"]), ex))
        time.sleep(0.3)  # 轻微限速

    eprint("")
    eprint("完成：新转写 %d 段，跳过 %d 段，失败 %d 段 -> %s/"
           % (done, skipped, len(failed), D_TEXT))
    if failed:
        for idx, why in failed:
            eprint("      段 %03d 未完成：%s" % (idx, why))
        eprint("      修好原因后重跑本步即可（只有失败的段会重试）。")
    eprint("")
    eprint("下一步：python 04_merge.py %s" % short_task_dir(task))


if __name__ == "__main__":
    main()
