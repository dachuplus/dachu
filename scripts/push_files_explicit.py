#!/usr/bin/env python3
"""显式推送指定文件到 GitHub main（绕过 git status 差异检测）。

背景：本地 git 索引(HEAD=b8bd927) 与 GitHub main(d600655b) 不同步 ——
权限墙代码在本地 HEAD 里一直存在，9/9 那次删除只是「未提交的工作区删除」
却被同步到了 GitHub。因此本地 checkout 恢复后，权限墙文件相对本地 HEAD
是 CLEAN 的，`git status` 检测不到，dachu_push_via_api.py 不会推送它们。
本脚本直接按路径列表读取本地文件内容并创建 commit，强制覆盖远端。
"""
import os
import sys
import json
import subprocess
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO_OWNER = "dachuplus"
REPO_NAME = "dachu"


def _load_token():
    """按优先级取 GITHUB_TOKEN：env → stdin（仅当管道确有数据）→ .env.local（即「数据中心」）。
    全程只在进程内存中使用，绝不打印明文。"""
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if t:
        return t
    # 仅在 stdin 是管道/重定向「且确有可读数据」时才读，避免在空管道上阻塞整个进程
    # （曾经的 bug：无输入时 readline() 挂住，被上层 SIGTERM 杀掉 → exit 137）。
    try:
        import select
        if not sys.stdin.isatty() and select.select([sys.stdin], [], [], 0)[0]:
            t = (sys.stdin.readline() or "").strip()
            if t:
                return t
    except Exception:
        pass
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")
    try:
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("GITHUB_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


TOKEN = _load_token()
if not TOKEN:
    sys.exit("缺少 GITHUB_TOKEN（env / stdin / .env.local 均未找到）")
print(f"token: len={len(TOKEN)} prefix={TOKEN[:4]}")

API = "https://api.github.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 脚本在 scripts/ 下，项目根是上一级

# 本次需推送的文件（相对仓库根）
# 主题：数据下载中心改为「Supabase 私有桶 downloads + RLS 管理员门控」，
#       公网不再托管任何 xlsx（2026-09-22 修复匿名可下载漏洞）。
FILES = [
    ".gitignore",
    ".github/workflows/update-scores.yml",
    "exports/downloads/index.json",
    "run_recover.sh",
    "scripts/deploy_pages.sh",
    "scripts/export_all_tables.py",
    "scripts/push_files_explicit.py",
    "scripts/sql/downloads_bucket_private.sql",
    "scripts/upload_downloads.py",
    "src/api/downloads.js",
    "src/pages/data-center/DataCenterPage.vue",
]

# 需要从远端树中删除的路径（GitHub trees API 约定：sha=None 即删除）
DELETE_FILES = [
    "public/downloads/index.json",
]


def api(method, path, body=None):
    url = f"{API}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else None
    except HTTPError as e:
        print(f"  API error {e.code}: {e.read().decode()[:300]}")
        return None


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "signal: 5项优化(资产配置/股债/大宗商品主力合约/行业估值右对齐/巴菲特指标)"
    print(f"显式推送 {len(FILES)} 个文件到 {REPO_OWNER}/{REPO_NAME}")

    parent = api("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/ref/heads/main")
    if not parent:
        sys.exit("无法获取 main ref")
    parent_sha = parent["object"]["sha"]
    print(f"  远端 HEAD: {parent_sha[:8]}")

    commit = api("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/commits/{parent_sha}")
    base_tree = commit["tree"]["sha"]

    items = []
    for rel in FILES:
        local = os.path.join(ROOT, rel)
        if not os.path.isfile(local):
            print(f"  ⏭ 跳过（本地不存在）{rel}")
            continue
        with open(local, "r", encoding="utf-8") as fh:
            content = fh.read()
        blob = api("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/blobs",
                   {"content": content, "encoding": "utf-8"})
        if not blob:
            print(f"  ✗ blob 创建失败 {rel}")
            continue
        items.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"  ✓ {rel} → {blob['sha'][:8]}")

    for rel in DELETE_FILES:
        items.append({"path": rel, "mode": "100644", "type": "blob", "sha": None})
        print(f"  − 删除 {rel}")

    if not items:
        sys.exit("没有可推送的文件")

    tree = api("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/trees",
               {"base_tree": base_tree, "tree": items})
    if not tree:
        sys.exit("tree 创建失败")
    print(f"  ✓ 新 tree: {tree['sha'][:8]}")

    new_commit = api("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/commits",
                     {"message": msg, "tree": tree["sha"], "parents": [parent_sha]})
    if not new_commit:
        sys.exit("commit 创建失败")

    api("PATCH", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/main",
        {"sha": new_commit["sha"], "force": False})
    print(f"  ✅ 推送完成 {new_commit['sha']}")
    print(f"  🔗 https://github.com/{REPO_OWNER}/{REPO_NAME}/commit/{new_commit['sha']}")


if __name__ == "__main__":
    main()
