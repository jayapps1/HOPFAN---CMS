import {test,expect,type Page} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs/promises";
import path from "node:path";
const api="http://localhost:8001";
async function login(page:Page,name="admin"){
  await page.goto("/login");await expect(page.getByLabel("Email or username")).toBeEnabled();
  await page.getByLabel("Email or username").fill(`portal-${name}@example.invalid`);
  await page.locator('input[name="password"]').fill("Portal-Synthetic!2026");
  await page.getByRole("button",{name:"Sign in",exact:true}).click();await expect(page).toHaveURL(/portal\/dashboard/);
}
test("public pages do not bootstrap private auth or leak church records",async({page})=>{
  const privateRequests:string[]=[];page.on("request",request=>{if(/\/api\/v1\/(me|members|auth\/)/.test(request.url()))privateRequests.push(request.url());});
  for(const url of ["/","/about","/leadership","/ministries","/sunday-school","/events","/sermons","/gallery","/contact","/give"]){
    await page.goto(url);await expect(page.getByRole("main")).toBeVisible();
    expect(await page.locator("main").textContent()).not.toContain("PRIVATE-");
  }
  expect(privateRequests).toEqual([]);
  expect((await page.request.get(api+"/api/v1/members")).status()).toBe(401);
  const publicResponse=await page.request.get(api+"/api/v1/public/ministries");
  expect(publicResponse.status()).toBe(200);expect(await publicResponse.text()).not.toContain("member_count");
});
test("CMS drafts, preview and publishing remain separate from the public site",async({page})=>{
  await login(page);await page.goto("/portal/website/pages");
  await page.getByRole("button",{name:"Create content",exact:true}).click();const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Title",{exact:true}).fill("Browser CMS draft");
  await dialog.getByLabel("Public URL name",{exact:true}).fill("browser-cms-draft");
  await dialog.getByLabel("Page content",{exact:true}).fill("<script>PUBLIC-XSS-TEST</script>");
  await dialog.getByRole("button",{name:"Save draft",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Browser CMS draft",exact:true})).toBeVisible();
  expect((await page.request.get(api+"/api/v1/public/pages/browser-cms-draft")).status()).toBe(404);
  const row=page.locator(".cms-content-row").filter({has:page.getByRole("heading",{name:"Browser CMS draft",exact:true})});
  await row.getByRole("button",{name:"Preview",exact:true}).click();await expect(page.getByRole("dialog")).toContainText("PUBLIC-XSS-TEST");await page.getByRole("button",{name:"Close preview",exact:true}).click();
  await row.getByRole("button",{name:"Publish",exact:true}).click();await page.getByRole("dialog").getByRole("button",{name:"Confirm",exact:true}).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(async()=>(await page.request.get(api+"/api/v1/public/pages/browser-cms-draft")).status()).toBe(200);
  await row.getByRole("button",{name:"Unpublish",exact:true}).click();await page.getByRole("dialog").getByRole("button",{name:"Confirm",exact:true}).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(async()=>(await page.request.get(api+"/api/v1/public/pages/browser-cms-draft")).status()).toBe(404);
});
test("visitor and prayer submissions remain private and do not create Members",async({page})=>{
  const before=await(await page.request.get(api+"/api/v1/public/ministries")).json();expect(before.total).toBeGreaterThan(0);
  await page.goto("/new-here");await page.getByLabel("First name",{exact:true}).fill("Browser");await page.getByLabel("Last name (optional)").fill("Inquiry");await page.getByLabel("Email (optional)").fill("browser-inquiry@example.invalid");
  await page.getByRole("button",{name:"Send visit inquiry",exact:true}).click();await expect(page.getByRole("heading",{name:"Thank you for reaching out."})).toBeVisible();
  await page.goto("/prayer-request");await page.getByLabel("Your prayer request",{exact:true}).fill("PRIVATE-BROWSER-PRAYER");
  await page.getByRole("button",{name:"Send prayer request",exact:true}).click();await expect(page.getByRole("heading",{name:"Thank you for reaching out."})).toBeVisible();
  expect(page.url()).not.toContain("PRIVATE-BROWSER-PRAYER");
  await login(page);await page.goto("/portal/visitors");await expect(page.getByRole("heading",{name:"Browser Inquiry",exact:true})).toBeVisible();
  const response=await page.request.get(api+"/api/v1/members");expect((await response.json()).total).toBe(36);
  await page.goto("/portal/prayer-requests");await expect(page.getByText("PRIVATE-BROWSER-PRAYER",{exact:true})).toBeVisible();
  await page.goto("/");expect(await page.locator("main").textContent()).not.toContain("PRIVATE-BROWSER-PRAYER");
});
test("scoped event drafting cannot approve or publish globally",async({page})=>{
  await login(page,"youth");await page.goto("/portal/events");await page.getByRole("button",{name:"Create event",exact:true}).click();const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Title",{exact:true}).fill("Scoped draft event");await dialog.getByLabel("Public URL name",{exact:true}).fill("scoped-draft-event");
  const upcoming=new Date(Date.now()+10*86400000).toISOString().slice(0,16);
  await dialog.getByLabel("Start date and time",{exact:true}).fill(upcoming);await dialog.getByLabel("Event visibility",{exact:true}).selectOption("PUBLIC");
  await dialog.getByRole("button",{name:"Save draft",exact:true}).click();await expect(page.getByRole("heading",{name:"Scoped draft event",exact:true})).toBeVisible();
  const row=page.locator(".cms-content-row").filter({has:page.getByRole("heading",{name:"Scoped draft event",exact:true})});
  await row.getByRole("button",{name:"Submit",exact:true}).click();await page.getByRole("dialog").getByRole("button",{name:"Confirm",exact:true}).click();
  await expect(row.getByText("SUBMITTED",{exact:true})).toBeVisible();await expect(row.getByRole("button",{name:"Publish",exact:true})).toHaveCount(0);
  expect((await page.request.get(api+"/api/v1/public/events/scoped-draft-event")).status()).toBe(404);
});
test("gallery lightbox is keyboard accessible and staging stays unindexed",async({page})=>{
  await page.goto("/gallery/fixture-album");await page.getByRole("button",{name:"View Synthetic fixture image",exact:true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();await page.keyboard.press("Escape");await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await page.locator('meta[name="robots"]').getAttribute("content")).toContain("noindex");
  const robots=await(await page.request.get("/robots.txt")).text();expect(robots).toContain("Disallow: /");
  const sitemap=await(await page.request.get("/sitemap.xml")).text();expect(sitemap).not.toContain("/portal");
});
test("public website remains usable at phone, tablet and desktop widths",async({page})=>{
  test.setTimeout(240000);const directory=path.resolve("../docs/screenshots/public-website");await fs.mkdir(directory,{recursive:true});
  for(const [width,height] of [[1920,1080],[1600,900],[1366,768],[1024,768],[768,1024],[430,932],[390,844]]){
    await page.setViewportSize({width,height});
    for(const [name,url] of [["home","/"],["about","/about"],["ministries","/ministries"],["ministry","/ministries/youth"],["events","/events"],["sermons","/sermons"],["gallery","/gallery/fixture-album"],["prayer","/prayer-request"],["visit","/new-here"],["contact","/contact"]]){
      await page.goto(url);await expect(page.getByRole("main")).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
      if(width===390||width===1366)expect((await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag22aa"]).analyze()).violations).toEqual([]);
      await page.screenshot({path:path.join(directory,`${name}_${width}.png`),fullPage:true});
    }
  }
});
