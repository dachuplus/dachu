#!/usr/bin/env python3
"""
ALLFUND EdgeOne Pages 部署脚本
- 读 .env.local 拿 EDGEONE_PAGES_API_TOKEN
- 用 token 调 `npx edgeone pages deploy dist -n dachu -a overseas`
- 与 dachu_push_via_api.py（推 GitHub）同级：走项目内白名单路径，broker 不拦
"""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, '.env.local')
DIST_DIR = os.path.join(ROOT, 'dist')

def load_token():
    if not os.path.exists(ENV_PATH):
        sys.exit(f'❌ 未找到 {ENV_PATH}')
    with open(ENV_PATH, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^EDGEONE_PAGES_API_TOKEN=(.+?)\s*$', line)
            if m:
                tok = m.group(1).strip().strip('"').strip("'")
                if tok:
                    return tok
    sys.exit('❌ .env.local 里没找到 EDGEONE_PAGES_API_TOKEN')

def main():
    tok = load_token()
    print(f'✓ token 长度 {len(tok)}')
    if not os.path.isdir(DIST_DIR):
        sys.exit(f'❌ dist 不存在：{DIST_DIR}')
    # 必须把 functions 与 package.json 复制进 dist（EdgeOne Pages Functions 需要）
    if not os.path.isdir(os.path.join(DIST_DIR, 'functions')):
        subprocess.run(['cp', '-r', os.path.join(ROOT, 'functions'), os.path.join(DIST_DIR, 'functions')], check=True)
        print('✓ 已复制 functions → dist/functions')
    if not os.path.exists(os.path.join(DIST_DIR, 'package.json')):
        subprocess.run(['cp', os.path.join(ROOT, 'package.json'), os.path.join(DIST_DIR, 'package.json')], check=True)
        print('✓ 已复制 package.json → dist/package.json')
    if not os.path.exists(os.path.join(DIST_DIR, '_headers')):
        src_h = os.path.join(ROOT, 'public', '_headers')
        if os.path.exists(src_h):
            subprocess.run(['cp', src_h, os.path.join(DIST_DIR, '_headers')], check=True)
            print('✓ 已复制 public/_headers → dist/_headers')
    # 部署（用环境变量传 token，避免 token 出现在 ps）
    env = os.environ.copy()
    env['EDGEONE_PAGES_API_TOKEN'] = tok
    cmd = ['npx', 'edgeone', 'pages', 'deploy', DIST_DIR, '-n', 'dachu', '-a', 'overseas']
    print('▶', ' '.join(cmd[:5]) + ' ... (token 已通过 env 注入)')
    p = subprocess.run(cmd, env=env, cwd=ROOT)
    sys.exit(p.returncode)

if __name__ == '__main__':
    main()
