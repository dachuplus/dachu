#!/usr/bin/env python3
"""全量同步本地改动到 GitHub main（云端备份，逐字节一致）。

默认自动对账：比对「本地工作树」与「GitHub 当前 HEAD 树」，
自动计算 新增 / 修改 / 删除 项并一次性推上去。
- 已跟踪文件的改动 + 未跟踪且未被 .gitignore 忽略的文件，全部纳入。
- .env.local / node_modules / dist 等因 .gitignore 天然排除，不会误推。
- 删除：本地已删但 GitHub 树中仍存在的路径，以 sha=None 从树中移除。

可选限制范围：设环境变量 PUSH_FILES="a.vue,b.js"（逗号分隔，相对仓库根）
则只同步这些文件，其余不动。

注意：本脚本用 api.github.com REST 直接建 commit，不依赖 git 协议
（沙箱里 github.com 不可达）。base 永远取 GitHub 当前 HEAD，保证 fast-forward。
"""
import os
import sys
import json
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO_OWNER = "dachuplus"
REPO_NAME = "dachu"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_token():
    """按优先级取 GITHUB_TOKEN：env → .env.local（即「数据中心」）。绝不打印明文。"""
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if t:
        return t
    env_path = os.path.join(ROOT, ".env.local")
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
    sys.exit("缺少 GITHUB_TOKEN（env / .env.local 均未找到）")
print(f"token: len={len(TOKEN)} prefix={TOKEN[:4]}")

API = "https://api.github.com"


def api(method, path, body=None):
    """带退避重试的 GitHub REST 调用。覆盖代理偶发抖动（伪 400/502/503/504、SSL EOF）。"""
    url = f"{API}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = Request(url, data=data, headers=headers, method=method)
    last = None
    transient = {400, 502, 503, 504}
    for attempt in range(4):
        try:
            with urlopen(req, timeout=60) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw else None
        except HTTPError as e:
            last = e
            if e.code in transient and attempt < 3:
                print(f"  ⚠ 重试({attempt + 1}/4) {method} {path}: HTTP {e.code}")
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"  API error {e.code}: {e.read().decode()[:300]}")
            return None
        except Exception as e:  # 代理偶发卡 SSL EOF / tunnel 中断
            last = e
            if attempt < 3:
                print(f"  ⚠ 重试({attempt + 1}/4) {method} {path}: {e}")
                time.sleep(1.5 * (attempt + 1))
    print(f"  ✗ 最终失败 {method} {path}: {last}")
    return None


def _git(*args):
    return subprocess.run(["git", "-C", ROOT] + list(args),
                          capture_output=True, text=True).stdout


def local_file_set():
    """本地应纳入的文件集合（相对仓库根）：已跟踪 + 未跟踪且未被忽略。"""
    files = set()
    # 已跟踪
    for p in _git("ls-files").splitlines():
        if p.strip():
            files.add(p.strip())
    # 未跟踪且未被忽略（git status 已按 .gitignore 过滤；!! 为被忽略，跳过）
    for line in _git("status", "--porcelain", "--untracked-files=all").splitlines():
        st = line[:2]
        path = line[3:].strip()
        if not path or st == "!!":
            continue
        files.add(path)
    return files


def blob_sha_local(rel):
    """本地文件的 git blob sha（与 GitHub 存储口径一致）。"""
    return _git("hash-object", rel).strip()


def get_gh_head():
    ref = api("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/ref/heads/main")
    if not ref:
        sys.exit("无法获取 main ref")
    sha = ref["object"]["sha"]
    commit = api("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/commits/{sha}")
    return sha, commit["tree"]["sha"]


def get_gh_tree(tree_sha):
    """返回 {path: sha}（递归）。"""
    tree = api("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/{tree_sha}?recursive=1")
    if not tree:
        sys.exit("无法获取 GitHub 树")
    if tree.get("truncated"):
        print("  ⚠ 树被截断，超大仓库请分段处理")
    return {e["path"]: e["sha"] for e in tree.get("tree", []) if e["type"] == "blob"}


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "chore: 同步本地改动到 GitHub（云端备份）"
    only = os.environ.get("PUSH_FILES")
    restrict = set(f.strip() for f in only.split(",") if f.strip()) if only else None

    gh_head, gh_tree_sha = get_gh_head()
    print(f"  GitHub HEAD: {gh_head[:8]}")
    gh_tree = get_gh_tree(gh_tree_sha)

    local = local_file_set()
    if restrict:
        local &= restrict
        # 限制模式下，也允许"限制范围内的删除"被识别
        gh_paths = set(gh_tree) & restrict
    else:
        gh_paths = set(gh_tree)

    items = []        # 新增 / 修改
    deletes = []      # 删除
    unchanged = 0

    # 遍历本地文件：新增或内容变更
    for rel in sorted(local):
        if restrict and rel not in restrict:
            continue
        local_sha = blob_sha_local(rel)
        if gh_tree.get(rel) == local_sha:
            unchanged += 1
            continue
        # 内容不同或 GitHub 无此文件 → 上传 blob
        with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
            content = fh.read()
        blob = api("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/blobs",
                   {"content": content, "encoding": "utf-8"})
        if not blob:
            print(f"  ✗ blob 失败 {rel}")
            continue
        items.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        tag = "新增" if rel not in gh_tree else "修改"
        print(f"  {tag} {rel} → {blob['sha'][:8]}")

    # 遍历 GitHub 树：本地已删 → 从树移除
    for rel in sorted(gh_paths):
        if rel not in local:
            deletes.append(rel)
            items.append({"path": rel, "mode": "100644", "type": "blob", "sha": None})
            print(f"  删除 {rel}")

    print(f"  （未变化 {unchanged} 个文件跳过）")
    if not items:
        print("  ✓ 本地与 GitHub 已一致，无需推送")
        return

    tree = api("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/trees",
               {"base_tree": gh_tree_sha, "tree": items})
    if not tree:
        sys.exit("tree 创建失败")
    print(f"  ✓ 新 tree: {tree['sha'][:8]}")

    new_commit = api("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/commits",
                     {"message": msg, "tree": tree["sha"], "parents": [gh_head]})
    if not new_commit:
        sys.exit("commit 创建失败")

    api("PATCH", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/main",
        {"sha": new_commit["sha"], "force": False})
    print(f"  ✅ 推送完成 {new_commit['sha']}")
    print(f"  🔗 https://github.com/{REPO_OWNER}/{REPO_NAME}/commit/{new_commit['sha']}")


if __name__ == "__main__":
    main()
