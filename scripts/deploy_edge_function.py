#!/usr/bin/env python3
"""部署 Supabase Edge Function（走官方 CLI，服务端打包）。

用法：
    set -a; . ./.env.local; set +a
    python3 scripts/deploy_edge_function.py publish-article [其他 slug ...]

为什么不用 Management API？
--------------------------------------------------------------------
2026-09-20「发布文章 HTTP 503」事故：
  之前以为 `PATCH /v1/projects/{ref}/functions/<slug>` 带上 base64 源码就能部署，
  实测**不行**——它只把文件存下来，服务端**不会生成产物包**
  （元数据 `ezbr_sha256` 恒为 null、`entrypoint_path` 停留在旧版本），
  函数实例起不来 → 返回 `503 {"code":"BOOT_ERROR"}`。
  已做对照实验：`POST /functions` 新建一个最小 Deno.serve 函数，同样 ezbr_sha256=null、同样 503。
  ⇒ 该接口不能用来部署可用函数，之前的「部署成功」是假成功。

正确做法（本项目已实测可用）：
  1. 用官方独立二进制 CLI（Mac arm64）：
     https://github.com/supabase/cli/releases/latest/download/supabase_darwin_arm64.tar.gz
     解包得到 `supabase`（bun 版入口）。首次运行需可写的 HOME，否则报
     `EPERM rename ~/.supabase/telemetry.json` → 本脚本统一把 HOME 指到工具目录下。
  2. 工程已 `supabase link`（supabase/.temp/project-ref），无需再 link。
  3. `supabase functions deploy <slug> --use-api`
     —— `--use-api` 走服务端打包，**不需要 Docker**（本机没装 Docker）。
     部署成功标志：元数据 `ezbr_sha256` 有值且 `entrypoint_path` 中的版本号 == version。
  4. 部署后做启动自检（见 verify）。

其它坑：
  - 本机没 Docker，`supabase functions --help` 下**看不到 deploy 子命令**（被裁剪），
    但 `supabase functions deploy ... --use-api` 仍可正常执行。
  - 不要用 `supabase-go`（裁剪版，只有 db / functions download）。
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

REF = "tqhtegazxykkqfcpejky"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_DIR = os.path.expanduser("~/.workbuddy/binaries/supabase-cli")
CLI = os.path.join(TOOL_DIR, "supabase")
HOME_DIR = os.path.join(TOOL_DIR, "home")
DL_URL = "https://github.com/supabase/cli/releases/latest/download/supabase_darwin_arm64.tar.gz"


def load_env(name):
    """按优先级取配置：环境变量 → .env.local。只返回字符串，不打印。"""
    v = os.environ.get(name, "").strip()
    if v:
        return v
    try:
        with open(os.path.join(ROOT, ".env.local"), "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def ensure_cli():
    if os.path.isfile(CLI) and os.access(CLI, os.X_OK):
        return True
    print(f"· 未找到 CLI，下载到 {TOOL_DIR}")
    os.makedirs(TOOL_DIR, exist_ok=True)
    os.makedirs(HOME_DIR, exist_ok=True)
    tgz = os.path.join(TOOL_DIR, "supabase.tar.gz")
    try:
        urllib.request.urlretrieve(DL_URL, tgz)
        subprocess.run(["tar", "-xzf", tgz, "supabase"], cwd=TOOL_DIR, check=True)
        os.chmod(CLI, 0o755)
    except Exception as e:
        print(f"✗ CLI 下载/解包失败：{e}")
        return False
    return os.path.isfile(CLI)


def deploy(slugs, token):
    os.makedirs(HOME_DIR, exist_ok=True)
    env = dict(os.environ)
    env["SUPABASE_ACCESS_TOKEN"] = token
    env["HOME"] = HOME_DIR          # 规避 EPERM rename ~/.supabase/telemetry.json
    env["DO_NOT_TRACK"] = "1"
    cmd = [CLI, "functions", "deploy", *slugs, "--use-api"]
    print("· " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.strip().splitlines():
        print("  " + line)
    return r.returncode == 0


def meta(slug, token):
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/functions/{slug}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  ✗ 读元数据失败：{e}")
        return {}


def verify(slug, token, anon):
    """1) ezbr_sha256 必须有值（= 服务端真的打包了）；2) 函数能启动（不是 BOOT_ERROR）。"""
    m = meta(slug, token)
    sha = m.get("ezbr_sha256")
    entry = m.get("entrypoint_path") or ""
    ver = m.get("version")
    if not sha:
        print(f"  ✗ ezbr_sha256 为空 —— 服务端未生成产物包，函数起不来（BOOT_ERROR）")
        return False
    if f"_{ver}/" not in entry:
        print(f"  ✗ entrypoint 版本({entry.split('/')[-3] if '/' in entry else '?'}) 与 version({ver}) 不一致")
        return False
    print(f"  ✓ 产物包已生成 ezbr_sha256={sha[:16]}… version={ver}")

    if not anon:
        print("  ⚠ 无 VITE_SUPABASE_ANON_KEY，跳过启动自检")
        return True
    url = f"https://{REF}.supabase.co/functions/v1/{slug}"
    req = urllib.request.Request(
        url, data=b"{}",
        headers={"Authorization": f"Bearer {anon}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8", "replace")
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
        body = e.read().decode("utf-8", "replace")
    if code == 503 and "BOOT_ERROR" in body:
        print(f"  ✗ 启动自检失败：HTTP 503 BOOT_ERROR")
        return False
    print(f"  ✓ 启动自检通过：HTTP {code} · {body[:100]}")
    return True


def main():
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not slugs:
        sys.exit("用法：python3 scripts/deploy_edge_function.py <slug> [<slug> ...]")
    token = load_env("SUPABASE_PAT")
    if not token:
        sys.exit("缺少 SUPABASE_PAT（env / .env.local 均未找到）")
    anon = load_env("VITE_SUPABASE_ANON_KEY")

    if not ensure_cli():
        sys.exit("Supabase CLI 不可用")

    print(f"→ 部署 {len(slugs)} 个函数：{', '.join(slugs)}")
    if not deploy(slugs, token):
        sys.exit("✗ CLI 部署失败")

    print("\n→ 校验")
    failed = []
    for slug in slugs:
        print(f"[{slug}]")
        if not verify(slug, token, anon):
            failed.append(slug)
        time.sleep(1)

    if failed:
        sys.exit(f"✗ 以下函数未通过校验：{', '.join(failed)}")
    print(f"\n✅ 全部完成（{len(slugs)} 个函数）")


if __name__ == "__main__":
    main()
