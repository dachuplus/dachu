#!/usr/bin/env python3
"""
allfund_push_via_api.py
通过 GitHub REST API 推送代码（绕过 git 协议）
用法: GITHUB_TOKEN=ghp_xxx python3 allfund_push_via_api.py "commit message"
"""

import os
import sys
import json
import base64
import urllib.request

# ===== 配置 =====
REPO_OWNER = "maoshanbo"
REPO_NAME = "allfund"
BRANCH = "main"
API_BASE = "https://api.github.com"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    print("❌ 未找到 GITHUB_TOKEN 环境变量")
    print("用法: GITHUB_TOKEN=ghp_xxx python3 allfund_push_via_api.py \"commit message\"")
    sys.exit(1)

BASE_DIR = "/Users/maoshanbo/WorkBuddy/20260405093252/allfund"


def api_request(method, path, data=None):
    """发送 GitHub API 请求"""
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "allfund-push-script"
    }
    if data is not None:
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"❌ API 错误 {e.code}: {body}")
        sys.exit(1)


def get_commit_tree_sha(commit_sha):
    """获取 commit 对应的 tree SHA"""
    data = api_request("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/commits/{commit_sha}")
    return data["tree"]["sha"]


def create_blob(content_bytes):
    """创建 blob，返回 SHA"""
    encoded = base64.b64encode(content_bytes).decode("utf-8")
    resp = api_request("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/blobs", {
        "encoding": "base64",
        "content": encoded
    })
    return resp["sha"]


def create_tree(base_tree_sha, items):
    """创建 tree，返回 SHA"""
    resp = api_request("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/trees", {
        "base_tree": base_tree_sha,
        "tree": items
    })
    return resp["sha"]


def create_commit(tree_sha, parent_sha, message):
    """创建 commit，返回 SHA"""
    resp = api_request("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/commits", {
        "message": message,
        "tree": tree_sha,
        "parents": [parent_sha]
    })
    return resp["sha"]


def update_ref(commit_sha):
    """更新 branch ref"""
    api_request("PATCH", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/{BRANCH}", {
        "sha": commit_sha,
        "force": False
    })


def get_local_changed_files():
    """通过 git diff 获取本地有改动的文件（相对远程）"""
    import subprocess
    # 使用本地缓存的 origin/main ref
    result = subprocess.run(
        ["git", "diff", "--name-only", f"origin/{BRANCH}...HEAD"],
        cwd=BASE_DIR, capture_output=True, text=True
    )
    files = [f for f in result.stdout.strip().split("\n") if f]
    # 也检查 untracked 文件
    result2 = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=BASE_DIR, capture_output=True, text=True
    )
    untracked = [f for f in result2.stdout.strip().split("\n") if f]
    return files + untracked


def main():
    if len(sys.argv) < 2:
        print("用法: GITHUB_TOKEN=xxx python3 allfund_push_via_api.py \"commit message\"")
        sys.exit(1)

    commit_msg = sys.argv[1]
    print(f"📡 通过 GitHub REST API 推送 ({REPO_OWNER}/{REPO_NAME})")

    # 1. 获取远程最新 commit
    print("  → 获取远程 HEAD...")
    ref_data = api_request("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/ref/heads/{BRANCH}")
    parent_sha = ref_data["object"]["sha"]
    print(f"  ✓ 远程 HEAD: {parent_sha[:8]}")

    # 2. 获取本地改动文件
    print("  → 检测本地改动...")
    changed = get_local_changed_files()
    if not changed or all(f == '' for f in changed):
        print("  ✗ 没有检测到改动，跳过推送")
        sys.exit(0)

    changed = [f for f in changed if f]
    print(f"  ✓ 检测到 {len(changed)} 个文件有变动")

    # 3. 读取本地文件内容，创建 blobs
    print("  → 上传文件内容到 GitHub...")
    tree_items = []
    for filepath in changed:
        full_path = os.path.join(BASE_DIR, filepath)
        if not os.path.exists(full_path):
            print(f"    ! 跳过不存在的文件(已删除?): {filepath}")
            continue
        with open(full_path, "rb") as f:
            content_bytes = f.read()
        blob_sha = create_blob(content_bytes)
        mode = "100755" if os.access(full_path, os.X_OK) else "100644"
        tree_items.append({
            "path": filepath,
            "mode": mode,
            "type": "blob",
            "sha": blob_sha
        })
        print(f"    ✓ {filepath[:60]} → blob {blob_sha[:8]}")

    if not tree_items:
        print("  ✗ 没有可推送的文件")
        sys.exit(0)

    # 4. 创建新 tree
    print("  → 创建 Git tree...")
    base_tree_sha = get_commit_tree_sha(parent_sha)
    new_tree_sha = create_tree(base_tree_sha, tree_items)
    print(f"  ✓ 新 tree: {new_tree_sha[:8]}")

    # 5. 创建 commit
    print("  → 创建 commit...")
    new_commit_sha = create_commit(new_tree_sha, parent_sha, commit_msg)
    print(f"  ✓ 新 commit: {new_commit_sha[:8]}")

    # 6. 更新 ref
    print("  → 更新远程分支...")
    update_ref(new_commit_sha)
    print(f"  ✅ 推送完成! commit: {new_commit_sha[:8]}")
    print(f"  🔗 https://github.com/{REPO_OWNER}/{REPO_NAME}/commit/{new_commit_sha}")


if __name__ == "__main__":
    main()
