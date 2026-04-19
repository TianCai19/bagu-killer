from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path("/data3/chenrenmiao/project/AI_offer_catcher")
REPORT_PATH = ROOT / "artifacts" / "reports" / "report_latest.json"
OUT_DIR = ROOT / "kaomian"
QUESTION_DIR = OUT_DIR / "题库"
SNAPSHOT = {
    "raw_posts": 767,
    "latest_keep_posts": 248,
    "canonical": 638,
    "extracted": 948,
    "min_published": "2025-03-22",
    "max_published": "2026-04-18",
}

TYPE_META = [
    ("knowledge_qa", "02_知识问答题", "知识问答题"),
    ("agent_rag_tool_memory", "03_Agent_RAG_Tool_Memory", "Agent / RAG / Tool Calling / Memory"),
    ("leetcode_algo", "04_LeetCode_算法手撕", "LeetCode / 算法手撕"),
    ("ml_llm_coding", "05_机器学习_大模型手撕", "机器学习 / 大模型手撕"),
    ("project_drilldown", "06_项目拷打题", "项目拷打题"),
]


def load_rows() -> list[dict]:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def fmt_list(values: list[str]) -> str:
    cleaned = [v.strip() for v in values if v and v.strip()]
    return "、".join(cleaned) if cleaned else "暂无"


def top_companies(rows: list[dict], limit: int = 10) -> list[tuple[str, int]]:
    counter: dict[str, int] = {}
    for row in rows[:100]:
        for company in row.get("companies", []):
            if company and company.strip():
                counter[company] = counter.get(company, 0) + 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def question_type_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["question_type"]] += 1
    return counts


def build_readme(rows: list[dict]) -> str:
    top10 = rows[:10]
    type_counts = question_type_counts(rows)
    company_lines = [f"- {company} `{count}`" for company, count in top_companies(rows)]
    lines = [
        "# 两年拷打，一年面经",
        "",
        "![烤面宣传图](./assets/intro.png)",
        "",
        "## 烤面",
        "",
        "> 把零散面经烤熟，烤成题库。",
        "",
        "`烤面` 不是一篇心得，也不是一份“谁记得多谁赢”的面经合集。",
        "",
        "它是把一批真实 AI Agent 面经帖子做完筛选、OCR、抽取、归并之后，留下来的高频拷打题数据库。",
        "",
        "一句话理解：",
        "",
        "- 普通面经：某个人记住了什么",
        "- `烤面`：不同公司、不同岗位，反复拷打什么",
        "",
        "## 快速入口",
        "",
        "- [题库总索引](./题库/00_题库总索引.md)",
        "- [Top 100 高频题](./题库/01_Top100_高频题.md)",
        "- [知识问答题](./题库/02_知识问答题.md)",
        "- [Agent / RAG / Tool Calling / Memory](./题库/03_Agent_RAG_Tool_Memory.md)",
        "- [LeetCode / 算法手撕](./题库/04_LeetCode_算法手撕.md)",
        "- [机器学习 / 大模型手撕](./题库/05_机器学习_大模型手撕.md)",
        "- [项目拷打题](./题库/06_项目拷打题.md)",
        "",
        "## 当前快照",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| 抓取帖子总数 | {SNAPSHOT['raw_posts']} |",
        f"| 最新分类口径下保留帖子 | {SNAPSHOT['latest_keep_posts']} |",
        f"| 抽取题目总数 | {SNAPSHOT['extracted']} |",
        f"| canonical question | {SNAPSHOT['canonical']} |",
        f"| 时间覆盖起点 | {SNAPSHOT['min_published']} |",
        f"| 时间覆盖终点 | {SNAPSHOT['max_published']} |",
        "",
        "题型分布：",
        "",
        f"- `knowledge_qa`：`{type_counts.get('knowledge_qa', 0)}`",
        f"- `agent_rag_tool_memory`：`{type_counts.get('agent_rag_tool_memory', 0)}`",
        f"- `leetcode_algo`：`{type_counts.get('leetcode_algo', 0)}`",
        f"- `ml_llm_coding`：`{type_counts.get('ml_llm_coding', 0)}`",
        f"- `project_drilldown`：`{type_counts.get('project_drilldown', 0)}`",
        "",
        "高频出现公司：",
        "",
        *company_lines,
        "",
        "## Top 10 高频题",
        "",
        "| 排名 | 出现帖子数 | 题型 | 问题 |",
        "| --- | ---: | --- | --- |",
    ]
    for idx, row in enumerate(top10, 1):
        lines.append(f"| {idx} | {row['unique_post_count']} | `{row['question_type']}` | {row['canonical_text']} |")

    lines.extend(
        [
            "",
            "## 这个库怎么来的",
            "",
            "`烤面` 不是手工抄帖，也不是把几篇热门面经 copy 一下拼成一个页面。",
            "",
            "它来自一条完整的数据流水线：",
            "",
            "1. **关键词抓取**",
            "   按 `ai agent 面试 / 凉经 / 智能体 / tool calling / rag / 多 agent` 等关键词抓小红书帖子。",
            "2. **帖子级过滤**",
            "   先判断是不是更像真实个人面经，而不是广告、卖课、课程号、题库合集、包装号。",
            "3. **昵称参与判断**",
            "   如果昵称里带有“大厂 / 面经 / offer / 上岸 / 求职 / 内推 / 辅导 / 陪跑”等信号，会显著提高对假面经和广告贴的警惕。",
            "4. **图片 OCR**",
            "   很多帖子真正值钱的信息都在图里，这一步会把图片里的题目也提出来。",
            "5. **结构化抽取**",
            "   从标题、正文、OCR 文本里抽出公司、岗位、面试阶段、题目列表。",
            "6. **题目级语义归并**",
            "   先标准化，再做 embedding 召回，再做语义判断，把同义题合并成同一个 canonical question。",
            "7. **可追溯统计**",
            "   每道题都能追到它出现在哪些帖子、哪些公司、哪些岗位。",
            "",
            "所以你现在看到的不是原始帖子的堆积，而是一份“从原始面经里烤出来”的结构化题库。",
            "",
            "## 这次实际用到的模型",
            "",
            "- 帖子筛选 / 分类：`Qwen3-VL-4B-Instruct`",
            "- 图片 OCR：`Qwen3-VL-4B-Instruct`",
            "- 题目结构化抽取：`Qwen3-VL-8B-Instruct`",
            "- 题目语义归并裁决：`Qwen3-VL-8B-Instruct`",
            "- 题目 embedding / 相似召回：`Qwen3-Embedding-8B`",
            "",
            "这里写的是**实际跑这版题库时用到的模型**，不是最初规划里的理想配置。",
            "",
            "## 为什么这份题库比普通面经合集更有用",
            "",
            "### 1. 它统计的是“重复出现的问题”",
            "",
            "普通面经告诉你某一个人被问了什么。",
            "",
            "`烤面` 更关心的是：",
            "",
            "- 哪些问题跨公司反复出现",
            "- 哪些问题不是偶发，而是高频",
            "- 哪些问题是 Agent 岗位的共识拷打区",
            "",
            "### 2. 它把图文一起算进去了",
            "",
            "很多高价值题并不写在正文里，而是藏在截图、备忘录、聊天记录、图片题单里。",
            "",
            "只看正文，会漏很多题。",
            "",
            "### 3. 它把“帖子去重”和“题目归并”分开了",
            "",
            "- 同一帖子只存一次",
            "- 一个帖子可以关联多道题",
            "- 同义题会尽量合并到同一个 canonical question",
            "",
            "最后统计的是“这道题出现于多少不同帖子”，不是“这句话被复制了多少次”。",
            "",
            "### 4. 它能追到公司和岗位",
            "",
            "这点很重要。",
            "",
            "不是只告诉你“有这题”，而是尽量告诉你：",
            "",
            "- 哪些公司反复问它",
            "- 哪些岗位更容易出现它",
            "- 它到底是行业共识题，还是某类岗位专属题",
            "",
            "## 你应该从哪里开始看",
            "",
            "- 如果你想快速抓重点：先看 [Top 100 高频题](./题库/01_Top100_高频题.md)",
            "- 如果你在准备专项：直接进对应题型文件",
            "- 如果你想完整刷库：从 [题库总索引](./题库/00_题库总索引.md) 开始",
        ]
    )
    return "\n".join(lines) + "\n"


def build_index(rows: list[dict]) -> str:
    by_type = defaultdict(list)
    for row in rows:
        by_type[row["question_type"]].append(row)

    lines = [
        "# 题库总索引",
        "",
        "按题型拆开的完整题库在下面。建议先看 Top 100，再决定深入哪一类。",
        "",
        "| 文件 | 题型 | canonical 数量 |",
        "| --- | --- | ---: |",
        f"| [01_Top100_高频题.md](./01_Top100_高频题.md) | 高频入口 | {min(100, len(rows))} |",
    ]
    for key, slug, label in TYPE_META:
        lines.append(f"| [{slug}.md](./{slug}.md) | {label} | {len(by_type[key])} |")

    lines.extend(
        [
            "",
            "## 怎么读",
            "",
            "- 如果你只想抓高频，先看每个文件最上面的高频区。",
            "- 如果你准备专项，就按题型读完整文件。",
            "- 每道题下面都带了出现帖子数、出现公司、出现岗位。",
            "",
            "### 编号说明",
            "",
            "- `00_` 留给总索引。",
            "- `01_` 开始才是正式阅读内容。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_top100(rows: list[dict]) -> str:
    lines = [
        "# Top 100 高频题",
        "",
        "这份文件适合第一次看 `烤面` 的人。",
        "",
        "规则：按出现帖子数从高到低排列；同频次下按题库顺序排列。",
        "",
    ]
    for idx, row in enumerate(rows[:100], 1):
        lines.extend(
            [
                f"## {idx}. {row['canonical_text']}",
                "",
                f"- 出现帖子数：`{row['unique_post_count']}`",
                f"- 题型：`{row['question_type']}`",
                f"- 公司：{fmt_list(row.get('companies', []))}",
                f"- 岗位：{fmt_list(row.get('roles', []))}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_type_doc(rows: list[dict], title: str) -> str:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["unique_post_count"]].append(row)

    lines = [
        f"# {title}",
        "",
        f"当前文件包含 `{len(rows)}` 道 canonical question。",
        "",
        "[返回题库总索引](./00_题库总索引.md) | [返回 README](../README.md)",
        "",
        "阅读方式：同一频次下按题目顺序排列。每道题后面都带了公司和岗位线索。",
    ]

    for count in sorted(grouped.keys(), reverse=True):
        lines.extend(["", f"## 出现 {count} 帖", ""])
        for idx, row in enumerate(grouped[count], 1):
            companies = fmt_list(row.get("companies", []))
            roles = fmt_list(row.get("roles", []))
            lines.extend(
                [
                    f"### {idx}. {row['canonical_text']}",
                    "",
                    f"- 出现帖子数：`{row['unique_post_count']}`",
                    f"- 公司：{companies}",
                    f"- 岗位：{roles}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    rows = load_rows()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    QUESTION_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "README.md").write_text(build_readme(rows), encoding="utf-8")
    (QUESTION_DIR / "00_题库总索引.md").write_text(build_index(rows), encoding="utf-8")
    (QUESTION_DIR / "01_Top100_高频题.md").write_text(build_top100(rows), encoding="utf-8")

    by_type = defaultdict(list)
    for row in rows:
        by_type[row["question_type"]].append(row)

    for key, slug, label in TYPE_META:
        content = build_type_doc(by_type[key], label)
        (QUESTION_DIR / f"{slug}.md").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
