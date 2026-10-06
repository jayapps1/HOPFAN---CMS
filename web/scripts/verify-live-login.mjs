// Live localhost login proof. Credentials stay in process memory and are never printed.
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
const web=path.resolve(fileURLToPath(new URL("..",import.meta.url)));const repo=path.dirname(web);
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(web,".playwright");
const { chromium } = await import("@playwright/test");
const result=spawnSync(path.join(repo,".venv/Scripts/python.exe"),["-c","import json; from dotenv import dotenv_values; v=dotenv_values('.env'); print(json.dumps({'email':v.get('SEED_ADMIN_EMAIL') or v.get('SEED_ADMIN_USERNAME'),'password':v.get('SEED_ADMIN_PASSWORD')}))"],{cwd:repo,encoding:"utf8",windowsHide:true});
if(result.status!==0)throw new Error("Unable to load the configured login identity.");
const credentials=JSON.parse(result.stdout);
const browser=await chromium.launch({headless:true});let signedIn=false;
try{
  const page=await browser.newPage();
  for(const endpoint of ["health","ready","version"]){const response=await page.request.get("http://localhost:8000/api/v1/"+endpoint);if(response.status()!==200)throw new Error("API readiness proof failed.");console.log(endpoint+": 200");}
  await page.goto("http://localhost:3000/login");
  await page.getByLabel("Email or username").waitFor();
  await page.getByLabel("Email or username").fill(credentials.email);
  await page.locator('input[name="password"]').fill(credentials.password);
  await page.getByRole("button",{name:"Sign in",exact:true}).click();
  await page.waitForURL("**/portal/dashboard",{timeout:30000});signedIn=true;
  const me=await page.request.get("http://localhost:8000/api/v1/me");if(me.status()!==200)throw new Error("Current user proof failed.");
  console.log("Existing seeded account: browser login and /me passed.");
  await page.reload();await page.getByRole("heading",{name:/Welcome back/}).waitFor();
  console.log("Authenticated page refresh: passed.");
  await page.getByRole("button",{name:"Account menu"}).click();
  await page.getByRole("menuitem",{name:"Sign out",exact:true}).click();
  await page.waitForURL("**/login");signedIn=false;
  if((await page.request.get("http://localhost:8000/api/v1/me")).status()!==401)throw new Error("Logout proof failed.");
  console.log("Logout invalidated the browser session.");
}catch{
  console.error("Live browser login verification failed. No credentials were logged.");process.exitCode=1;
}finally{
  // Do not leave this proof's authenticated session active if an assertion fails.
  if(signedIn){const context=browser.contexts()[0];if(context){const csrf=await context.request.get("http://localhost:8000/api/v1/auth/csrf",{headers:{Origin:"http://localhost:3000"}});if(csrf.ok()){const token=(await csrf.json()).csrf_token;await context.request.post("http://localhost:8000/api/v1/auth/logout",{headers:{Origin:"http://localhost:3000","X-CSRF-Token":token}});}}}
  credentials.password="";await browser.close();
}
