const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert'),path=require('path');
(async()=>{
 const browser=await chromium.launch({...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}:{}),headless:true,args:['--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1060,height:1600},deviceScaleFactor:1});
 const external=process.argv[2];
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const requests=[];if(external){await page.context().setOffline(true);page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});}
 await page.goto((external||'http://127.0.0.1:8876/').split('#')[0]+'#original');
 const frame=external?page.mainFrame():page.frames().find(f=>f.parentFrame());
 await frame.waitForFunction(()=>window.MOTOR_GW?.ready,{timeout:60000});
 await frame.locator('#gw-spatial canvas').waitFor();
 await page.screenshot({path:path.join(__dirname,(external?'external-':'')+'desktop.png'),fullPage:true});
 const result=await frame.evaluate(()=>({spatial:MOTOR_GW.spatial.inspect(),matrices:MOTOR_GW.charts.map(c=>({key:c.def.key,rows:c.def.rows,cols:c.def.cols})),metric:document.getElementById('gw-value').textContent}));
 assert.equal(result.matrices.length,5);assert.deepEqual(result.spatial.nodeCounts,[202,193]);assert.equal(result.spatial.connectorCount,394);
 async function hoverMatrix(key,i,j,axis=false,click=false){
   const sv=frame.locator('[data-key="'+key+'"] svg');await sv.scrollIntoViewIfNeeded();
   const box=await sv.boundingBox();const geo=await frame.evaluate(key=>{const c=MOTOR_GW.charts.find(c=>c.def.key===key);return {...c.geometry(),rows:c.def.rows,cols:c.def.cols};},key);
   const x=axis?geo.left-10:geo.left+(j+.5)*geo.size/geo.cols;const y=geo.top+(i+.5)*geo.size/geo.rows;
   await page.mouse.move(box.x+x,box.y+y);if(click)await page.mouse.click(box.x+x,box.y+y);
   return frame.evaluate(()=>({state:MOTOR_GW.getState(),spatial:MOTOR_GW.spatial.inspect().selection,marks:[...document.querySelectorAll('.gw-matrix')].map(e=>({key:e.dataset.key,rows:[...e.querySelectorAll('[data-row]')].map(x=>+x.dataset.row),cols:[...e.querySelectorAll('[data-col]')].map(x=>+x.dataset.col)}))}));
 }
 result.rowHover=await hoverMatrix('da',47,0,true);assert.deepEqual(result.rowHover.state.explicitA,[47]);assert.equal(result.rowHover.state.explicitB.length,0);assert(result.rowHover.spatial.a.includes(47));assert(result.rowHover.marks.find(c=>c.key==='t').rows.includes(47));assert(result.rowHover.marks.find(c=>c.key==='db').rows.length>0);
 result.cellHover=await hoverMatrix('db',20,60);assert.deepEqual(result.cellHover.state.explicitB,[20,60]);assert.equal(result.cellHover.state.metric.name,'Tree distance');assert(result.cellHover.marks.find(c=>c.key==='t').cols.includes(60));
 result.transportHover=await hoverMatrix('t',18,54);assert.deepEqual(result.transportHover.state.pair,[18,54]);assert.deepEqual(result.transportHover.spatial.a,[18]);assert.deepEqual(result.transportHover.spatial.b,[54]);
 result.adjacencyHover=await hoverMatrix('aa',10,12);assert.deepEqual(result.adjacencyHover.state.explicitA,[10,12]);assert.equal(result.adjacencyHover.state.metric.name,'Edge length');
 await hoverMatrix('da',80,81,false,true);await page.mouse.move(5,5);assert(await frame.evaluate(()=>MOTOR_GW.getPinned()?.a.includes(80)));result.pin=true;
 await frame.locator('#gw-node-b').selectOption('33');result.nodeSelector=await frame.evaluate(()=>MOTOR_GW.getState());assert.deepEqual(result.nodeSelector.explicitB,[33]);
 await frame.locator('#gw-layout').selectOption('native');assert.equal(await frame.evaluate(()=>MOTOR_GW.spatial.inspect().layout),'native');
 await frame.locator('#gw-connectors').uncheck();assert.equal(await frame.evaluate(()=>MOTOR_GW.spatial.inspect().connectorsVisible),false);
 await frame.locator('#gw-connectors').check();await frame.locator('#gw-layout').selectOption('separated');await frame.locator('#gw-node-a').selectOption('');
 result.layouts=true;
 await frame.locator('#gw-spatial').scrollIntoViewIfNeeded();
 const canvas=await frame.locator('#gw-spatial canvas').boundingBox();const before=await frame.evaluate(()=>MOTOR_GW.spatial.inspect().cameraPosition);
 await page.mouse.move(canvas.x+canvas.width*.5,canvas.y+canvas.height*.5);await page.mouse.down();await page.mouse.move(canvas.x+canvas.width*.58,canvas.y+canvas.height*.55,{steps:12});await page.mouse.up();await page.waitForTimeout(350);
 result.cameraRotated=JSON.stringify(before)!==JSON.stringify(await frame.evaluate(()=>MOTOR_GW.spatial.inspect().cameraPosition));assert(result.cameraRotated);
 await frame.locator('#gw-layout').selectOption('native');await frame.locator('#gw-layout').selectOption('separated');
 if(await frame.evaluate(()=>typeof MOTOR_GW.spatial.projectNode==='function')){
   let picked=null;
   for(const i of [0,20,50,90,130,180]){const pt=await frame.evaluate(i=>MOTOR_GW.spatial.projectNode(0,i),i);await page.mouse.move(canvas.x+pt.localX,canvas.y+pt.localY);const s=await frame.evaluate(()=>MOTOR_GW.getState());if(s&&s.source==='spatial'&&s.a.includes(i)&&!s.pair){picked={target:i,state:s};break;}}
   assert(picked,'Real 3D node hover must select and cross-link');result.spatialHover=picked;
   let linkPicked=null;
   for(const i of [0,20,60,110,180,260,330]){const pt=await frame.evaluate(i=>MOTOR_GW.spatial.projectConnector(i,.48),i);await page.mouse.move(canvas.x+pt.localX,canvas.y+pt.localY);const s=await frame.evaluate(()=>MOTOR_GW.getState());if(s&&s.source==='spatial'&&s.pair){linkPicked=s;break;}}
   assert(linkPicked,'Real 3D connector hover must cross-link');assert(await frame.evaluate(s=>MOTOR_GW.T[s.pair[0]*193+s.pair[1]]>0,linkPicked));result.connectorHover=linkPicked;
 }
 await page.mouse.move(5,5);
 await page.emulateMedia({colorScheme:'dark'});await page.waitForTimeout(500);await page.screenshot({path:path.join(__dirname,(external?'external-':'')+'dark.png'),fullPage:true});
 await page.emulateMedia({colorScheme:'light'});await page.setViewportSize({width:390,height:1800});await page.waitForTimeout(600);
 result.liveResize=await frame.evaluate(()=>({width:innerWidth,root:document.getElementById('motor-gw-linked').clientWidth,canvas:MOTOR_GW.spatial.inspect().canvasWidth}));assert(result.liveResize.root<=result.liveResize.width);assert(result.liveResize.canvas<=result.liveResize.width);
 await page.reload();
 const mobileFrame=external?page.mainFrame():page.frames().find(f=>f.parentFrame());await mobileFrame.waitForFunction(()=>window.MOTOR_GW?.ready);await page.waitForTimeout(500);
 result.mobile=await mobileFrame.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,rootWidth:document.getElementById('motor-gw-linked').getBoundingClientRect().width,svgCount:document.querySelectorAll('.gw-matrix:not([hidden]) .gw-matrix-svg').length,labelsOverflow:document.getElementById('motor-gw-linked').dataset.labelOverflow,spatial:MOTOR_GW.spatial.inspect()}));
 assert(result.mobile.scrollWidth<=result.mobile.width+1,'No horizontal overflow on mobile');assert(result.mobile.rootWidth<=result.mobile.width);assert.equal(result.mobile.svgCount,5);assert(result.mobile.spatial.canvasWidth<=result.mobile.width);
 await page.screenshot({path:path.join(__dirname,(external?'external-':'')+'mobile.png'),fullPage:true});
 result.errors=errors;assert.deepEqual(errors,[]);result.networkRequests=requests;if(external)assert.deepEqual(requests,[]);result.passed=true;fs.writeFileSync(path.join(__dirname,(external?'external-':'')+'browser_check.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:true,metric:result.metric,spatialHover:!!result.spatialHover,mobile:result.mobile,errors}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
