#!/usr/bin/env python3
"""
导出已发布文章列表到 public/articles-list.json

为博客列表页提供「零等待」首屏：EdgeOne Pages CDN 直接静态返回，
绕开 EdgeOne 函数 → Supabase 新加坡偶发 10-16s 的慢链。

调用：
  python scripts/export_articles_list.py                # 默认写到 <repo>/public/articles-list.json
  python scripts/export_articles_list.py --output P     # 自定义输出路径
"""
import os, sys, json, time, requests
from datetime import datetime

SUPABASE_URL = os.environ.get('SUPABASE_URL') or os.environ.get('VITE_SUPABASE_URL') or 'https://tqhtegazxykkqfcpejky.supabase.co'
SUPABASE_KEY = os.environ.get('SUPABASE_ANON_KEY') or os.environ.get('VITE_SUPABASE_ANON_KEY') or 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'

# 仅取列表页必要字段，与前端 listArticles 的 FIELDS 保持一致；content 等大字段不在此取
FIELDS = 'id,title,summary,status,published_at,updated_at,views,tags,cover_image,author_email,is_pinned,scheduled_at'

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Accept': 'application/json',
}

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'public', 'articles-list.json')
if '--output' in sys.argv:
    idx = sys.argv.index('--output')
    OUTPUT_PATH = sys.argv[idx + 1]
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)


def fetch_published():
    """拉取已发布文章（含定时文章中 scheduled_at 已到点的；前端按需再过滤）"""
    url = (
        f'{SUPABASE_URL}/rest/v1/articles'
        f'?select={FIELDS}'
        f'&status=eq.published'
        f'&order=is_pinned.desc,published_at.desc.nullslast'
        f'&limit=200'
    )
    last_err = None
    for attempt in range(1, 6):  # 最多重试 5 次（10-15s 慢链偶发，重试有效）
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code == 200:
                rows = r.json()
                return rows if isinstance(rows, list) else []
            last_err = f'HTTP {r.status_code}: {r.text[:120]}'
        except Exception as e:
            last_err = f'{type(e).__name__}: {e}'
        print(f'  ⚠️ attempt {attempt} failed: {last_err}', file=sys.stderr)
        if attempt < 5:
            time.sleep(2 * attempt)
    raise RuntimeError(f'导出失败（重试 5 次后仍异常）: {last_err}')


def main():
    print(f'📝 导出已发布文章 → {OUTPUT_PATH}')
    rows = fetch_published()
    payload = {
        'generated_at': datetime.now().isoformat(),
        'count': len(rows),
        'articles': rows,
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=None)  # 紧凑 JSON，体积小
    print(f'✅ 完成：{len(rows)} 篇 → {OUTPUT_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())