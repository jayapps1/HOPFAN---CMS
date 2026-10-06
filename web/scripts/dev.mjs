const {AbortSignal}=globalThis;
import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync,existsSync } from "node:fs";
const root=path.resolve(fileURLToPath(new URL("..",import.meta.url)));
const repo=path.dirname(root);
const python=path.join(repo,process.platform==="win32"?".venv/Scripts/python.exe":".venv/bin/python");
const result=spawnSync(python,["-c","import json; from src.config.online_settings import OnlineSettings; s=OnlineSettings.from_environment(); print(json.dumps({'env':s.app_env,'port':s.api_port,'origins':s.cors_origins}))"],{cwd:repo,encoding:"utf8",windowsHide:true});
if(result.status!==0){console.error("Unable to load the API configuration. Check the backend environment.");process.exit(1);}
const config=JSON.parse(result.stdout);
if(config.env!=="development"){console.error("Use this combined launcher only for local development.");process.exit(1);}
const local=path.join(root,".env.local");
const fileOrigin=existsSync(local)?readFileSync(local,"utf8").match(/^NEXT_PUBLIC_API_BASE_URL=(.+)$/m)?.[1].trim().replace(/^["']|["']$/g,""):null;
const origin=process.env.NEXT_PUBLIC_API_BASE_URL||fileOrigin||`http://localhost:${config.port}`;
const expected=`http://localhost:${config.port}`;
if(origin!==expected){console.error("For local development, NEXT_PUBLIC_API_BASE_URL must match "+expected+". Use localhost for both services.");process.exit(1);}
if(!config.origins.includes("http://localhost:3000")){console.error("Allow http://localhost:3000 in the existing API CORS configuration.");process.exit(1);}
let apiProcess,webProcess;let stopping=false;
function stop(child){if(!child)return;if(process.platform==="win32")spawn("taskkill",["/PID",String(child.pid),"/T","/F"],{windowsHide:true,stdio:"ignore"});else child.kill("SIGTERM");}
function shutdown(){if(stopping)return;stopping=true;stop(webProcess);stop(apiProcess);}
process.on("SIGINT",shutdown);process.on("SIGTERM",shutdown);process.on("exit",shutdown);
async function ready(){try{const r=await fetch(origin+"/api/v1/ready",{signal:AbortSignal.timeout(2000)});return r.ok;}catch{return false;}}
if(!await ready()){
  console.log("Starting HOPFAN API at "+origin);
  apiProcess=spawn(python,["run_api.py"],{cwd:repo,stdio:"inherit",windowsHide:true});
  let available=false;
  for(let count=0;count<40;count++){if(await ready()){available=true;break;}if(apiProcess.exitCode!==null)break;await new Promise(resolve=>setTimeout(resolve,500));}
  if(!available){console.error("The API did not become ready. Check PostgreSQL and the existing backend .env.");shutdown();process.exit(1);}
}
console.log("HOPFAN website and portal: http://localhost:3000");
let frontendRunning=false;
try {
  const response=await fetch("http://localhost:3000/login",{signal:AbortSignal.timeout(5000)});
  frontendRunning=response.ok && (await response.text()).includes("HOPFAN");
}catch{ /* A missing frontend will be started below. */ }
if(frontendRunning)console.log("Using the HOPFAN frontend already running on localhost:3000.");
else {
webProcess=spawn(process.execPath,[path.join(root,"node_modules/next/dist/bin/next"),"dev","--hostname","localhost","--port","3000"],{
  cwd:root,stdio:"inherit",windowsHide:true,env:{...process.env,NEXT_PUBLIC_API_BASE_URL:origin}});
webProcess.on("exit",code=>{shutdown();process.exitCode=code??1;});
}
