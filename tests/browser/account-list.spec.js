const {test,expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const url='/system-admin/accounts/user/';

for(const code of ['en','si','ta']) {
  test(`${code}: role filter and dark account list remain accessible`,async({page})=>{
    await page.addInitScript(()=>localStorage.setItem('theme','dark'));
    await page.setViewportSize({width:1440,height:900});
    await page.goto('/accounts/login/');
    await page.locator('[name=username]').fill('sysadmin@test.example');
    await page.locator('[name=password]').fill('Browser-Test-2026!');
    await page.locator('.auth-card form:not([data-language-form]) button[type=submit]').click();
    await page.goto(url);
    await page.locator('[data-language-menu] summary').click();
    await page.locator(`[data-language-form] button[value=${code}]`).click();
    await expect(page.locator('html')).toHaveAttribute('lang',code);
    await expect(page.locator('[data-language-menu]')).not.toHaveAttribute('aria-busy','true');
    await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
    await expect(page.locator('.account-role-filter')).toBeVisible();
    await expect(page.locator('#result_list .column-cpm_number')).toHaveCount(0);
    const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    expect(result.violations).toEqual([]);
    for(const [role,column,irrelevant] of [['student','cpm_number','lecturer_id'],['lecturer','lecturer_id','cpm_number'],['authority','authority','lecturer_id']]) {
      await page.locator('select[name=role__exact]').selectOption(role);
      await page.locator('.account-role-filter button').click();
      await expect(page.locator(`#result_list .column-${column}`)).toBeVisible();
      await expect(page.locator(`#result_list .column-${irrelevant}`)).toHaveCount(0);
    }
    await page.evaluate(()=>document.fonts.ready);
    await page.screenshot({path:`test-results/${code}-accounts-dark-desktop.png`,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await expect(page.locator('.account-role-filter')).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await page.evaluate(async()=>{ document.activeElement?.blur(); window.scrollTo(0,0); await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); });
    await page.screenshot({path:`test-results/${code}-accounts-dark-mobile.png`,fullPage:true});
  });
}

test('account role filtering works without JavaScript',async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false});
  const page=await context.newPage();
  await page.goto('http://127.0.0.1:8765/accounts/login/');
  await page.locator('[name=username]').fill('sysadmin@test.example');
  await page.locator('[name=password]').fill('Browser-Test-2026!');
  await page.locator('.auth-card form:not([data-language-form]) button[type=submit]').click();
  await page.goto('http://127.0.0.1:8765'+url);
  for(const role of ['student','lecturer','']) {
    await page.locator('select[name=role__exact]').selectOption(role);
    await page.locator('.account-role-filter button').click();
    await expect(page.locator('select[name=role__exact]')).toHaveValue(role);
  }
  await context.close();
});
