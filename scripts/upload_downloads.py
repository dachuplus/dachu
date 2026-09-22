#!/usr/bin/env python3
"""
上传「数据下载中心」的导出文件到 Supabase Storage 私有桶 `downloads`。

背景（2026-09-22）：
    这些 xlsx 原先直接放在 public/downloads/，由 EdgeOne Pages 静态托管。
    但静态托管会绕过前端路由守卫 —— 任何人都能直接 curl 到文件（实测匿名 200）。
    现在改为：文件进 Supabase 私有桶，读取权限由 storage.objects 上的 RLS 策略
    （public.can_read_downloads()）判定，只有「注册登录 + 已开通管理员权限」的用户
    才能通过 createSignedUrl 拿到临时下载地址。

上传通道（自动选择，无需手工指定）：
    - direct：直连 https://<ref>.supabase.co（GitHub Actions / 正常网络走这条，最快）
    - proxy ：经同域 EdgeOne 函数 https://dachu.me/api/sb-proxy 转发
              （本机开发沙箱屏蔽了 *.supabase.co 的 TLS，只能走这条）

⚠️ EdgeOne Pages Functions 的请求体上限是 5 MB（实测 4.69 MB 通过、5.38 MB 返回 545）。
   因此大于 SINGLE_PUT_MAX 的文件改用 TUS 分片续传（/storage/v1/upload/resumable），
   每片 3 MB，逐片 PATCH，既绕过上限也不受单次超时影响。

增量策略：
    先用 list 接口拉取桶内对象的 metadata，比对 size + eTag(即 md5)。
    一致就跳过，只上传变化的文件 —— 每晚 20+ MB 的导出不必重复发送。

用法：
    python scripts/upload_downloads.py                      # 源目录 exports/downloads
    python scripts/upload_downloads.py --dry-run            # 只看会传哪些
    python scripts/upload_downloads.py --only fund_scores.xlsx,index.json
    python scripts/upload_downloads.py --endpoint proxy     # 强制走同域代理
    python scripts/upload_downloads.py --force              # 忽略增量比对，全部重传
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PROJECT_REF = os.environ.get('SUPABASE_PROJECT_REF', 'tqhtegazxykkqfcpejky')
SUPABASE_DIRECT = f'https://{PROJECT_REF}.supabase.co'
DEFAULT_PROXY = 'https://dachu.me/api/sb-proxy'
DEFAULT_BUCKET = 'downloads'
DEFAULT_SOURCE = 'exports/downloads'

# EdgeOne Pages Functions 请求体上限 5 MB（实测边界 4.69 OK / 5.38 挂）。
# 单次直传留足余量；超过则走 TUS 分片。
SINGLE_PUT_MAX = 4 * 1024 * 1024
# TUS 分片大小：同样留足余量
CHUNK_SIZE = 3 * 1024 * 1024

XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
UA = 'dachu-upload-downloads/1.0'

SKIP_NAMES = {'.DS_Store', 'Thumbs.db'}

# 增量比对清单：放在桶内，记录每个对象的 md5。
# 为什么不直接用对象的 eTag 做比对：TUS 分片上传（>4MB 的文件）在 S3 侧是多段上传，
# eTag 形如 "<md5>-<段数>"，与文件本身的 md5 不同，无法比对（实测 fund_scores.xlsx）。
MANIFEST_NAME = '_manifest.json'


# --------------------------------------------------------------------------- #
# 凭据
# --------------------------------------------------------------------------- #
def resolve_service_key() -> str:
    """service_role key：优先环境变量，否则用 Management API 取。"""
    for var in ('SUPABASE_SERVICE_ROLE_KEY', 'SUPABASE_SERVICE_KEY'):
        v = (os.environ.get(var) or '').strip()
        if v:
            return v

    pat = (os.environ.get('SUPABASE_PAT') or os.environ.get('SUPABASE_MGMT_TOKEN') or '').strip()
    if not pat:
        raise SystemExit(
            '缺少凭据：请设置 SUPABASE_SERVICE_ROLE_KEY，或 SUPABASE_PAT / SUPABASE_MGMT_TOKEN'
        )
    url = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/api-keys'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {pat}', 'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        keys = json.loads(resp.read().decode())
    for k in keys:
        if k.get('name') == 'service_role' and k.get('api_key'):
            return k['api_key']
    raise SystemExit('Management API 未返回 service_role key')


# --------------------------------------------------------------------------- #
# 通道
# --------------------------------------------------------------------------- #
class Channel:
    """把「相对路径」翻译成最终请求 URL；direct / proxy 两种模式。"""

    def __init__(self, mode: str, proxy_url: str):
        self.mode = mode
        self.proxy_url = proxy_url

    @staticmethod
    def _probe(url: str, key: str, timeout: float = 6.0) -> bool:
        req = urllib.request.Request(
            url + '/storage/v1/bucket',
            headers={'apikey': key, 'Authorization': f'Bearer {key}', 'User-Agent': UA},
        )
        try:
            urllib.request.urlopen(req, timeout=timeout)
            return True
        except urllib.error.HTTPError:
            # 401/400 也说明链路是通的（能拿到 HTTP 响应）
            return True
        except Exception:
            return False

    @classmethod
    def create(cls, mode: str, proxy_url: str, key: str) -> 'Channel':
        if mode == 'auto':
            if cls._probe(SUPABASE_DIRECT, key):
                print('通道：direct（直连 Supabase）')
                return cls('direct', proxy_url)
            print('通道：proxy（直连不可达，改走同域代理）')
            return cls('proxy', proxy_url)
        print(f'通道：{mode}')
        return cls(mode, proxy_url)

    def url(self, path: str) -> str:
        """path 形如 /storage/v1/object/downloads/x.xlsx"""
        if path.startswith('http://') or path.startswith('https://'):
            parsed = urllib.parse.urlparse(path)
            path = parsed.path + (('?' + parsed.query) if parsed.query else '')
        if self.mode == 'proxy':
            return f'{self.proxy_url}?path={urllib.parse.quote(path, safe="")}'
        return SUPABASE_DIRECT + path


def _open(url: str, key: str, method: str = 'GET', data: bytes | None = None,
          extra: dict | None = None, timeout: int = 120):
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'User-Agent': UA,
    }
    if extra:
        headers.update(extra)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


# --------------------------------------------------------------------------- #
# 桶内清单
# --------------------------------------------------------------------------- #
def list_bucket(ch: Channel, key: str, bucket: str) -> dict:
    """返回 {object_name: {'size': int, 'etag': str}}"""
    url = ch.url(f'/storage/v1/object/list/{bucket}')
    payload = json.dumps({'prefix': '', 'limit': 1000, 'offset': 0,
                          'sortBy': {'column': 'name', 'order': 'asc'}}).encode()
    try:
        with _open(url, key, 'POST', payload, {'Content-Type': 'application/json'}) as resp:
            items = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f'⚠️ 列桶失败（{e.code}）：{e.read().decode()[:200]}')
        return {}
    out = {}
    for it in items:
        if not isinstance(it, dict) or not it.get('name'):
            continue
        md = it.get('metadata') or {}
        etag = (md.get('eTag') or '').strip('"')
        out[it['name']] = {'size': md.get('size'), 'etag': etag}
    return out


# --------------------------------------------------------------------------- #
# 上传
# --------------------------------------------------------------------------- #
def md5_of(path: str) -> tuple[str, int]:
    h = hashlib.md5()
    size = 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
            size += len(b)
    return h.hexdigest(), size


def put_single(ch: Channel, key: str, bucket: str, name: str, data: bytes, mime: str) -> None:
    url = ch.url(f'/storage/v1/object/{bucket}/{urllib.parse.quote(name)}')
    with _open(url, key, 'POST', data,
               {'Content-Type': mime, 'x-upsert': 'true', 'Content-Length': str(len(data))}) as resp:
        resp.read()


def put_resumable(ch: Channel, key: str, bucket: str, name: str, data: bytes, mime: str) -> None:
    b64 = lambda s: base64.b64encode(s.encode()).decode()
    meta = ','.join([
        f'bucketName {b64(bucket)}',
        f'objectName {b64(name)}',
        f'contentType {b64(mime)}',
        f'cacheControl {b64("3600")}',
    ])
    init_url = ch.url('/storage/v1/upload/resumable')
    with _open(init_url, key, 'POST', b'', {
        'Tus-Resumable': '1.0.0',
        'Upload-Length': str(len(data)),
        'Upload-Metadata': meta,
        'x-upsert': 'true',
    }, timeout=60) as resp:
        location = resp.headers.get('Location')
        resp.read()
    if not location:
        raise RuntimeError('TUS 初始化未返回 Location')

    patch_url = ch.url(location)  # proxy 模式下这里会把绝对 URL 再折回代理
    offset = 0
    while offset < len(data):
        chunk = data[offset:offset + CHUNK_SIZE]
        with _open(patch_url, key, 'PATCH', chunk, {
            'Tus-Resumable': '1.0.0',
            'Upload-Offset': str(offset),
            'Content-Type': 'application/offset+octet-stream',
            'Content-Length': str(len(chunk)),
        }, timeout=120) as resp:
            server_offset = resp.headers.get('Upload-Offset')
            resp.read()
        offset = int(server_offset) if server_offset else offset + len(chunk)


def mime_for(name: str) -> str:
    return 'application/json' if name.endswith('.json') else XLSX_MIME


def delete_object(ch: Channel, key: str, bucket: str, name: str) -> None:
    url = ch.url(f'/storage/v1/object/{bucket}/{urllib.parse.quote(name)}')
    with _open(url, key, 'DELETE') as resp:
        resp.read()


def _with_retry(fn, name: str, attempts: int = 3) -> None:
    """小文件直传的重试：经 EdgeOne 代理时偶发 upstream timeout(502)，重试 2 次即可。"""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code not in (429, 500, 502, 503, 504):
                raise
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
    raise last  # type: ignore[misc]


def put_large(ch: Channel, key: str, bucket: str, name: str, data: bytes, mime: str) -> None:
    """
    大文件走 TUS 分片。SUPABASE 的 TUS 初始化在「同名对象已存在」或
    「上一轮留下未完成的 uploading 会话」时会返回 409 The resource already exists，
    此时删掉旧对象再重试一次即可（源文件在本地/CI，可重传，无数据风险）。
    """
    try:
        put_resumable(ch, key, bucket, name, data, mime)
        return
    except urllib.error.HTTPError as e:
        if e.code != 409:
            raise
        try:
            e.read()
        except Exception:
            pass
        print(f'    ↻ {name} 已存在同名对象/残留会话，删除后重传')
    delete_object(ch, key, bucket, name)
    put_resumable(ch, key, bucket, name, data, mime)


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def read_manifest(ch: Channel, key: str, bucket: str) -> dict:
    # 必须带缓存破坏参数：经同域代理读取时，EdgeOne CDN 会缓存 GET 响应，
    # 否则会读到上一轮的旧清单（实测：写入了 29 条，读回来还是 2 条）。
    bust = int(time.time() * 1000)
    url = ch.url(f'/storage/v1/object/{bucket}/{MANIFEST_NAME}?t={bust}')
    try:
        with _open(url, key, 'GET', None, {'Cache-Control': 'no-cache'}) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return {'generated_at': None, 'files': {}}
    if not isinstance(data, dict) or not isinstance(data.get('files'), dict):
        return {'generated_at': None, 'files': {}}
    return data


def write_manifest(ch: Channel, key: str, bucket: str, manifest: dict) -> None:
    manifest['generated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    body = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True).encode()
    put_single(ch, key, bucket, MANIFEST_NAME, body, 'application/json')


def is_up_to_date(name: str, md5: str, size: int, manifest: dict, remote: dict) -> bool:
    """已是最新？优先看清单里的 md5；清单没有时退化为比对 eTag（且必须是纯 md5 形态）。"""
    entry = (manifest.get('files') or {}).get(name)
    if entry:
        return entry.get('md5') == md5 and entry.get('size') == size
    cur = remote.get(name) or {}
    etag = cur.get('etag') or ''
    return bool(etag) and etag == md5 and cur.get('size') == size


def main() -> int:
    ap = argparse.ArgumentParser(description='上传下载中心导出文件到 Supabase 私有桶')
    ap.add_argument('--source-dir', default=DEFAULT_SOURCE)
    ap.add_argument('--bucket', default=DEFAULT_BUCKET)
    ap.add_argument('--endpoint', choices=['auto', 'direct', 'proxy'], default='auto')
    ap.add_argument('--proxy-url', default=os.environ.get('DACHU_PROXY_URL', DEFAULT_PROXY))
    ap.add_argument('--only', default='', help='只上传指定文件名，逗号分隔')
    ap.add_argument('--force', action='store_true', help='忽略增量比对')
    ap.add_argument('--prune', action='store_true', help='删除桶内源目录已不存在的对象')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    src = args.source_dir
    if not os.path.isdir(src):
        print(f'❌ 源目录不存在：{src}')
        return 2

    names = sorted(n for n in os.listdir(src)
                   if not n.startswith('.') and n not in SKIP_NAMES
                   and os.path.isfile(os.path.join(src, n)))
    if args.only:
        want = {x.strip() for x in args.only.split(',') if x.strip()}
        names = [n for n in names if n in want]
    if not names:
        print('没有待上传文件')
        return 0

    key = resolve_service_key()
    ch = Channel.create(args.endpoint, args.proxy_url, key)

    existing = {} if args.force else list_bucket(ch, key, args.bucket)
    manifest = {} if args.force else read_manifest(ch, key, args.bucket)
    mf_files = dict(manifest.get('files') or {})
    if not args.force:
        print(f'桶内对象 {len(existing)} 个，清单记录 {len(mf_files)} 条')

    uploaded, skipped, failed = [], [], []
    total_bytes = 0
    mf_dirty = False
    t_all = time.time()

    for name in names:
        path = os.path.join(src, name)
        md5, size = md5_of(path)
        if (not args.force) and is_up_to_date(name, md5, size, manifest, existing):
            skipped.append(name)
            entry = mf_files.get(name) or {}
            if entry.get('md5') != md5 or entry.get('size') != size:
                # 清单缺这条（首次引入清单时桶里已有对象）→ 补录，下次比对就走 md5
                mf_files[name] = {'md5': md5, 'size': size, 'uploaded_at': None}
                mf_dirty = True
            print(f'  · 跳过 {name}（未变化 {size / 1048576:.2f} MB）')
            continue
        if args.dry_run:
            uploaded.append(name)
            print(f'  → 待传 {name}（{size / 1048576:.2f} MB）')
            continue

        with open(path, 'rb') as f:
            data = f.read()
        ch_size = 'single' if size <= SINGLE_PUT_MAX else 'tus'
        t0 = time.time()
        try:
            if ch_size == 'single':
                _with_retry(lambda: put_single(ch, key, args.bucket, name, data, mime_for(name)), name)
            else:
                put_large(ch, key, args.bucket, name, data, mime_for(name))
            dt = time.time() - t0
            uploaded.append(name)
            total_bytes += size
            mf_files[name] = {
                'md5': md5,
                'size': size,
                'uploaded_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            }
            print(f'  ✓ {name}  {size / 1048576:.2f} MB  [{ch_size}]  {dt:.1f}s')
        except urllib.error.HTTPError as e:
            failed.append(name)
            body = ''
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            print(f'  ✗ {name}  HTTP {e.code}  {body}')
        except Exception as e:  # noqa: BLE001
            failed.append(name)
            print(f'  ✗ {name}  {type(e).__name__}: {e}')

    # 清单落库：仅在确有变化时写回，避免每晚多一次无意义写入
    if args.prune and not args.dry_run:
        keep = set(names) | {MANIFEST_NAME}
        stale = [n for n in existing if n not in keep]
        for n in stale:
            try:
                delete_object(ch, key, args.bucket, n)
                mf_files.pop(n, None)
                mf_dirty = True
                print(f'  − 清理陈旧对象 {n}')
            except Exception as e:  # noqa: BLE001
                print(f'  ⚠️ 清理 {n} 失败：{e}')

    # 清单落库：仅在确有变化时写回，避免每晚多一次无意义写入
    if (uploaded or mf_dirty) and not args.dry_run:
        write_manifest(ch, key, args.bucket, {'files': mf_files})
        print(f'  · 已更新桶内清单 {MANIFEST_NAME}（{len(mf_files)} 条）')

    print('')
    print(f'完成：上传 {len(uploaded)} 个（{total_bytes / 1048576:.2f} MB）、'
          f'跳过 {len(skipped)} 个、失败 {len(failed)} 个，用时 {time.time() - t_all:.1f}s')
    if failed:
        print('失败清单：' + ', '.join(failed))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
