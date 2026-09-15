const {spawnSync}=require('node:child_process');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
for(const [script,args] of [
  ['browser_check.cjs',[pathToFileURL(path.join(root,'index.html')).href]],
  ['rotation_browser_check.cjs',[]],
  ['deformation_browser_check.cjs',[]]
]) {
  const result=spawnSync(process.execPath,[path.join(__dirname,script),...args],{cwd:root,env:process.env,stdio:'inherit'});
  if(result.error)throw result.error;
  if(result.status!==0)process.exit(result.status||1);
}
