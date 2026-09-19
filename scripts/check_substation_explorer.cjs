const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path'),fs=require('node:fs'),os=require('node:os');
const {pathToFileURL}=require('node:url');
const output=fs.mkdtempSync(path.join(os.tmpdir(),'gridmend-explorer-check-'));
const html=path.resolve(__dirname,'../reference/substation-explorer.html');
(async()=>{
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:2});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto(pathToFileURL(html).href);
assert.equal(await page.locator('[data-part]').count(),36);
const counts={};for(const route of ['PRINT','CNC','FABRICATE','SUPPLIER','ENGINEERED']){
await page.selectOption('#ss-route',route);counts[route]=await page.locator('[data-part]').count();assert.ok(counts[route]>0);
}
await page.click('#ss-reset');await page.selectOption('#ss-family','TX');assert.equal(await page.locator('[data-part]').count(),6);
await page.getByRole('button',{name:'TX05 · External sensor mounting bracket',exact:true}).click();
assert.match(await page.locator('#ss-detail').innerText(),/CNC milling/);assert.match(await page.locator('#ss-detail').innerText(),/Sheet cutting/);assert.match(await page.locator('#ss-detail').innerText(),/Metal additive/);
const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Download component brief (JSON)'}).click();const download=await downloadPromise;await download.saveAs(path.join(output,'gridmend-TX05-brief.json'));
const brief=JSON.parse(require('node:fs').readFileSync(path.join(output,'gridmend-TX05-brief.json')));assert.equal(brief.component.id,'TX05');assert.equal(brief.manufacturing_routes.length,3);assert.equal(brief.ai_reconstruction.manufacturing_cad_uri,null);
await page.getByRole('button',{name:'TX02 · HV / LV bushings',exact:true}).click();assert.match(await page.locator('#ss-detail').innerText(),/outside this pilot/);assert.equal(await page.locator('#ss-detail .route-card h3').count(),0);
await page.selectOption('#ss-route','PRINT');assert.match(await page.locator('#ss-detail').innerText(),/Select a component/);
await page.fill('#ss-search','not-a-part');assert.equal(await page.locator('[data-part]').count(),0);assert.match(await page.locator('#ss-breakdown').innerText(),/No components match/);
await page.click('#ss-reset');await page.getByRole('button',{name:'TX05 · External sensor mounting bracket',exact:true}).click();
await page.screenshot({path:path.join(output,'gridmend-explorer-desktop.png'),fullPage:true});
await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'gridmend-explorer-mobile.png'),fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
assert.deepEqual(errors,[]);console.log(JSON.stringify({counts,output,checks:'PASS: filters, selection, supplier exclusion, empty state, downloaded JSON, mobile width, no JS errors'}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
