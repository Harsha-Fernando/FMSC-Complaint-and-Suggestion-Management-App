const {test, expect} = require('@playwright/test');

test('reporter dashboard fits a desktop screen with six cases in every language', async ({page}) => {
  await page.setViewportSize({width:1440,height:900});
  await page.goto('/accounts/login/');
  await page.locator('[name=username]').fill('student@test.example');
  await page.locator('[name=password]').fill('Browser-Test-2026!');
  await page.locator('.auth-card form:not([data-language-form]) button[type=submit]').click();
  for (let i=0;i<6;i++) {
    await page.goto('/cases/new/');
    await page.locator('[name=case_type][value=complaint]').check();
    await page.getByRole('combobox',{name:'Category',exact:true}).click();
    await page.getByRole('option',{name:'Facilities',exact:true}).click();
    await page.locator('[name=location]').fill('Test room');
    await page.locator('[name=title]').fill(`Compact dashboard ${i+1}`);
    await page.locator('[name=description]').fill('Temporary case for dashboard layout validation.');
    await page.locator('[name=declaration]').check();
    await page.getByRole('button',{name:'Submit case',exact:true}).click();
    await expect(page.locator('.case-head')).toBeVisible();
    if (i===0) {
      await page.goto('/');
      await page.setViewportSize({width:1440,height:720});
      for (const code of ['en','si','ta']) {
        await page.locator('[data-language-menu] summary').click();
        await page.locator(`[data-language-form] button[value=${code}]`).click();
        await expect(page.locator('html')).toHaveAttribute('lang',code);
        await page.evaluate(()=>document.fonts.ready);
        await page.screenshot({path:`test-results/${code}-dashboard-laptop.png`,fullPage:true});
        expect(await page.evaluate(()=>document.documentElement.scrollHeight)).toBeLessThanOrEqual(720);
      }
      await page.locator('[data-language-menu] summary').click();
      await page.locator('[data-language-form] button[value=en]').click();
      await expect(page.locator('html')).toHaveAttribute('lang','en');
      await page.setViewportSize({width:1440,height:900});
    }
  }
  await page.goto('/');
  for (const code of ['en','si','ta']) {
    await page.locator('[data-language-menu] summary').click();
    await page.locator(`[data-language-form] button[value=${code}]`).click();
    await expect(page.locator('html')).toHaveAttribute('lang',code);
    await page.evaluate(()=>document.fonts.ready);
    await expect(page.locator('.recent-panel tbody tr')).toHaveCount(6);
    await expect(page.locator('.quick-action')).toHaveCount(4);
    const dimensions=await page.evaluate(()=>({height:document.documentElement.scrollHeight,width:document.documentElement.scrollWidth}));
    await page.screenshot({path:`test-results/${code}-dashboard-compact.png`,fullPage:true});
    expect(dimensions.height).toBeLessThanOrEqual(900);
    expect(dimensions.width).toBeLessThanOrEqual(1440);
    await page.locator('.chart-data summary').click();
    await expect(page.locator('.chart-data tbody tr')).toHaveCount(7);
    await expect(page.locator('.chart-data tbody tr').last()).toBeVisible();
    await page.locator('.chart-data summary').click();
  }
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await expect(page.locator('.quick-action').last()).toBeVisible();
});
