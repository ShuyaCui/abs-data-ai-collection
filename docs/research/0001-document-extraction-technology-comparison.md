# PDF 文档信息抽取技术比较调研

调研日期：2026-08-21

## 结论摘要

当前任务不应选择一个“全能 PDF 项目”直接贯穿生产链路。可靠方案至少分成三个可替换层：

```text
PDF 字节
  ↓
可信文档解析：文本 / OCR / 版面 / 表格 / page / bbox
  ↓
字段抽取：42 字段契约 / 候选定位 / 结构化模型输出
  ↓
事实确认：确定性校验 / 证据反查 / 分析师复核
```

建议进入样例实测、但尚未正式选定的最小候选组合是：

1. **Docling**：原生文本 PDF、统一文档结构及 provenance 的底座候选。
2. **PaddleOCR PP-StructureV3**：中文扫描页、旋转页及复杂表格的 OCR 候选。
3. **MinerU**：中文复杂版面和跨页表格的对照候选。
4. **LangExtract 或 Instructor + Pydantic**：字段结构化抽取与原文引用的候选；不能代替 PDF 坐标解析。

不建议 MVP 同时引入 Unstructured、Marker、RAGFlow、Unstract、DocETL、Kafka 和 Ray Serve。它们分别有能力重叠、许可、产品边界或过度基础设施问题；只有样例基准或真实规模证明需要时再加入。

## 当前材料形成的约束

- 10 份 PDF，共 832 页。
- 8 份有可用文本层；2 份共 33 页为纯扫描，另有发行说明书首页需要 OCR fallback。
- 发行说明书共 708 页，是长文档吞吐和候选页定位的主要压力源。
- 4 份受托机构报告为同模板的时间序列文档，适合模板/规则复用。
- Excel 只有 42 个字段名，没有字段口径、实体粒度、答案或证据，当前不是验证集。
- 输出必须精确定位到报告名、页码、表格/段落，复核后才成为正式数据。

因此，所有页面统一 OCR、整本 PDF 送入大模型、让模型直接生成页码或以单个宽表覆盖历史值，都不适合本任务。

### 为什么原生文本页不直接交给 PaddleOCR

这里的选择不是“Docling 一定比 PaddleOCR 准”，而是避免重复识别已经存在的字符：

```text
原生文本页（约 96%）                 扫描页（约 4%）
PDF 内已有字符 + 字符坐标             PDF 内没有可信字符
        │                                  │
Docling / 原生解析                       PaddleOCR
保留原字、阅读顺序、页码和 bbox           识别文字、版面和表格
        │                                  │
复杂表格时可叠加 Paddle 的结构框           输出统一 BlockIndex
        └────────────────┬─────────────────┘
                         ↓
                  统一证据与字段抽取
```

把原生页先渲染成图片再 OCR，会新增数字、小数点、百分号和证券代码误识别机会，同时增加渲染、GPU 和延迟成本。复杂原生表格页仍可让 PaddleOCR 识别版面或单元格结构，但应优先把原生字符对齐到这些结构框，而不是用 OCR 文本覆盖原文。最终路由仍需由当前开发集实测决定。

### 原生文本可信度门控

门控按页执行，不按文件名或报告类型直接决定。MVP 不训练一个“可信度模型”，而是保存可解释诊断并按规则路由：

```text
原生解析
   ↓
硬失败：无/极少文字、乱码、坐标非法？ ──是──→ OCR
   │否
   ↓
文字层与页面图像、字符分布明显不一致？ ──是──→ 灰区双路解析
   │否
   ↓
复杂表格、跨栏或阅读顺序异常？ ──────是──→ 原文 + Paddle结构
   │否
   ↓
原生文本 PASS
```

每页至少记录以下诊断：

| 指标 | 检查内容 | 典型异常 | 路由作用 |
|---|---|---|---|
| `native_char_count` | 可打印字符数量 | 0 字或封面仅 1 字 | 极少文字且页面有明显内容时转 OCR |
| `bad_unicode_ratio` | `�`、控制符、私用区及不可打印字符比例 | 复制出来是乱码 | 超阈值直接转 OCR |
| `useful_char_ratio` | 中文、数字、拉丁字母及正常标点占比 | 大量无意义符号 | 低于阈值转 OCR/复核 |
| `bbox_valid_ratio` | 字符框是否非空、位于页面内 | 坐标越界、全部重叠 | 不能形成可靠证据时转 OCR |
| `duplicate_overlap_ratio` | 同一文字是否在近似坐标重复出现 | 隐藏文本层与可见文字叠加 | 灰区双路解析 |
| `image_area_ratio` | 大图覆盖页面的比例 | 扫描图覆盖整页但仅有少量隐藏文字 | 转 OCR |
| `reading_order_check` | 行内坐标、分栏与段落顺序是否合理 | 两栏文字交叉、表格逐列串行 | 走布局/表格结构解析 |
| `domain_token_check` | 金额、日期、百分号、证券代码等能否正常解析 | `1.32%` 变成 `I.32%` | 灰区 OCR 对照或人工复核 |

初始规则只设少数硬门槛，例如：`native_char_count < 20`、坏字符比例过高、绝大多数 bbox 非法，或大图覆盖整页但文字层极少。20–100 字、隐藏文本、复杂表格等灰区才运行 OCR 对照；不对全部文本页做双路处理。

灰区页的“双路一致性”重点比较领域敏感 token，而不是要求两份全文完全相同：

```text
原生结果：发行规模 13,200万元，利率 3.50%
OCR结果 ：发行规模 13,200万元，利率 3.50%
                           ↓
金额 / 日期 / 百分比 / 证券代码一致 → 保留原生文本

原生结果：发行规模 13,200万元
OCR结果 ：发行规模 18,200万元
                           ↓
关键 token 冲突 → 不自动通过，进入复核
```

阈值必须用当前 832 页开发集标定，并在独立验证集冻结，不能凭经验值直接作为生产标准。文档类型和历史模板只可调整“优先检查哪些区域”，不得绕过逐页质量门控。

## 开源解析与 OCR 项目比较

Stars 是 2026-08-21 的近似快照，只表示社区热度，不表示本项目准确率。

| 项目 | Stars / 许可 | 主要优势 | 关键缺口或风险 | 本项目定位 |
|---|---:|---|---|---|
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | 约88k / Apache-2.0 | 中文优先；方向与去扭曲；PP-StructureV3 提供版面、文本及表格单元格坐标；CPU/GPU/ONNX/服务部署 | 组件和模型组合较多；官方综合 benchmark 不能替代金融样例实测 | **扫描页/OCR/表格主候选** |
| [MinerU](https://github.com/opendatalab/MinerU) | 约78.1k / 带附加条件的 MinerU License | 中文、扫描、复杂版面、跨页表格；Markdown/JSON；bbox；CPU/GPU、API、Router、多 GPU | 系统较重；许可含商业门槛和在线服务标识义务 | **复杂解析对照候选** |
| [Docling](https://github.com/docling-project/docling) | 约65.3k / MIT，模型另核 | 统一 `DoclingDocument`；页码、bbox、char span 和 provenance；本地隔离网；异步 API 和 Redis worker | 未见中文不良资产证券专项基准；内置信息抽取按页返回字段，但不直接保证字段值 bbox | **原生文本与证据底座候选** |
| [Marker](https://github.com/datalab-to/marker) | 约38.9k / 代码 Apache-2.0，模型权重另有限制 | 选择性 OCR、版面、表格、JSON block/polygon；速度设计较好 | 模型权重存在企业商用限制；自带 server 官方定位为小规模 | 仅在法务批准后做精度对照 |
| [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) + [Tesseract](https://github.com/tesseract-ocr/tesseract) | 约33.7k + 75.4k / MPL-2.0 + Apache-2.0 | 旋转、deskew、中文语言包、搜索文本层；CPU 简单稳定；可输出 hOCR/TSV 坐标 | 不理解表格语义；复杂中文扫描件准确率上限较低 | OCR 预处理与 CPU 成本基线 |
| [Unstructured](https://github.com/Unstructured-IO/unstructured) | 约15.3k / Apache-2.0 | 多格式 ETL、连接器、fast/ocr_only/hi_res 路由、Element 输出 | 中文质量缺少可靠证据；完整生产平台和 OSS 库边界不同；不是42字段抽取器 | 暂不进入最小 PoC |
| [PyMuPDF4LLM](https://github.com/pymupdf/pymupdf4llm) | 约2.1k / AGPL-3.0 或商业许可 | 原生 PDF 速度、bbox、表格和混合 OCR 接口 | 闭源生产需 AGPL/商业许可评估；无分布式任务能力 | 性能基线，不作为默认依赖 |

### 关键证据能力

- Docling 的 [DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/) 保存结构、bbox 和 provenance；其 `ProvenanceItem` 包含 `page_no`、`bbox` 和 `charspan`。
- MinerU 的 [输出格式](https://opendatalab.github.io/MinerU/reference/output_files/)按页输出 block，并提供 bbox；开发版公共格式仍明确标注可能变化，生产应做内部格式归一化。
- PaddleOCR 的 [PP-StructureV3](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md)提供版面框、文字框、表格单元格框、单元格文字和置信度；官方仓库还提供并行推理及多种硬件后端。
- Unstructured 的开源库主要输出文档 Element；其商业 Platform 的能力不能直接当作开源自部署能力。

### 许可判断

- Docling 核心代码为 MIT，但选用的 OCR 或模型权重需要单独核对。
- PaddleOCR 为 Apache-2.0，当前候选中企业生产许可最清晰。
- [MinerU 当前许可](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)不是标准 Apache-2.0：达到特定 MAU/月收入门槛需要额外商业许可，向第三方提供在线服务还有标识要求。
- Marker 的代码和模型权重采用不同许可，不能只看仓库代码许可证。
- PyMuPDF/PyMuPDF4LLM 是 AGPL/商业双许可，闭源服务必须经过法务判断。

## 结构化字段抽取项目比较

| 方案 | Stars / 许可 | 能解决什么 | 不能解决什么 | 判断 |
|---|---:|---|---|---|
| [LangExtract](https://github.com/google/langextract) | 约38.5k / Apache-2.0 | 长文本切分、并行多轮抽取、字段回到原文字符区间、交互式高亮、本地/云模型 provider | 不解析 PDF 版面；字符区间必须映射到解析层 bbox；引用存在不代表字段正确 | **强候选：原文 grounding** |
| [Instructor](https://github.com/567-labs/instructor) | 约13.7k / MIT | Pydantic schema、验证失败重试、异步、多模型 provider、引用子串辅助 | 不是 PDF 解析器或任务队列；引用校验不等于事实正确 | **强候选：MVP 模型适配** |
| [Outlines](https://github.com/dottxt-ai/outlines) | 约15k / Apache-2.0 | 本地模型的 JSON/Pydantic/regex/grammar 约束解码，支持 vLLM 等 | 只保证格式，不保证值或证据正确 | 私有模型阶段再评估 |
| [Guardrails](https://github.com/guardrails-ai/guardrails) | 约7k / Apache-2.0 | 可插拔输入输出 validator | 与 Pydantic 和少量确定性校验重叠；增加运行与依赖复杂度 | MVP 不引入 |
| [DocETL](https://github.com/ucbepic/docetl) | 约4k / MIT | 文档 map/reduce、并行处理、提示与计划优化 | 不提供 PDF bbox 证据；无独立验证集时无法证明“优化”有效 | 未来离线实验工具 |
| [Unstract](https://github.com/Zipstack/unstract) | 约6.6k / AGPL-3.0 | 提示式抽取、API/ETL、provider 连接；产品包含 HITL 能力 | 复核、SSO等部分能力属于企业产品；AGPL；整体平台偏重 | 参考交互，不作为核心底座 |

[LangExtract 官方仓库](https://github.com/google/langextract)明确支持精确原文定位、长文档切分、并行处理及本地 Ollama provider；但其 grounding 是字符区间。PDF 页码、表名和 bbox 仍必须来自前置解析层。

结构化输出只保证 JSON 形状合法，不保证金额、日期或证券代码正确。金融关键字段仍需 exact quote、类型/单位校验、勾稽关系和人工复核。

## 证据契约建议

模型不得直接生成页码、bbox、表名或段落编号。解析层先产生不可变的 block/cell 索引，模型只选择 ID：

```text
可信 BlockIndex
├─ doc_hash
├─ block_id / cell_id
├─ physical_page / printed_page
├─ section
├─ table / row / column / paragraph
├─ exact_text
└─ bbox
        ↓
模型输出
├─ field_id
├─ value_raw / normalized_value / unit
├─ entity_key / as_of_date
├─ evidence.block_id / cell_id
└─ exact_quote
        ↓
服务端反查与验证
├─ ID 属于当前 doc_hash
├─ quote 是对应 block 的原文子串
├─ 关键值可由 quote 确定性归一化
├─ 类型 / 单位 / 范围正确
└─ 跨字段勾稽关系成立
```

模型自报置信度不应直接作为自动通过依据。可操作的质量分数应由证据精确匹配、确定性校验、来源优先级、多来源一致性和历史模板表现共同计算。

### 证据 ID 的具体例子

假设本地解析层从《簿记建档发行结果公告》第 3 页的“发行结果”表得到：

```json
{
  "cell_id": "doc_a-p003-t01-r04-c03",
  "document_name": "簿记建档发行结果公告.pdf",
  "physical_page": 3,
  "table": "发行结果",
  "row": "优先档",
  "column": "实际发行额",
  "exact_text": "13,200万元",
  "bbox": [356, 412, 468, 438]
}
```

模型只允许返回业务判断和已给出的证据 ID：

```json
{
  "field_id": "issue_amount_tranche",
  "normalized_value": 1.32,
  "unit": "亿元",
  "evidence_id": "doc_a-p003-t01-r04-c03",
  "exact_quote": "13,200万元"
}
```

服务端随后反查该 ID，验证它属于当前文档、引用是原文子串、`13,200万元 = 1.32亿元`，并从索引补齐报告名、页码、表名、行列和 bbox。这样模型负责“这个单元格对应哪个字段”，程序负责“证据在哪里且是否可验证”；模型无法只靠编造一个页码通过校验。

## 大模型技术比较

以下为 2026-08-21 的官方能力快照。旗舰型号用于说明各家能力上限；“本项目候选”才是局部字段抽取应优先测试的型号。供应商声称的通用 benchmark 不能替代本项目字段级验证集。

| 厂商 | 最新旗舰 | 本项目优先候选 | 结构化输出 | 多模态 | 批处理/并发 | 私有化边界 | 判断 |
|---|---|---|---|---|---|---|---|
| Qwen | `qwen3.8-max`，1M 上下文 | **`qwen3.7-plus-2026-05-26` 非思考**；规模化再挑战 `qwen3.7-flash-2026-07-15` | Plus 和 Max 在官方严格 JSON Schema 清单内；Flash 需本地校验 | 三者均支持图文；但默认仍只发必要片段 | Plus/Flash 支持 Batch；北京区 alias 公开额度 30k RPM / 5M TPM | 有 Qwen3.8 开放权重；本项目应先评测 27B，不自托管 2.4T 旗舰；许可证逐权重核验 | **首选**：schema、中文、多模态、Batch 和迁移路径最均衡 |
| DeepSeek | `deepseek-v4-pro`，1M 上下文 | **`deepseek-v4-flash` 非思考**；疑难升级 Pro | JSON Object；严格 tool schema 仍为 Beta，必须本地 schema 校验和重试 | 托管 V4 API 未文档化图像/PDF输入 | Flash 官方并发 2,500、Pro 500；未见托管 Batch API | V4 有开放权重，但 Flash 284B、Pro 1.6T，私有化仍很重 | **文本性价比候选**：便宜、高并发，但证据契约要由本地校验兜底 |
| Kimi | `kimi-k3`，1M、原生多模态 | **`kimi-k2.6` 非思考**；疑难升级 K3 | K3 支持严格 JSON Schema；K2.6 宜采用扁平 schema | K2.6/K3 支持图像；不要上传整份 PDF 到 file-extract | K2.6 支持 Batch；K3 不支持；实时并发按账户档位 | K3/K2.5 开放权重但为巨型 MoE；K3 采用专用许可，私有化门槛高 | **强备选**：严格 schema 和视觉好，K3 默认全量调用过重 |
| GLM | `glm-5.2`，1M 上下文 | `glm-5.2` 非思考仅作对照 | 官方支持 JSON/Schema 验证 | GLM-5.2 为文本模型；视觉需另用 GLM-5V | 有 Batch 产品，但当前公开 Batch 支持表未列 GLM-5.2；实时并发取决于账号并可申请 | GLM-5.2 开放权重约 744B，官方本地部署需要多卡高显存集群 | **对照候选**：长程 Agent 能力强，但对局部字段抽取偏重，批量能力需商务核实 |

### 模型选型建议

MVP 默认选择 **`qwen3.7-plus-2026-05-26`、关闭思考、严格 JSON Schema**。它不依赖把整本 708 页说明书送进模型；输入仅是本地检索出的 block/cell 文本及必要页面裁剪。困难字段才升级 `qwen3.8-max`。

形成独立金标后，用同一输入、schema 和提示词让 `qwen3.7-flash`、`deepseek-v4-flash`、`kimi-k2.6` 和 `glm-5.2` 做一次盲测。若 Flash 达到相同验收线，则让 Flash 成为规模化默认通道，Plus 只处理校验失败或多来源冲突。没有验证集前，不宣称任何厂商达到 97%/99.5%。

供应商解耦点固定在内部 `ExtractionRequest` / `ExtractionFact` 契约：模型只能接收候选证据并返回字段值、单位和 `evidence_id`；模型名称、API 格式、思考参数和重试规则由 adapter 处理。无需为每家重写 PDF 解析、证据索引、校验、复核或验收集。

### 锁定模型前的盲测计划（已确认）

1. 先冻结独立验证集、42 字段契约、证据格式和验收脚本；开发集不得混入最终验收分数。
2. 对 `qwen3.7-plus`、`deepseek-v4-flash`、`kimi-k2.6`、`glm-5.2` 使用完全相同的候选片段、扁平 Schema、非思考配置和最大重试次数。
3. 分别记录字段精确正确率、证据定位正确率、空值误填率、人工复核率、P50/P95 延迟、失败率及单文档成本。
4. 先按关键字段门槛淘汰不合格模型，再比较成本和吞吐；不得用平均分掩盖证券代码、金额、日期等关键字段错误。
5. 对默认模型的失败样本评测旗舰升级路径，决定“廉价默认模型 → 强模型复核 → 人工复核”的级联策略。
6. 只有盲测和目标并发压测均通过，才锁定生产默认模型；保留供应商无关契约以支持后续替换。

官方资料：

- Qwen：[模型选择](https://help.aliyun.com/zh/model-studio/text-generation-model)、[结构化输出](https://help.aliyun.com/zh/model-studio/qwen-structured-output)、[Batch](https://help.aliyun.com/zh/model-studio/batch-inference)、[价格](https://help.aliyun.com/zh/model-studio/model-pricing)、[限流](https://help.aliyun.com/zh/model-studio/rate-limit)、[Qwen3.8 开放权重](https://github.com/QwenLM/Qwen3.8)。
- DeepSeek：[V4 定价与功能](https://api-docs.deepseek.com/quick_start/pricing/)、[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)、[并发限制](https://api-docs.deepseek.com/quick_start/rate_limit/)、[更新日志](https://api-docs.deepseek.com/updates/)。
- Kimi：[模型列表](https://platform.kimi.ai/docs/models)、[结构化输出](https://platform.kimi.ai/docs/guide/response_format)、[Batch](https://platform.kimi.ai/docs/guide/use-batch-api)、[K3 开放权重](https://github.com/MoonshotAI/Kimi-K3)。
- GLM：[GLM-5.2](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.2)、[结构化输出](https://docs.bigmodel.cn/cn/guide/capabilities/struct-output)、[Batch](https://docs.bigmodel.cn/cn/guide/tools/batch)、[开放权重与部署](https://github.com/zai-org/GLM-5)。

## 公共 benchmark 能说明什么

[OmniDocBench](https://github.com/opendatalab/OmniDocBench)覆盖金融报告、表格、文字、公式和阅读顺序，适合了解通用文档解析能力；其 v1.6 页面包含最新解析/VLM 项目的统一指标。

但公开 benchmark 不能回答本项目最重要的问题：

- “发行总额—本级”是否绑定了正确分层证券；
- “最新余额”是否绑定正确报告日期；
- 表格跨页后行列是否仍与字段口径一致；
- 42 字段值能否回到正确报告、表格和段落；
- 多来源冲突时是否选出正确当前值。

因此，官方榜单只能用于筛选候选，不能用于最终选型。

## 三档规模的工作量投影

以下仅把当前样例的平均 83.2 页/文档、约 4% 扫描页比例外推，用于揭示量级，不是硬件 sizing：

| SLA 档位 | 文档吞吐 | 总页吞吐 | 文本页吞吐 | OCR 页吞吐 |
|---|---:|---:|---:|---:|
| 1,000 份 / 30 分钟 | 0.56 doc/s | 46 page/s | 44 page/s | 1.8 page/s |
| 10,000 份 / 2 小时 | 1.39 doc/s | 116 page/s | 111 page/s | 4.6 page/s |
| 1,000,000 份 / 24 小时 | 11.57 doc/s | 963 page/s | 925 page/s | 38.2 page/s |

真正昂贵的通常是 `model_fragment`。候选页定位必须把708页说明书压缩为少量相关表/段落后才调用模型，否则三档成本都会失控。

### 基础设施取舍

- 1,000/30分钟及10,000/2小时：Python 任务队列、独立 text/OCR/model worker、PostgreSQL、对象存储和 Kubernetes HPA 足够；不需要 Kafka。
- 1,000,000/24小时历史回灌：使用对象存储 manifest + Kubernetes Indexed Jobs 或等价批任务分片；不要把约8,300万页全部拆成 broker 消息。
- Ray Serve 只在私有 GPU 模型确实需要动态 batching/自动扩缩时使用；不能替代可靠任务队列。
- Kafka 只在需要多消费方、长期事件回放、上游已是 Kafka 或必须保持分区顺序时引入，不能因为“百万文档”自动引入。

节点和 GPU 数量必须由样例实测得到：

```text
replicas = ceil(目标阶段吞吐 × 单任务服务时间 / 目标利用率)
```

在没有各阶段 P50/P95 和每页显存/内存数据前，直接给固定 GPU 数属于虚假精确。

## 没有验证集时的最小可行处理

当前产品应被定义为开发集，而不是验证集：

1. 由业务负责人确认42字段的值、空值语义、实体粒度和证据位置。
2. 从33个扫描页中选约10页，覆盖旋转、密集文字、横表、无线表和低清晰度，标注文字与单元格位置。
3. 在相同输入上运行候选组合，不调参地保留初次结果；之后允许基于开发集调整。
4. 后续每收到一个新产品，先 shadow extraction，再由分析师确认，逐步形成 prospective gold set。
5. 在出现独立产品前，只能声称“当前产品流程跑通”，不能声称同类产品准确率达到97%或99.5%。

## 建议的最小实测矩阵

不要把所有项目两两组合。先测试三条路径：

| 路径 | 文本页 | 扫描/复杂页 | 字段抽取 | 目的 |
|---|---|---|---|---|
| A | Docling | PaddleOCR PP-StructureV3 | LangExtract 或 Instructor | 平衡许可、证据和中文 OCR 的主候选 |
| B | Docling | MinerU | 同 A | 比较跨页表格与复杂扫描质量 |
| C | 原生快速解析基线 | OCRmyPDF/Tesseract | 同 A | 测定最低成本和最高吞吐基线 |

统一记录：

- 42字段精确匹配率与缺失率；
- 关键字段零容忍错误数；
- 表格单元格准确率和跨页表恢复率；
- 证据报告/页码/表段/bbox准确率；
- 文本页、OCR页、模型片段各自 P50/P95；
- 峰值 CPU、GPU、内存及每千页成本；
- 同一输入重复运行的一致性；
- 失败是否可诊断、可重试且不产生重复事实。

只有这轮实测完成，才有足够依据决定 Q14 的具体抽取组合。
