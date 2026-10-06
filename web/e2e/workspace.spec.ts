import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs/promises";
import path from "node:path";
const api="http://localhost:8001";
async function signIn(page: Page, name="admin") {
  await page.goto("/login"); await expect(page.getByLabel("Email or username")).toBeEnabled();
  await page.getByLabel("Email or username").fill(`portal-${name}@example.invalid`);
  await page.locator('input[name="password"]').fill("Portal-Synthetic!2026");
  await page.getByRole("button",{name:"Sign in",exact:true}).click();
  await expect(page).toHaveURL(/portal\/dashboard/);
  await expect(page.locator(".metric-grid")).toBeVisible();
}
async function fixtures(page: Page): Promise<{ ministry_ids: Record<string,string>; member_ids: string[] }> {
  return (await page.request.get(api+"/_test/fixtures")).json();
}
test("global dashboard and member directory use real counts, search and URL pagination",async({page})=>{
  await signIn(page);
  await expect(page.locator(".metric-grid .card").filter({has:page.getByText("Members",{exact:true})}).locator(".metric-value")).toHaveText("36");
  await page.goto("/portal/members"); await expect(page.getByRole("heading",{name:"36 members"})).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(25);
  await page.getByRole("button",{name:"Next",exact:true}).click();
  await expect(page).toHaveURL(/page=2/); await expect(page.locator("tbody tr")).toHaveCount(11);
  await page.reload(); await expect(page.locator("tbody tr")).toHaveCount(11);
  await page.locator('input[name="search"]').fill("PORTAL-PERSON-000"); await page.getByRole("button",{name:"Search",exact:true}).click();
  await expect(page.getByRole("heading",{name:"1 members"})).toBeVisible();
  await page.getByRole("link",{name:/Youth Synthetic000/}).click(); await expect(page.getByRole("heading",{name:"Youth Synthetic000",exact:true,level:1})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Household",exact:true})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Sunday School",exact:true})).toBeVisible();
  expect(await page.locator("main").textContent()).not.toContain("PRIVATE-");
});
test("scoped profiles, configured offices and direct ID tampering stay protected",async({page})=>{
  await signIn(page,"youth"); const data=await fixtures(page);
  await page.goto("/portal/members/"+data.member_ids[0]); await expect(page.getByRole("heading",{name:"Youth Synthetic000",exact:true,level:1})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Household",exact:true})).toHaveCount(0);
  await expect(page.getByRole("heading",{name:"Sunday School",exact:true})).toHaveCount(0);
  await expect(page.locator(".profile-banner .avatar")).toBeVisible();
  await page.goto("/portal/ministries/"+data.ministry_ids.Youth);
  await page.getByRole("button",{name:"Leadership",exact:true}).click();
  await expect(page.getByText("Community Mentor",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Members",exact:true}).click();
  await expect(page.getByRole("heading",{name:"22 members"})).toBeVisible();
  for(const endpoint of ["/members/"+data.member_ids[29],"/ministries/"+data.ministry_ids.Women,
    "/ministries/"+data.ministry_ids.Women+"/members","/ministries/"+data.ministry_ids.Women+"/leadership",
    "/media/member-photo/"+data.member_ids[29],"/dashboard?ministry_id="+data.ministry_ids.Women]){
    expect((await page.request.get(api+"/api/v1"+endpoint)).status()).toBe(403);
  }
  await page.goto("/portal/members/"+data.member_ids[29]);
  await expect(page.getByRole("heading",{name:"Access denied",exact:true})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Youth Synthetic000",exact:true,level:1})).toHaveCount(0);
});
test("ministry switching refreshes data without reloading the authenticated user",async({page})=>{
  await signIn(page,"multi"); await page.goto("/portal/members");
  const select=page.getByLabel("Current workspace");
  await select.selectOption({label:"Youth Ministry"}); await expect(page.getByRole("heading",{name:"22 members"})).toBeVisible();
  let meRequests=0;page.on("request",request=>{if(request.url().endsWith("/api/v1/me"))meRequests++;});
  await select.selectOption({label:"Choir Ministry"}); await expect(page.getByRole("heading",{name:"6 members"})).toBeVisible();
  await expect(page.getByRole("link",{name:/Youth Synthetic000/})).toBeVisible();
  await expect(page.getByRole("link",{name:/Youth Synthetic001/})).toHaveCount(0);
  expect(meRequests).toBe(0);
});
test("global ministry filter, empty results and recoverable request failure",async({page})=>{
  await signIn(page); await page.goto("/portal/members");
  await page.getByLabel("Current workspace").selectOption({label:"Women Ministry"});
  await expect(page.getByRole("heading",{name:"5 members"})).toBeVisible();
  await page.locator('input[name="search"]').fill("no-such-person");await page.getByRole("button",{name:"Search",exact:true}).click();
  await expect(page.getByRole("heading",{name:"No members found",exact:true})).toBeVisible();
  await page.route("**/api/v1/members?**",route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({error:{code:"DATABASE_UNAVAILABLE"}})}));
  await page.getByRole("button",{name:"Clear filters",exact:true}).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("temporarily unavailable");
  await page.unroute("**/api/v1/members?**");await page.getByRole("button",{name:"Try again",exact:true}).click();
  await expect(page.getByRole("heading",{name:"5 members"})).toBeVisible();
});
test("business pages work at every requested width in both themes",async({page})=>{
  test.setTimeout(180_000); await signIn(page); const data=await fixtures(page);
  const directory=path.resolve("../docs/screenshots/online-workspaces");await fs.mkdir(directory,{recursive:true});
  for(const width of [1920,1600,1366,1024,768,390]){
    await page.setViewportSize({width,height:width===390?844:900});
    for(const theme of ["light","dark"]){
      for(const [name,url,heading] of [
        ["members","/portal/members","Members"],["member","/portal/members/"+data.member_ids[0],"Youth Synthetic000"],
        ["ministries","/portal/ministries","Ministries"],["ministry","/portal/ministries/"+data.ministry_ids.Youth,"Youth Ministry"]]){
        await page.goto(url);await page.getByLabel("Colour theme").selectOption(theme);
        await expect(page.getByRole("heading",{name:heading,exact:true,level:1})).toBeVisible();
        await expect(page.locator(".record-state .skeleton")).toHaveCount(0);
        expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
        if(width===390||width===1366)expect((await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa"]).analyze()).violations).toEqual([]);
        await page.screenshot({path:path.join(directory,`${name}_${width}_${theme}.png`),fullPage:true});
      }
    }
  }
});
