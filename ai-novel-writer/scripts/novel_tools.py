#!/usr/bin/env python3
"""小说工作区的两个小工具：初始化设定、校验蓝图与章节路线。

子命令:
  init <dir> [options]                初始化工作区 (project.json + chapters/)
  validate <file> --type blueprint    校验蓝图契约
  validate <file> --type outline      校验章节路线 (数量与 ID 白名单)

仅用 Python 标准库。所有文件 UTF-8。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


def fail(message: str) -> "None":
    print(f"错误: {message}", file=sys.stderr)
    sys.exit(1)


def read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        fail(f"文件不存在: {path}")
    except json.JSONDecodeError as error:
        fail(f"文件不是有效 JSON: {path} ({error})")


def write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


# ---------------------------------------------------------------------------
# 校验规则
# ---------------------------------------------------------------------------

def issue(code: str, field: str, message: str) -> dict:
    return {"code": code, "field": field, "message": message}


def check_text(value, field: str, minimum: int, maximum: int, issues: list) -> None:
    if value is None:
        issues.append(issue("null", field, f"{field} 不能为 null。"))
    elif not (minimum <= len(str(value).strip()) and len(str(value)) <= maximum):
        issues.append(issue("length", field, f"{field} 长度必须在 {minimum} 到 {maximum} 之间。"))


def check_count(value, field: str, minimum: int, maximum: int, issues: list) -> None:
    if value is None:
        issues.append(issue("null_collection", field, f"{field} 不能为 null。"))
    elif not (minimum <= len(value) <= maximum):
        issues.append(issue("count", field, f"{field} 数量必须在 {minimum} 到 {maximum} 之间。"))


def check_id(value, field: str, issues: list) -> None:
    if not isinstance(value, str) or not STABLE_ID.match(value):
        issues.append(issue("stable_id", field, f"{field} 必须是稳定的字母数字 ID。"))


def check_unique_ids(values, field: str, issues: list) -> None:
    clean = [v for v in values if isinstance(v, str) and v.strip()]
    if len(set(clean)) != len(clean):
        issues.append(issue("duplicate_id", field, f"{field} 包含重复稳定 ID。"))


def validate_blueprint(value: dict) -> list:
    issues: list = []
    if not isinstance(value, dict):
        return [issue("type", "$", "蓝图必须是 JSON object。")]
    check_text(value.get("theme"), "theme", 2, 2000, issues)
    check_text(value.get("coreConflict"), "coreConflict", 2, 4000, issues)
    check_text(value.get("protagonistArc"), "protagonistArc", 2, 4000, issues)
    check_text(value.get("beats"), "beats", 10, 8000, issues)
    for key, minimum, maximum in (("characters", 3, 50), ("plotThreads", 3, 50), ("timeline", 6, 200)):
        items = value.get(key) or []
        check_count(items, key, minimum, maximum, issues)
        check_unique_ids([item.get("id") for item in items], key, issues)
        for index, item in enumerate(items):
            check_id(item.get("id"), f"{key}[{index}].id", issues)
    for index, item in enumerate(value.get("characters") or []):
        for field, maximum in (("name", 200), ("role", 500), ("goal", 2000), ("fear", 2000), ("secret", 2000)):
            check_text(item.get(field), f"characters[{index}].{field}", 1, maximum, issues)
    for index, item in enumerate(value.get("plotThreads") or []):
        for field, maximum in (("name", 200), ("setup", 2000), ("plannedPayoff", 2000)):
            check_text(item.get(field), f"plotThreads[{index}].{field}", 1, maximum, issues)
    for index, item in enumerate(value.get("timeline") or []):
        for field, maximum in (("when", 500), ("event", 4000), ("consequence", 4000)):
            check_text(item.get(field), f"timeline[{index}].{field}", 1, maximum, issues)
    return issues


def blueprint_ids(value: dict) -> set:
    ids: set = set()
    for key in ("characters", "plotThreads", "timeline"):
        for item in value.get(key) or []:
            if isinstance(item.get("id"), str):
                ids.add(item["id"])
    return ids


def validate_outline(value: dict, expected_count: int, known_ids: set | None) -> list:
    issues: list = []
    if not isinstance(value, dict):
        return [issue("type", "$", "章节路线必须是 JSON object。")]
    chapters = value.get("chapters")
    check_count(chapters, "chapters", expected_count, expected_count, issues)
    for index, plan in enumerate(chapters or []):
        if plan.get("sequence") != index + 1:
            issues.append(issue("sequence", f"chapters[{index}].sequence", "章节序号必须从 1 连续递增。"))
        check_text(plan.get("title"), f"chapters[{index}].title", 1, 200, issues)
        check_text(plan.get("sceneGoal"), f"chapters[{index}].sceneGoal", 5, 2000, issues)
        check_text(plan.get("summaryTarget"), f"chapters[{index}].summaryTarget", 5, 2000, issues)
        required = plan.get("requiredStateIds") or []
        check_count(required, f"chapters[{index}].requiredStateIds", 0, 30, issues)
        for state_id in required:
            check_id(state_id, f"chapters[{index}].requiredStateIds", issues)
            if known_ids is not None and isinstance(state_id, str) and state_id not in known_ids:
                issues.append(issue("unknown_id", f"chapters[{index}].requiredStateIds",
                                    f"requiredStateIds 中的 {state_id} 不在蓝图稳定 ID 列表中。"))
    return issues


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_init(args) -> None:
    workspace = Path(args.dir)
    if workspace.exists() and any(workspace.iterdir()) and not args.force:
        fail(f"目录 {workspace} 非空；确认后使用 --force。")
    (workspace / "chapters").mkdir(parents=True, exist_ok=True)
    project = {
        "title": args.title or "",
        "premise": args.premise or "",
        "genre": args.genre or "",
        "narrativeStructure": args.structure or "",
        "pointOfView": args.pov or "",
        "style": args.style or "",
        "targetChapterCount": args.chapters,
        "language": args.language,
    }
    write_json(workspace / "project.json", project)
    print(f"工作区已初始化: {workspace}")
    print("下一步: 生成 blueprint.json，校验后请用户确认。")


def cmd_validate(args) -> None:
    path = Path(args.file)
    workspace = path.parent
    if args.type == "blueprint":
        issues = validate_blueprint(read_json(path))
    else:
        project_path = Path(args.project) if args.project else workspace / "project.json"
        expected = args.expected
        if expected is None:
            if not project_path.exists():
                fail("校验 outline 需要 --expected N 或同目录 project.json。")
            expected = read_json(project_path).get("targetChapterCount")
        blueprint_path = workspace / "blueprint.json"
        known = blueprint_ids(read_json(blueprint_path)) if blueprint_path.exists() else None
        if known is None:
            print("提示: 未找到 blueprint.json，跳过 requiredStateIds 白名单校验。", file=sys.stderr)
        issues = validate_outline(read_json(path), expected, known)

    if issues:
        print(f"校验失败，共 {len(issues)} 个问题:")
        for item in issues:
            print(f"  [{item['field']}] {item['code']}: {item['message']}")
        print("按契约修复协议重试一次：只修格式/契约字段，缺依据的条目整条删除。")
        sys.exit(1)
    print("OK: 契约校验通过。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="初始化小说工作区")
    init.add_argument("dir")
    init.add_argument("--title", default="")
    init.add_argument("--premise", default="")
    init.add_argument("--genre", default="")
    init.add_argument("--structure", default="")
    init.add_argument("--pov", default="")
    init.add_argument("--style", default="")
    init.add_argument("--chapters", type=int, default=30)
    init.add_argument("--language", default="zh")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    validate = sub.add_parser("validate", help="校验蓝图或章节路线")
    validate.add_argument("file")
    validate.add_argument("--type", required=True, choices=["blueprint", "outline"])
    validate.add_argument("--project", help="project.json 路径 (outline 校验用)")
    validate.add_argument("--expected", type=int, help="期望章节数 (outline 校验用)")
    validate.set_defaults(func=cmd_validate)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
