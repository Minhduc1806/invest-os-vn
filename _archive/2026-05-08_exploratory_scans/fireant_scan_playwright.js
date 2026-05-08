const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async()=>{
  const out='outputs/fireant_scan';
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1200}});
  const requests=[]; const responses=[];
  page.on('request', req=>{ requests.push({url:req.url(), method:req.method(), resourceType:req.resourceType(), headers:req.headers()}); });
  page.on('response', async res=>{
    const url=res.url();
    let item={url, status:res.status(), headers:res.headers()};
    if(/api|foreign|flow|stock|market|sector|industry|dashboard|graphql|socket|signalr|ownership|trading/i.test(url)){
      try{
        const ct=res.headers()['content-type']||'';
        if(ct.includes('json') || ct.includes('text')){
          const txt=await res.text(); item.body=txt.slice(0,30000);
        }
      }catch(e){ item.bodyError=String(e); }
    }
    responses.push(item);
  });
  try { await page.goto('https://fireant.vn/dashboard',{waitUntil:'domcontentloaded',timeout:60000}); } catch(e) { fs.writeFileSync(path.join(out,'goto_error.txt'),String(e),'utf8'); }
  await page.waitForTimeout(12000);
  await page.screenshot({path:path.join(out,'dashboard.png'),fullPage:true});
  fs.writeFileSync(path.join(out,'dashboard.html'),await page.content(),'utf8');
  fs.writeFileSync(path.join(out,'dashboard_text.txt'),await page.locator('body').innerText().catch(e=>''),'utf8');
  fs.writeFileSync(path.join(out,'requests.json'),JSON.stringify(requests,null,2),'utf8');
  fs.writeFileSync(path.join(out,'responses.json'),JSON.stringify(responses,null,2),'utf8');
  await browser.close();
})();
