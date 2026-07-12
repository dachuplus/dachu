#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI大PK —— 真实大模型自选脚本

功能：
  让已配置 API 的大模型（目前 DeepSeek / 豆包）从 ALLFUND.CN 真实基金库（fund_scores 表）
  中「自己」挑选 5 只基金（每只 20% 等权），并产出两层选基逻辑：
      第一层 category_logic：为何选这些品类、为何不选其他品类。
      第二层 picks[].reason：为何选这只而非候选池里同品类的其他基金（基于真实指标）。

约束（用户硬性要求）：
  - 只能在 fund_scores 表内选基金，不编造、不引入表外数据。
  - 不强制按靠谱指数(k_all)排序——模型按自己的风格自由选品类与单基。

工作流程：
  1. 读 ai_pk_models，挑出 enabled 且配置了 api_provider 的模型。
  2. 从 fund_scores 构建「多样化候选池」（各大类 Top，真实指标齐全）。
  3. 逐模型调用真实 API（DeepSeek chat / 火山方舟 Ark）。
  4. 解析模型返回的 JSON（5 个 code + 两层理由），校验 code 真实存在、份额去重。
  5. 写入 ai_pk_picks（mode='real'），并把模型 mode 置为 'real'。

豆包(火山方舟)特别说明：
  - 必须先在火山方舟控制台创建「推理接入点」得到 ep-xxxx，并把 ep-xxxx 写入该模型行的 api_model。
  - 脚本读取 api_key_env（默认 ARK_API_KEY）作为 Bearer Token。
  - api_model 若不是以 'ep-' 开头（即仍是占位），脚本会跳过豆包并提示，不影响其他模型。

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

# ===== 候选池：全市场 fund_combined 各大类中立抽样，保证模型能自由选择品类 =====
# 注意：数据源改为 fund_combined（全市场基金，约 2 万条）；排序用「基金规模」而非 k_all，
# 避免用历史评分引导模型，让模型基于研究独立判断品类与单品。
POOL_CATEGORIES = ["混合型", "指数型", "债券型", "股票型", "QDII", "FOF"]
POOL_PER_CAT = 55
SELECT_FIELDS = "c,name,t0,t1,k_all,r1y,r3y,r5y,dd1y,sr1y,fund_scale"

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


def build_candidate_pool():
    """全市场 fund_combined 各大类中立抽样，份额去重，返回 (list, code->fund)。

    数据源改为 fund_combined（全市场），排序按基金规模(fund_scale)倒序（中性，不按 k_all），
    避免用历史评分引导模型。候选 code 统一追加 .OF 后缀，与下游 fund_scores / 前端保持一致。
    """
    collected = []
    for cat in POOL_CATEGORIES:
        params = {
            "select": SELECT_FIELDS,
            "t0": f"eq.{cat}",
            "fund_scale": "gt.2",
            "r1y": "not.is.null",
            "order": "fund_scale.desc",
            "limit": str(POOL_PER_CAT),
        }
        data = rest_select(params, table="fund_combined")
        # fund_combined.c 不带 .OF 后缀，下游 fund_scores 校验 / 前端 / picks 存储均期望带 .OF
        for row in data:
            if row.get("c") and not row["c"].endswith(".OF"):
                row["c"] = row["c"] + ".OF"
        collected.extend(data)

    # ===== 最高风控规则：剔除持有期/定开等带锁定期产品 =====
    # 这类产品带锁定期，月度调仓时根本卖不掉，会破坏组合流动性，绝不允许进入候选池。
    # fund_combined 无持有期专用列，按基金名称识别（与 FundRankPage 定开筛选口径一致）。
    before_filter = len(collected)
    collected = [f for f in collected if not is_locked_fund(f.get('name'))]
    print(f"[POOL] 已剔除持有期/定开产品: {before_filter - len(collected)} 只（剩余 {len(collected)}）")

    # 份额去重：同基金只留一个主代码（优先 A 份额，否则规模大者）
    groups = {}
    for f in collected:
        groups.setdefault(norm_name(f.get('name')), []).append(f)
    out = []
    for items in groups.values():
        if len(items) == 1:
            out.append(items[0])
            continue
        a_items = [x for x in items if (x.get('name') or '').rstrip().endswith('A')]
        out.append(max(a_items, key=lambda x: (x.get('fund_scale') or 0)) if a_items
                   else max(items, key=lambda x: (x.get('fund_scale') or 0)))
    by_code = {f["c"]: f for f in out}
    print(f"[POOL] 候选池规模: {len(out)} 只（来自 {len(collected)} 原始，已份额去重）")
    return out, by_code


def fmt_num(v, pct=False):
    if v is None:
        return "无"
    return (f"{v:+.2f}%" if pct else f"{v:.2f}")


def pool_to_text(pool):
    lines = []
    for f in pool:
        lines.append(
            f"- code={f['c']} | 名称={f.get('name')} | 大类={f.get('t0')}/{f.get('t1')} | "
            f"k_all={fmt_num(f.get('k_all'))} | 近1年={fmt_num(f.get('r1y'), True)} | "
            f"近3年={fmt_num(f.get('r3y'), True)} | 近1年回撤={fmt_num(f.get('dd1y'), True)} | "
            f"夏普1y={fmt_num(f.get('sr1y'))} | "
            f"规模={fmt_num(f.get('fund_scale'))}亿"
        )
    return "\n".join(lines)


def build_messages(model, pool_text):
    system = (
        "你是一名顶级基金投顾 AI，正在参加一场「AI 大 PK」选基竞赛。"
        "你的核心目标：从候选池中选出 5 只基金（每只 20% 等权）构建组合。"
        "你必须严格基于候选池真实数据决策，绝不编造基金或指标；缺失数据处注明『以最新定期报告为准』。"
        "你只能从候选池选择，输出严格 JSON。"
    )
    user = f"""你代表「{model.get('name')}」——一个独立思考的大语言模型。
你的任务：从下方候选基金池中挑选恰好 5 只基金，每只等权 20%，构建一个投资组合。

核心原则：
- 你拥有完全的自主权，不受任何预设风格、角色或策略限制，应基于你作为投顾的研究框架独立判断。
- 候选池来自全市场抽样（已是全市场范围），你可以自由地从候选池中选任何基金，不要被历史评分引导。
- 你的目标是：在所有参赛模型中，让这个组合的实际收益率尽可能高、回撤可控。
- 给出清晰、有研究支撑、可执行的两层逻辑，并用真实指标数字支撑。

第一层（category_logic）——品类配置逻辑：
请结合以下研究维度，独立判断本期应超配 / 低配哪些基金品类（混合型 / 指数型 / 债券型 / 股票型 / QDII / FOF）：
  · 宏观研究：利率、通胀、货币政策、经济增长（美林时钟 / 宏观象限）。
  · 策略研究：动量、价值、质量、成长等风格因子的相对强弱。
  · 行业研究：行业景气度、估值分位、产业政策导向。
  · 流动性研究：市场资金面、成交换手、资金流入流出。
  · 金融工程：因子暴露、风险模型、组合相关性。
  · 胜率与赔率研究：盈亏比、历史胜率统计、预期收益风险比。
明确要求：不要仅依赖候选池里罗列的历史评分表，要基于上述研究独立判断，并给出清晰可执行的配置结论（哪些品类超配、哪些低配、为什么）。

第二层（picks[].reason）——单品逻辑：
对所选的每一只基金，请从以下维度逐一说明「为什么选它」：
  ① 同类对比：同类排名、风格定位（如跑赢基准 / 同类前 10%）。
  ② 收益：中长期业绩（近 1/3/5 年），相对指数或同类。
  ③ 回撤：最大回撤控制能力、下行风险。
  ④ 规模：基金规模是否合理（过大影响灵活性 / 过小有清盘风险）。
  ⑤ 持仓：前十大持仓、行业集中度、与配置逻辑是否吻合。
  ⑥ 费率：管理费 + 托管费合计，相对同类是否低廉。
  ⑦ 基金经理：任职年限、历史管理业绩、投资理念。
  ⑧ 基金公司：平台投研实力、管理规模。
  ⑨ 综合结论：为何最终入选组合。
若候选池数据缺失某维度（如持仓 / 费率 / 基金经理），允许基于公开常识合理描述，但不得编造具体数字，缺失处请注明「以最新定期报告为准」。

硬性要求（最高风控规则优先，绝不违反）：
- 【最高规则·不可违反】严禁选择任何「持有期」或「定开」类基金（即带有锁定期、在锁定期内无法赎回的产品）。这类产品在月度调仓时根本卖不掉，会直接破坏组合的流动性。候选池已预先剔除此类产品，你也必须再次确认不在候选池之外引入任何带锁定期的产品。
1. 只能从下方候选池挑选（code 必须出现在列表中），不可编造基金。
2. 恰好 5 只，权重各 20%。
3. 同一基金的不同份额（A/C/E 等）视为同一标的，不要同时选 A 和 C。
4. 输出严格 JSON（不要任何多余文字/解释），结构如下：
{{
  "category_logic": "第一层：结合宏观/策略/行业/流动性/金工/胜率赔率研究，独立给出本期品类超配低配逻辑（4-8句，清晰可执行）",
  "picks": [
    {{"code": "基金code", "reason": "第二层：按①同类②收益③回撤④规模⑤持仓⑥费率⑦基金经理⑧基金公司⑨综合，逐维度说明为何选它"}},
    ... 共 5 个
  ]
}}

候选基金池（JSON）：
{pool_text}
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
    """确认 code 真实存在于 fund_scores，并取规范名称。返回 {code: name}。"""
    if not codes:
        return {}
    placeholders = ",".join(f"'{c}'" for c in codes)
    rows = mgmt_query(
        f"SELECT c, n FROM public.fund_scores WHERE c IN ({placeholders});"
    )
    return {r["c"]: r.get("n") or r["c"] for r in (rows or [])}


def run_model(model, pool, by_code, period_month, dry_run):
    print(f"\n===== [{model['id']}] {model['name']} ({model.get('api_provider')}) =====")
    messages = build_messages(model, pool_to_text(pool))
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
    if not cat_logic or len(picks) < 5:
        print(f"  [SKIP] 返回结构不完整：category_logic={'有' if cat_logic else '无'}, picks={len(picks)}")
        return False

    # 校验 code 真实存在 + 份额去重
    chosen_codes = []
    seen_names = set()
    valid_codes = set(by_code.keys())
    for p in picks:
        code = (p.get("code") or "").strip()
        if not code:
            continue
        if code in chosen_codes:
            continue
        # 真实存在性：在候选池中 OR 回库查 fund_scores
        name = by_code.get(code, {}).get("n")
        if code not in valid_codes:
            names = resolve_names([code])
            if code not in names:
                print(f"  [WARN] code={code} 不在 fund_scores，跳过")
                continue
            name = names[code]
        # 份额去重
        nn = norm_name(name)
        if nn in seen_names:
            print(f"  [WARN] {name}({code}) 与已选基金同标的（份额重复），跳过")
            continue
        seen_names.add(nn)
        chosen_codes.append(code)

    if len(chosen_codes) < 5:
        print(f"  [SKIP] 去重/校验后仅 {len(chosen_codes)} 只，不足 5")
        return False

    # 组装 picks（取前 5）
    final = []
    reason_map = {p.get("code"): p.get("reason", "") for p in picks}
    names_map = resolve_names(chosen_codes)
    for code in chosen_codes[:5]:
        final.append({
            "code": code,
            "name": names_map.get(code, by_code.get(code, {}).get("n", code)),
            "weight": 20,
            "reason": (reason_map.get(code) or "由模型自选").strip(),
        })

    print(f"  [OK] 选基：{', '.join(f['name'] for f in final)}")

    if dry_run:
        print(f"  [DRY-RUN] category_logic: {cat_logic[:120]}...")
        for f in final:
            print(f"    - {f['name']} ({f['code']}) 20% | {f['reason'][:80]}")
        return True

    # 写入 ai_pk_picks（mode='real'）
    picks_json = json.dumps(final, ensure_ascii=False).replace("'", "''")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="限定模型 id，逗号分隔，如 ds,doubao")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写入")
    ap.add_argument("--period", help="期次 YYYY-MM，默认当月")
    args = ap.parse_args()

    period_month = args.period or datetime.date.today().strftime("%Y-%m")
    print(f"=== AI大PK 真实模型自选 (期次 {period_month}) ===")

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
    print(f"待跑模型: {', '.join(m['id'] for m in models)}")

    pool, by_code = build_candidate_pool()
    if not pool:
        print("[ERR] 候选池为空")
        sys.exit(1)

    ok = 0
    for m in models:
        if run_model(m, pool, by_code, period_month, args.dry_run):
            ok += 1
    print(f"\n=== 完成：{ok}/{len(models)} 个模型成功生成真实选基 ===")


if __name__ == "__main__":
    main()
