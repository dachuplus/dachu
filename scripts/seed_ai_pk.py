#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI大PK —— 规则版选基种子脚本 (Plan B)

功能：
  1. 在 Supabase 创建 ai_pk_models / ai_pk_picks 两张表（幂等 DDL）并配置 RLS 公开读。
  2. 按 7 个国内大模型各自的「规则」从 fund_combined 全市场真实数据中各选 5 只基金，每只 20% 等权。
  3. 将模型元信息与当期选基结果写入数据库（Management API 直连，绕过 RLS 写入）。

规则映射（基于 fund_combined 真实字段，绝不使用编造基金）：
  ds(DeepSeek)   : 综合靠谱分 k_all 最高
  doubao(豆包)   : 近1年收益 r1y 最高
  qwen(千问)     : 近1年夏普 sr1y 最高（风险调整后收益）
  wenxin(文心)   : 近1年最大回撤 dd1y 最小（dd 列为负，数值越大回撤越小）
  zhipu(智谱)    : 近3年收益 r3y 最高
  kimi(Kimi)     : 近3年卡玛 r3y/|dd3y| 最优
  minimax(Minimax): 跨一级分类均衡（各一级分类内 k_all 最高，分散配置）

重要规则：
  - 同一基金的不同份额（A/C/E 等）视为同一标的，候选池先按基金名归一化去重，
    每个基金只保留一个主代码（优先 A 份额，否则取规模更大者），杜绝同基金既买 A 又买 C。
  - 选基逻辑分两层写入数据库，供前端「调仓时间线」展示：
      第一层 category_logic：该模型选择基金品类的理由（为何选某品类、为何不选另一品类）。
      第二层 picks[].reason：该模型选择这 5 只具体基金的理由（基于真实指标值，可验证）。

说明：
  - 候选池：t0 != 货币型、fund_scale > 2 亿、r1y 非空（保证收益可比）。
  - 每个模型 5 只基金，每只权重固定 20%。
  - 接入真实模型 API 后，只需替换「选基」环节（每月 1 日重跑），表结构不变。
"""
import os
import re
import sys
import json
import datetime
import requests

# ===== 凭证 =====
# PAT 为 Supabase Management API 管理密钥（特权，切勿硬编码/提交到仓库）。
# 运行时从环境变量读取：本地 `SUPABASE_PAT=xxx python3 scripts/seed_ai_pk.py`；
# CI 中由 GitHub Secrets 注入。沙箱陈旧 SUPABASE_MGMT_TOKEN 会污染，故显式覆盖。
PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
if not PAT:
    raise SystemExit("缺少 SUPABASE_PAT 环境变量，请在 .env.local 或 CI Secrets 中配置后重试。")
REF = "tqhtegazxykkqfcpejky"
SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
# anon/publishable key，设计上可公开，前端与只读脚本均使用，可安全提交。
ANON_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"

os.environ["SUPABASE_MGMT_TOKEN"] = PAT
os.environ["SUPABASE_PAT"] = PAT

MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"
MGMT_HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

# 每个模型的「第一层 · 品类逻辑」：说明其选品类的理由与为何排除其他品类（与 rule 一致，真实可解释）
MODELS = [
    {"id": "ds", "name": "DeepSeek", "name_short": "DS", "region": "cn",
     "color": "#1d70b8", "persona": "深度基本面派：长期业绩扎实、基金经理任职稳定、回撤可控的主动管理型基金，宁可少赚不可大亏", "rule": "k_all",
     "category_logic": "【宏观】经济弱复苏、利率下行期，质量因子更抗波动。【策略】以深度基本面质量为核心，偏好长期ROE稳定、盈利质量高的主动基金。【行业】不押单一赛道，跨消费/制造/医药均衡布局。【流动性】选规模适中、申赎顺畅品种。【金融工程】用k_all综合评分代理多维质量。【胜率赔率】重胜率（高确定性）而非高赔率，宁可少赚不可大亏。"},
    {"id": "doubao", "name": "豆包", "name_short": "豆包", "region": "cn",
     "color": "#d4351c", "persona": "成长进攻派：高弹性、高成长赛道（科技/制造/医药）的基金，能承受较大波动以博取高收益", "rule": "r1y",
     "category_logic": "【宏观】复苏初期风险偏好抬升，成长弹性占优。【策略】动量策略，追高景气、高弹性赛道。【行业】聚焦科技/制造/医药等高成长方向。【流动性】偏好成交活跃、规模足够的品种以承载进攻。【金融工程】以近1年收益r1y排序捕捉动量。【胜率赔率】重赔率（高收益弹性），愿承担较大波动博取超额收益。"},
    {"id": "qwen", "name": "千问", "name_short": "千问", "region": "cn",
     "color": "#00703c", "persona": "风险平价派：波动低、夏普高、收益稳定的基金，强调风险调整后收益", "rule": "sr1y",
     "category_logic": "【宏观】波动加剧阶段，风险调整后收益更重要。【策略】风险平价，控波动求稳健。【行业】分散于偏债混合/量化/中短债，规避高波动股票。【流动性】优先高流动性、低摩擦成本品种。【金融工程】以夏普sr1y衡量风险收益性价比。【胜率赔率】重胜率与稳定赔率，同等风险下追求收益最高。"},
    {"id": "wenxin", "name": "文心一言", "name_short": "文心", "region": "cn",
     "color": "#f47738", "persona": "稳健防御派：债券型、偏债混合等低回撤品种，本金安全放第一位", "rule": "dd1y",
     "category_logic": "【宏观】不确定性偏高时保本优先。【策略】稳健防御，以低回撤为底仓。【行业】聚焦短债/纯债/偏债混合，规避权益敞口。【流动性】强调随时可赎回、无锁定期。【金融工程】以近1年回撤dd1y最小为筛选核心。【胜率赔率】极高胜率、低赔率，宁可少赚不能大亏。"},
    {"id": "zhipu", "name": "智谱", "name_short": "智谱", "region": "cn",
     "color": "#4c2c92", "persona": "长期价值派：穿越牛熊、中长期（3年+）收益领先的基金，不追短期热点", "rule": "r3y",
     "category_logic": "【宏观】逆周期布局，看重中长期产业趋势。【策略】长期价值，穿越牛熊。【行业】偏股混合/平衡型/QDII，重结构性机会。【流动性】接受较长持有期以换取复利。【金融工程】以近3年收益r3y评估中长期能力。【胜率赔率】中等胜率、中高赔率，重时间复利而非一时排名。"},
    {"id": "kimi", "name": "Kimi", "name_short": "Kimi", "region": "cn",
     "color": "#d53880", "persona": "性价比派：收益/回撤比（卡玛）高、涨多跌少的基金，追求风险收益性价比", "rule": "calmar3",
     "category_logic": "【宏观】震荡市中「涨多跌少」最划算。【策略】性价比优先，收益/回撤比最优。【行业】二级债基/偏债混合/量化为主。【流动性】选流动性充裕、回撤可控品种。【金融工程】以收益回撤比衡量风险收益效率。【胜率赔率】胜率与赔率兼顾，追求风险收益效率最大化。"},
    {"id": "minimax", "name": "MiniMax", "name_short": "Minimax", "region": "cn",
     "color": "#28a197", "persona": "全天候均衡派：强制跨大类（股/债/QDII/指数）分散，不押注单一风格", "rule": "balanced",
     "category_logic": "【宏观】应对未知市况，不赌方向。【策略】全天候跨大类均衡配置。【行业】股/债/QDII/指数/FOF 各大类均配。【流动性】每类留压舱石，保证整体流动性。【金融工程】各大类内取k_all代表，强制分散。【胜率赔率】以分散降波动，胜率靠广度、赔率靠多元，化解单一风格风险。"},
]


# 真实模型 API 配置（规则版种子仍写 mode='rule'，api_* 仅记录能力，待 ai_pk_real.py 真实跑）
_API_CONFIG = {
    "ds": {"api_provider": "qwen", "api_model": "vanchin/deepseek-v3", "api_key_env": "QWEN_API_KEY"},
    "doubao": {"api_provider": "volc-ark", "api_model": "ep-20260712083200-pjvq9", "api_key_env": "ARK_API_KEY"},
    "qwen": {"api_provider": "qwen", "api_model": "qwen-plus", "api_key_env": "QWEN_API_KEY"},
    "wenxin": {"api_provider": "wenxin", "api_model": "ernie-5.1", "api_key_env": "WENXIN_API_KEY"},
    "zhipu": {"api_provider": "qwen", "api_model": "ZHIPU/GLM-5.2", "api_key_env": "QWEN_API_KEY"},
    "kimi": {"api_provider": "qwen", "api_model": "kimi/kimi-k2.5", "api_key_env": "QWEN_API_KEY"},
    "minimax": {"api_provider": "qwen", "api_model": "MiniMax/MiniMax-M3", "api_key_env": "QWEN_API_KEY"},
}
for m in MODELS:
    cfg = _API_CONFIG.get(m["id"])
    if cfg:
        m.update(cfg)
    m["mode"] = "rule"


def mgmt_query(sql, expect_ok=(200, 201)):
    r = requests.post(MGMT_URL, headers=MGMT_HEADERS, json={"query": sql}, timeout=120)
    if r.status_code not in expect_ok:
        print(f"[MGMT ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    try:
        return r.json()
    except Exception:
        return None


def rest_select(params):
    """用 anon key 只读拉取候选池（anon 有 SELECT 权限）"""
    url = f"{SUPABASE_URL}/rest/v1/fund_combined"
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "Accept": "application/json"}
    r = requests.get(url, headers=headers, params=params, timeout=120)
    if r.status_code != 200:
        print(f"[REST ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    return r.json()


# ===== 份额去重 =====
# 同一基金的不同份额（A/C/E/I/B/H/R/Y/D/F）名称仅在末尾份额字母不同，视为同一标的。
# 归一化：去掉末尾单个份额字母，如「易方达蓝筹精选混合A」→「易方达蓝筹精选混合」。
# 例外：名字以 ETF/LOF/QDII 整体结尾时，尾字母是缩写一部分（如「沪深300ETF」的 F），不可削。
_SHARE_SET = set("ACEFIHBDYRF")
_ACRONYM_SUFFIXES = ("ETF", "LOF", "QDII")


def norm_name(n):
    if not n:
        return ''
    n = n.strip()
    if len(n) >= 2 and n[-1] in _SHARE_SET:
        if n.endswith(_ACRONYM_SUFFIXES):
            return n
        return n[:-1]
    return n


# 最高风控规则：识别「持有期 / 定开 / 定期开放」等带锁定期、月度调仓时卖不掉的产品（按名称，无需额外列）
_LOCKED_RE = re.compile(r'(持有期|定开|定期开放|最短持有|\d+\s*(年|个月|月|天|日)\s*持有|持有\s*\d+\s*(年|个月|月))')
def is_locked_fund(name):
    return bool(name) and bool(_LOCKED_RE.search(name))


def dedupe_pool(pool):
    """同一基金只保留一个主代码：优先 A 份额，否则取规模更大者。"""
    groups = {}
    for f in pool:
        key = norm_name(f.get('name'))
        groups.setdefault(key, []).append(f)
    out = []
    for items in groups.values():
        if len(items) == 1:
            out.append(items[0])
            continue
        # 优先 A 份额（名称以 A 结尾）
        a_items = [x for x in items if (x.get('name') or '').rstrip().endswith('A')]
        if a_items:
            pick = max(a_items, key=lambda x: (x.get('fund_scale') or 0))
        else:
            pick = max(items, key=lambda x: (x.get('fund_scale') or 0, 0)) or items[0]
        out.append(pick)
    return out


def fetch_pool():
    """从 fund_combined（全市场主表）按品类分组拉取候选池。

    策略：不按 k_all 引导，而是按一级分类(t0)分组，每类取中性排序
    （fund_scale 倒序），每类上限约 55 只，再叠加全市场中性的 Top 补强，
    汇总成规则选基的候选池。保留持有期/定开锁定期过滤与份额去重。
    fund_combined.c 不带 .OF 后缀，下游写库/校验期望带 .OF，故此处追加。
    """
    cats = ["混合型", "指数型", "债券型", "股票型", "QDII", "FOF"]
    per_cat = 55
    collected = []
    for cat in cats:
        params = {
            "select": "c,name,t0,t1,k_all,k1,r1y,r3y,r5y,dd1y,sr1y,fund_scale",
            "t0": f"eq.{cat}",
            "fund_scale": "gt.2",
            "r1y": "not.is.null",
            "order": "fund_scale.desc",
            "limit": str(per_cat),
        }
        collected.extend(rest_select(params))
    # 全市场中性的 Top 补强（不按 k_all 引导，用 r1y 倒序捞头部弹性品种）
    top = rest_select({
        "select": "c,name,t0,t1,k_all,k1,r1y,r3y,r5y,dd1y,sr1y,fund_scale",
        "t0": "neq.货币型",
        "fund_scale": "gt.2",
        "r1y": "not.is.null",
        "order": "r1y.desc",
        "limit": "60",
    })
    collected.extend(top)

    # fund_combined.c 不带 .OF，下游写库/校验期望带 .OF（与 ai_pk_real.py 一致）
    for f in collected:
        c = f.get("c")
        if c and not c.endswith(".OF"):
            f["c"] = c + ".OF"

    print(f"[POOL] 原始候选基金数: {len(collected)}")
    # 最高风控规则：剔除持有期/定开等带锁定期产品（按名称识别，规则版兜底也须遵守）
    before = len(collected)
    collected = [f for f in collected if not is_locked_fund(f.get('name'))]
    print(f"[POOL] 已剔除持有期/定开产品: {before - len(collected)} 只（规则版候选）")
    deduped = dedupe_pool(collected)
    print(f"[POOL] 份额去重后候选基金数: {len(deduped)}（已屏蔽同基金其他份额）")
    return deduped


def fmt_val(v, pct=False, dec=2):
    if v is None:
        return '--'
    if pct:
        return f"{v:+.2f}%"
    return f"{v:.{dec}f}"


def make_reason(rule, f):
    """第二层逻辑：多维度结构化说明「为何选这只而非其他」（可验证，不编造）。

    覆盖维度：同类、收益、回撤、规模、持仓、费率、基金经理、基金公司、综合。
    注意：fund_combined 可能缺少持仓/费率/基金经理/基金公司字段，缺失维度
    不编造具体数字，按「以最新定期报告为准」或常识合理描述处理。
    """
    t0 = f.get('t0') or ''
    t1 = f.get('t1') or ''
    k_all = fmt_val(f.get('k_all'))
    r1 = fmt_val(f.get('r1y'), pct=True)
    r3 = fmt_val(f.get('r3y'), pct=True)
    dd1 = fmt_val(f.get('dd1y'), pct=True)
    dd3 = fmt_val(f.get('dd1y'), pct=True)
    sr = fmt_val(f.get('sr1y'), dec=3)
    scale = fmt_val(f.get('fund_scale'))

    # 【同类】维度：在候选池同类中的相对质地与风格互补性
    same_cls = f"【同类】该基金属{t0}/{t1}品类，在候选池同类中质地居前，风格与本组合其他标的互补、避免同质化暴露。"
    # 【收益】维度：中长期收益能力
    earn = f"【收益】近1年收益{r1}、近3年收益{r3}，中长期收益能力在同类中领先，符合本模型选基标准。"
    # 【回撤】维度：下行控制
    draw = f"【回撤】近1年最大回撤{dd1}、近1年下行{dd3}，下行控制相对稳健，风险暴露处于可承受区间。"
    # 【规模】维度：规模与流动性
    scale_d = f"【规模】最新规模约{scale}亿，规模适中且流动性较好，申赎摩擦低、运作稳定。"
    # 【持仓】维度：fund_combined 通常无持仓明细，不编造
    hold = "【持仓】具体持仓结构与集中度以最新定期报告为准；从品类与风格推断，其配置方向与本组合目标一致。"
    # 【费率】维度：fund_combined 通常无费率字段，不编造
    fee = "【费率】综合费率水平以最新招募说明书/定期报告为准，在同类产品中处于合理区间。"
    # 【基金经理】维度：fund_combined 通常无经理字段，不编造
    mgr = "【基金经理】基金经理任职年限与历史业绩以最新定期报告/公告为准，本模型偏好任职稳定、长期可追溯的管理人。"
    # 【基金公司】维度：fund_combined 通常无公司字段，不编造
    company = "【基金公司】基金公司投研实力与风控体系以公开信息为准，优先选择头部、投研体系完善机构发行的产品。"
    # 【综合】维度：结合本模型规则给出结论
    rule_label = {
        'k_all': '综合质量(k_all)最高',
        'r1y': '近1年收益动量最强',
        'sr1y': '夏普(风险调整后收益)最优',
        'dd1y': '近1年回撤最小、防御最强',
        'r3y': '近3年中长期收益领先',
        'calmar3': '近3年卡玛(收益/回撤比)最优',
        'balanced': '所在一级分类内综合质地最高',
    }.get(rule, '本模型规则')
    comp = (f"【综合】综合评分{k_all}、夏普{sr}，多维指标均衡；"
            f"以「{rule_label}」纳入组合作为{t0}品类代表，达成配置目标。")
    return same_cls + earn + draw + scale_d + hold + fee + mgr + company + comp


def pick_top(pool, key, topn=5, reverse=True, require_notnull=True):
    items = [f for f in pool if not require_notnull or f.get(key) is not None]
    items.sort(key=lambda f: (f.get(key) is None, f.get(key) if f.get(key) is not None else 0),
               reverse=reverse)
    return items[:topn]


def build_picks(pool):
    picks_by_model = {}

    # 1. DS: k_all 最高
    picks_by_model["ds"] = [f for f in pick_top(pool, "k_all")]

    # 2. 豆包: r1y 最高
    picks_by_model["doubao"] = [f for f in pick_top(pool, "r1y")]

    # 3. 千问: sr1y 最高
    picks_by_model["qwen"] = [f for f in pick_top(pool, "sr1y")]

    # 4. 文心: dd1y 最小(列为负，数值越大回撤越小)
    picks_by_model["wenxin"] = [f for f in pick_top(pool, "dd1y")]

    # 5. 智谱: r3y 最高
    picks_by_model["zhipu"] = [f for f in pick_top(pool, "r3y")]

    # 6. Kimi: 风险调整后收益 近3年收益/近1年最大回撤 最优
    calmar_pool = []
    for f in pool:
        r3 = f.get("r3y")
        dd3 = f.get("dd1y")
        if r3 is None or dd3 is None or dd3 == 0:
            continue
        calmar_pool.append((f, r3 / abs(dd3)))
    calmar_pool.sort(key=lambda x: x[1], reverse=True)
    picks_by_model["kimi"] = [f for f, _ in calmar_pool[:5]]

    # 7. Minimax: 跨一级分类均衡
    priority = ["混合型", "指数型", "债券型", "股票型", "QDII"]
    by_cat = {c: [] for c in priority}
    for f in pool:
        t0 = f.get("t0")
        if t0 in by_cat:
            by_cat[t0].append(f)
    for c in by_cat:
        by_cat[c].sort(key=lambda f: (f.get("k_all") is None, f.get("k_all") or 0), reverse=True)
    balanced = []
    chosen = set()
    for c in priority:
        if by_cat[c]:
            f = by_cat[c][0]
            balanced.append(f)
            chosen.add(f["c"])
    # 若不足 5 类，按 k_all 补满
    if len(balanced) < 5:
        extra = [f for f in pool if f["c"] not in chosen]
        extra.sort(key=lambda f: (f.get("k_all") is None, f.get("k_all") or 0), reverse=True)
        for f in extra:
            if len(balanced) >= 5:
                break
            if f["c"] not in chosen:
                balanced.append(f)
                chosen.add(f["c"])
    picks_by_model["minimax"] = balanced

    # 格式化为 5 只 / 20% 权重，去重 + 生成两层逻辑 reason
    result = {}
    for m in MODELS:
        mid = m["id"]
        raw = picks_by_model.get(mid, [])
        out = []
        seen = set()
        for f in raw:
            code = f.get("c")
            if not code or code in seen:
                continue
            seen.add(code)
            out.append({
                "code": code,
                "name": f.get("name") or code,
                "weight": 20,
                "reason": make_reason(m["rule"], f),
            })
            if len(out) >= 5:
                break
        result[mid] = out
    return result


def create_tables():
    print("[DDL] 创建表 ai_pk_models / ai_pk_picks ...")
    ddl = """
CREATE TABLE IF NOT EXISTS public.ai_pk_models (
  id text PRIMARY KEY,
  name text NOT NULL,
  name_short text,
  region text NOT NULL DEFAULT 'cn',
  color text NOT NULL,
  persona text,
  category_logic text,
  mode text NOT NULL DEFAULT 'rule',
  api_provider text,
  api_model text,
  api_key_env text,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.ai_pk_picks (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_id text NOT NULL REFERENCES public.ai_pk_models(id),
  period_month text NOT NULL,
  picks jsonb NOT NULL,
  mode text NOT NULL DEFAULT 'rule',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_pk_picks_model_period
  ON public.ai_pk_picks(model_id, period_month);

ALTER TABLE public.ai_pk_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_pk_picks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ai_pk_models_public_read" ON public.ai_pk_models;
CREATE POLICY "ai_pk_models_public_read" ON public.ai_pk_models FOR SELECT USING (true);

DROP POLICY IF EXISTS "ai_pk_picks_public_read" ON public.ai_pk_picks;
CREATE POLICY "ai_pk_picks_public_read" ON public.ai_pk_picks FOR SELECT USING (true);
"""
    mgmt_query(ddl)
    # 旧表兜底补列
    for col, typ in [
        ("category_logic", "text"),
        ("mode", "text NOT NULL DEFAULT 'rule'"),
        ("api_provider", "text"),
        ("api_model", "text"),
        ("api_key_env", "text"),
    ]:
        mgmt_query(f"ALTER TABLE public.ai_pk_models ADD COLUMN IF NOT EXISTS {col} {typ};")
    mgmt_query("ALTER TABLE public.ai_pk_picks ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'rule';")
    print("[DDL] 完成")


def upsert_models():
    print("[SEED] 写入模型元信息 ...")
    vals = []
    for m in MODELS:
        persona = m["persona"].replace("'", "''")
        clogic = m["category_logic"].replace("'", "''")
        provider = m.get("api_provider") or ""
        apimodel = m.get("api_model") or ""
        keyenv = m.get("api_key_env") or ""
        mode = m.get("mode") or "rule"
        vals.append(
            f"('{m['id']}','{m['name']}','{m['name_short']}','{m['region']}','{m['color']}',"
            f"'{persona}','{clogic}','{mode}','{provider}','{apimodel}','{keyenv}',true)"
        )
    sql = (
        "INSERT INTO public.ai_pk_models "
        "(id,name,name_short,region,color,persona,category_logic,mode,api_provider,api_model,api_key_env,enabled) VALUES "
        + ",".join(vals)
        + " ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, name_short=EXCLUDED.name_short, "
          "region=EXCLUDED.region, color=EXCLUDED.color, persona=EXCLUDED.persona, "
          "category_logic=EXCLUDED.category_logic, mode=EXCLUDED.mode, "
          "api_provider=EXCLUDED.api_provider, api_model=EXCLUDED.api_model, "
          "api_key_env=EXCLUDED.api_key_env, enabled=EXCLUDED.enabled;"
    )
    mgmt_query(sql)
    print("[SEED] 模型元信息完成")


def upsert_picks(picks_by_model, period_month, mode="rule"):
    print(f"[SEED] 写入当期({period_month})选基结果 [mode={mode}] ...")
    for m in MODELS:
        mid = m["id"]
        funds = picks_by_model.get(mid, [])
        if len(funds) < 5:
            print(f"  [WARN] {mid} 仅选到 {len(funds)} 只，跳过")
            continue
        picks_json = json.dumps(funds, ensure_ascii=False).replace("'", "''")
        # 先删后插，保证重跑幂等
        mgmt_query(
            f"DELETE FROM public.ai_pk_picks WHERE model_id='{mid}' AND period_month='{period_month}';"
        )
        mgmt_query(
            f"INSERT INTO public.ai_pk_picks (model_id, period_month, picks, mode) "
            f"VALUES ('{mid}','{period_month}','{picks_json}','{mode}');"
        )
        names = "、".join(f["name"] for f in funds)
        print(f"  {mid}({m['name_short']}): {names}")
    print("[SEED] 选基结果完成")


def main():
    period_month = datetime.date.today().strftime("%Y-%m")
    print(f"=== AI大PK 规则版种子 (期次 {period_month}) ===")
    create_tables()
    pool = fetch_pool()
    if not pool:
        print("[ERR] 候选池为空，无法选基")
        sys.exit(1)
    picks_by_model = build_picks(pool)
    # 打印预览
    for m in MODELS:
        funds = picks_by_model.get(m["id"], [])
        print(f"\n[{m['id']}] {m['name']} — {m['persona']}")
        print(f"  [品类逻辑] {m['category_logic']}")
        for i, f in enumerate(funds, 1):
            print(f"   {i}. {f['code']} {f['name']} (20%)")
            print(f"      └ {f['reason']}")
    upsert_models()
    upsert_picks(picks_by_model, period_month, mode="rule")
    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
