const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}:{}),headless:true,args:['--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1280,height:1600}});await page.context().setOffline(true);
 const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});
 await page.goto('file://'+path.resolve(__dirname,'../index.html'));await page.waitForFunction(()=>window.MOTOR_GW?.ready);
 assert.equal(await page.evaluate(()=>MOTOR_GW.experimentKey),'bend_05');assert.equal(await page.evaluate(()=>MOTOR_GW.orderKey),'shuffled_fresh');
 const result={cases:[]};
 const snapshot=()=>page.evaluate(()=>{
   const v=MOTOR_GW,n=v.p.length,matched=v.truth.reduce((s,j,i)=>s+v.T[i*n+j],0);
   return {case:v.experimentKey,order:v.orderKey,run:v.runKey,charts:v.charts.length,nodes:v.trees.map(t=>t.nodes.length),
     truth:v.truth,reportedMatch:v.raw.gw.matchedIdMass,computedMatch:matched,rootIndex:v.trees[1].rootIndex,
     sameOrder:v.trees[1].nodes.every((node,i)=>node.id===v.trees[0].nodes[i].id),
     deltaDMax:Math.max(...v.charts.find(c=>c.def.key==='dd').def.values.map(Math.abs)),
     deltaError:Math.max(...v.charts.find(c=>c.def.key==='dd').def.values.map((x,k)=>{
       const i=Math.floor(k/n),j=k%n;return Math.abs(x-(v.D[1][v.truth[i]*n+v.truth[j]]-v.D[0][k]));})),
     transport:Array.from(v.T),canvases:document.querySelectorAll('#gw-spatial canvas').length};
 });
 let current=await snapshot();assert.equal(current.charts,7);assert(!current.sameOrder);assert(current.rootIndex!==0);assert(current.deltaError<1e-10);assert(Math.abs(current.computedMatch-current.reportedMatch)<1e-12);
 await page.screenshot({path:path.join(__dirname,'deformation-default.png'),fullPage:true});
 // A target row must address the shuffled target index, not the old SWC row.
 async function hover(key,i,j,axis=false){const svg=page.locator('[data-key="'+key+'"] svg');await svg.scrollIntoViewIfNeeded();const box=await svg.boundingBox();const g=await page.evaluate(key=>{const c=MOTOR_GW.charts.find(c=>c.def.key===key);return {...c.geometry(),n:c.def.rows,m:c.def.cols};},key);await page.mouse.move(box.x+(axis?g.left-10:g.left+(j+.5)*g.size/g.m),box.y+g.top+(i+.5)*g.size/g.n);return page.evaluate(()=>({selection:MOTOR_GW.getState(),spatial:MOTOR_GW.spatial.inspect().selection}));}
 result.targetRowHover=await hover('db',33,0,true);assert.deepEqual(result.targetRowHover.selection.explicitB,[33]);assert.deepEqual(result.targetRowHover.spatial.b,[33]);
 result.deltaHover=await hover('dd',80,120);const truth=await page.evaluate(()=>MOTOR_GW.truth);assert.deepEqual(result.deltaHover.selection.a,[80,120]);assert.deepEqual(result.deltaHover.selection.b,[truth[80],truth[120]]);assert.deepEqual(result.deltaHover.spatial.b,[truth[80],truth[120]]);
 // Selecting a poor initialization must really replace transport, not just text.
 const bestTransport=current.transport;await page.locator('#gw-start').selectOption('3');const random=await snapshot();assert.equal(random.run,'3');assert(random.transport.some((x,i)=>x!==bestTransport[i]));assert(random.reportedMatch<.9);result.randomMatch=random.reportedMatch;
 result.randomMismatchCount=await page.evaluate(()=>MOTOR_GW.spatial.inspect().mismatchConnectorCount);assert.equal(result.randomMismatchCount,202-Math.round(202*random.computedMatch));
 await page.screenshot({path:path.join(__dirname,'deformation-random-start.png'),fullPage:true});
 await page.locator('#gw-start').selectOption('best');assert.deepEqual((await snapshot()).transport,bestTransport);
 const knownKeyList=['rotation','bend_isometric','bend_02','bend_05','bend_10','bend_20','bend_40'];
 for(const key of knownKeyList){
   await page.locator('#gw-experiment').selectOption(key);await page.locator('#gw-order').selectOption('ordered');const ordered=await snapshot();assert(ordered.sameOrder);assert.equal(ordered.canvases,1);assert.equal(ordered.charts,7);
   await page.locator('#gw-order').selectOption('shuffled_matched');const shuffled=await snapshot();assert(!shuffled.sameOrder);assert.equal(shuffled.canvases,1);assert(shuffled.deltaError<1e-10);
   for(let i=0;i<202;i++)for(let j=0;j<202;j++)assert(Math.abs(ordered.transport[i*202+j]-shuffled.transport[i*202+shuffled.truth[j]])<1e-12);
   assert(Math.abs(ordered.deltaDMax-shuffled.deltaDMax)<1e-10);
   if(['rotation','bend_isometric'].includes(key)){assert.equal(shuffled.deltaDMax,0);assert(shuffled.reportedMatch>1-1e-12);}
   if(key==='bend_40')assert(shuffled.reportedMatch<.85);
   result.cases.push({key,match:shuffled.reportedMatch,deltaDMax:shuffled.deltaDMax,permutationConsistent:true});
 }
 assert.equal(await page.locator('#gw-study-rows tr').count(),7);
 await page.screenshot({path:path.join(__dirname,'deformation-stress.png'),fullPage:true});
 await page.locator('#gw-order').selectOption('shuffled_fresh');await page.locator('#gw-experiment').selectOption('bend_05');
 await page.locator('#gw-spatial').scrollIntoViewIfNeeded();let picked=null;
 for(const i of [0,33,60,100,160]){const p=await page.evaluate(i=>MOTOR_GW.spatial.projectNode(1,i),i);await page.mouse.move(p.x,p.y);const state=await page.evaluate(()=>MOTOR_GW.getState());if(state?.source==='spatial'&&state.explicitB.includes(i)&&!state.pair){picked=state;break;}}
 assert(picked,'Shuffled-target spatial hover must cross-link');result.spatialHover=picked;
 await page.emulateMedia({colorScheme:'dark'});await page.waitForTimeout(350);await page.screenshot({path:path.join(__dirname,'deformation-dark.png'),fullPage:true});
 await page.setViewportSize({width:390,height:1600});await page.waitForTimeout(350);result.mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,overflow:document.getElementById('motor-gw-linked').dataset.labelOverflow,canvases:document.querySelectorAll('#gw-spatial canvas').length}));
 assert(result.mobile.scrollWidth<=result.mobile.width);assert.equal(result.mobile.overflow,'false');assert.equal(result.mobile.canvases,1);
 await page.screenshot({path:path.join(__dirname,'deformation-mobile.png'),fullPage:true});
 result.errors=errors;result.requests=requests;assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);result.passed=true;
 fs.writeFileSync(path.join(__dirname,'deformation_browser_check.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:true,cases:result.cases,randomMatch:result.randomMatch,mobile:result.mobile}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
