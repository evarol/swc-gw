const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}:{}),headless:true,args:['--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1280,height:1600}});await page.context().setOffline(true);
 const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});
 await page.goto('file://'+path.resolve(__dirname,'../index.html')+'#rotation');
 await page.waitForFunction(()=>window.MOTOR_GW?.ready&&MOTOR_GW.experimentKey==='rotation');
 if(await page.locator('#gw-order').isVisible())await page.locator('#gw-order').selectOption('ordered');
 const result=await page.evaluate(()=>{
   const v=MOTOR_GW,n=v.p.length;
   return {experiment:v.experimentKey,nodes:v.trees.map(t=>t.nodes.length),connectors:v.coupling.length,
     distance:v.raw.gw.dGW,matchingMass:v.coupling.reduce((sum,c)=>sum+(c.i===c.j?c.mass:0),0),
     allDiagonal:v.coupling.every(c=>c.i===c.j&&Math.abs(c.mass-1/n)<1e-15),
     equalDisplayDistances:v.D[0].every((x,i)=>Math.abs(x-v.D[1][i])<1e-10),equalDisplayAdjacency:v.A[0].every((x,i)=>Math.abs(x-v.A[1][i])<1e-10),
     labels:[...document.querySelectorAll('.gw-matrix h3')].map(e=>e.textContent),
     matrices:v.charts.map(c=>[c.def.rows,c.def.cols]),
     transformError:Math.max(...v.trees[0].nodes.map((a,i)=>{const b=v.trees[1].nodes[i],c=['x','y','z'].map(axis=>v.trees[0].nodes.reduce((s,r)=>s+r[axis],0)/n);return Math.max(Math.abs(b.x-(2*c[0]-a.x)),Math.abs(b.y-(2*c[1]-a.y)),Math.abs(b.z-a.z));}))};
 });
 assert.deepEqual(result.nodes,[202,202]);assert.equal(result.connectors,202);assert(result.distance<1e-10);
 assert(result.allDiagonal&&result.equalDisplayDistances&&result.equalDisplayAdjacency);assert(result.transformError<1e-10);
 assert(result.labels.filter(x=>x.includes('Ti8 180°')).length===2);assert(result.matrices.every(x=>x[0]===202&&x[1]===202));
 await page.screenshot({path:path.join(__dirname,'rotation-desktop.png'),fullPage:true});
 const plot=page.locator('[data-key="t"] svg');await plot.scrollIntoViewIfNeeded();const box=await plot.boundingBox();
 const geo=await page.evaluate(()=>MOTOR_GW.charts.find(c=>c.def.key==='t').geometry());
 await page.mouse.move(box.x+geo.left+75.5*geo.size/202,box.y+geo.top+75.5*geo.size/202);
 result.matrixHover=await page.evaluate(()=>({selection:MOTOR_GW.getState(),spatial:MOTOR_GW.spatial.inspect().selection,marks:[...document.querySelectorAll('.gw-matrix')].map(e=>({key:e.dataset.key,rows:[...e.querySelectorAll('[data-row]')].map(x=>+x.dataset.row),cols:[...e.querySelectorAll('[data-col]')].map(x=>+x.dataset.col)}))}));
 assert.deepEqual(result.matrixHover.selection.pair,[75,75]);assert.deepEqual(result.matrixHover.spatial.a,[75]);assert.deepEqual(result.matrixHover.spatial.b,[75]);assert(result.matrixHover.marks.every(c=>c.rows.includes(75)&&c.cols.includes(75)));
 await page.locator('#gw-spatial').scrollIntoViewIfNeeded();let picked=null;
 for(const i of [0,20,50,90,130,180]){const p=await page.evaluate(i=>MOTOR_GW.spatial.projectNode(1,i),i);await page.mouse.move(p.x,p.y);const s=await page.evaluate(()=>MOTOR_GW.getState());if(s?.source==='spatial'&&s.explicitB.includes(i)&&!s.pair){picked=s;break;}}
 assert(picked);assert.deepEqual(picked.a,picked.b);result.spatialHover=picked;
 await page.locator('#gw-layout').selectOption('native');assert.equal(await page.evaluate(()=>MOTOR_GW.spatial.inspect().layout),'native');
 await page.locator('#gw-node-a').selectOption('75');await page.screenshot({path:path.join(__dirname,'rotation-native-selected.png'),fullPage:true});
 for(const key of ['original','rotation','original','rotation']){
   await page.locator('#gw-experiment').selectOption(key);await page.waitForFunction(key=>MOTOR_GW.experimentKey===key,key);
   assert.equal(await page.locator('#gw-spatial canvas').count(),1);
   assert.deepEqual(await page.evaluate(()=>MOTOR_GW.trees.map(t=>t.nodes.length)),key==='original'?[202,193]:[202,202]);
   assert.equal(await page.locator('#gw-node-b option').count(),key==='original'?194:203);
 }
 result.switching=true;
 await page.setViewportSize({width:390,height:1600});await page.waitForTimeout(400);
 result.mobile=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,labelsOverflow:document.getElementById('motor-gw-linked').dataset.labelOverflow,canvases:document.querySelectorAll('#gw-spatial canvas').length}));
 assert(result.mobile.scroll<=result.mobile.width);assert.equal(result.mobile.canvases,1);
 result.errors=errors;result.networkRequests=requests;assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
 result.passed=true;fs.writeFileSync(path.join(__dirname,'rotation_browser_check.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify({passed:true,distance:result.distance,nodes:result.nodes,connectors:result.connectors,allDiagonal:result.allDiagonal,switching:result.switching,mobile:result.mobile}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
