# Third-Party Notices

`bagu_killer` 使用或集成了第三方项目与组件。它们各自的版权与许可证归原作者所有。

## MediaCrawler

- Project: `MediaCrawler`
- Upstream: https://github.com/NanmiCoder/MediaCrawler
- Role in this project:
  - 提供小红书登录、浏览器上下文复用、搜索与详情抓取能力
  - `bagu_killer` 在其基础上实现了自己的抓取编排、checkpoint、数据库落库、OCR、抽取、归并和报表流水线
- Integration model:
  - 本仓库不直接 vendoring `MediaCrawler` 源码
  - 运行时通过 `AI_OFFER_MEDIACRAWLER_ROOT` 指向本地 `MediaCrawler` checkout

### Reported upstream license

根据本地 `MediaCrawler/LICENSE`，其许可证声明为：

- `NON-COMMERCIAL LEARNING LICENSE 1.1`

并包含至少以下约束方向：

- 仅限非商业学习与研究用途
- 不应用于大规模爬虫或干扰平台运营的行为
- 需要在合理显著位置保留版权声明和许可证声明

本文件不替代上游许可证文本，也不对上游许可证做法律解释。若你实际使用本项目的小红书抓取能力，请自行阅读并遵守上游许可证与平台规则。

## Model dependencies

本项目的处理流水线可接本地大模型，包括但不限于：

- `Qwen3-VL-4B-Instruct`
- `Qwen3-VL-8B-Instruct`
- `Qwen3-Embedding-4B`

这些模型的权利与许可证不属于本项目。使用者应自行确认对应模型的许可证、使用限制与分发条件。
