#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
四个步骤共用的小工具：读配置、打日志、跑外部命令、时间格式、任务目录约定。

只使用 Python 标准库。这里不放任何业务逻辑，改流程请改 01~04 脚本。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
WORKSPACE = ROOT / "workspace"
BIN = ROOT / "bin"            # 内置的 ffmpeg 放这里

# 任务目录内的固定文件名（04 步就是终点）
F_PREP = "01_prep.wav"
F_SEGJSON = "02_segments.json"
D_SEGAUDIO = "02_audio"
D_TEXT = "03_text"
F_MD = "04_transcript.md"
F_TXT = "04_transcript.txt"


def eprint(*args):
    print(*args, file=sys.stderr)


def die(msg):
    eprint("[错误] " + msg)
    sys.exit(1)


def load_config() -> dict:
    """优先读本地 config.json（可放密钥，被 .gitignore 忽略）；
    不存在时回退到仓库里的 config.example.json（空模板）。"""
    path = CONFIG_PATH if CONFIG_PATH.is_file() else ROOT / "config.example.json"
    if not path.is_file():
        die("缺少配置文件：把 config.example.json 复制成 config.json 再填自己的密钥")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as ex:
        die("%s 不是合法 JSON：%s" % (path.name, ex))


def run(cmd, capture=False):
    """执行外部命令；失败时把 ffmpeg 的报错原文打出来"""
    try:
        r = subprocess.run(cmd, check=True,
                           stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                           stderr=subprocess.PIPE)
        return r.stdout.decode("utf-8", "replace") if capture else None
    except subprocess.CalledProcessError as ex:
        err = ex.stderr.decode("utf-8", "replace")[-800:] if ex.stderr else ""
        die("命令执行失败：%s\n%s" % (" ".join(map(str, cmd)), err))
    except OSError as ex:
        die("找不到可执行程序 %s：%s" % (cmd[0], ex))


def resolve_tool(name: str) -> str:
    """优先用项目 bin/ 里内置的二进制；bin 里没有才退回系统 PATH"""
    suffix = ".exe" if sys.platform == "win32" else ""
    f = BIN / (name + suffix)
    if f.is_file():
        return str(f)
    return name


FFMPEG = resolve_tool("ffmpeg")


def check_ffmpeg():
    try:
        subprocess.run([FFMPEG, "-version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
    except (OSError, subprocess.CalledProcessError):
        die("没找到可用的 ffmpeg（尝试的是：%s）\n"
            "  - Windows：bin/ 里已内置 ffmpeg.exe，请确认它还在、"
            "没被杀毒软件误删；\n"
            "  - macOS / Linux：请自行安装 ffmpeg，或把对应的 ffmpeg "
            "二进制放进 bin/。" % FFMPEG)


def probe_duration(path: Path) -> float:
    """用 ffmpeg -i 读取时长（解析 stderr 的 Duration），不依赖 ffprobe"""
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
                  r.stderr.decode("utf-8", "replace"))
    if not m:
        die("无法读取音频时长：%s（ffmpeg 无法解析这个文件？）" % path)
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def fmt_time(sec: float) -> str:
    s = int(sec)
    h, m, x = s // 3600, (s % 3600) // 60, s % 60
    return "%02d:%02d:%02d" % (h, m, x) if h else "%02d:%02d" % (m, x)


def get_task_dir(arg: str) -> Path:
    """后三步统一接收『任务目录』作为唯一参数"""
    p = Path(arg).expanduser().resolve()
    if not p.is_dir():
        die("任务目录不存在：%s\n（先跑 01_prepare.py，它会创建这个目录）" % p)
    return p


def short_task_dir(task: Path) -> str:
    """打印给用户的下一步命令用相对路径，方便直接复制"""
    try:
        return str(task.relative_to(ROOT))
    except ValueError:
        return str(task)


def api_key(cfg: dict) -> str:
    """密钥两种放法任选：config.json 的 api_key 字段（优先）或环境变量"""
    k = str(cfg.get("api_key") or "").strip()
    if k:
        return k
    k = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not k:
        die("没有找到密钥。两种放法任选其一：\n"
            "  1. 直接填进 config.json 的 \"api_key\" 字段（本机自用最简单）\n"
            "  2. 设环境变量 SILICONFLOW_API_KEY（不想让 key 出现在文件里时用）")
    return k
