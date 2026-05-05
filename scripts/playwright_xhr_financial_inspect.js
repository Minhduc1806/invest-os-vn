const { chromium } = require('playwright');
const fs = require('fs'); const path=require('path');
const ROOT=path.resolve(__dirname,'..'); const OUT=path.join(ROOT,'data_live');
async function inspect(url,name){
 const browser=await chromium.launch({headless:true}); const page=await browser.newPage({viewport:{width:1440,height:1200}});
 const events=[];
 page.on('request', r=>{ const rt=r.resourceType(); if(['xhr','fetch','document'].includes(rt)) events.push({kind:'request',type:rt,method:r.method(),url:r.url(),postData:r.postData()}); });
 page.on('response', async r=>{ const req=r.request(); const rt=req.resourceType(); if(!['xhr','fetch','document'].includes(rt)) return; const u=r.url(); let text=''; let ctype=''; try{ctype=r.headers()['content-type']||''; if(/json|text|html|javascript/i.test(ctype)) text=(await r.text()).slice(0,5000);}catch(e){} events.push({kind:'response',type:rt,status:r.status(),url:u,contentType:ctype,bodyHead:text}); });
 await page.goto(url,{waitUntil:'networkidle',timeout:90000}).catch(e=>events.push({kind:'goto_error',error:String(e)}));
 await page.waitForTimeout(5000);
 const tables=await page.$$eval('table',ts=>ts.map((t,i)=>({i, id:t.id, class:t.className, text:t.innerText.slice(0,2000), rows:Array.from(t.querySelectorAll('tr')).slice(0,8).map(tr=>Array.from(tr.children).map(td=>td.innerText.trim()))}))).catch(e=>[]);
 const scripts=await page.$$eval('script[src]',ss=>ss.map(s=>s.src)).catch(e=>[]);
 const links=await page.$$eval('a',as=>as.map(a=>({text:a.innerText.trim(),href:a.href})).filter(x=>/báo cáo|bao cao|tài chính|tai chinh|cân đối|ket qua|lưu chuyển|download|pdf|financial/i.test((x.text||'')+' '+(x.href||''))).slice(0,200)).catch(e=>[]);
 await page.screenshot({path:path.join(ROOT,'outputs',`${name}.png`),fullPage:true}).catch(()=>{});
 await browser.close(); return {url,name,title:undefined,events,tables,scripts,links};
}
(async()=>{
 const urls=[
  ['cafef_incsta','https://cafef.vn/du-lieu/bao-cao-tai-chinh/fpt/incsta/2024/2/0/0/ket-qua-hoat-dong-kinh-doanh-cong-ty-co-phan-fpt.chn'],
  ['cafef_bsheet','https://cafef.vn/du-lieu/bao-cao-tai-chinh/fpt/bsheet/2024/2/0/0/can-doi-ke-toan-cong-ty-co-phan-fpt.chn'],
  ['cafef_cashflow','https://cafef.vn/du-lieu/bao-cao-tai-chinh/fpt/cashflow/2024/2/0/0/luu-chuyen-tien-te-cong-ty-co-phan-fpt.chn'],
  ['vietstock_financial','https://finance.vietstock.vn/FPT/tai-chinh.htm'],
  ['vietstock_bctc','https://finance.vietstock.vn/FPT/bao-cao-tai-chinh.htm']
 ];
 const results=[]; for(const [name,url] of urls){ console.error('inspect',name); results.push(await inspect(url,name)); }
 const out={as_of:new Date().toISOString(),results}; fs.writeFileSync(path.join(OUT,'financial_xhr_inspect.vn.json'),JSON.stringify(out,null,2),'utf8'); console.log(JSON.stringify(out,null,2).slice(0,8000));
})();
