const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'outputs', 'browser_financial_pages');
fs.mkdirSync(OUT, { recursive: true });

async function captureCafeF(page, ticker='FPT') {
  const url = `https://cafef.vn/du-lieu/hose/${ticker.toLowerCase()}-bao-cao-tai-chinh.chn`;
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.screenshot({ path: path.join(OUT, `cafef_${ticker}_financial_page.png`), fullPage: true });
  const api = await page.evaluate(async (ticker) => {
    const out = {};
    const url = `/du-lieu/Ajax/PageNew/FileBCTC.ashx?Symbol=${ticker.toLowerCase()}&Type=1&Year=0`;
    const r = await fetch(url, { headers: { accept: 'application/json,text/plain,*/*' } });
    out.status = r.status;
    out.text = await r.text();
    return out;
  }, ticker);
  let data = null;
  try { data = JSON.parse(api.text); } catch(e) { data = { parse_error: String(e), raw: api.text.slice(0, 1000) }; }
  return {
    source: 'CafeF rendered browser + same-origin Ajax', ticker, url,
    title: await page.title(),
    screenshot: `outputs/browser_financial_pages/cafef_${ticker}_financial_page.png`,
    api_status: api.status,
    document_count: data && data.Data ? data.Data.length : 0,
    documents: data && data.Data ? data.Data.slice(0, 20) : data
  };
}

async function captureVietstock(page, ticker='FPT') {
  const url = `https://finance.vietstock.vn/${ticker}/tai-tai-lieu.htm`;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(OUT, `vietstock_${ticker}_documents_page.png`), fullPage: true });
  const tables = await page.$$eval('table', tables => tables.map((table, i) => ({
    index: i,
    text: table.innerText.slice(0, 5000),
    rows: Array.from(table.querySelectorAll('tr')).slice(0, 20).map(tr => Array.from(tr.children).map(td => td.innerText.trim()))
  })));
  const links = await page.$$eval('a', as => as.map(a => ({ text: a.innerText.trim(), href: a.href })).filter(x => /báo cáo|bao cao|financial|pdf|download|tải/i.test((x.text||'') + ' ' + (x.href||''))).slice(0, 100));
  return { source:'Vietstock rendered browser', ticker, url, title: await page.title(), screenshot:`outputs/browser_financial_pages/vietstock_${ticker}_documents_page.png`, table_count: tables.length, tables, links };
}

(async () => {
  const tickers = (process.argv[2] || 'FPT,MWG,VCB,SSI').split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 }, userAgent: 'Mozilla/5.0 invest-os-vn playwright' });
  const results = [];
  for (const t of tickers) {
    const item = { ticker: t };
    try { item.cafef = await captureCafeF(page, t); } catch(e) { item.cafef_error = String(e); }
    try { item.vietstock = await captureVietstock(page, t); } catch(e) { item.vietstock_error = String(e); }
    results.push(item);
  }
  await browser.close();
  const out = { as_of: new Date().toISOString(), results };
  fs.writeFileSync(path.join(ROOT, 'data_live', 'browser_financial_pages.vn.json'), JSON.stringify(out, null, 2), 'utf8');
  console.log(JSON.stringify(out, null, 2).slice(0, 4000));
})();
