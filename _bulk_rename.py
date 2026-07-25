#!/usr/bin/env python3
# Bulk rename dachu -> dachu (safe strings only; email-domain lines handled manually elsewhere)
import os, io

ROOT = "/Users/maoshanbo/WorkBuddy/20260405093252/dachu"

# Files containing 'dachu' (non-dist), excluding the 4 email-domain files we edit manually
# and excluding already-deleted files (build-miniprogram.yml, mp-permissions, migration-to-miniprogram.md).
MANUAL = {
    "src/components/LoginDialog.vue",
    "src/composables/useAuth.js",
    "src/pages/data-center/DataCenterPage.vue",
    "supabase/functions/wechat-login/index.ts",
}

MAPPINGS = [
    ("大厨先生", "大厨先生"),
    ("dachu", "dachu"),
    ("dachu", "dachu"),
    ("dachu", "dachu"),
]

def walk_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # skip heavy / irrelevant dirs
        dirnames[:] = [d for d in dirnames if d not in (
            "node_modules", "dist", ".git", ".workbuddy", "__pycache__",
            "exports", "data", "logs", "mp-weixin", ".edgeone", "assets")]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT)
            if rel in MANUAL:
                continue
            try:
                with open(p, "rb") as f:
                    data = f.read()
                # skip binary-ish files
                if b"\x00" in data[:4096]:
                    continue
            except Exception:
                continue
            if b"dachu" in data.lower():
                out.append(p)
    return out

files = walk_files()
print(f"Files to process: {len(files)}")
total_changes = 0
for p in files:
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    original = text
    for src, dst in MAPPINGS:
        if src in text:
            text = text.replace(src, dst)
    if text != original:
        n = sum(original.count(s) for s, _ in MAPPINGS)
        total_changes += n
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        rel = os.path.relpath(p, ROOT)
        print(f"  edited {rel}  (changes~{n})")
print(f"TOTAL changes ~{total_changes} across {len(files)} files")
