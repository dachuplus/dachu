#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI大PK —— 真实大模型自选脚本

功能：
  让已配置 API 的真实大模型（DeepSeek / 豆包 / 千问 / 文心 / 智谱 / Kimi / MiniMax）
  基于自身研究「独立提名」5 只真实公募基金（每只 20% 等权），并产出两层选基逻辑：
      第一层 category_logic：模型独立研究的品类配置逻辑。
      第二层 picks[].reason：为何选这只而非其他基金（多维度）。

约束（用户硬性要求）：
  - 模型必须独立提名基金，不基于数据库任何表来引导选择；脚本仅用 fund_combined 做
    事后真实性校验，不向模型提供候选池、不泄露任何数据。
  - 不强制按靠谱指数(k_all)排序——模型按自己的研究框架自由选品类与单基。

工作流程：
  1. 读 ai_pk_models，挑出 enabled 且配置了 api_provider 的模型。
  2. 从 fund_scores 构建「多样化候选池」（各大类 Top，真实指标齐全）。
  3. 逐模型调用真实 API（DeepSeek chat / 火山方舟 Ark）。
  4. 解析模型返回的 JSON（5 个 code + 两层理由），校验 code 真实存在、份额去重。
  5. 写入 ai_pk_picks（mode='real'），并把模型 mode 置为 'real'。

豆包(火山方舟)特别说明：
  - 豆包已接入真实大模型（火山方舟推理接入点 ep-20260712083200-pjvq9，api_key=ARK_API_KEY），
    与其他模型一样由 call_ark 真实调用、独立提名基金，不再置「待接入」。
  - 若火山方舟接入点或 key 未配置（api_model 非 ep- 前缀或缺 ARK_API_KEY），call_model 抛错跳过，不影响其他模型。

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

# ===== 全市场校验字典（仅用于校验/归一化模型自由提名的基金，绝不作为候选池）=====
# 用户硬性要求：模型必须「独立选基金」，不基于数据库任何表来引导选择。
# 因此本脚本不再向模型提供候选池，而是由模型基于自身研究自由提名；
# 下面构建的 by_code / name_index 仅用于事后校验提名是否真实存在、并归一化名称/代码，
# 不参与任何选基决策。
LOOKUP_FIELDS = "c,name"

# 最高风控规则：识别「持有期 / 定开 / 定期开放」等带锁定期、月度调仓时卖不掉的产品（按名称，无需额外列）
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


# build_lookup_index() 已移除：原内存字典分页有 bug（只加载首段导致漏校验）。
# 改为 resolve_fund() 直接按 code/name 查库校验，见下方。


def fmt_num(v, pct=False):
    if v is None:
        return "无"
    return (f"{v:+.2f}%" if pct else f"{v:.2f}")


def resolve_fund(qname, qcode):
    """校验模型提名的基金是否真实存在于 fund_combined，并返回归一化记录（含 c/name）。
    解析顺序：① code（多种形态精确匹配）→ ② 归一化名称精确匹配 → ③ 子串模糊匹配。
    直接查库（每只最多几次小查询），避免内存字典分页不全导致的漏校验。
    """
    def _one(params):
        rows = rest_select(params, table="fund_combined")
        return rows[0] if rows else None
    if qcode:
        cq = qcode.strip()
        for cand in [cq, cq.replace(".OF", ""), (cq + ".OF") if not cq.endswith(".OF") else cq]:
            r = _one({"select": "c,name", "c": f"eq.{cand}"})
            if r:
                return {"c": r.get("c"), "name": r.get("name")}
    qn = norm_name(qname)
    if qn:
        r = _one({"select": "c,name", "name": f"eq.{qname}"})
        if r:
            return {"c": r.get("c"), "name": r.get("name")}
        r = _one({"select": "c,name", "name": f"ilike.%{qn}%"})
        if r:
            return {"c": r.get("c"), "name": r.get("name")}
    return None


def build_messages(model):
    system = (
        "你是一名顶级基金投顾 AI，正在参加一场「AI 大 PK」选基竞赛。"
        "你的任务：从你自己的知识库中，独立提名 5 只真实存在的中国公募基金（含 name 与 code），"
        "每只 20% 等权，构建投资组合。你必须基于独立研究自主决策，绝不编造不存在的基金；"
        "若对 code 不确定，仍需给出 best-effort 的 6 位代码 + .OF。输出严格 JSON。"
    )
    user = f"""你代表「{model.get('name')}」——一个独立思考的大语言模型，正在与其他 6 个模型同台竞技。

【任务】
从你掌握的中国公募基金知识中，独立提名恰好 5 只真实存在的公募基金（含 name 与 code），每只等权 20%，构建一个投资组合。
不要依赖任何外部提供的候选列表（本环境不会提供），完全由你基于研究判断。

【核心目标】
在所有参赛模型中，让你的组合实际收益尽可能高、回撤可控。你拥有完全自主权，不受任何预设风格限制。

【第一层 · 模型独立研究（category_logic）——必须达到研究级、有说服力的推理】
请基于以下六个维度做自上而下（top-down）的独立研究，并给出清晰、可执行、带具体结论的配置逻辑：
  · 宏观研究：当前宏观经济象限（美林时钟）、增长/通胀/利率/汇率/货币财政基调，判断风险资产 vs 避险资产的天平。
  · 策略研究：动量 / 价值 / 质量 / 成长 / 红利 / 小盘等风格因子的相对强弱与轮动，本期超配哪些风格。
  · 行业研究：高景气 / 低估 / 政策受益的具体行业与赛道（点名行业，而非泛泛而谈），及其估值分位。
  · 流动性研究：市场资金面、北向/融资/新基金发行、成交活跃度，对组合流动性的含义。
  · 金融工程：因子暴露、相关性/风险预算、组合层面对冲与分散设计。
  · 胜率与赔率研究：各资产/风格的预期收益风险比、历史胜率、盈亏比，据此分配胜率型与赔率型仓位。
明确要求：必须给出具体结论（哪些品类/风格超配、哪些低配、为什么是「现在」），用真实的研究逻辑支撑，
严禁停留在产品层面空话（例如不要说「近1年收益前10中有8只偏股型，所以选偏股」这类事后统计式理由）。

【第二层 · 单品逻辑（picks[].reason）】
对所选的每一只基金，说明「为什么是这只而非同类其他基金」：
  · 基金经理：任职年限、代表业绩、投资理念与能力圈。
  · 投资策略与定位：主动/指数、风格、仓位与换手，如何承接第一层的研究结论。
  · 历史业绩：中长期（1/3/5 年）相对基准与同类的表现、稳定性。
  · 风险控制：最大回撤、波动、下行保护。
  · 规模与流动性：规模是否适配策略（过大影响灵活、过小有清盘风险）。
  · 综合：为何它是该 thesis 下的最优载体。

【硬性约束 · 最高风控，绝不违反】
- 严禁选择任何「持有期 / 定开 / 定期开放 / 最短持有」类基金（带锁定期、锁定期内无法赎回，会破坏月度调仓流动性）。
1. 提名 5 只真实存在的公募基金（name + code 都要给），不可编造。
2. 恰好 5 只，权重各 20%。
3. 同一基金的不同份额（A/C/E 等）视为同一标的，只选其一（优先 A）。
4. 输出严格 JSON（不要任何多余文字），结构如下：
{{
  "category_logic": "第一层：结合宏观/策略/行业/流动性/金融工程/胜率赔率六维度，给出本期超配低配的具体研究结论（6-10句，有说服力、可执行）",
  "picks": [
    {{"name": "基金全称（如 易方达蓝筹精选混合）", "code": "基金code(如 005827.OF)", "reason": "第二层：按基金经理/策略/业绩/风控/规模/综合说明为何选这只"}},
    ... 共 5 个
  ]
}}
"""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
def extract_json(text):
    # 去掉 markdown 代码块围栏（可能出现在任意位置、多行）
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```", "", text)
    text = text.strip()
    # 直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 提取第一个完整 JSON 对象（容错：允许截断）
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        candidate = m.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            pass
    # 兜底：尝试修复常见问题后重试（截断的尾部补全）
    m2 = re.search(r"\{", text)
    if m2:
        tail = text[m2.start():]
        # 补齐未闭合的引号和括号
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
        "max_tokens": 1600,
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
        "max_tokens": 1600,
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
                wait = 2 ** attempt * 5  # 指数退避：5s, 10s
                print(f"  [ARK RETRY] 第 {attempt + 1} 次调用失败({e})，{wait}s 后重试")
                time.sleep(wait)
            else:
                raise
    raise last_err


def call_qwen(model_id, prompt_messages, key):
    # 阿里云百炼 OpenAI 兼容端点（支持自研qwen+第三方智谱/MiniMax/Kimi等）
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
        # 推理模型可能把输出放在 reasoning_content 里（finish_reason=length 时）
        rc = r.json()["choices"][0]["message"].get("reasoning_content", "")
        raise RuntimeError(f"百炼模型({model_id})返回空内容，reasoning={rc[:200]}… 可能需要更大 max_tokens")
    return content


def call_wenxin(model_id, prompt_messages, key):
    # 百度智能云千帆 OpenAI 兼容端点
    # 注意：ernie-5.1 不支持 response_format json_object，依赖 prompt 指令输出 JSON
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


def call_wenxin(model_id, prompt_messages, key):
    # 百度智能云千帆 OpenAI 兼容端点
    # 注意：ernie-5.1 不支持 response_format json_object，依赖 prompt 指令输出 JSON
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
    # 智谱 OpenAI 兼容端点（bigmodel / glm-4 系列支持 response_format json_object）
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
    # 月之暗面 Kimi / Moonshot OpenAI 兼容端点（kimi-k2 / moonshot-v1 系列支持 response_format json_object）
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


def resolve_names(codes):
    """（兼容保留）按 code 取规范名称；新逻辑主要用 resolve_fund。"""
    if not codes:
        return {}
    placeholders = ",".join(f"'{c}'" for c in codes)
    rows = mgmt_query(
        f"SELECT c, n FROM public.fund_scores WHERE c IN ({placeholders});"
    )
    return {r["c"]: r.get("n") or r["c"] for r in (rows or [])}


def run_model(model, period_month, dry_run):
    print(f"\n===== [{model['id']}] {model['name']} ({model.get('api_provider')}) =====")
    messages = build_messages(model)
    try:
        raw = call_model(model, messages)
    except Exception as e:
        print(f"  [SKIP] 调用失败: {e}")
        return False

    try:
        data = extract_json(raw)
    except Exception as e:
        print(f"  [SKIP] JSON 解析失败: {e}\n  原始返回前200字: {raw[:200]}")
        return False

    cat_logic = (data.get("category_logic") or "").strip()
    picks = data.get("picks") or []
    if not cat_logic or not isinstance(picks, list) or len(picks) < 5:
        print(f"  [SKIP] 返回结构不完整：category_logic={'有' if cat_logic else '无'}, picks={len(picks) if isinstance(picks,list) else '非列表'}")
        return False

    # 校验模型提名（基于全市场校验字典，事后确认真实存在 + 归一化）
    chosen = []
    seen_norm = set()
    for p in picks:
        qname = (p.get("name") or "").strip()
        qcode = (p.get("code") or "").strip()
        rec = resolve_fund(qname, qcode)
        if not rec:
            print(f"  [WARN] 无法校验基金（name={qname}, code={qcode}），跳过")
            continue
        code = rec["c"]
        if not code.endswith(".OF"):
            code = code + ".OF"
        name = rec.get("name") or qname
        if is_locked_fund(name):
            print(f"  [WARN] {name} 为持有期/定开产品（最高风控），跳过")
            continue
        nn = norm_name(name)
        if nn in seen_norm:
            print(f"  [WARN] {name} 与已选同标的（份额重复），跳过")
            continue
        seen_norm.add(nn)
        chosen.append({
            "code": code,
            "name": name,
            "weight": 20,
            "reason": (p.get("reason") or "由模型自选").strip(),
        })
        if len(chosen) >= 5:
            break

    if len(chosen) < 5:
        print(f"  [SKIP] 校验后仅 {len(chosen)} 只有效基金，不足 5，本模型跳过")
        return False

    print(f"  [OK] 选基：{', '.join(f['name'] for f in chosen)}")

    if dry_run:
        print(f"  [DRY-RUN] category_logic: {cat_logic[:120]}...")
        for f in chosen:
            print(f"    - {f['name']} ({f['code']}) 20% | {f['reason'][:80]}")
        return True

    # 写入 ai_pk_picks（mode='real'）
    picks_json = json.dumps(chosen, ensure_ascii=False).replace("'", "''")
    cat_json = cat_logic.replace("'", "''")
    mgmt_query(f"DELETE FROM public.ai_pk_picks WHERE model_id='{model['id']}' AND period_month='{period_month}';")
    mgmt_query(
        f"INSERT INTO public.ai_pk_picks (model_id, period_month, picks, mode) "
        f"VALUES ('{model['id']}','{period_month}','{picks_json}','real');"
    )
    # 更新模型 mode='real'，并写入本期第一层逻辑（覆盖规则版 category_logic）
    mgmt_query(
        f"UPDATE public.ai_pk_models SET mode='real', category_logic='{cat_json}' "
        f"WHERE id='{model['id']}';"
    )
    print(f"  [WRITE] 已写入当期({period_month})真实选基（mode=real）")
    return True


# handle_doubao_pending() 已移除：豆包现已接入真实大模型（火山方舟），由 run_model 正常处理。


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="限定模型 id，逗号分隔，如 ds,qwen")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写入")
    ap.add_argument("--period", help="期次 YYYY-MM，默认当月")
    args = ap.parse_args()

    period_month = args.period or datetime.date.today().strftime("%Y-%m")
    print(f"=== AI大PK 真实模型自选（独立提名，不基于任何表）(期次 {period_month}) ===")

    # 读模型配置
    rows = mgmt_query(
        "SELECT id,name,persona,category_logic,mode,api_provider,api_model,api_key_env,enabled "
        "FROM public.ai_pk_models WHERE enabled=true;"
    )
    models = [r for r in (rows or []) if r.get("api_provider")]
    if args.models:
        want = set(args.models.split(","))
        models = [m for m in models if m["id"] in want]
    if not models:
        print("[ERR] 没有已配置 api_provider 且启用的模型。请先在 ai_pk_models 配置 api_provider/api_model/api_key_env。")
        sys.exit(1)
    print(f"待跑模型: {', '.join(m['id'] for m in models)}（豆包将置为待接入）")

    ok = 0
    for m in models:
        if run_model(m, period_month, args.dry_run):
            ok += 1
    print(f"\n=== 完成：{ok}/{len(models)} 个模型成功生成独立选基（含豆包·火山方舟真实模型） ===")


if __name__ == "__main__":
    main()
