const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path'),fs=require('node:fs'),os=require('node:os');
const {pathToFileURL}=require('node:url');
const output=fs.mkdtempSync(path.join(os.tmpdir(),'gridmend-energy-check-'));
(async()=>{
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:2});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto(pathToFileURL(path.resolve(__dirname,'../reference/energy-asset-explorer.html')).href);
assert.equal(await page.locator('[data-asset]').count(),6);
for(const id of ['SUB','BESS','PCS','SOLAR','WIND','THERMAL']){
 await page.click(`[data-asset="${id}"]`);assert.equal(await page.locator('[data-part]').count(),id==='SUB'?36:11);
 for(const route of ['PRINT','CNC','FABRICATE','SUPPLIER','ENGINEERED']){
  await page.selectOption('#ss-route',route);
  const count=await page.locator('[data-part]').count();
  assert.equal(count,Number(await page.locator(`#ss-stats [data-route="${route}"] strong`).innerText()));
 }
 await page.click('#ss-reset');await page.check('#ss-explode');await page.uncheck('#ss-explode');
 await page.screenshot({path:path.join(output,id+'.png'),fullPage:true});
}
await page.click('[data-asset="BESS"]');
await page.getByRole('button',{name:'BESS01 · Battery modules and racks',exact:true}).click();
assert.match(await page.locator('#ss-detail').innerText(),/outside this pilot/);
assert.equal(await page.locator('#ss-detail .route-card h3').count(),0);
await page.selectOption('#ss-role','TOOLING_ONLY');assert.equal(await page.locator('[data-part]').count(),2);
await page.getByRole('button',{name:'TOOL01 · Workshop drilling template',exact:true}).click();
assert.match(await page.locator('#ss-detail').innerText(),/Ordinary workshop wood/);
assert.match(await page.locator('#ss-detail').innerText(),/not an installed replacement/);
const pending=page.waitForEvent('download');await page.getByRole('button',{name:'Download component brief (JSON)'}).click();const download=await pending;await download.saveAs(path.join(output,'tool.json'));
const brief=JSON.parse(fs.readFileSync(path.join(output,'tool.json')));assert.equal(brief.asset_view,'BESS');assert.equal(brief.component.application_role,'TOOLING_ONLY');assert.equal(brief.component.asset_applicability.length,5);assert.equal(brief.ai_reconstruction.manufacturing_cad_uri,null);assert.ok(brief.manufacturing_routes.every(r=>r.application_role==='TOOLING_ONLY'));
await page.click('[data-asset="PCS"]');assert.equal(await page.locator('#ss-role').inputValue(),'');assert.match(await page.locator('#ss-detail').innerText(),/Select a component/);
await page.fill('#ss-search','no such part');assert.equal(await page.locator('[data-part]').count(),0);
await page.click('[data-asset="BESS"]');await page.getByRole('button',{name:'BOP02 · External monitoring-sensor bracket',exact:true}).click();
await page.screenshot({path:path.join(output,'selected-desktop.png'),fullPage:true});
await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'selected-mobile.png'),fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
assert.deepEqual(errors,[]);
console.log(JSON.stringify({status:'PASS',output,checks:'six asset views; all route counts; role filter; supplier exclusion; shared IDs; tooling-only export; asset switch clears state; empty search; mobile; no JS errors'}));
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
