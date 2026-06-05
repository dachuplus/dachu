/**
 * 补充导入 fund_scores（从索引 13554 开始）
 */
import fs from 'fs';
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co';
const ANON_KEY = process.env.SUPABASE_ANON_KEY || 'YOUR_ANON_KEY';
const MGMT_TOKEN = process.env.SUPABASE_MGMT_TOKEN || 'YOUR_MGMT_TOKEN';
const MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query';

const FT_MAP = { gp:'股票型基金', zq:'债券型基金', hh:'混合型基金', fof:'FOF', qdii:'QDII基金' };

function _float(v) { if (!v || String(v).trim()==='') return 0; return parseFloat(v)||0; }
function esc(s) { return s==null ? "''" : "'"+String(s).replace(/\\/g,'\\\\').replace(/'/g,"''")+"'"; }
function escNum(v) {
  if (v==null||v===0||isNaN(v)) return 'NULL';
  const n=parseFloat(v);
  if (!isFinite(n)||Math.abs(n)>999999) return 'NULL';
  return n.toFixed(4);
}

async function runSQL(sql) {
  const resp = await fetch(MGMT_API, {
    method:'POST',
    headers:{'Authorization':`Bearer ${MGMT_TOKEN}`,'Content-Type':'application/json'},
    body:JSON.stringify({query:sql}),
    signal:AbortSignal.timeout(60000)
  });
  if (!resp.ok) { const e=await resp.text(); throw new Error(`SQL ${resp.status}: ${e.substring(0,200)}`); }
  return resp.json();
}

async function fetchFunds(ft) {
  const all=[];
  for (let pi=1;pi<=4;pi++) {
    const url=`https://fund.eastmoney.com/data/FundGuideapi.aspx?dt=0&ft=${ft}&sd=&ed=&sc=3nzf&st=desc&pi=${pi}&pn=5000&zf=diy&sh=list`;
    try {
      const r=await fetch(url,{headers:{'User-Agent':'Mozilla/5.0','Referer':'https://fund.eastmoney.com/'},signal:AbortSignal.timeout(15000)});
      const t=await r.text();
      const s=t.indexOf('{'),e=t.lastIndexOf('}')+1;
      if(s<0||e<=s)break;
      const d=JSON.parse(t.substring(s,e)),items=d.datas||[],tc=parseInt(d.datacount)||0;
      for(const item of items){const f=item.split(',');if(f.length<17)continue;
        all.push({c:f[0].trim()+'.OF',n:(f[1]||'').trim(),t0:FT_MAP[ft],t1:(f[3]||'').trim()||FT_MAP[ft],t2:(f[3]||'').trim(),t6:'',a:0,hp:0,
          ytd:_float(f[4]),r0w:_float(f[5]),r1m:_float(f[6]),r3m:_float(f[7]),r6m:_float(f[8]),r1y:_float(f[9]),r2y:_float(f[10]),r3y:_float(f[11]),r5y:_float(f[12]),nav:_float(f[16]),date:(f[15]||'').trim()});
      }
      if(all.length>=tc||items.length<5000)break;
    }catch(e){break;}
    await new Promise(r=>setTimeout(r,300));
  }
  return all;
}

// Simple score calc
function calcScores(funds) {
  const periods=[{k:'k1',r:'r1y'},{k:'k2',r:'r2y'},{k:'k3',r:'r3y'},{k:'k5',r:'r5y'}];
  for(const p of periods){
    const valid=funds.filter(f=>(f[p.r]||0)>0);
    if(!valid.length)continue;
    const vn=valid.length;
    const ranked=[...valid].sort((a,b)=>(b[p.r]||0)-(a[p.r]||0));
    ranked.forEach((f,rank)=>{f[p.k]=Math.round((vn>1?(1-rank/(vn-1))*100:50)*10000)/10000;});
  }
}

(async()=>{
  console.log('Fetching all funds...');
  let all=[];
  for(const ft of Object.keys(FT_MAP)){const f=await fetchFunds(ft);all=all.concat(f);await new Promise(r=>setTimeout(r,200));}
  const deduped={};for(const f of all)deduped[f.c]=f;
  all=Object.values(deduped);
  for(const f of all){f.k1=0;f.k2=0;f.k3=0;f.k5=0;f.k7=0;f.k10=0;f.dd1y=null;f.dd2y=null;f.dd3y=null;f.dd5y=null;f.sr1y=null;f.sr2y=null;f.sr3y=null;f.sr5y=null;}
  calcScores(all);

  // Get existing codes
  const existing = await runSQL("SELECT c FROM fund_scores");
  const existingSet = new Set(existing.map(r=>r.c));
  const toInsert = all.filter(f=>!existingSet.has(f.c));
  console.log(`Existing: ${existingSet.size}, To insert: ${toInsert.length}`);

  if(!toInsert.length){console.log('Nothing to insert');return;}

  const BATCH=200;let imported=0;
  const cols='c,n,t0,t1,t2,t6,a,hp,ytd,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,nav,date,k1,k2,k3,k5,k7,k10,dd1y,dd2y,dd3y,dd5y,sr1y,sr2y,sr3y,sr5y';
  for(let i=0;i<toInsert.length;i+=BATCH){
    const batch=toInsert.slice(i,i+BATCH);
    const values=batch.map(r=>`(${[esc(r.c),esc(r.n),esc(r.t0),esc(r.t1),esc(r.t2),esc(r.t6),r.a||0,escNum(r.hp),escNum(r.ytd),escNum(r.r0w),escNum(r.r1m),escNum(r.r3m),escNum(r.r6m),escNum(r.r1y),escNum(r.r2y),escNum(r.r3y),escNum(r.r5y),escNum(r.nav),esc(r.date),escNum(r.k1),escNum(r.k2),escNum(r.k3),escNum(r.k5),escNum(r.k7),escNum(r.k10),escNum(r.dd1y),escNum(r.dd2y),escNum(r.dd3y),escNum(r.dd5y),escNum(r.sr1y),escNum(r.sr2y),escNum(r.sr3y),escNum(r.sr5y)].join(',')})`).join(',\n');
    try{await runSQL(`INSERT INTO fund_scores (${cols}) VALUES\n${values}`);imported+=batch.length;console.log(`  +${batch.length} (total ${imported})`);}
    catch(e){console.error(`  ERR at ${i}: ${e.message.substring(0,80)}`);}
    await new Promise(r=>setTimeout(r,200));
  }
  console.log(`Done! Inserted ${imported}, total ${existingSet.size+imported}`);
})();
