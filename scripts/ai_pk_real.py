#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI大PK —— 真实大模型自选脚本（v2：基于 fund_scores 两层选基）

功能：
  让已配置 API 的真实大模型（豆包 / 千问 / 文心 / 智谱 / Kimi / MiniMax / DeepSeek）
  基于 fund_scores 表的真实数据做「两层」选基：
      第一层（品类 layer）：从 fund_scores 的「二级分类 t1」中，结合真实品类统计
              + 宏观/策略/行业/流动性/金融工程/胜率赔率研究，选出本期超配品类并给出完整推理。
      第二层（单品 layer）：在所选品类的真实候选基金中，挑选 5 只（每只 20% 等权），
              逐只给出基于表内真实指标（k_all/收益/回撤/夏普/规模）的单品推理。

硬性约束（用户要求）：
  - 候选池与品类统计 100% 来自 fund_scores 真实表，模型不接触任何表外数据。
  - 模型推理只允许引用「下方提供的真实数字」，严禁提及基金经理、公司历史、网络抓取等表外信息
    （此类内容纯属臆测，判为无效）。
  - 最高风控：剔除持有期/定开/定期开放等锁定期产品，绝不允许进入组合。

工作流程：
  1. 读 ai_pk_models（enabled 且配了 api_provider 的模型）。
  2. build_category_summary()：从 fund_scores 按 t1 聚合品类级真实统计。
  3. 逐模型：Step1 品类选择（category_logic + 选中 t1 列表）→ Step2 单品选择（picks + reason）。
  4. 校验 code 真实存在于 fund_scores、份额去重、剔除锁定期产品。
  5. 写入 ai_pk_picks（mode='real'），并把模型 mode 置为 'real'。

用法：
  python3 scripts/ai_pk_real.py                 # 跑所有已配置模型
  python3 scripts/ai_pk_real.py --models ds     # 只跑 DeepSeek
  python3 scripts/ai_pk_real.py --dry-run       # 只打印不写入
"""
import os
import re
import sys
import json
import time
import datetime
import argparse
import requests

# ===== 凭证 =====
PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
if not PAT:
    raise SystemExit("缺少 SUPABASE_PAT 环境变量。")
REF = "tqhtegazxykkqfcpejky"
SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
ANON_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"
os.environ["SUPABASE_MGMT_TOKEN"] = PAT
os.environ["SUPABASE_PAT"] = PAT
MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"
MGMT_HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

# ===== 候选池参数 =====
POOL_PER_CAT = 25          # 每个二级分类取 Top N（按 k_all 倒序）作为单品候选
CANDIDATE_SELECT = "c,n,t0,t1,k_all,r1y,r3y,r5y,dd1y,sr1y,fund_scale"
ARK_MAX_TOKENS = 4096      # 火山方舟：放宽以避免第一层长推理把 JSON 截断

# 最高风控规则：识别「持有期 / 定开 / 定期开放」等带锁定期、月度调仓时卖不掉的产品（按名称，fund_scores 无专用列）
_LOCKED_RE = re.compile(r'(持有期|定开|定期开放|最短持有|\d+\s*(年|个月|月|天|日)\s*持有|持有\s*\d+\s*(年|个月|月))')
def is_locked_fund(name):
    return bool(name) and bool(_LOCKED_RE.search(name))

# 份额归一化（同 seed_ai_pk.py）
_SHARE_SET = set("ACEFIHBDYRF")
_ACRONYM_SUFFIXES = ("ETF", "LOF", "QDII")


def norm_name(n):
    if not n:
        return ''
    n = n.strip()
    if len(n) >= 2 and n[-1] in _SHARE_SET and not n.endswith(_ACRONYM_SUFFIXES):
        return n[:-1]
    return n


def mgmt_query(sql, expect_ok=(200, 201)):
    r = requests.post(MGMT_URL, headers=MGMT_HEADERS, json={"query": sql}, timeout=120)
    if r.status_code not in expect_ok:
        print(f"[MGMT ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    try:
        return r.json()
    except Exception:
        return None


def rest_select(params, table="fund_scores"):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "Accept": "application/json"}
    r = requests.get(url, headers=headers, params=params, timeout=120)
    if r.status_code != 200:
        print(f"[REST ERR] {r.status_code}: {r.text[:400]}")
        raise SystemExit(1)
    return r.json()


# ===== 品类摘要 / 候选池（全部基于 fund_scores 真实数据）=====
def build_category_summary():
    """从 fund_scores 按二级分类(t1)聚合真实统计，供第一层品类推理。"""
    print("[CAT] 构建 fund_scores 二级分类品类摘要 ...")
    sql = (
        "SELECT t1, COUNT(*) AS cnt, "
        "ROUND(AVG(k_all)::numeric,1) AS avg_k, "
        "ROUND(AVG(r1y)::numeric,2) AS avg_r1y, "
        "ROUND(AVG(r3y)::numeric,2) AS avg_r3y, "
        "ROUND(AVG(dd1y)::numeric,2) AS avg_dd1y, "
        "ROUND(AVG(sr1y)::numeric,2) AS avg_sr1y "
        "FROM public.fund_scores "
        "WHERE t1 IS NOT NULL AND k_all IS NOT NULL AND r1y IS NOT NULL "
        "GROUP BY t1 ORDER BY avg_k DESC;"
    )
    rows = mgmt_query(sql) or []
    print(f"[CAT] 品类数: {len(rows)}")
    return rows


def build_candidate_pool(chosen_t1s):
    """针对模型选定的二级分类，从 fund_scores 取 Top POOL_PER_CAT（按 k_all 倒序）作为单品候选。
    排除持有期/定开等锁定期产品（最高风控）。返回 {t1: [fund,...]}。"""
    pool = {}
    for t1 in chosen_t1s:
        t1q = t1.replace("'", "''")
        rows = rest_select({
            "select": CANDIDATE_SELECT,
            "t1": f"eq.{t1q}",
            "k_all": "not.is.null",
            "r1y": "not.is.null",
            "order": "k_all.desc",
            "limit": str(POOL_PER_CAT),
        }, table="fund_scores")
        funds = [f for f in rows if not is_locked_fund(f.get("n"))]
        pool[t1] = funds
    total = sum(len(v) for v in pool.values())
    print(f"[POOL] 候选池: {len(chosen_t1s)} 个品类, 共 {total} 只真实基金")
    return pool


def validate_in_scores(code):
    """按 code 在 fund_scores 中确认基金真实存在并返回记录（含 c/n）。"""
    if not code:
        return None
    cands = [code.strip(), code.strip().replace(".OF", ""),
             (code.strip() + ".OF") if not code.strip().endswith(".OF") else code.strip()]
    for c in cands:
        rows = rest_select({"select": CANDIDATE_SELECT, "c": f"eq.{c}"}, table="fund_scores")
        if rows:
            return rows[0]
    return None


def fmt_num(v, pct=False):
    if v is None:
        return "无"
    return (f"{v:+.2f}%" if pct else f"{v:.2f}")


# ===== Prompt 构造（两层）=====
def build_category_messages(model, cat_summary):
    lines = []
    for r in cat_summary:
        lines.append(
            f"- 二级分类={r['t1']} | 基金数={r['cnt']} | 平均靠谱指数k_all={r['avg_k']} | "
            f"近1年平均收益={r['avg_r1y']}% | 近3年平均收益={r['avg_r3y']}% | "
            f"平均最大回撤={r['avg_dd1y']}% | 平均夏普={r['avg_sr1y']}"
        )
    cat_text = "\n".join(lines)
    system = (
        "你是一名顶级基金投顾 AI，参加「AI 大 PK」选基竞赛。"
        "你必须严格基于下方提供的 fund_scores 真实品类统计做决策，只输出 JSON，"
        "不编造、不引用任何表外或网络信息。"
    )
    user = f"""你代表「{model.get('name')}」，正在与其他 6 个模型同台竞技。

【第一层任务 · 选基金品类（从 fund_scores 二级分类中选）】
下方是 fund_scores 表中所有「二级分类(t1)」的真实聚合统计（平均靠谱指数 k_all、平均收益、平均回撤、平均夏普、基金数量）。
请基于这些真实数据，结合宏观/策略/行业/流动性/金融工程/胜率赔率研究，从全部品类中选出你本期要超配的若干品类（建议 5~8 个），
并给出完整、有说服力的推理：
  · 为什么选这些品类（宏观象限、风格因子强弱、行业景气、流动性、风险预算、胜率赔率）；
  · 为什么不选其他品类。
推理必须结合上方提供的真实统计数字（如某品类平均收益/回撤/夏普），严禁空话、严禁引用任何表外或网络信息。

【输出严格 JSON（不要任何多余文字）】：
{{
  "category_logic": "第一层完整推理：结合真实品类统计+宏观/策略/行业/流动性/金融工程/胜率赔率，说明为何超配这些品类、低配哪些（8-15句，须有真实数字支撑）",
  "categories": [
    {{"t1": "选中的二级分类名称（必须来自上方列表）", "reason": "为何选该品类的简短理由（须结合真实统计）"}},
    ... 共 5~8 个
  ]
}}

可供选择的二级分类及真实统计：
{cat_text}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_single_messages(model, cat_logic, pool):
    blocks = []
    code_to_fund = {}
    name_to_fund = {}
    for t1, funds in pool.items():
        flines = []
        for f in funds:
            c = f.get("c")
            flines.append(
                f"  - code={c} | 名称={f.get('n')} | k_all={fmt_num(f.get('k_all'))} | "
                f"近1年={fmt_num(f.get('r1y'), True)} | 近3年={fmt_num(f.get('r3y'), True)} | "
                f"近5年={fmt_num(f.get('r5y'), True)} | 近1年回撤={fmt_num(f.get('dd1y'), True)} | "
                f"夏普1y={fmt_num(f.get('sr1y'))} | 规模={fmt_num(f.get('fund_scale'))}亿"
            )
            code_to_fund[c] = f
            name_to_fund[norm_name(f.get("n"))] = f
        blocks.append(f"【品类 {t1} 候选基金】\n" + "\n".join(flines))
    pool_text = "\n\n".join(blocks)
    system = (
        "你是一名顶级基金投顾 AI，参加「AI 大 PK」选基竞赛。"
        "你必须严格基于下方提供的 fund_scores 真实基金数据做单品选择，只输出 JSON，"
        "严禁引用任何表外/网络信息（尤其不得提及基金经理、公司历史等表外内容——这些不在提供的数据中，纯属臆测，判为无效）。"
    )
    user = f"""你代表「{model.get('name')}」。第一层品类选择已完成，结论如下：
{cat_logic}

【第二层任务 · 选基金单品（在所选品类内选）】
下方是你在第一层所选品类的真实候选基金（已按品类分组，数据来自 fund_scores 真实表：k_all/收益/回撤/夏普/规模）。
请从这些候选基金中挑选恰好 5 只（每只 20% 等权）构建组合。要求：
  · 所选基金必须来自上方候选列表（code 必须出现），不可编造、不可引入列表外基金。
  · 优先覆盖第一层选定的多个品类，体现分散。
  · 对每只基金，给出完整、有说服力的单品推理，必须且仅基于上方真实数据：
    ① 同类对比：该基金 k_all / 收益在所属品类中的相对位置；
    ② 收益：近1/3/5年收益，相对品类均值；
    ③ 回撤：最大回撤控制能力；
    ④ 夏普：风险调整后收益；
    ⑤ 规模：规模是否适配策略（过大影响灵活、过小有清盘风险）；
    ⑥ 综合：为何它是该品类下的最优载体。
  · 【严禁】提及基金经理、任职年限、公司历史、任何网络/表外信息——这些不在提供的数据中，纯属臆测，会判为无效。

【硬性约束 · 最高风控】
- 严禁选择「持有期/定开/定期开放/最短持有」类基金（锁定期内无法赎回）。候选已预先剔除，也不得自行引入。

【输出严格 JSON（不要任何多余文字）】：
{{
  "picks": [
    {{"code": "基金code(必须来自上方候选列表)", "reason": "第二层单品推理：基于真实数据①②③④⑤⑥说明为何选它（禁止表外信息）"}},
    ... 共 5 个
  ]
}}

候选基金（真实数据，来自 fund_scores）：
{pool_text}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], code_to_fund, name_to_fund


def extract_json(text):
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    m2 = re.search(r"\{", text)
    if m2:
        tail = text[m2.start():]
        open_quotes = tail.count('"') % 2
        open_braces = tail.count('{') - tail.count('}')
        fixed = tail + ('"' * open_quotes) + ('}' * max(0, open_braces))
        try:
            return json.loads(fixed)
        except Exception:
            pass
    raise ValueError(f"无法从返回文本中提取JSON: {text[:200]}…")


def call_deepseek(prompt_messages, key):
    url = "https://api.deepseek.com/v1/chat/completions"
    body = {
        "model": "deepseek-chat",
        "messages": prompt_messages,
        "temperature": 0.7,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_ark(model_id, prompt_messages, key, timeout=300, max_retries=2):
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    body = {
        "model": model_id,
        "messages": prompt_messages,
        "temperature": 0.7,
        "max_tokens": ARK_MAX_TOKENS,
    }
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                              json=body, timeout=timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            last_err = e
            if attempt < max_retries:
                wait = 2 ** attempt * 5
                print(f"  [ARK RETRY] 第 {attempt + 1} 次调用失败({e})，{wait}s 后重试")
                time.sleep(wait)
            else:
                raise
    raise last_err


def call_qwen(model_id, prompt_messages, key):
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    body = {
        "model": model_id,
        "messages": prompt_messages,
        "temperature": 0.7,
        "max_tokens": 8192,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    if r.status_code != 200:
        raise RuntimeError(f"百炼 API 返回 {r.status_code}: {r.text[:400]}")
    content = r.json()["choices"][0]["message"]["content"]
    if not content:
        rc = r.json()["choices"][0]["message"].get("reasoning_content", "")
        raise RuntimeError(f"百炼模型({model_id})返回空内容，reasoning={rc[:200]}… 可能需要更大 max_tokens")
    return content


def call_wenxin(model_id, prompt_messages, key):
    url = "https://qianfan.baidubce.com/v2/chat/completions"
    body = {
        "model": model_id,
        "messages": prompt_messages,
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_zhipu(model_id, prompt_messages, key):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    body = {
        "model": model_id,
        "messages": prompt_messages,
        "temperature": 0.7,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    if r.status_code != 200:
        raise RuntimeError(f"智谱 API 返回 {r.status_code}: {r.text[:400]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"智谱返回解析失败: {e}; 原始: {r.text[:400]}")


def call_kimi(model_id, prompt_messages, key):
    url = "https://api.moonshot.cn/v1/chat/completions"
    body = {
        "model": model_id,
        "messages": prompt_messages,
        "temperature": 0.7,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json=body, timeout=150)
    if r.status_code != 200:
        raise RuntimeError(f"Kimi API 返回 {r.status_code}: {r.text[:400]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Kimi 返回解析失败: {e}; 原始: {r.text[:400]}")


def call_model(model, prompt_messages):
    provider = model.get("api_provider")
    keyenv = model.get("api_key_env")
    key = os.environ.get(keyenv) if keyenv else None
    if not key:
        raise RuntimeError(f"缺少环境变量 {keyenv}（{provider} 需要 API Key）")
    if provider == "deepseek":
        return call_deepseek(prompt_messages, key)
    if provider == "qwen":
        return call_qwen(model.get("api_model") or "qwen-plus", prompt_messages, key)
    if provider == "wenxin":
        return call_wenxin(model.get("api_model") or "ernie-4.5-8k-preview", prompt_messages, key)
    if provider == "zhipu":
        return call_zhipu(model.get("api_model") or "glm-4-plus", prompt_messages, key)
    if provider == "kimi":
        return call_kimi(model.get("api_model") or "kimi-k2", prompt_messages, key)
    if provider == "volc-ark":
        apimodel = model.get("api_model") or ""
        if not apimodel.startswith("ep-"):
            raise RuntimeError(
                f"豆包(api_model={apimodel}) 不是有效的推理接入点(ep-xxxx)。"
                f"请在火山方舟控制台创建推理接入点并把 ep-xxxx 写入 ai_pk_models.api_model。"
            )
        return call_ark(apimodel, prompt_messages, key)
    raise RuntimeError(f"未知 api_provider: {provider}")


def run_model(model, cat_summary, period_month, dry_run):
    print(f"\n===== [{model['id']}] {model['name']} ({model.get('api_provider')}) =====")

    # ---------- Step 1：选品类 ----------
    msgs1 = build_category_messages(model, cat_summary)
    try:
        raw1 = call_model(model, msgs1)
    except Exception as e:
        print(f"  [SKIP] Step1 调用失败: {e}")
        return False
    try:
        d1 = extract_json(raw1)
    except Exception as e:
        print(f"  [SKIP] Step1 JSON 解析失败: {e}\n  原始前200字: {raw1[:200]}")
        return False
    cat_logic = (d1.get("category_logic") or "").strip()
    cats = d1.get("categories") or []
    chosen = [c.get("t1") for c in cats if isinstance(c, dict) and c.get("t1")]
    if not cat_logic or len(chosen) < 3:
        print(f"  [SKIP] Step1 结构不完整：category_logic={'有' if cat_logic else '无'}, 选中品类={len(chosen)}")
        return False
    print(f"  [STEP1] 选中品类: {', '.join(chosen)}")

    # ---------- Step 2：选单品 ----------
    pool = build_candidate_pool(chosen)
    msgs2, code_to_fund, name_to_fund = build_single_messages(model, cat_logic, pool)
    try:
        raw2 = call_model(model, msgs2)
    except Exception as e:
        print(f"  [SKIP] Step2 调用失败: {e}")
        return False
    try:
        d2 = extract_json(raw2)
    except Exception as e:
        print(f"  [SKIP] Step2 JSON 解析失败: {e}\n  原始前200字: {raw2[:200]}")
        return False
    picks = d2.get("picks") or []
    if not isinstance(picks, list) or len(picks) < 5:
        print(f"  [SKIP] Step2 picks 不足 5：{len(picks) if isinstance(picks, list) else '非列表'}")
        return False

    chosen_funds = []
    seen = set()
    for p in picks:
        code = (p.get("code") or "").strip()
        f = code_to_fund.get(code) or code_to_fund.get(code.replace(".OF", "")) or code_to_fund.get(code + ".OF")
        if not f:
            f = validate_in_scores(code)
        if not f:
            nn = norm_name(p.get("name"))
            f = name_to_fund.get(nn)
        if not f:
            print(f"  [WARN] 无法校验基金（code={code}, name={p.get('name')}），跳过")
            continue
        if is_locked_fund(f.get("n")):
            print(f"  [WARN] {f.get('n')} 为锁定期产品（最高风控），跳过")
            continue
        nn = norm_name(f.get("n"))
        if nn in seen:
            print(f"  [WARN] {f.get('n')} 与已选同标的（份额重复），跳过")
            continue
        seen.add(nn)
        chosen_funds.append({
            "code": f["c"],
            "name": f.get("n"),
            "weight": 20,
            "reason": (p.get("reason") or "由模型自选").strip(),
        })
        if len(chosen_funds) >= 5:
            break

    if len(chosen_funds) < 5:
        print(f"  [SKIP] 校验后仅 {len(chosen_funds)} 只有效基金，不足 5，本模型跳过")
        return False

    print(f"  [OK] 选基：{', '.join(x['name'] for x in chosen_funds)}")

    if dry_run:
        print(f"  [DRY-RUN] category_logic: {cat_logic[:160]}...")
        for x in chosen_funds:
            print(f"    - {x['name']} ({x['code']}) 20% | {x['reason'][:90]}")
        return True

    picks_json = json.dumps(chosen_funds, ensure_ascii=False).replace("'", "''")
    cat_json = cat_logic.replace("'", "''")
    mgmt_query(f"DELETE FROM public.ai_pk_picks WHERE model_id='{model['id']}' AND period_month='{period_month}';")
    mgmt_query(
        f"INSERT INTO public.ai_pk_picks (model_id, period_month, picks, mode) "
        f"VALUES ('{model['id']}','{period_month}','{picks_json}','real');"
    )
    mgmt_query(
        f"UPDATE public.ai_pk_models SET mode='real', category_logic='{cat_json}' "
        f"WHERE id='{model['id']}';"
    )
    print(f"  [WRITE] 已写入当期({period_month})选基（mode=real）")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="限定模型 id，逗号分隔，如 ds,doubao")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写入")
    ap.add_argument("--period", help="期次 YYYY-MM，默认当月")
    args = ap.parse_args()

    period_month = args.period or datetime.date.today().strftime("%Y-%m")
    print(f"=== AI大PK 真实模型自选（基于 fund_scores 两层选基：先选 t1 品类，再选单品）(期次 {period_month}) ===")

    rows = mgmt_query(
        "SELECT id,name,persona,category_logic,mode,api_provider,api_model,api_key_env,enabled "
        "FROM public.ai_pk_models WHERE enabled=true;"
    )
    models = [r for r in (rows or []) if r.get("api_provider")]
    if args.models:
        want = set(args.models.split(","))
        models = [m for m in models if m["id"] in want]
    if not models:
        print("[ERR] 没有已配置 api_provider 且启用的模型。")
        sys.exit(1)
    print(f"待跑模型: {', '.join(m['id'] for m in models)}")

    cat_summary = build_category_summary()
    if not cat_summary:
        print("[ERR] 品类摘要为空")
        sys.exit(1)

    ok = 0
    for m in models:
        if run_model(m, cat_summary, period_month, args.dry_run):
            ok += 1
    print(f"\n=== 完成：{ok}/{len(models)} 个模型成功生成两层选基 ===")


if __name__ == "__main__":
    main()
