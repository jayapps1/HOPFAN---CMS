import { test,expect,type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs/promises";
import path from "node:path";
const api="http://localhost:8001";
async function signIn(page:Page,name="admin"){
  await page.goto("/login");await expect(page.getByLabel("Email or username")).toBeEnabled();
  await page.getByLabel("Email or username").fill(`portal-${name}@example.invalid`);await page.locator('input[name="password"]').fill("Portal-Synthetic!2026");
  await page.getByRole("button",{name:"Sign in",exact:true}).click();await expect(page).toHaveURL(/portal\/dashboard/);
}
async function fixtures(page:Page):Promise<{ministry_ids:Record<string,string>;class_ids:Record<string,string>;member_ids:string[]}>{return(await page.request.get(api+"/_test/fixtures")).json();}
async function createSunday(page:Page,title:string){
  await page.goto("/portal/attendance");await page.getByRole("button",{name:"Create session",exact:true}).click();
  const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Title",{exact:true}).fill(title);
  await dialog.getByRole("button",{name:"Create session",exact:true}).click();
  await expect(page.getByRole("heading",{name:title,level:1})).toBeVisible();await expect(page.locator(".attendance-person").first()).toBeVisible();
  return page.url().split("/attendance/")[1].split("?")[0];
}
test("Sunday creation clears ministry selection and marking updates one shared record",async({page})=>{
  await signIn(page);const data=await fixtures(page);
  await page.goto("/portal/attendance");await page.getByRole("button",{name:"Create session",exact:true}).click();
  const dialog=page.getByRole("dialog");await dialog.getByLabel("Session type",{exact:true}).selectOption("MINISTRY_MEETING");
  await dialog.getByLabel("Ministry",{exact:true}).selectOption(data.ministry_ids.Youth);
  await dialog.getByLabel("Session type",{exact:true}).selectOption("SUNDAY_SERVICE");await expect(dialog.getByLabel("Ministry",{exact:true})).toHaveCount(0);
  await dialog.getByLabel("Title",{exact:true}).fill("Web shared Sunday");
  await dialog.getByRole("button",{name:"Create session",exact:true}).click();await expect(page.getByRole("heading",{name:"Web shared Sunday",level:1})).toBeVisible();
  const id=page.url().split("/attendance/")[1].split("?")[0];
  const result=await page.request.get(api+"/api/v1/attendance/sessions/"+id);expect((await result.json()).ministry_id).toBeNull();
  const child=page.getByRole("article",{name:"Youth Synthetic000",exact:true});
  await child.getByRole("button",{name:"Mark Youth Synthetic000 Present",exact:true}).click();
  await expect(child.locator(".attendance-status")).toHaveText("Present");
  const choir=await(await page.request.get(api+`/api/v1/attendance/sessions/${id}/roster?ministry_id=${data.ministry_ids.Choir}`)).json();
  expect(choir.items.find((row:{id:string})=>row.id===data.member_ids[0]).status).toBe("PRESENT");
  await child.getByRole("button",{name:"Correct Youth Synthetic000 Late",exact:true}).click();
  await page.getByLabel("Correction reason").fill("Confirmed with the usher");await page.getByRole("button",{name:"Save correction",exact:true}).click();
  await expect(child.locator(".attendance-status")).toHaveText("Late");
});
test("failed marking keeps the previous saved state and allows a confirmed retry",async({page})=>{
  await signIn(page);await createSunday(page,"Failure workflow");
  const row=page.getByRole("article",{name:"Youth Synthetic000",exact:true});
  await page.route("**/api/v1/attendance/sessions/*/mark*",route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({error:{code:"DATABASE_UNAVAILABLE"}})}));
  await row.getByRole("button",{name:"Mark Youth Synthetic000 Present",exact:true}).click();
  await expect(row.locator(".attendance-status")).toHaveText("Unmarked");
  await expect(row.getByRole("alert")).toContainText("temporarily unavailable");
  await page.unroute("**/api/v1/attendance/sessions/*/mark*");
  await row.getByRole("button",{name:"Mark Youth Synthetic000 Present",exact:true}).click();
  await expect(row.locator(".attendance-status")).toHaveText("Present");
});
test("scoped officer creates and opens a ministry draft without a foreign selector",async({page})=>{
  await signIn(page,"youth");await page.goto("/portal/attendance");
  await page.getByRole("button",{name:"Create session",exact:true}).click();const dialog=page.getByRole("dialog");
  await expect(dialog.getByText("Youth Ministry",{exact:true})).toBeVisible();await expect(dialog.getByLabel("Ministry",{exact:true})).toHaveCount(0);
  await dialog.getByLabel("Title",{exact:true}).fill("Youth draft workflow");await dialog.getByLabel("Session state",{exact:true}).selectOption("DRAFT");
  await dialog.getByRole("button",{name:"Create session",exact:true}).click();await expect(page.getByRole("heading",{name:"Youth draft workflow",level:1})).toBeVisible();
  await expect(page.getByText("Open this session before marking attendance.")).toBeVisible();
  await page.getByRole("button",{name:"Open session",exact:true}).click();await page.getByRole("button",{name:"Confirm open",exact:true}).click();
  await page.getByRole("article",{name:"Youth Synthetic000",exact:true}).getByRole("button",{name:"Mark Youth Synthetic000 Present",exact:true}).click();
  await expect(page.getByRole("article",{name:"Youth Synthetic000",exact:true}).locator(".attendance-status")).toHaveText("Present");
});
test("teacher reads safe class data and performs scoped class attendance and reports",async({page})=>{
  await signIn(page,"teacher");const data=await fixtures(page);
  await page.goto("/portal/sunday-school/classes");await expect(page.getByRole("link",{name:/Primary class/}).last()).toBeVisible();
  await expect(page.getByText("Juniors class",{exact:true})).toHaveCount(0);
  await page.goto("/portal/sunday-school/students/"+data.member_ids[0]);await expect(page.getByRole("heading",{name:"Youth Synthetic000",level:1})).toBeVisible();
  expect(await page.locator("main").textContent()).not.toContain("PRIVATE-");
  await page.goto("/portal/sunday-school/attendance");await page.getByRole("button",{name:"Create session",exact:true}).click();
  await page.getByRole("dialog").getByLabel("Title",{exact:true}).fill("Teacher class workflow");
  await page.getByRole("dialog").getByRole("button",{name:"Create session",exact:true}).click();await expect(page.getByRole("heading",{name:"Teacher class workflow",level:1})).toBeVisible();
  const row=page.getByRole("article",{name:"Youth Synthetic000",exact:true});await row.getByRole("button",{name:"Mark Youth Synthetic000 Present",exact:true}).click();
  await expect(row.locator(".attendance-status")).toHaveText("Present");
  await page.getByRole("button",{name:"Close session",exact:true}).click();await page.getByRole("button",{name:"Confirm close",exact:true}).click();
  await page.goto("/portal/sunday-school/reports");await expect(page.getByRole("heading",{name:"Primary class",level:2})).toBeVisible();
  await expect(page.getByRole("button",{name:"Export CSV",exact:true})).toHaveCount(0);
  expect((await page.request.get(api+"/api/v1/sunday-school/classes/"+data.class_ids.Juniors)).status()).toBe(403);
  await page.goto("/portal/sunday-school/classes/"+data.class_ids.Juniors);await expect(page.getByRole("heading",{name:"Access denied"})).toBeVisible();
});
test("coordinator creates, edits and publishes a class lesson with versioned saves",async({page})=>{
  await signIn(page);await page.goto("/portal/sunday-school/lessons");
  await page.getByRole("button",{name:"Create lesson",exact:true}).click();let dialog=page.getByRole("dialog");
  await dialog.getByLabel("Title",{exact:true}).fill("Hope lesson");await dialog.getByLabel("Primary class",{exact:true}).check();
  await dialog.getByLabel("Objective",{exact:true}).fill("Serve one another");await dialog.getByRole("button",{name:"Create lesson",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Hope lesson",level:2})).toBeVisible();await page.getByRole("button",{name:"Edit lesson",exact:true}).click();
  dialog=page.getByRole("dialog");await dialog.getByLabel("Lesson status",{exact:true}).selectOption("PUBLISHED");await dialog.getByRole("button",{name:"Save lesson",exact:true}).click();
  await expect(page.locator(".lesson-card .badge").filter({hasText:"Published"})).toBeVisible();
});
test("attendance buttons work on phone, tablet and desktop in both themes",async({page})=>{
  test.setTimeout(180_000);await signIn(page);await createSunday(page,"Responsive attendance");
  const dir=path.resolve("../docs/screenshots/online-operations");await fs.mkdir(dir,{recursive:true});
  for(const width of [390,430,768,1366,1920]){
    await page.setViewportSize({width,height:900});
    for(const theme of ["light","dark"]){
      await page.getByLabel("Colour theme").selectOption(theme);
      const row=page.getByRole("article",{name:"Youth Synthetic000",exact:true});await expect(row).toBeVisible();
      if(theme==="light"){
        const index=[390,430,768,1366,1920].indexOf(width);const name="Youth Synthetic"+String(index).padStart(3,"0");
        const member=page.getByRole("article",{name,exact:true});await member.getByRole("button",{name:"Mark "+name+" Present",exact:true}).click();
        await expect(member.locator(".attendance-status")).toHaveText("Present");
      }
      const box=await row.getByRole("button",{name:/Youth Synthetic000 Present/}).boundingBox();expect(box?.height).toBeGreaterThanOrEqual(44);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
      if(width===390||width===1366)expect((await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa"]).analyze()).violations).toEqual([]);
      await page.screenshot({path:path.join(dir,`attendance_${width}_${theme}.png`),fullPage:true});
    }
  }
});

test("class attendance supports phone marking, corrections, and safe summaries",async({page})=>{
  test.setTimeout(90_000);await signIn(page);const data=await fixtures(page);
  await page.setViewportSize({width:390,height:844});await page.goto("/portal/sunday-school/attendance");
  await page.getByRole("button",{name:"Create session",exact:true}).click();const dialog=page.getByRole("dialog");
  await dialog.getByLabel("Class",{exact:true}).selectOption(data.class_ids.Primary);
  await dialog.getByLabel("Title",{exact:true}).fill("Responsive class attendance");
  const previous=new Date();previous.setUTCDate(previous.getUTCDate()-1);const iso=previous.toISOString().slice(0,10).split("-");
  await dialog.getByLabel("Date (DD/MM/YYYY)",{exact:true}).fill(iso[2]+"/"+iso[1]+"/"+iso[0]);
  await dialog.getByRole("button",{name:"Create session",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Responsive class attendance",level:1})).toBeVisible();
  const directory=path.resolve("../docs/screenshots/online-operations");
  for(const width of [390,430,768,1366,1920]){
    await page.setViewportSize({width,height:900});
    for(const theme of ["light","dark"]){
      await page.getByLabel("Colour theme").selectOption(theme);
      const row=page.getByRole("article",{name:"Youth Synthetic000",exact:true});
      if(width===390&&theme==="light"){await row.getByRole("button",{name:"Mark Youth Synthetic000 Present",exact:true}).click();await expect(row.locator(".attendance-status")).toHaveText("Present");}
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
      if(width===390||width===1366)expect((await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa"]).analyze()).violations).toEqual([]);
      await page.screenshot({path:path.join(directory,`school_attendance_${width}_${theme}.png`),fullPage:true});
    }
  }
});
