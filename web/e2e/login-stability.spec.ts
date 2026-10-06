import {test,expect} from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("wrong credentials remain an authentication error, not a connection error",async({page})=>{
  await page.goto("/login");await expect(page.getByLabel("Email or username")).toBeEnabled();
  await page.getByLabel("Email or username").fill("portal-admin@example.invalid");
  await page.locator('input[name="password"]').fill("Wrong-Synthetic!Password");
  await page.getByRole("button",{name:"Sign in",exact:true}).click();
  await expect(page.locator("#login-error")).toHaveText("Invalid email or password.");
  await expect(page.getByText("Server unavailable",{exact:true})).toHaveCount(0);
});
test("compact login fits the requested desktop and phone sizes in both themes",async({page})=>{
  test.setTimeout(120000);
  for(const [width,height] of [[1920,1080],[1600,900],[1366,768],[1024,768],[768,1024],[430,932],[390,844]]){
    await page.setViewportSize({width,height});await page.goto("/login");await expect(page.getByLabel("Email or username")).toBeEnabled();
    for(const theme of ["light","dark"]){
      await page.getByLabel("Colour theme").selectOption(theme);
      const surface=await page.locator(".login-surface").boundingBox();expect(surface?.width).toBeLessThanOrEqual(1041);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
      if(width===1366||width===390){
        expect(await page.evaluate(()=>document.documentElement.scrollHeight<=window.innerHeight)).toBe(true);
        expect((await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag22aa"]).analyze()).violations).toEqual([]);
      }
    }
  }
});
