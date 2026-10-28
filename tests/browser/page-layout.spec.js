const {test, expect} = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

for (const code of ['en', 'si', 'ta']) {
  test(`${code}: sign-in typography fits desktop and mobile without JavaScript`, async ({browser}) => {
    const context = await browser.newContext({javaScriptEnabled: false, viewport: {width: 1440, height: 900}});
    const page = await context.newPage();
    await page.goto('http://127.0.0.1:8765/accounts/login/');
    await page.locator('[data-language-menu] summary').click();
    await page.locator(`[data-language-form] button[value=${code}]`).click();
    await page.evaluate(() => document.fonts.ready);
    const measurements = await page.evaluate(() => {
      const heading = document.querySelector('.auth-side h1');
      const card = document.querySelector('.auth-card');
      return {height: document.documentElement.scrollHeight, headingHeight: heading.getBoundingClientRect().height,
        letterSpacing: getComputedStyle(heading).letterSpacing, cardWidth: card.getBoundingClientRect().width};
    });
    expect(measurements.height).toBeLessThanOrEqual(900);
    expect(measurements.headingHeight).toBeLessThanOrEqual(160);
    expect(measurements.cardWidth).toBeGreaterThanOrEqual(420);
    if (code !== 'en') expect(measurements.letterSpacing).toBe('normal');
    await page.screenshot({path: `test-results/${code}-signin-desktop.png`, fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await expect(page.locator('input[name=username]')).toBeVisible();
    await page.screenshot({path: `test-results/${code}-signin-mobile.png`, fullPage: true});
    await page.locator('input[name=username]').fill('student@test.example');
    await page.locator('input[name=password]').fill('Browser-Test-2026!');
    await page.locator('.auth-card form:not([data-language-form]) button[type=submit]').click();
    await expect(page.locator('.utility-bar')).toBeVisible();
    await context.close();
  });
}

test('case details use both columns with navigation before the content', async ({page}) => {
  await page.goto('/accounts/login/');
  await page.locator('[name=username]').fill('student@test.example');
  await page.locator('[name=password]').fill('Browser-Test-2026!');
  await page.locator('.auth-card form:not([data-language-form]) button[type=submit]').click();
  await page.goto('/cases/new/');
  await page.locator('[name=case_type][value=complaint]').check();
  await page.getByRole('combobox', {name:'Category',exact:true}).click();
  await page.getByRole('option', {name:'Facilities',exact:true}).click();
  await page.locator('[name=location]').fill('Test room');
  await page.locator('[name=title]').fill('Layout regression case');
  await page.locator('[name=description]').fill('A temporary case to check the detail layout.');
  await page.locator('[name=declaration]').check();
  await page.getByRole('button', {name:'Submit case', exact:true}).click();
  await expect(page.locator('.case-head h1')).toHaveText('Layout regression case');
  await expect(page.locator('.case-navigation a')).toHaveAttribute('href','/cases/mine/');
  await expect(page.locator('.case-navigation a')).toHaveClass(/btn-primary/);
  await expect(page.locator('.case-navigation a')).toHaveCSS('text-decoration-line', 'none');
  await expect(page.locator('.case-sidebar .facts')).toBeVisible();
  await expect(page.locator('.case-content')).toContainText('A temporary case to check the detail layout.');
  for (const code of ['en', 'si', 'ta']) {
    await page.locator('[data-language-menu] summary').click();
    await page.locator(`[data-language-form] button[value=${code}]`).click();
    await expect(page.locator('html')).toHaveAttribute('lang',code);
    await expect(page.locator('[data-language-menu]')).not.toHaveAttribute('aria-busy','true');
    await page.evaluate(() => document.fonts.ready);
    await page.setViewportSize({width:1440,height:1000});
    const heading = await page.locator('.case-heading-info').boundingBox();
    const back = await page.locator('.case-navigation').boundingBox();
    expect(back.x).toBeGreaterThanOrEqual(heading.x + heading.width);
    expect(back.y).toBeGreaterThanOrEqual(heading.y);
    expect(back.y + back.height).toBeLessThanOrEqual(heading.y + heading.height + 1);
    await page.screenshot({path:`test-results/${code}-case-desktop.png`,fullPage:true});
    const result = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    expect(result.violations).toEqual([]);
    await page.setViewportSize({width:390,height:844});
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await page.screenshot({path:`test-results/${code}-case-mobile.png`,fullPage:true});
  }
});
