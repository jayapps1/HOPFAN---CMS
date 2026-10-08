import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
const api='http://localhost:8001';
async function login(page:Page){await page.goto('/login');await expect(page.getByLabel('Email or username')).toBeEnabled();await page.getByLabel('Email or username').fill('portal-admin@example.invalid');await page.locator('input[name="password"]').fill('Portal-Synthetic!2026');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).toHaveURL(/portal\/dashboard/);}
test('Home places substantial weekly services and published upcoming events near the top',async({page})=>{
  await page.goto('/');await expect(page.getByRole('heading',{name:'Weekly Services',exact:true})).toBeVisible();
  const services=page.locator('.homepage-service');await expect(services).toHaveCount(3);await expect(services.first()).toContainText('7:00 AM');await expect(services.last()).toContainText('6:30 PM');
  expect((await page.locator('.homepage-hero').boundingBox())!.height).toBeGreaterThanOrEqual(620);expect((await services.first().boundingBox())!.height).toBeGreaterThanOrEqual(220);
  const headings=await page.locator('.homepage-section h2').allTextContents();expect(headings.slice(0,3)).toEqual(['Weekly Services','Upcoming Events','About HOPFAN']);
  await expect(page.locator('.homepage-event')).toHaveCount(5);expect(await page.locator('.homepage').textContent()).not.toContain('Synthetic private draft event');expect(await page.locator('.homepage').textContent()).not.toContain('Synthetic past event');
});
test('event controls, dots and keyboard navigation update the large carousel',async({page})=>{
  await page.goto('/');const carousel=page.getByRole('region',{name:'Upcoming events',exact:true});await carousel.scrollIntoViewIfNeeded();
  await carousel.getByRole('button',{name:'Next event',exact:true}).click();await expect(carousel.getByText('Event 2 of 5',{exact:true})).toBeVisible();
  await carousel.getByRole('button',{name:'Previous event',exact:true}).click();await expect(carousel.getByText('Event 1 of 5',{exact:true})).toBeVisible();
  await carousel.getByRole('button',{name:'Show event 3: Synthetic upcoming event 3',exact:true}).click();await expect(carousel.getByText('Event 3 of 5',{exact:true})).toBeVisible();
  const track=page.locator('.homepage-carousel-track');await track.focus();await page.keyboard.press('Home');await expect(carousel.getByText('Event 1 of 5',{exact:true})).toBeVisible();await page.keyboard.press('ArrowRight');await expect(carousel.getByText('Event 2 of 5',{exact:true})).toBeVisible();await page.keyboard.press('End');await expect(carousel.getByText('Event 5 of 5',{exact:true})).toBeVisible();
});
test('service management saves a private draft and publishing updates Home',async({page})=>{
  await login(page);await page.goto('/portal/website/service-times');await expect(page.getByRole('heading',{name:'Service Times',exact:true})).toBeVisible();
  await page.getByLabel('Start time 1',{exact:true}).fill('08:00');await page.getByRole('button',{name:'Save settings draft',exact:true}).click();
  await expect.poll(async()=>{const response=await page.request.get(api+'/api/v1/website/settings');return (await response.json()).data.service_times[0].start_time;}).toBe('08:00:00');
  await page.goto('/');await expect(page.locator('.homepage-service').first()).toContainText('7:00 AM');
  await page.goto('/portal/website/service-times');await page.getByRole('button',{name:'Publish settings',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Confirm',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.goto('/');await expect(page.locator('.homepage-service').first()).toContainText('8:00 AM');
});
test('unpublishing a real Event record immediately removes it from Home and the Events page',async({page})=>{
  await login(page);const token=(await(await page.request.get(api+'/api/v1/auth/csrf',{headers:{Origin:'http://localhost:3002'}})).json()).csrf_token;
  const records=(await(await page.request.get(api+'/api/v1/events?page_size=100')).json()).items;const event=records.find((row:{slug:string})=>row.slug==='synthetic-upcoming-1');
  const response=await page.request.post(api+'/api/v1/events/'+event.id+'/unpublish',{headers:{Origin:'http://localhost:3002','X-CSRF-Token':token},data:{expected_updated_at:event.updated_at}});expect(response.ok()).toBe(true);
  await page.goto('/');await expect(page.locator('.homepage-event')).toHaveCount(4);expect(await page.locator('.homepage-carousel').textContent()).not.toContain(event.title);
  expect((await page.request.get(api+'/api/v1/public/events/'+event.slug)).status()).toBe(404);
  let updated=await response.json();
  for(const action of ['submit','approve','publish']){const restored=await page.request.post(api+'/api/v1/events/'+event.id+'/'+action,{headers:{Origin:'http://localhost:3002','X-CSRF-Token':token},data:{expected_updated_at:updated.updated_at}});expect(restored.ok(),await restored.text()).toBe(true);updated=await restored.json();}
});
test('zero events show a compact useful state and image failures use branded artwork',async({page})=>{
  expect((await page.request.post(api+'/_test/home-events?visible=false')).ok()).toBe(true);
  try{await page.goto('/');await expect(page.getByRole('heading',{name:'New events will be announced soon.',exact:true})).toBeVisible();await expect(page.locator('.homepage-carousel')).toHaveCount(0);await expect(page.getByRole('heading',{name:'Weekly Services',exact:true})).toBeVisible();}finally{expect((await page.request.post(api+'/_test/home-events?visible=true')).ok()).toBe(true);}
  await page.route('**/api/v1/public/media/**',route=>route.abort());await page.goto('/');await page.locator('.homepage-carousel').scrollIntoViewIfNeeded();await expect(page.locator('.homepage-event').first().locator('.homepage-photo-fallback')).toBeVisible();
});
test('the editorial Home layout is accessible at every requested size',async({page})=>{
  test.setTimeout(240000);const directory=path.resolve('../docs/screenshots/homepage-redesign');await fs.mkdir(directory,{recursive:true});
  for(const [width,height] of [[1920,1080],[1600,900],[1366,768],[1024,768],[768,1024],[430,932],[390,844]]){
    await page.setViewportSize({width,height});await page.goto('/');await expect(page.locator('.homepage-service')).toHaveCount(3);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    if(width===1366||width===390)expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag22aa']).analyze()).violations).toEqual([]);
    await page.screenshot({path:path.join(directory,'home_'+width+'.png'),fullPage:true});
  }
});
test('mobile touch gestures and reduced motion can browse the event carousel',async({browser})=>{
  const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,reducedMotion:'reduce'});const page=await context.newPage();await page.goto('http://localhost:3002/');const track=page.locator('.homepage-carousel-track');await track.scrollIntoViewIfNeeded();const box=(await track.boundingBox())!;
  const session=await context.newCDPSession(page);const x=box.x+box.width*.8,y=box.y+Math.min(100,box.height/2);
  await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});for(let step=1;step<=8;step++)await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-step*25,y}]});await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await expect.poll(()=>track.evaluate(node=>node.scrollLeft)).toBeGreaterThan(50);await page.getByRole('button',{name:'Show event 3: Synthetic upcoming event 3',exact:true}).click();await expect(page.getByText('Event 3 of 5',{exact:true})).toBeVisible();await context.close();
});
