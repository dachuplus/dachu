import urllib.request, urllib.parse, json, re

def get(url, referer=None, timeout=12):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    if referer:
        req.add_header('Referer', referer)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8','ignore'), resp.status
    except urllib.error.HTTPError as e:
        return f"HTTPError {e.code}: {e.read().decode('utf-8','ignore')[:200]}", e.code
    except Exception as e:
        return f"ERR {e}", None

print("="*72)
print("TEST 1: push2 clist 板块 多周期字段(f104~f116,f160) — 概念板")
fs = 'm:90+t:3'
params = urllib.parse.urlencode({
    'pn':'1','pz':'20','po':'1','np':'1','fltt':'2','invt':'2',
    'fs':fs,
    'fields':'f12,f14,f3,f104,f105,f106,f107,f108,f109,f110,f111,f112,f113,f114,f160',
    'fid':'f3','callback':'cb1'
})
raw, st = get(f'https://push2.eastmoney.com/api/qt/clist/get?{params}')
print(f"  status={st}")
if 'cb1(' in raw:
    m = re.match(r'^cb1\((.*)\)\s*;?$', raw.strip(), re.DOTALL)
    if m:
        d = json.loads(m.group(1))
        diff = d.get('data',{}).get('diff',[])
        for x in diff[:6]:
            print(f"  {x.get('f14')}({x.get('f12')}): f3={x.get('f3')} f104={x.get('f104')} f106={x.get('f106')} f108={x.get('f108')} f110={x.get('f110')} f113={x.get('f113')} f160={x.get('f160')}")
else:
    print(f"  resp: {raw[:200]}")

print("="*72)
print("TEST 2: push2 clist 直接按代码拉 医疗服务(BK000096) 多周期")
params2 = urllib.parse.urlencode({
    'pn':'1','pz':'1','po':'1','np':'1','fltt':'2','invt':'2',
    'fs':'b:BK000096',
    'fields':'f12,f14,f3,f104,f105,f106,f107,f108,f109,f110,f111,f112,f113,f114,f160',
    'fid':'f3','callback':'cb2'
})
raw, st = get(f'https://push2.eastmoney.com/api/qt/clist/get?{params2}')
print(f"  status={st}")
if 'cb2(' in raw:
    m = re.match(r'^cb2\((.*)\)\s*;?$', raw.strip(), re.DOTALL)
    if m:
        d = json.loads(m.group(1))
        diff = d.get('data',{}).get('diff',[])
        for x in diff:
            print(f"  {x.get('f14')}({x.get('f12')}):")
            for k in ['f3','f104','f105','f106','f107','f108','f109','f110','f111','f112','f113','f114','f160']:
                print(f"    {k}={x.get(k)}")
else:
    print(f"  resp: {raw[:200]}")

print("="*72)
print("TEST 3: ZTJJ 医疗(BK000096) 对照值(带fund.eastmoney.com referer)")
params3 = urllib.parse.urlencode({'callback':'zt','tp':'BK000096'})
raw, st = get(f'https://api.fund.eastmoney.com/ztjj/GetBKDetailInfoNew?{params3}', referer='https://fund.eastmoney.com')
print(f"  status={st}")
if 'zt(' in raw:
    m = re.match(r'^zt\((.*)\)\s*;?$', raw.strip(), re.DOTALL)
    if m:
        d = json.loads(m.group(1))
        D = d.get('Data', d.get('data'))
        if isinstance(D, dict):
            print(f"  ZTJJ: D={D.get('D')} W={D.get('W')} M={D.get('M')} Q={D.get('Q')} Y={D.get('Y')} SY={D.get('SY')}")
else:
    print(f"  resp: {raw[:200]}")
