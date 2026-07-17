#!/usr/bin/env python3
"""Maintain the persistent frontend interview knowledge base."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
KB_DIR = REPO_ROOT / "knowledge-base"
STATE_PATH = KB_DIR / "state.json"
QUESTIONS_DIR = KB_DIR / "questions"
SESSIONS_DIR = KB_DIR / "sessions"

SCORE_LIMITS = {
    "accuracy": 35,
    "completeness": 25,
    "depth": 15,
    "practice": 15,
    "communication": 10,
}

STATUS_LABELS = {
    "queued": "待学习",
    "learning": "学习中",
    "review": "待复习",
    "mastered": "已掌握",
}


def default_state() -> dict:
    return {
        "schema_version": 1,
        "next_question_number": 1,
        "questions": [],
        "sessions": [],
    }


def ensure_layout() -> None:
    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        save_state(default_state())


def load_state() -> dict:
    ensure_layout()
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"无法读取 {STATE_PATH}: {exc}")
    if state.get("schema_version") != 1:
        fail("不支持的知识库 schema_version")
    return state


def save_state(state: dict) -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp_path.replace(STATE_PATH)


def fail(message: str) -> None:
    print(f"错误：{message}", file=sys.stderr)
    raise SystemExit(2)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    return date.today().isoformat()


def md_cell(value: object) -> str:
    return str(value or "-").replace("|", "\\|").replace("\n", " ")


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def find_question(state: dict, question_id: str) -> dict:
    normalized = question_id.upper()
    for question in state["questions"]:
        if question["id"] == normalized:
            return question
    fail(f"题目不存在：{question_id}")


def find_session(state: dict, session_id: str) -> dict:
    normalized = session_id.upper()
    for session in state["sessions"]:
        if session["id"] == normalized:
            return session
    fail(f"面试记录不存在：{session_id}")


def best_score(question: dict) -> int | None:
    scores = [attempt["total"] for attempt in question.get("attempts", [])]
    return max(scores) if scores else None


def question_status(question: dict) -> str:
    attempts = question.get("attempts", [])
    if not attempts:
        return "queued"
    best = best_score(question) or 0
    distinct_sessions = {a.get("session") for a in attempts if a.get("session")}
    if best >= 90 and len(distinct_sessions) >= 2:
        return "mastered"
    if best >= 80:
        return "review"
    return "learning"


def review_interval(total: int) -> int:
    if total < 60:
        return 1
    if total < 75:
        return 3
    if total < 85:
        return 7
    if total < 95:
        return 14
    return 30


def question_path(question_id: str) -> Path:
    return QUESTIONS_DIR / f"{question_id}.md"


def session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.md"


def write_question_stub(question: dict) -> None:
    path = question_path(question["id"])
    if path.exists():
        return
    tags = "、".join(question.get("tags", [])) or "待补充"
    content = f"""# {question['id']} {question['question']}

- 顺序：{question['order']}
- 主分类：{question['category']}
- 标签：{tags}
- 首次记录：{question['created_at'][:10]}
- 来源：{question['source']}

## 原题

{question['question']}

## 换一种问法

<!-- VARIANTS_START -->
暂无。
<!-- VARIANTS_END -->

## 面试官考察意图

待首次练习后补充。

## 面试官最希望听到的回答

待首次练习后补充。

## 系统知识讲解

待首次练习后补充。

## 边界、误区与工程实践

待首次练习后补充。

## 可能追问

待首次练习后补充。

## 作答与点评

暂无作答记录。
"""
    path.write_text(content, encoding="utf-8")


def append_attempt_to_question(question: dict, attempt: dict) -> None:
    path = question_path(question["id"])
    write_question_stub(question)
    strengths = "；".join(attempt["strengths"]) or "暂无明确得分点"
    weaknesses = "；".join(
        f"{item['type']}：{item['detail']}" if item["detail"] else item["type"]
        for item in attempt["weaknesses"]
    ) or "暂无"
    next_actions = "；".join(attempt["next_actions"]) or "暂无"
    scores = attempt["scores"]
    block = f"""### {attempt['created_at'][:10]} · {attempt.get('session') or '未关联场次'} · 第 {attempt['round']} 轮 · {attempt['total']}/100

- 准确性：{scores['accuracy']}/35
- 完整性：{scores['completeness']}/25
- 原理深度：{scores['depth']}/15
- 工程实践：{scores['practice']}/15
- 表达沟通：{scores['communication']}/10
- 回答摘要：{attempt['answer_summary'] or '未记录'}
- 得分点：{strengths}
- 主要缺陷：{weaknesses}
- 后续行动：{next_actions}
- 下次复习：{attempt['next_review_at']}
"""
    current = path.read_text(encoding="utf-8")
    if "\n暂无作答记录。\n" in current:
        current = current.replace("\n暂无作答记录。\n", "\n", 1)
    path.write_text(f"{current.rstrip()}\n\n{block.rstrip()}\n", encoding="utf-8")


def append_attempt_to_session(session: dict, question: dict, attempt: dict) -> None:
    path = session_path(session["id"])
    weaknesses = "；".join(item["type"] for item in attempt["weaknesses"]) or "暂无"
    block = f"""### {question['id']} · 第 {attempt['round']} 轮 · {attempt['total']}/100

- 题目：{question['question']}
- 回答摘要：{attempt['answer_summary'] or '未记录'}
- 主要缺陷：{weaknesses}
- 下次复习：{attempt['next_review_at']}
"""
    current = path.read_text(encoding="utf-8")
    path.write_text(f"{current.rstrip()}\n\n{block.rstrip()}\n", encoding="utf-8")


def write_views(state: dict) -> None:
    questions = sorted(state["questions"], key=lambda item: item["order"])
    attempts = [a for q in questions for a in q.get("attempts", [])]
    statuses = Counter(question_status(q) for q in questions)
    categories = Counter(q["category"] for q in questions)
    scored = [a["total"] for a in attempts]
    due = [
        q
        for q in questions
        if q.get("next_review_at") and q["next_review_at"] <= today_iso()
    ]

    index_lines = [
        "# 前端面试知识库",
        "",
        f"> 最后同步：{now_iso()}",
        "",
        "## 学习总览",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| 题目总数 | {len(questions)} |",
        f"| 作答轮次 | {len(attempts)} |",
        f"| 平均分 | {sum(scored) / len(scored):.1f} |" if scored else "| 平均分 | - |",
        f"| 待学习 | {statuses['queued']} |",
        f"| 学习中 | {statuses['learning']} |",
        f"| 待复习 | {statuses['review']} |",
        f"| 已掌握 | {statuses['mastered']} |",
        f"| 今日到期复习 | {len(due)} |",
        "",
        "## 分类分布",
        "",
        "| 分类 | 题数 |",
        "| --- | ---: |",
    ]
    if categories:
        index_lines.extend(f"| {md_cell(name)} | {count} |" for name, count in categories.most_common())
    else:
        index_lines.append("| 暂无题目 | 0 |")

    index_lines.extend(["", "## 到期复习", ""])
    if due:
        index_lines.extend(
            f"- [{q['id']}](questions/{q['id']}.md) {q['question']}（{q['next_review_at']}）"
            for q in due
        )
    else:
        index_lines.append("暂无到期题目。")

    index_lines.extend(["", "## 最近面试记录", ""])
    recent_sessions = list(reversed(state["sessions"][-10:]))
    if recent_sessions:
        index_lines.extend(
            f"- [{s['id']}](sessions/{s['id']}.md) · {s['mode']} · {s['created_at'][:10]}"
            for s in recent_sessions
        )
    else:
        index_lines.append("暂无面试记录。")

    index_lines.extend(
        [
            "",
            "## 常用对话指令",
            "",
            "- `记录以下题目：……`：按发送顺序归档，并从第一题开始。",
            "- `开始今天的面试`：继续待学习或到期复习题。",
            "- `请随机出题`：从已有题库按薄弱度加权抽取，并可换一种问法。",
            "- `查看我的薄弱点`：按历史作答证据汇总缺陷和待补内容。",
            "- `继续上次的题`：根据最近场次和题目状态恢复练习。",
            "",
            "## 文件入口",
            "",
            "- [完整题库](QUESTION_BANK.md)",
            "- [缺陷清单](WEAKNESSES.md)",
            "- `questions/`：逐题讲解与历次点评",
            "- `sessions/`：每次模拟面试记录",
            "- `sources/`：面经来源、岗位背景与反问记录",
            "",
        ]
    )
    (KB_DIR / "INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")

    bank_lines = [
        "# 面试题库",
        "",
        "题号严格按用户首次发题的顺序递增。",
        "",
        "| 顺序 | 题号 | 分类 | 题目 | 状态 | 最佳分 | 下次复习 |",
        "| ---: | --- | --- | --- | --- | ---: | --- |",
    ]
    if questions:
        for q in questions:
            best = best_score(q)
            bank_lines.append(
                f"| {q['order']} | [{q['id']}](questions/{q['id']}.md) | "
                f"{md_cell(q['category'])} | {md_cell(q['question'])} | "
                f"{STATUS_LABELS[question_status(q)]} | {best if best is not None else '-'} | "
                f"{q.get('next_review_at') or '-'} |"
            )
    else:
        bank_lines.append("| - | - | - | 暂无题目 | - | - | - |")
    bank_lines.append("")
    (KB_DIR / "QUESTION_BANK.md").write_text("\n".join(bank_lines), encoding="utf-8")

    weakness_groups: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "questions": set(), "details": [], "latest": ""}
    )
    for q in questions:
        for attempt in q.get("attempts", []):
            for weakness in attempt.get("weaknesses", []):
                group = weakness_groups[weakness["type"]]
                group["count"] += 1
                group["questions"].add(q["id"])
                if weakness.get("detail"):
                    group["details"].append(weakness["detail"])
                group["latest"] = max(group["latest"], attempt["created_at"][:10])

    weakness_lines = [
        "# 面试回答缺陷清单",
        "",
        "缺陷按稳定标签归并；次数表示在不同作答轮次中出现的次数。",
        "",
        "| 缺陷类型 | 出现次数 | 涉及题目 | 最近出现 | 最近的具体表现 |",
        "| --- | ---: | --- | --- | --- |",
    ]
    if weakness_groups:
        ordered = sorted(weakness_groups.items(), key=lambda item: (-item[1]["count"], item[0]))
        for kind, group in ordered:
            question_links = "、".join(
                f"[{qid}](questions/{qid}.md)" for qid in sorted(group["questions"])
            )
            detail = group["details"][-1] if group["details"] else "-"
            weakness_lines.append(
                f"| {md_cell(kind)} | {group['count']} | {question_links} | "
                f"{group['latest']} | {md_cell(detail)} |"
            )
    else:
        weakness_lines.append("| 暂无已记录缺陷 | 0 | - | - | - |")
    weakness_lines.extend(
        [
            "",
            "## 使用说明",
            "",
            "随机复习会提高未作答、低分、缺陷较多和已经到期题目的抽取权重。",
            "缺陷是否消除以之后独立作答的证据为准，不因阅读过讲解而自动关闭。",
            "",
        ]
    )
    (KB_DIR / "WEAKNESSES.md").write_text("\n".join(weakness_lines), encoding="utf-8")


def cmd_init(_: argparse.Namespace) -> None:
    state = load_state()
    for question in state["questions"]:
        write_question_stub(question)
    write_views(state)
    print(f"知识库已初始化：{KB_DIR}")


def cmd_add(args: argparse.Namespace) -> None:
    state = load_state()
    number = state["next_question_number"]
    question_id = f"FE-{number:04d}"
    question = {
        "id": question_id,
        "order": number,
        "question": args.question.strip(),
        "category": args.category.strip(),
        "tags": split_csv(args.tags),
        "source": args.source.strip(),
        "created_at": now_iso(),
        "status": "queued",
        "attempts": [],
        "variants": [],
        "last_asked_at": None,
        "next_review_at": None,
    }
    if not question["question"]:
        fail("题目不能为空")
    state["questions"].append(question)
    state["next_question_number"] = number + 1
    save_state(state)
    write_question_stub(question)
    write_views(state)
    print(json.dumps({"id": question_id, "category": question["category"], "order": number}, ensure_ascii=False))


def cmd_start_session(args: argparse.Namespace) -> None:
    state = load_state()
    day_key = date.today().strftime("%Y%m%d")
    pattern = re.compile(rf"^S{day_key}-(\d+)$")
    sequence = max(
        (int(match.group(1)) for s in state["sessions"] if (match := pattern.match(s["id"]))),
        default=0,
    ) + 1
    session_id = f"S{day_key}-{sequence:02d}"
    question_ids = [item.upper() for item in split_csv(args.questions)]
    for question_id in question_ids:
        find_question(state, question_id)
    session = {
        "id": session_id,
        "mode": args.mode,
        "question_ids": question_ids,
        "created_at": now_iso(),
    }
    state["sessions"].append(session)
    save_state(state)
    title_questions = "、".join(question_ids) or "按对话动态加入"
    content = f"""# 面试记录 {session_id}

- 日期：{session['created_at'][:10]}
- 模式：{args.mode}
- 计划题目：{title_questions}

## 本次总评

待本次练习结束后总结，包括主要进步、反复缺陷和下一步计划。

## 逐题记录
"""
    session_path(session_id).write_text(content, encoding="utf-8")
    write_views(state)
    print(session_id)


def parse_weakness(value: str) -> dict:
    kind, separator, detail = value.partition("|")
    kind = kind.strip()
    if not kind:
        fail("缺陷标签不能为空")
    return {"type": kind, "detail": detail.strip() if separator else ""}


def cmd_record(args: argparse.Namespace) -> None:
    state = load_state()
    question = find_question(state, args.id)
    session = find_session(state, args.session) if args.session else None
    scores = {name: getattr(args, name) for name in SCORE_LIMITS}
    for name, value in scores.items():
        if value < 0 or value > SCORE_LIMITS[name]:
            fail(f"{name} 应在 0-{SCORE_LIMITS[name]} 之间")
    total = sum(scores.values())
    next_review = date.today() + timedelta(days=review_interval(total))
    attempt = {
        "created_at": now_iso(),
        "session": session["id"] if session else None,
        "round": args.round,
        "scores": scores,
        "total": total,
        "answer_summary": args.answer_summary.strip(),
        "strengths": args.strength or [],
        "weaknesses": [parse_weakness(item) for item in (args.weakness or [])],
        "next_actions": args.next_action or [],
        "next_review_at": next_review.isoformat(),
    }
    question["attempts"].append(attempt)
    question["last_asked_at"] = attempt["created_at"]
    question["next_review_at"] = attempt["next_review_at"]
    question["status"] = question_status(question)
    if session and question["id"] not in session["question_ids"]:
        session["question_ids"].append(question["id"])
    save_state(state)
    append_attempt_to_question(question, attempt)
    if session:
        append_attempt_to_session(session, question, attempt)
    write_views(state)
    print(
        json.dumps(
            {
                "id": question["id"],
                "round": args.round,
                "total": total,
                "status": question["status"],
                "next_review_at": attempt["next_review_at"],
            },
            ensure_ascii=False,
        )
    )


def random_weight(question: dict) -> float:
    attempts = question.get("attempts", [])
    if not attempts:
        return 9.0
    best = best_score(question) or 0
    weight = 1.0 + (100 - best) / 15.0
    weakness_count = sum(len(a.get("weaknesses", [])) for a in attempts)
    weight += min(weakness_count * 0.75, 4.0)
    if question.get("next_review_at") and question["next_review_at"] <= today_iso():
        weight += 4.0
    return max(weight, 0.25)


def cmd_random(args: argparse.Namespace) -> None:
    state = load_state()
    candidates = [
        q for q in state["questions"] if not args.category or q["category"] == args.category
    ]
    if not candidates:
        fail("没有符合条件的题目")
    count = min(args.count, len(candidates))
    if count < 1:
        fail("count 必须大于 0")

    recently_asked = sorted(
        (q for q in candidates if q.get("last_asked_at")),
        key=lambda q: q["last_asked_at"],
        reverse=True,
    )[:3]
    recent_ids = {q["id"] for q in recently_asked}
    filtered = [q for q in candidates if q["id"] not in recent_ids]
    if len(filtered) >= count:
        candidates = filtered

    rng = random.Random(args.seed)
    selected = []
    pool = list(candidates)
    for _ in range(count):
        choice = rng.choices(pool, weights=[random_weight(q) for q in pool], k=1)[0]
        selected.append(choice)
        pool.remove(choice)

    asked_at = now_iso()
    for question in selected:
        question["last_asked_at"] = asked_at
    save_state(state)
    write_views(state)
    print(
        json.dumps(
            [
                {
                    "id": q["id"],
                    "question": q["question"],
                    "category": q["category"],
                    "tags": q.get("tags", []),
                    "best_score": best_score(q),
                }
                for q in selected
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_variant(args: argparse.Namespace) -> None:
    state = load_state()
    question = find_question(state, args.id)
    text = args.text.strip()
    if not text:
        fail("变体题目不能为空")
    if text not in question["variants"]:
        question["variants"].append(text)
        save_state(state)
        path = question_path(question["id"])
        write_question_stub(question)
        content = path.read_text(encoding="utf-8")
        rendered = "\n".join(f"- {item}" for item in question["variants"])
        marked_pattern = re.compile(
            r"(<!-- VARIANTS_START -->\n).*?(\n<!-- VARIANTS_END -->)", re.DOTALL
        )
        if marked_pattern.search(content):
            content = marked_pattern.sub(
                lambda match: f"{match.group(1)}{rendered}{match.group(2)}",
                content,
                count=1,
            )
        else:
            legacy_pattern = re.compile(
                r"(## 换一种问法\n\n).*?(\n\n## 面试官考察意图)", re.DOTALL
            )
            content = legacy_pattern.sub(
                lambda match: (
                    f"{match.group(1)}<!-- VARIANTS_START -->\n{rendered}\n"
                    f"<!-- VARIANTS_END -->{match.group(2)}"
                ),
                content,
                count=1,
            )
        path.write_text(content, encoding="utf-8")
    write_views(state)
    print(json.dumps({"id": question["id"], "variant": text}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化并刷新知识库视图")
    init_parser.set_defaults(func=cmd_init)

    add_parser = subparsers.add_parser("add", help="按顺序添加一道题")
    add_parser.add_argument("--question", required=True)
    add_parser.add_argument("--category", required=True)
    add_parser.add_argument("--tags")
    add_parser.add_argument("--source", default="用户输入")
    add_parser.set_defaults(func=cmd_add)

    session_parser = subparsers.add_parser("start-session", help="创建一次面试记录")
    session_parser.add_argument("--mode", choices=["daily", "random", "review"], default="daily")
    session_parser.add_argument("--questions")
    session_parser.set_defaults(func=cmd_start_session)

    record_parser = subparsers.add_parser("record", help="记录一轮作答评分")
    record_parser.add_argument("--id", required=True)
    record_parser.add_argument("--session")
    record_parser.add_argument("--round", type=int, choices=[1, 2], required=True)
    for score_name in SCORE_LIMITS:
        record_parser.add_argument(f"--{score_name}", type=int, required=True)
    record_parser.add_argument("--answer-summary", default="")
    record_parser.add_argument("--strength", action="append")
    record_parser.add_argument("--weakness", action="append")
    record_parser.add_argument("--next-action", action="append")
    record_parser.set_defaults(func=cmd_record)

    random_parser = subparsers.add_parser("random", help="按学习权重随机抽题")
    random_parser.add_argument("--count", type=int, default=1)
    random_parser.add_argument("--category")
    random_parser.add_argument("--seed", type=int)
    random_parser.set_defaults(func=cmd_random)

    variant_parser = subparsers.add_parser("variant", help="记录题目的改写问法")
    variant_parser.add_argument("--id", required=True)
    variant_parser.add_argument("--text", required=True)
    variant_parser.set_defaults(func=cmd_variant)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
