# Automation-2 Memory: 靠谱指数每日全量更新

## 执行历史

### 2026-06-14 (首次)
- Step1: full_fund_update.py 成功，19,684条基金，有靠谱分12,864只，耗时约60s
- Step2: bulk_patch.cjs 成功创建并运行，✓19,676 / ✗8 / 共19,684，耗时458s，QPS=42.9
- 失败原因：8条因 ECONNRESET/timeout 失败，占比0.04%，可忽略
- 分级分布：金884 橙5154 青8230 灰5416
- 净值日期：2026-06-12
- 注意：bulk_patch.cjs 是新创建的脚本，使用 Node.js https + IPv6 (family:6) 并发 PATCH

## 踩坑记录
- bulk_patch.cjs 原路径指向 allfund/scripts/，但文件不存在，需从 asset-config-miniapp/scripts/funds_full.ndjson 读取数据
- IPv6 family:6 连接 Supabase REST API 工作正常
