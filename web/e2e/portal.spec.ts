import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs/promises";
import path from "node:path";

const api = "http://localhost:8001";
const password = "Portal-Synthetic!2026";
const screenshotDirectory = path.resolve("../docs/screenshots/portal");
async function login(page: Page, name = "admin") {
  await page.goto("/login");
  await expect(page.getByLabel("Email or username")).toBeEnabled();
  await page.getByLabel("Email or username").fill(`portal-${name}@example.invalid`);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/portal\/dashboard/);
  await expect(page.getByRole("heading", { name: /Welcome back/ })).toBeVisible();
}
async function screenshot(page: Page, name: string) {
  await fs.mkdir(screenshotDirectory, { recursive: true });
  await page.mouse.move(0,0);
  await page.screenshot({ path: path.join(screenshotDirectory, name+".png"), fullPage: true });
}

test("unauthenticated routes hide protected content and redirect", async ({ page }) => {
  await page.goto("/portal/members");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Welcome back", exact: true })).toBeVisible();
});

test("password login, persistent shell navigation, HttpOnly cookies and logout", async ({ page }) => {
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.name));
  await login(page);
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link", { name: "Members", exact: true })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Administration", exact: true })).toBeVisible();
  const cookie = (await page.context().cookies()).find(value => value.name === "hopfan_session");
  expect(cookie?.httpOnly).toBe(true);
  expect(await page.evaluate(() => document.cookie)).not.toContain("hopfan_session=");
  expect(await page.evaluate(() => Object.entries(localStorage).every(([key,value]) => key === 'hopfan-theme' && ['light','dark','system'].includes(value)))).toBe(true);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  await page.evaluate(() => { document.querySelector('.desktop-sidebar')?.setAttribute('data-persistence-check', 'kept'); });
  await nav.getByRole("link", { name: "Members", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Members", exact: true })).toBeVisible();
  await expect(page.locator('.desktop-sidebar')).toHaveAttribute('data-persistence-check', 'kept');
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login/);
  expect((await page.request.get(api+"/api/v1/me")).status()).toBe(401);
  expect(errors).toEqual([]);
});

test("repeated sign-in clicks create a single authentication request", async ({ page }) => {
  await page.goto('/login'); await expect(page.getByLabel('Email or username')).toBeEnabled();
  await page.getByLabel('Email or username').fill('portal-admin@example.invalid');
  await page.locator('input[name="password"]').fill(password);
  let submissions = 0; page.on('request', request => { if (request.url().endsWith('/auth/password-login')) submissions += 1; });
  await page.locator('button[type="submit"]').evaluate(element => { (element as HTMLButtonElement).click(); (element as HTMLButtonElement).click(); });
  await expect(page).toHaveURL(/\/portal\/dashboard/);
  expect(submissions).toBe(1);
});

test("authenticator paste auto-submits once without a password", async ({ page }) => {
  await page.goto("/login"); await expect(page.getByLabel("Email or username")).toBeEnabled();
  await page.getByRole("tab", { name: "Authenticator" }).click();
  await page.getByLabel("Email or username").fill("portal-youth@example.invalid");
  await expect(page.locator('input[name="password"]')).toHaveCount(0);
  const code: { code: string } = await (await page.request.get(api+"/_test/totp")).json();
  let submissions = 0; page.on("request", request => { if (request.url().endsWith("/auth/totp-login")) submissions += 1; });
  await page.getByLabel("Digit 1 of 6").evaluate((element, value) => {
    const clipboardData = new DataTransfer(); clipboardData.setData('text/plain', value);
    element.dispatchEvent(new ClipboardEvent('paste', { clipboardData, bubbles: true, cancelable: true }));
  }, code.code);
  await expect(page).toHaveURL(/\/portal\/dashboard/);
  expect(submissions).toBe(1);
  expect(await page.evaluate(() => Object.values(localStorage).some(value => /[0-9]{6}/.test(value)))).toBe(false);
});

test("permission navigation and direct backend ministry isolation", async ({ page }) => {
  await login(page, "youth");
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav.getByRole("link", { name: "Administration" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Finance" })).toHaveCount(0);
  await expect(page.getByText("Youth Ministry", { exact: true }).first()).toBeVisible();
  await page.goto("/portal/administration");
  await expect(page.getByRole("heading", { name: "Access denied" })).toBeVisible();
  const data: { ministry_ids: Record<string, string> } = await (await page.request.get(api+"/_test/fixtures")).json();
  expect((await page.request.get(api+"/_test/ministry/"+data.ministry_ids.Women)).status()).toBe(403);
  expect((await page.request.get(api+"/_test/ministry/"+data.ministry_ids.Youth)).status()).toBe(200);
  await page.goto('/portal/dashboard?ministry='+data.ministry_ids.Women);
  await expect(page.getByRole("heading", { name: "Access denied" })).toBeVisible();
});

test("multi-scope workspace switches only between authorised options", async ({ page }) => {
  await login(page, "multi"); const select = page.getByLabel("Current workspace");
  await expect(select.locator('option')).toHaveCount(2);
  await select.selectOption({ label: "Youth Ministry" });
  await expect(select.locator('option:checked')).toHaveText("Youth Ministry");
  await select.selectOption({ label: "Choir Ministry" });
  await expect(select.locator('option:checked')).toHaveText("Choir Ministry");
});

test("session expiry clears protected state and shows a clear sign-in message", async ({ page }) => {
  await login(page, "youth");
  expect((await page.request.post(api+"/_test/expire")).status()).toBe(200);
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page).toHaveURL(/\/login\?reason=expired/);
  await expect(page.getByText("Your session expired. Please sign in again.")).toBeVisible();
});

for (const [name, label] of [["secretary", "Church secretary"], ["overseer", "General Overseer"], ["teacher", "Sunday School"]]) {
  test(`${name} dashboard presentation does not grant unrelated modules`, async ({ page }) => {
    await login(page, name); await expect(page.locator('.page-heading .eyebrow')).toHaveText(label);
    await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Finance" })).toHaveCount(0);
    if (name === "teacher") { await expect(page.getByText("Primary class", { exact: true }).first()).toBeVisible(); await expect(page.getByText("Juniors class", { exact: true })).toHaveCount(0); }
  });
}

test("all requested viewports and themes stay usable without horizontal overflow", async ({ page }) => {
  test.setTimeout(120_000);
  for (const [width, height] of [[1920,1080], [1600,900], [1366,768], [1024,768], [768,1024], [390,844]]) {
    await page.setViewportSize({ width, height }); await page.goto('/login');
    for (const theme of ['light','dark']) {
      await page.getByLabel('Colour theme').selectOption(theme);
      await expect(page.getByRole('button', { name:'Sign in', exact:true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await screenshot(page, `login_${width}_${theme}`);
    }
    await login(page);
    for (const theme of ['light','dark']) {
      await page.getByLabel('Colour theme').selectOption(theme);
      await expect(page.getByRole('heading', { name:/Welcome back/ })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await screenshot(page, `dashboard_${width}_${theme}`);
    }
    if (width <= 1024) {
      await page.getByRole('button', { name:'Open navigation' }).click();
      await expect(page.getByRole('dialog', { name:'Navigation' })).toBeVisible();
      await page.keyboard.press('Escape'); await expect(page.getByRole('dialog', { name:'Navigation' })).toHaveCount(0);
    }
    await page.getByRole('button', { name:'Account menu' }).click(); await page.getByRole('menuitem', { name:'Sign out',exact:true }).click();
    await expect(page).toHaveURL(/\/login/);
  }
});

test("login and portal pass browser accessibility checks and theme persists", async ({ page }) => {
  await page.goto('/login'); await expect(page.getByLabel('Email or username')).toBeEnabled();
  for (const theme of ['light','dark']) {
    await page.getByLabel('Colour theme').selectOption(theme);
    for (const tab of ['Password','Authenticator']) {
      await page.getByRole('tab',{name:tab,exact:true}).click();
      expect((await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa']).analyze()).violations).toEqual([]);
    }
  }
  await login(page); await page.getByLabel('Colour theme').selectOption('dark'); await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await expect(page.getByRole('heading',{name:/Welcome back/})).toBeVisible();
  for (const theme of ['light','dark']) {
    await page.getByLabel('Colour theme').selectOption(theme);
    expect((await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa']).analyze()).violations).toEqual([]);
  }
});
