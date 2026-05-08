const { chromium } = require('playwright');
const fs = require('fs'); const path=require('path');
(async()=>{
 const out='outputs/fireant_scan'; fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1200}});
 let messages=[];
 page.on('websocket', ws=>{
   messages.push({type:'ws_open',url:ws.url(),ts:Date.now()});
   ws.on('framesent', f=>messages.push({type:'sent',url:ws.url(),payload:f.payload.slice(0,2000),ts:Date.now()}));
   ws.on('framereceived', f=>messages.push({type:'recv',url:ws.url(),payload:f.payload.slice(0,2000),ts:Date.now()}));
 });
 await page.goto('https://fireant.vn/dashboard',{waitUntil:'domcontentloaded',timeout:60000});
 await page.waitForTimeout(20000);
 await page.screenshot({path:path.join(out,'dashboard_ws.png'),fullPage:true});
 fs.writeFileSync(path.join(out,'websocket_frames.json'),JSON.stringify(messages,null,2),'utf8');
 console.log('frames',messages.length);
 for (const m of messages.slice(0,30)) console.log(m.type,m.url,(m.payload||'').slice(0,160).replace(/\n/g,' '));
 await browser.close();
})();
