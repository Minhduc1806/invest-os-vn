const { chromium } = require('playwright');
const fs = require('fs');
(async()=>{
 const out='outputs/fireant_scan';
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1200}});
 let req=[], resp=[];
 page.on('request', r=>req.push({method:r.method(),url:r.url(),postData:r.postData()}));
 page.on('response', async r=>{let url=r.url(); if(url.includes('fireant')) {let text=''; try{text=await r.text()}catch(e){} resp.push({status:r.status(),url,headers:r.headers(),text:text.slice(0,100000)});}});
 await page.goto('https://fireant.vn/dashboard',{waitUntil:'networkidle',timeout:60000});
 // click visible Nước ngoài tabs/buttons
 const els=await page.locator('text=Nước ngoài').all();
 console.log('nuocngoai count', els.length);
 for(let i=0;i<Math.min(els.length,5);i++){ try{ await els[i].click({timeout:3000}); await page.waitForTimeout(5000);}catch(e){console.log('click err',i,e.message)} }
 await page.screenshot({path:out+'/dashboard_foreign_click.png', fullPage:true});
 fs.writeFileSync(out+'/foreign_click_requests.json',JSON.stringify(req,null,2),'utf8');
 fs.writeFileSync(out+'/foreign_click_responses.json',JSON.stringify(resp,null,2),'utf8');
 console.log('req',req.length,'resp',resp.length);
 await browser.close();
})();
