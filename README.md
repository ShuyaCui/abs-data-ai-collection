# 不良资产证券化 PDF 证据抽取

面向中国不良资产证券化（NPL ABS）披露文件的可追溯字段抽取 Demo。它将支持范围内的 PDF 转为带页码、原文和证据定位的候选事实，供业务人员复核后导出到 42 字段 Excel 模板。

## 能做什么

- 校验本地 PDF，并保存可复用的解析与证据工件。
- 从已支持的发行公告、发行结果公告、发行说明书、评级报告和受托报告中抽取确定性字段。
- 按产品批量处理文件夹，生成候选 Excel、候选 JSONL 与批次清单。
- 生成离线复核页面，并将人工 `accept`、`correct`、`reject` 决定作为不可变记录保存。

```mermaid
flowchart LR
  PDF[披露 PDF] --> Extract[解析与字段抽取]
  Extract --> Evidence[候选事实与证据]
  Evidence --> Review[人工复核]
  Review --> Export[42 字段 Excel]
```

## 处理原则与边界

- 候选事实不是正式数据：业务复核决定才会生成已确认事实。
- 每个披露值必须绑定报告名、页码、表格或段落和原文证据；派生值保留规则版本与输入事实。
- 不支持、歧义、未披露或待定义的字段不会被静默填入结果。
- 这是受限文档类型和字段的 Demo，不宣称通用 PDF 理解、自动确认或生产级准确率。

## 快速开始

需要 Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)。安装基础、Excel 导出和测试依赖：

```bash
uv sync --extra export --extra dev
```

将同一产品的 PDF 放在一个输入目录，准备 42 字段 Excel 模板后运行：

```bash
uv run npl-extract extract-folder ./data/input \
  --product-key product:demo \
  --product-name "经业务确认的产品展示名" \
  --template ./data/42字段模板.xlsx \
  --output ./output/candidates.xlsx \
  --runs-dir ./runs
```

该命令同时写出 `candidates.xlsx`、`candidates.jsonl` 和 `candidates.manifest.json`。输出 Excel 必须位于输入 PDF 目录之外。

生成离线复核页面：

```bash
uv run npl-extract review-page \
  --facts ./output/candidates.jsonl \
  --fields config/fields.v1.json \
  --output ./output/review.html
```

页面只导出复核草稿；正式决定使用 `npl-extract review` 写入不可变 `ReviewDecision`。完整操作见[人工校验手册](docs/manual-human-validation.md)。

## 开发

运行测试：

```bash
uv run --extra dev --extra export pytest -q
```

核心代码位于 `src/npl_extract/`：`cli.py` 提供命令行入口，`contracts.py` 定义事实与复核契约，`pipeline.py` 负责工件持久化。

## 文档

- [方案总览](docs/2026-08-28-abs-data-ai-collection-feasibility-and-production-plan-overview.md)：面向业务与评审的能力、边界与演进方向。
- [完整方案](docs/2026-08-28-abs-data-ai-collection-feasibility-and-production-plan-complete.md)：可行性、MVP 与生产化设计依据。
- [人工校验手册](docs/manual-human-validation.md)：批处理、证据复核和正式 `ReviewDecision` 的操作说明。
- [字段契约](config/fields.v1.json)：42 个字段的粒度、类型、状态与证据要求。
- [技术调研](docs/research/)：工程依据和可复现验收记录。

原始 PDF、运行工件、Excel 和缓存应保存在 `data/` 或 `runs/`，不提交至 `docs/`。
