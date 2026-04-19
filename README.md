# bagu_killer / 八股杀手

> 八股杀手，专杀八股。
>
> 不是再背一遍面经，而是把大厂 AI Agent 面试里真正会反复出现的拷打题，从原始帖子里抓出来、筛干净、烤成题库。

![bagu_killer 宣传图](./assets/bagu_killer_intro.png)

`bagu_killer` 是一个面向 AI Agent / RAG / Tool Calling / Memory / 多 Agent 岗位的面经采集与归并系统。

它做的不是“收藏几篇热门面经”，而是把零散帖子变成一条可复盘的数据流水线：

- 抓帖子
- 存原文和图片
- 过滤广告帖 / 卖课帖 / 包装号 / 无关帖 / 题目合集帖
- OCR 识别图片里的题
- 抽取结构化面试题
- 语义归并成 canonical question
- 统计每道题出现于多少帖子、哪些公司、什么岗位
- 最后导出成 GitHub 可读的 Markdown 题库

一句话说，这是一个把“零散面经”加工成“可追溯题库”的采集器。

## 已上线成品

针对 AI Agent 方向的成品题库已经上线：

- `kaomian / 烤面`：https://github.com/smile-struggler/kaomian

这也是 `bagu_killer` 当前最直接的成品示例：从小红书原始面经出发，经过抓取、筛选、OCR、抽取、归并，最后产出一个可以直接在 GitHub 阅读的高频题库。

如果你不做 AI Agent，也没关系。这套系统本质上不是写死给某个方向的，它更像一条“领域面经加工流水线”：

- 你可以换关键词，做 RAG
- 你可以换关键词，做推荐算法 / 搜广推 / LLM Infra
- 你可以换关键词，做数据开发 / 后端 / AIGC 产品
- 你也可以继续扩平台，不只抓小红书

也就是说，`kaomian` 是针对 AI Agent 的一份已经烤好的成品，而 `bagu_killer` 是把任何细分方向烤成题库的那台炉子。

## 它到底解决什么问题

普通面经的问题，不是信息少，而是信息太散：

- 同一道题，几十个人换不同说法重复写
- 广告帖、卖课帖、包装号，把真实信号稀释掉
- 真题藏在长图里，纯文本搜索根本搜不出来
- 你能看到“有人被问了什么”，但看不到“市场到底在反复问什么”

`bagu_killer` 的目标，就是把这些噪声压平，把高频拷打题从帖子流里捞出来。

这也是它和普通“面经合集”最大的区别：

- 普通合集回答的是：`某个人记住了什么`
- `bagu_killer` 回答的是：`不同公司、不同岗位，最近一段时间在反复拷打什么`

## 核心能力

- 基于 `MediaCrawler` 抓取小红书帖子，支持关键词搜索
- 以 `关键词 + 时间窗 + 最新发布时间 watermark` 做断点续传
- 帖子级去重和题目级归并完全分离
- 垃圾帖只打标签，不物理删除
- 图片 OCR、帖子分类、题目抽取、语义归并全链路留痕
- 每个阶段都能单独重跑，方便调试和人工复盘
- 一键 daily sync，从抓取一路跑到报表
- 支持把最终题库导出成 GitHub 友好的 Markdown 文档

## 这套系统为什么比较狠

### 1. 它不是“搜帖子”，而是“增量扫盘”

抓取不是按页码死跑，而是按 `keyword + date window + watermark` 管理进度。

实际做法是：

- 搜索时优先按最新排序
- 每个关键词单独维护 checkpoint
- 记录该关键词在当前时间窗下，已经见过的最新 `published_at`
- 每次重跑都从最新结果重新扫
- 一旦某一页整体落到历史 watermark 之下，就自动停掉后续翻页

这意味着：

- 可以每天跑一次，不会把旧帖子反复看完
- 中断以后能续跑
- 不依赖“上次跑到第几页”这种脆弱状态

### 2. 它知道“帖子”和“题目”不是一回事

很多类似项目会把“帖子去重”和“问题归并”揉成一团，最后统计口径会崩。

这里是明确拆开的：

- `raw_posts` 只按帖子唯一键存一次
- 一个帖子可以关联多道题
- 同一道题可以来自多个帖子
- 题目统计按 `COUNT(DISTINCT raw_post_id)` 做帖子级计数

所以不会出现：

- 同一帖子里同一道题重复出现，把频次刷高
- 删除垃圾帖导致题目追溯链断掉

### 3. 它不是简单字符串去重，而是“规则 + 向量 + 二判”

题目归并流程是：

1. 对抽取题做 `normalize`
2. 生成 `fingerprint`
3. 先走精确归并
4. 未命中再做 embedding 检索
5. 高相似候选直接并入
6. 灰区候选交给 LLM 做语义二判
7. 真没命中才新建 canonical question

所以它不是粗暴地拿字符串做去重，而是尽量把“问法不同、核心考点相同”的题并到一起。

### 4. 它不是黑盒，整个流程都能回放

系统会把每个阶段的中间结果落盘：

- 搜索页原始响应
- 原始帖子 JSON
- 下载图片
- 分类 prompt / 模型输出
- OCR prompt / 模型输出
- 抽取 prompt / 模型输出
- 归并 judge prompt / 模型输出

出了问题可以回看，不需要猜“模型为什么这么判”。

## 技术路线

### 采集层

- 复用 `MediaCrawler` 的小红书登录与搜索能力
- 自己实现抓取编排、存储、checkpoint 和水位控制
- `MediaCrawler` 作为外部依赖使用，不直接 vendoring 到这个公开仓库里
- 搜索关键词默认放在 [config/keywords.txt](./config/keywords.txt)
- 当前关键词覆盖 `ai agent / 智能体 / 多 agent / tool calling / rag / 面试 / 面经 / 凉经`

### 处理层

- 帖子分类：识别 `real_experience / ad / course_selling / irrelevant / question_collection / unclear`
- 广告识别除了看标题正文，还把作者昵称纳入判断
- 对昵称中出现 `大厂 / 面经 / offer / 上岸 / 求职 / 内推 / 辅导 / 陪跑 / 简历 / 刷题` 这类模式做高风险标记
- OCR 对每张图单独处理，再把 OCR 文本回灌到帖子级 `merged_text`
- 题目抽取输入为 `标题 + 正文 + OCR 文本`

### 归并层

- 标准化：`normalize_question`
- 精确判重：`fingerprint_text`
- 语义召回：`pgvector + embedding`
- 语义裁决：LLM judge
- 落库后维护：
  - `canonical_questions`
  - `question_aliases`
  - `post_question_links`

## 这次实际用到的模型

- `Qwen3-VL-4B-Instruct`
  - 帖子筛选 / 分类
  - 图片 OCR
- `Qwen3-VL-8B-Instruct`
  - 题目结构化抽取
  - 归并阶段的语义二判
- `Qwen3-Embedding-4B`
  - 题目 embedding
  - canonical question 相似召回

## 数据库设计

底层使用 `Postgres + pgvector`。

初始化 SQL 在 [sql/init.sql](./sql/init.sql)。

主要表分成 5 组：

### 抓取与进度

- `crawl_jobs`
- `crawl_job_pages`
- `crawl_keyword_checkpoints`
- `crawl_events`

### 原始帖子

- `raw_posts`
- `post_keyword_hits`
- `post_images`

### 内容处理

- `post_classifications`
- `post_ocr_results`
- `post_extractions`
- `extracted_questions`

### 题目归并

- `canonical_questions`
- `question_aliases`
- `post_question_links`

### 设计原则

- 垃圾帖打标签，不删数据
- 帖子只存一次
- 题目抽取和题目归并分层存
- 所有关键决策都可追溯到原帖、公司、岗位、阶段输出

## 产物长什么样

系统最终会产出两类东西：

### 1. 机器可消费报表

- `artifacts/reports/report_latest.json`
- 适合后续做统计、可视化、再加工

### 2. GitHub 可读题库

- [scripts/generate_kaomian_markdown.py](./scripts/generate_kaomian_markdown.py)
- 可以把报表渲染成 Markdown 题库
- 当前对应的题库成品在 [kaomian](./kaomian/)

也就是说，这个仓库负责“从原始数据烤到结构化结果”，`kaomian` 负责“把结果排版成适合人读的题库”。

## 项目结构

```text
.
├── config/
│   ├── keywords.txt               # 搜索关键词
│   └── prompts/                   # 分类 / OCR / 抽取 / 归并 prompt
├── scripts/
│   ├── run_daily_sync.sh          # 一键全流程
│   └── generate_kaomian_markdown.py
├── sql/
│   └── init.sql                   # Postgres + pgvector schema
├── src/ai_offer_catcher/
│   ├── crawler/                   # MediaCrawler 适配与抓取编排
│   ├── db/                        # DB 连接与仓储
│   ├── llm/                       # Qwen VL / Embedding 封装
│   ├── reports/                   # 报表导出
│   ├── stages/                    # classify / ocr / extract / merge
│   ├── app_settings.py
│   ├── cli.py
│   └── pipeline.py
├── tests/
└── kaomian/                       # 已生成的 Markdown 题库示例
```

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
playwright install chromium
```

另外需要你自己准备一份本地 `MediaCrawler` checkout，并在 `.env` 里把 `AI_OFFER_MEDIACRAWLER_ROOT` 指到那份目录。

### 2. 配置环境变量

```bash
cp .env.example .env
```

然后至少改这些项：

- `AI_OFFER_DB_DSN`
- `AI_OFFER_MEDIACRAWLER_ROOT`
- `AI_OFFER_CLASSIFY_MODEL_PATH`
- `AI_OFFER_OCR_MODEL_PATH`
- `AI_OFFER_EXTRACT_MODEL_PATH`
- `AI_OFFER_EMBED_MODEL_PATH`

如果你不配路径，程序默认会按“仓库根目录 + 相对路径”推断部分目录；但数据库和模型路径最好明确写。

### 3. 初始化数据库

```bash
ai-offer init-db
```

### 4. 先跑一个 smoke test

```bash
ai-offer pipeline run \
  --job-name smoke \
  --date-from 2025-01-20 \
  --max-pages 1 \
  --limit 20
```

### 5. 日常增量同步

```bash
ai-offer pipeline daily-sync --date-from 2025-01-20
```

或者直接：

```bash
scripts/run_daily_sync.sh
```

## CLI 命令

```bash
ai-offer init-db
ai-offer crawl-xhs --job-name xhs_backfill --date-from 2025-01-20 --max-pages 200
ai-offer classify-posts --limit 100
ai-offer ocr-images --limit 200
ai-offer extract-questions --limit 100
ai-offer merge-questions --limit 500
ai-offer report --format json
ai-offer pipeline run --job-name smoke --max-pages 1
ai-offer pipeline daily-sync --date-from 2025-01-20
```

## 公开仓库前的安全提示

这个项目本身可以公开，但你本地跑出来的运行产物不应该直接提交。

已经确认的高风险内容有：

- `.env`
  - 可能包含数据库地址、口令、模型路径
- `artifacts/crawl/**`
  - 包含小红书原始返回 JSON
  - 里面有大量 `xsec_token`
- `artifacts/login/**`
  - 可能包含登录二维码
- `MediaCrawler/browser_data/**`
  - 可能包含浏览器登录态 / 本地会话信息
- `.local_pg/**`
  - 本地数据库文件和日志

这些路径已经加入 [.gitignore](./.gitignore)，默认不建议提交。

## 现阶段限制

- 当前只做小红书
- 更偏离线批处理，不是在线服务
- 低置信度结果虽然会留痕，但暂时没有审核 UI
- 默认依赖本地 Hugging Face 模型和本地 Postgres

## 一句话总结

如果说普通面经是“别人记住了什么”，那 `bagu_killer` 做的是另一件事：

把一堆零散、含噪、带图、带营销包装的帖子，压成一套可追溯、可统计、可持续更新的 AI Agent 面试题数据库。
