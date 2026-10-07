import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
const api='http://localhost:8001';
async function fillDonation(page:Page){
  await page.goto('/donate');await expect(page.getByRole('heading',{name:'Support the Ministry',exact:true})).toBeVisible();
  await page.getByLabel('Full name',{exact:true}).fill('PRIVATE-BROWSER-DONOR');await page.getByLabel('Email',{exact:true}).fill('private-browser-donor@example.invalid');
  await page.getByLabel('Phone number (optional)',{exact:true}).fill('+233 200 000 001');await page.getByLabel('Donation purpose',{exact:true}).selectOption({label:'Reviewed fixture offering'});
  await page.getByLabel('Amount (GHS)',{exact:true}).fill('45.25');await page.getByLabel('Note (optional)',{exact:true}).fill('PRIVATE-DONATION-NOTE');
}
async function checkout(page:Page,status:'success'|'failed'|'abandoned'|'pending'){
  let reference='';
  // Simulate the external TEST checkout; never visit or charge a real provider.
  await page.route('https://checkout.paystack.com/**',async route=>{
    reference=new URL(route.request().url()).pathname.slice(1);
    expect((await page.request.post(api+'/_test/payments/'+reference+'?status='+status)).ok()).toBe(true);
    await route.fulfill({status:302,headers:{location:'http://localhost:3002/donate/result?reference='+reference+(status==='abandoned'?'&cancelled=1':'')}});
  });
  await page.getByRole('button',{name:'Continue to secure checkout',exact:true}).click();await expect(page).toHaveURL(/\/donate\/result\?reference=/);
  return reference;
}
test('Donate is reachable from desktop, mobile, footer and Home',async({page})=>{
  await page.goto('/');await expect(page.getByRole('navigation',{name:'Public navigation',exact:true}).getByRole('link',{name:'Donate',exact:true})).toHaveAttribute('href','/donate');
  await expect(page.getByRole('contentinfo').getByRole('link',{name:'Donate',exact:true})).toHaveAttribute('href','/donate');
  await page.getByRole('link',{name:'Donate Now',exact:true}).click();await expect(page).toHaveURL(/\/donate$/);
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Open public navigation'}).click();await page.getByRole('navigation',{name:'Mobile public navigation'}).getByRole('link',{name:'Donate',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.goto('/give');await expect(page).toHaveURL(/\/donate$/);
});
test('Home uses eight distinct published profiles and the full page lists all ten',async({page})=>{
  await page.goto('/');const section=page.locator('section').filter({has:page.getByRole('heading',{name:'Meet Our Leadership',exact:true})});
  await expect(section.locator('.public-leadership-card')).toHaveCount(8);
  const names=await section.locator('h3').allTextContents();expect(new Set(names).size).toBe(8);
  await expect(section.locator('.public-leadership-initials')).toHaveCount(7);
  // An approved portrait which fails to download also gets a neutral fallback.
  await page.route('**/api/v1/public/media/**',route=>route.abort());await page.reload();await section.locator('.public-leadership-card').first().scrollIntoViewIfNeeded();await expect(section.locator('.public-leadership-initials')).toHaveCount(8);
  await page.getByRole('link',{name:'View All Leadership',exact:true}).click();await expect(page.locator('.public-leadership-card')).toHaveCount(10);
  await expect(page.locator('.public-leadership-card').last()).toContainText('Synthetic leader 9');
});
test('donation amount is validated before checkout',async({page})=>{
  await fillDonation(page);let submitted=0;page.on('request',request=>{if(request.method()==='POST'&&request.url().endsWith('/api/v1/public/donations'))submitted++;});
  await page.getByLabel('Amount (GHS)',{exact:true}).fill('0');await page.getByRole('button',{name:'Continue to secure checkout'}).click();
  expect(await page.getByLabel('Amount (GHS)',{exact:true}).evaluate((input:HTMLInputElement)=>input.validity.valid)).toBe(false);expect(submitted).toBe(0);
});
test('TEST checkout returns a private receipt and repeated callbacks stay successful',async({page,browser})=>{
  await fillDonation(page);const reference=await checkout(page,'success');
  await expect(page.getByRole('heading',{name:'Thank you for supporting HOPFAN.',exact:true})).toBeVisible();await expect(page.locator('.public-receipt')).toContainText('45.25');
  await expect(page.locator('.public-receipt')).toContainText('Reviewed fixture offering');expect(await page.locator('main').textContent()).not.toContain('PRIVATE-');
  await page.reload();await expect(page.getByRole('heading',{name:'Thank you for supporting HOPFAN.',exact:true})).toBeVisible();
  const context=await browser.newContext();const stranger=await context.newPage();await stranger.goto('/donate/result?reference='+reference);await expect(stranger.locator('main').getByRole('alert')).toContainText('same browser tab');expect(await stranger.locator('main').textContent()).not.toContain('45.25');await context.close();
});
for(const status of ['failed','abandoned'] as const)test('TEST checkout '+status+' supports retry and returning Home',async({page})=>{
  await fillDonation(page);await checkout(page,status);await expect(page.getByRole('heading',{name:'Payment was not completed.',exact:true})).toBeVisible();await expect(page.getByRole('link',{name:'Try Again',exact:true})).toHaveAttribute('href','/donate');await page.getByRole('link',{name:'Return Home',exact:true}).click();await expect(page).toHaveURL('http://localhost:3002/');
});
test('private donor records are visible only to authorized finance users',async({page})=>{
  await fillDonation(page);await checkout(page,'success');
  await page.goto('/login');await expect(page.getByLabel('Email or username')).toBeEnabled();await page.getByLabel('Email or username').fill('portal-admin@example.invalid');await page.locator('input[name="password"]').fill('Portal-Synthetic!2026');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).toHaveURL(/portal\/dashboard/);
  await page.goto('/portal/finance');await expect(page.getByRole('heading',{name:'Online donations',exact:true})).toBeVisible();await expect(page.getByText('PRIVATE-DONATION-NOTE',{exact:true}).first()).toBeVisible();
});
test('donation and leadership pages fit phones, tablets and desktop with accessible controls',async({page})=>{
  test.setTimeout(180000);
  const screenshots=path.resolve('../docs/screenshots/public-giving');await fs.mkdir(screenshots,{recursive:true});
  for(const width of [1920,1366,1024,768,430,390]){
    await page.setViewportSize({width,height:900});for(const url of ['/donate','/leadership','/']){
      await page.goto(url);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
      if([1366,768,390].includes(width)&&url!=='/')await page.screenshot({path:path.join(screenshots,url.slice(1)+'_'+width+'.png'),fullPage:true});
      if(width===1366||width===390)expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag22aa']).analyze()).violations).toEqual([]);
    }
  }
});
