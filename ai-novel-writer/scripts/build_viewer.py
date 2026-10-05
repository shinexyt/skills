#!/usr/bin/env python3
"""为小说工作区生成单文件本地阅读器 viewer.html。

用法:
  build_viewer.py <工作区> [--out 路径] [--open]

  --out 路径   输出路径，默认 <工作区>/viewer.html
  --open       生成后在浏览器打开

产出的 viewer.html 自带全部数据，双击即可离线阅读，不需要服务器、不联网。
写完新章节后重新运行一次本脚本，再刷新浏览器页面即可看到更新。

仅用 Python 标准库。所有文件 UTF-8。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TOKEN = "@@NOVEL_DATA@@"
SCHEMA_VERSION = 1
TEMPLATE_NAME = "viewer_template.html"

LEADING_NUM = re.compile(r"^(\d+)")
HEADING_ONE = re.compile(r"^\s*#\s+(.*)$")
WHITESPACE = re.compile(r"\s+")
MARKDOWN_SUFFIXES = (".md", ".markdown")


def fail(message: str) -> "None":
    print(f"错误: {message}", file=sys.stderr)
    sys.exit(1)


def template_path() -> Path:
    return Path(__file__).resolve().parent / TEMPLATE_NAME


# ---------------------------------------------------------------------------
# 读取工作区
# ---------------------------------------------------------------------------

def load_json_optional(path: Path, notices: list) -> tuple:
    """返回 (值, 状态)。状态为 ok / missing / broken；任何情况都不中断。"""
    if not path.exists():
        return None, "missing"
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), "ok"
    except (OSError, ValueError) as error:
        notices.append({
            "level": "warn",
            "message": f"{path.name} 无法解析，相关视图将为空：{error}",
        })
        return None, "broken"


def collect_chapters(folder: Path, notices: list) -> list:
    if not folder.is_dir():
        notices.append({"level": "info", "message": "未找到 chapters/ 目录，尚无正文。"})
        return []

    rows = []
    for path in sorted(folder.iterdir(), key=lambda p: p.name):
        if not path.is_file() or path.suffix.lower() not in MARKDOWN_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            notices.append({"level": "warn", "message": f"{path.name} 读取失败：{error}"})
            continue

        match = LEADING_NUM.match(path.stem)
        seq = int(match.group(1)) if match else None

        title = ""
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            found = HEADING_ONE.match(line)
            if found:
                title = found.group(1).strip()
                break
        if not title:
            title = f"第{seq}章" if seq else path.stem

        rows.append({
            "seq": seq,
            "file": path.name,
            "title": title,
            "markdown": text,
            "charCount": len(WHITESPACE.sub("", text)),
        })

    rows.sort(key=lambda r: (r["seq"] is None, r["seq"] or 0, r["file"]))
    return rows


def build_payload(workspace: Path) -> tuple:
    notices: list = []

    project, project_state = load_json_optional(workspace / "project.json", notices)
    if project_state == "missing":
        notices.append({"level": "warn", "message": "未找到 project.json，概览的设定区将为空。"})

    blueprint, blueprint_state = load_json_optional(workspace / "blueprint.json", notices)
    if blueprint_state == "missing":
        notices.append({"level": "info", "message": "未找到 blueprint.json，蓝图视图将为空。"})

    outline, outline_state = load_json_optional(workspace / "outline.json", notices)
    if outline_state == "missing":
        notices.append({"level": "info", "message": "未找到 outline.json，路线视图将为空。"})

    # state.json 是备忘而非契约，缺失时不加提示——状态视图自身会说明。
    state, _ = load_json_optional(workspace / "state.json", notices)

    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "workspaceName": workspace.name,
        "project": project,
        "blueprint": blueprint,
        "outline": outline,
        "state": state,
        "chapters": collect_chapters(workspace / "chapters", notices),
        "notices": notices,
    }
    return payload, notices


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render_html(template: str, payload: dict) -> str:
    occurrences = template.count(TOKEN)
    if occurrences != 1:
        fail(f"{TEMPLATE_NAME} 中占位符 {TOKEN} 应恰好出现 1 次，实际 {occurrences} 次。")
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # 破坏 </script>：HTML 解析器遇到 </script 即终止脚本块。
    # \/ 是合法 JSON 转义，解析回来仍是 /，数据不受影响。
    blob = blob.replace("</", "<\\/")
    return template.replace(TOKEN, blob)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def cmd_build(args) -> None:
    workspace = Path(args.dir)
    if not workspace.is_dir():
        fail(f"目录不存在: {workspace}")

    source = template_path()
    if not source.is_file():
        fail(f"找不到模板文件: {source}")
    try:
        template = source.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"模板读取失败: {error}")

    payload, notices = build_payload(workspace)
    html = render_html(template, payload)

    destination = Path(args.out) if args.out else workspace / "viewer.html"
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html, encoding="utf-8", newline="\n")
    except OSError as error:
        fail(f"写入失败 {destination}: {error}")

    size_kb = len(html.encode("utf-8")) / 1024
    print(f"已生成 {destination}（{size_kb:.0f} KB，内嵌 {len(payload['chapters'])} 章）")
    print("双击打开即可阅读；写了新章节就重新运行本脚本，再刷新页面。")
    for item in notices:
        print(f"  [{item['level']}] {item['message']}")

    if args.open:
        webbrowser.open(destination.resolve().as_uri())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="为小说工作区生成单文件本地阅读器 viewer.html（纯标准库）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("dir", help="小说工作区目录")
    parser.add_argument("--out", default=None, help="输出路径，默认 <dir>/viewer.html")
    parser.add_argument("--open", action="store_true", help="生成后在浏览器打开")
    parser.set_defaults(func=cmd_build)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
