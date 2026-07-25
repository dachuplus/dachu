# 数据模型与评分来源规则（DATA MODEL RULES）

> 本文件是 dachu 数据层的**权威规则文档**。每日自动更新（GitHub Actions `update-fund-data.yml`）
> 与所有数据脚本**必须**遵守以下规则。任何改动不得违反。

---

## 核心规则（必读）

### 规则 1 —— 靠谱指数页面数据来自 `fund_scores`

- 网站「靠谱指数」页面（FundRankPage）展示的所有评分、分类、收益、回撤、夏普数据，
  **唯一真实数据源是 `fund_scores` 表**。
- 前端（`src/api/fund-api.js` 等）只读取 `fund_scores`，**不得**直接读取
  `fund_combined` 或 `fund_quarterly_scores` 作为评分来源。

### 规则 2 —— `fund_scores` 的评分是**独立**的，不依赖 `fund_quarterly_scores`

- `fund_scores` 的评分（`k0w / k1m / k3m / k6m / k1 / k2 / k3 / k5 / k_all / score_grade`）
  **完全由 `import_via_rest.py` 在每日更新中计算**，算法为：
  - 以日历对齐的阶段收益 / 回撤 / 夏普（`r1y/dd1y/sr1y`、`r2y/dd2y/sr2y`、…）为输入；
  - 做**全市场横截面百分位排名**（收益 50% + 回撤 25% + 夏普 25%）；
  - 再按 v7 权重合成 `k_all`。
- **`fund_scores` 的计算过程不得引用 `fund_quarterly_scores` 的任何列。**
  两者是两套互相独立的评分引擎，禁止耦合。
- 实现保障：在 `import_via_rest.py` 顶部已加注释护栏，明确其评分来源仅为
  `funds_output.ndjson` / `risk_indicators.ndjson` 等基础数据，**不读** `fund_quarterly_scores`。

### 规则 3 —— `fund_combined` 的评分**基于 `fund_quarterly_scores`** 计算

- `fund_combined` 是「合并表」（分类 + 评分 + 详情），其中**评分列应来自于
  `fund_quarterly_scores`（季度引擎）**，而不是从 `fund_scores` 复制。
- 字段映射（`fund_quarterly_scores` → `fund_combined`）：

  | fund_quarterly_scores | fund_combined | 说明 |
  |---|---|---|
  | `score_3m`  | `k3m`  | 近 3 个月 |
  | `score_6m`  | `k6m`  | 近 6 个月 |
  | `score_1y`  | `k1`   | 近 1 年 |
  | `score_2y`  | `k2`   | 近 2 年 |
  | `score_3y`  | `k3`   | 近 3 年 |
  | `score_5y`  | `k5`   | 近 5 年 |

- `k_all` 由上述各周期分按 v7 权重（k0w 5 / k1m 5 / k3m 10 / k6m 15 / k1 20 / k2 20 / k3 15 / k5 10）
  重算；`score_grade` 由 `k_all` 全市场百分位重算（≥80% 绿 / ≥50% 蓝 / 其余 橙）。
- **已知例外（已在 `sync_fund_combined_scores.py` 中 documented）**：
  `fund_quarterly_scores` 不提供「成立以来」(`k0w`) 与「1 个月」(`k1m`) 窗口，
  这两个周期在 `fund_combined` 中沿用 `fund_scores` 的对应值。该例外属设计取舍，
  后续若季度引擎扩展窗口可移除。
- **优雅降级**：当某只基金在 `fund_quarterly_scores` 中缺失对应评分时，
  `sync_fund_combined_scores.py` 自动回退到 `fund_combined` 现有值（即上一次同步值），
  保证评分列**永远不为 NULL**。
- 实现保障：`sync_fund_combined_scores.py` 主流程改为 `UPDATE fund_combined ... FROM fund_quarterly_scores`，
  而非原先的 `FROM fund_scores`。

---

## 每日自动更新如何遵守本规则

`scripts/update-fund-data.yml`（GitHub Actions，北京时间 21:30）的评分相关步骤：

1. `fetch_and_import_funds.py --output-only`
   → 拉取基础数据（收益 / 规模 / 分类），输出 NDJSON。
2. `fetch_risk_indicators.py` / `fetch_tsdata_risk.py` / `fetch_return_all.py` / `fetch_fund_basic_info.py`
   → 补充回撤 / 夏普 / 成立以来收益 / 基金经理等。
3. **`compute_quarterly_scores.py`（新增，continue-on-error）**
   → 刷新 `fund_quarterly_scores`（季度引擎评分），为规则 3 提供最新数据源。
   ⚠️ 该步骤联网抓取净值，若被限流失败，**不阻断**整体流程，下一轮继续补齐。
4. `import_via_rest.py --staging`
   → 计算 `fund_scores` 独立评分（规则 2），写入 `fund_scores_staging`。
5. `promote_staging.py`
   → 校验 `fund_scores_staging` → 原子切换生产 `fund_scores`（规则 1/2）；
   → 调用 `sync_fund_combined_scores.py` 重建 `fund_combined`（规则 3，从 `fund_quarterly_scores` 派生）。

**任何提交到仓库的脚本改动，都必须保证上述「fund_scores 独立、fund_combined 来自 fund_quarterly_scores」
的依赖方向不被破坏。**

---

## 三张核心表职责一览

| 表 | 职责 | 评分来源 | 谁写 |
|---|---|---|---|
| `fund_scores` | 靠谱指数页面真实数据源 | **独立引擎**（日历对齐百分位） | `import_via_rest.py` |
| `fund_quarterly_scores` | 季度引擎评分（fund_combined 的来源） | 自算（季度窗口年化） | `compute_quarterly_scores.py` |
| `fund_combined` | 合并表（下载 / 数据中心） | **来自 `fund_quarterly_scores`** | `sync_fund_combined_scores.py` |

> 注意：`fund_scores` 与 `fund_combined` 的评分**算法不同、数值不同**，这是预期行为，
> 不应强行让两者一致。如需一致，应修改规则本身而非破坏依赖方向。
