# 发行说明书预测回收切片与审查去重设计

## 目标

补齐《发行说明书》p102–104 的确定性预测回收切片，并消除代码审查发现的三处重复逻辑。范围仅限字段 36、37、38 与对应的批处理路径。

## 设计

### 预测回收切片

- 在 `extract.py` 增加 `extract_prospectus_recovery_prediction_facts`。
- 仅接受已安全准入、唯一绑定到产品的《发行说明书》，以及物理页 102–104 且 `ocr_requested=False` 的原生 block；不调用模型或外部服务。批处理中的 `ambiguous`、`rejected` 或 `failed` 文档不得进入本切片。
- 字段 36/37 仅在“中债资信”标签、预计回收金额、预计回收率和“采用中债资信预测的回收情况”关系同时唯一成立时产生。
- 同值同单位的中债披露可增加 evidence；不同值、不同单位、额外同结构行、机构无法绑定或采用关系缺失时，字段 36/37 fail closed。
- 字段 38 从明确出现的机构名按文档顺序去重，输出 `string[]`；它不依赖采用关系。

### 批处理与来源优先级

- `extract-folder` 为发行说明书新增 p102–104 的 `pypdf` 解析范围。
- 批处理先处理评级报告，再处理发行说明书；若已存在评级报告来源的字段 36 或 37，则丢弃本切片的同字段候选，确保 prospectus 不覆盖 `rating_reports`。
- 单文件 `extract` 仍可输出发行说明书字段 36–38 候选；跨文档优先级只由 folder batch 执行。

### 审查去重

- 在 CLI 复用 `--native-parser` 选项声明。
- 在 Harness bridge 以一个最小 helper 统一 evidence 的字符上限校验与截断。
- 在 Harness bridge 以一个最小 helper 统一 content-addressed fact artifact 的读取与按 ID 查找；保留 `validate_facts` 的歧义检查。

## 验收

- 测试覆盖成功、缺采用关系、冲突中债值、跨页同值同单位交叉印证、OCR 页/页码边界拒绝、字段 38 无采用关系，以及字段 36/37 的批处理来源优先级。
- 每个输出断言产品粒度、`disclosed` 状态、精确值、单位与完整 parser-owned evidence-ID 集。
- 现有离线回归套件保持通过。

## 不做

- 不实现通用来源选择器、全文发现/router、其余 42 字段或任何 Agent loop。
- 不修改当前生产方案 A。
