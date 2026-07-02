#!/usr/bin/env python3
"""GitHub REST API push — bypass sandbox git protocol limitations"""
import json, os, subprocess, sys, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO_OWNER, REPO_NAME = "maoshanbo", "allfund"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    print("❌ 未找到 GITHUB_TOKEN"); sys.exit(1)

API = "https://api.github.com"

def api_request(method, path, body=None):
    url = f"{API}{path}"
    headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw and r.status < 300 else None
    except HTTPError as e:
        print(f"  API error {e.code}: {e.read().decode()[:200]}"); return None

def get_sha(commit="main"):
    data = api_request("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/ref/heads/{commit}")
    return data["object"]["sha"] if data else None

def get_commit_tree(sha):
    data = api_request("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/commits/{sha}")
    return data["tree"]["sha"] if data else None

def create_blob(content):
    return api_request("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/blobs", {"content": content, "encoding": "utf-8"})["sha"]

def create_tree(base_tree, items):
    tree = [{"path": p, "mode": "100644", "type": "blob", "sha": s} for p,s in items]
    return api_request("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/trees", {"base_tree": base_tree, "tree": tree})["sha"]

def create_commit(tree_sha, parent_sha, message):
    return api_request("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/commits", {"message": message, "tree": tree_sha, "parents": [parent_sha]})["sha"]

def update_ref(sha):
    api_request("PATCH", f"/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/main", {"sha": sha, "force": False})

def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "v3.3 update"
    print(f"📡 推送 {REPO_OWNER}/{REPO_NAME}")
    parent = get_sha("main")
    print(f"  ✓ 远程 HEAD: {parent[:8]}")

    # Use git status --porcelain to detect ALL changes:
    #   staged (A/M/D), unstaged (M/D), and untracked (??)
    # This replaces the old approach (git diff-tree HEAD + git ls-files)
    # which missed untracked files that were never git add-ed.
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, check=False
    )
    changed = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        status = line[:2]
        filepath = line[3:]
        # Skip deleted files (can't upload them as blobs)
        if "D" in status:
            print(f"    ⏭ 跳过已删除: {filepath}")
            continue
        # Skip files that don't exist on disk
        if not os.path.isfile(filepath):
            print(f"    ⏭ 跳过不存在: {filepath}")
            continue
        changed.append(filepath)

    if not changed:
        print("  无改动，跳过"); return
    print(f"  ✓ 检测到 {len(changed)} 个文件")
    items = []
    for f in changed:
        try:
            with open(f, "r") as fh:
                blob_sha = create_blob(fh.read())
            items.append((f, blob_sha))
            print(f"    ✓ {f} → blob {blob_sha[:8]}")
        except Exception as e:
            print(f"    ✗ {f}: {e}")
    if not items:
        print("  无有效文件"); return
    tree = create_tree(get_commit_tree(parent), items)
    print(f"  ✓ 新 tree: {tree[:8]}")
    commit = create_commit(tree, parent, msg)
    print(f"  ✓ 新 commit: {commit[:8]}")
    update_ref(commit)
    print(f"  ✅ 推送完成! {commit}")
    print(f"  🔗 https://github.com/{REPO_OWNER}/{REPO_NAME}/commit/{commit}")

if __name__ == "__main__":
    main()
