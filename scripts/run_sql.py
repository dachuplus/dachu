import os, sys, json, urllib.request

SQL = sys.argv[1] if len(sys.argv) > 1 else None
if not SQL:
    SQL = sys.stdin.read()

PAT = os.environ.get("SUPABASE_PAT")
REF = os.environ.get("SUPABASE_REF") or "tqhtegazxykkqfcpejky"
if not PAT:
    print("SUPABASE_PAT not set", file=sys.stderr); sys.exit(2)

url = f"https://api.supabase.com/v1/projects/{REF}/database/query"
req = urllib.request.Request(url, data=json.dumps({"query": SQL}).encode(),
    headers={"Authorization": f"Bearer {PAT}",
             "Content-Type": "application/json",
             "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode()
        print("HTTP", r.status)
        print(body)
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(e.read().decode())
    sys.exit(1)
