const {test, expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const headers={en:'FMSC Dashboard',si:'FMSC පාලක පුවරුව',ta:'FMSC முகப்பு'};
async function signIn(page,role='student') {
  await page.goto('/accounts/login/');
  await page.locator('input[name=username]').fill(`${role}@test.example`);
  await page.locator('input[name=password]').fill('Browser-Test-2026!');
  await page.locator('.auth-card form:not([data-language-form]) button[type=submit]').click();
  await expect(page.locator('.utility-bar')).toBeVisible();
}
async function language(page,code) {
  await page.locator('[data-language-menu] summary').click();
  await page.locator(`[data-language-form] button[value="${code}"]`).click();
  await expect(page.locator('html')).toHaveAttribute('lang',code);
  for (const [value, name] of [['en','English'], ['si','සිංහල'], ['ta','தமிழ்']]) {
    await expect(page.locator(`[data-language-form] button[value="${value}"]`)).toHaveText(new RegExp(`^${name}(?:✓)?$`));
  }
  await expect.poll(() => page.evaluate(() => typeof window.gettext==='function' && window.gettext('Notifications'))).toBe({en:'Notifications',si:'දැනුම්දීම්',ta:'அறிவிப்புகள்'}[code]);
}

for(const role of ['student','lecturer','admin','authority','management','sysadmin']) {
  test(`${role}: English, Sinhala, Tamil remain accessible and scoped`,async({page})=>{
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await signIn(page,role);
    for(const code of ['en','si','ta']) {
      await language(page,code);
      await expect(page.locator('.workspace-title strong')).toHaveText(headers[code]);
      await expect(page.locator('.language-menu')).toBeVisible();
      const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      expect(result.violations).toEqual([]);
      if(['student','lecturer','authority'].includes(role)) await expect(page.locator('.nav a[href="/reports/"]')).toHaveCount(0);
    }
    expect(errors).toEqual([]);
  });
}

test('switching languages preserves text, selections and evidence files in memory',async({page})=>{
  await signIn(page);
  await page.goto('/cases/new/');
  await page.getByLabel('Suggestion',{exact:true}).check();
  await page.getByLabel('Urgent',{exact:true}).check();
  await page.getByRole('combobox',{name:'Category',exact:true}).click();
  await page.getByRole('option',{name:'Facilities',exact:true}).click();
  await page.locator('[name=location]').fill('Library நூலகம்');
  await page.locator('[name=title]').fill('Draft සිංහල தமிழ்');
  await page.locator('[name=description]').fill('Keep this private draft exactly as entered.');
  await page.locator('[name=declaration]').check();
  await page.locator('[name=images]').setInputFiles({name:'draft.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==','base64')});
  for(const code of ['si','ta','en']) {
    await language(page,code);
    await expect(page.locator('[name=title]')).toHaveValue('Draft සිංහල தமிழ்');
    await expect(page.locator('[name=description]')).toHaveValue('Keep this private draft exactly as entered.');
    await expect(page.locator('[name=case_type][value=suggestion]')).toBeChecked();
    await expect(page.locator('[name=priority][value=urgent]')).toBeChecked();
    await expect(page.locator('[name=declaration]')).toBeChecked();
    await expect(page.locator('select[name=category] option:checked')).toHaveText('Facilities');
    expect(await page.locator('[name=images]').evaluate(input=>input.files[0]?.name)).toBe('draft.png');
    await expect(page.locator('.file-picker-caption').first()).toHaveText('draft.png');
  }
  const stored=await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}));
  expect(stored).not.toContain('private draft');
  await expect(page.getByRole('combobox',{name:'Category',exact:true})).toContainText('Facilities');
  await page.getByRole('button',{name:'Submit case',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Draft සිංහල தமிழ்',exact:true})).toBeVisible();
  await expect(page.locator('.case-head .status')).toContainText('Submitted');
});

for(const code of ['si','ta']) {
  test(`${code}: mobile language control and localized forms fit`,async({page})=>{
    await page.setViewportSize({width:390,height:844});
    await signIn(page);
    await language(page,code);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    const menu=await page.locator('.language-menu').boundingBox();
    const bell=await page.locator('.notification-link').boundingBox();
    expect(menu.x+menu.width).toBeLessThanOrEqual(bell.x+1);
    await page.goto('/cases/new/');
    await expect(page.locator('html')).toHaveAttribute('lang',code);
  for (const [value, name] of [['en','English'], ['si','සිංහල'], ['ta','தமிழ்']]) {
    await expect(page.locator(`[data-language-form] button[value="${value}"]`)).toHaveText(new RegExp(`^${name}(?:✓)?$`));
  }
    await expect(page.locator('.select-trigger')).toBeVisible();
    const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    expect(result.violations).toEqual([]);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:`test-results/${code}-submission-mobile.png`,fullPage:true});
  });
}

test('language preference survives reload and sign-out; JavaScript returns to English',async({page})=>{
  await signIn(page);
  await language(page,'ta');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang','ta');
  await page.locator('.sidebar form[action="/accounts/logout/"] button').click();
  await expect(page.locator('html')).toHaveAttribute('lang','ta');
  await language(page,'en');
  await signIn(page);
  await page.route('**/notifications/summary/',route=>route.fulfill({json:{unread_count:7}}));
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await expect(page.locator('.notification-link')).toHaveAttribute('aria-label','Notifications, 7 unread');
});

test('language switching works without JavaScript',async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false});
  const page=await context.newPage();
  await page.goto('http://127.0.0.1:8765/accounts/login/');
  await page.locator('[data-language-menu] summary').click();
  await page.locator('[data-language-form] button[value=si]').click();
  await expect(page.locator('html')).toHaveAttribute('lang','si');
  await expect(page.locator('input[name=username]')).toBeVisible();
  await context.close();
});

test('failed language request keeps the form and reports a retry action',async({page})=>{
  await signIn(page);
  await page.goto('/cases/new/');
  await page.locator('[name=title]').fill('Keep my unsaved title');
  await page.route('**/i18n/setlang/',route=>route.abort());
  await page.locator('[data-language-menu] summary').click();
  await page.locator('[data-language-form] button[value=si]').click();
  await expect(page.getByRole('alert')).toContainText('Please try again');
  await expect(page.locator('[name=title]')).toHaveValue('Keep my unsaved title');
  await expect(page.locator('html')).toHaveAttribute('lang','en');
});

test('Sinhala and Tamil desktop dashboard previews',async({page})=>{
  await page.setViewportSize({width:1536,height:1024});
  await signIn(page);
  for(const code of ['si','ta']) {
    await language(page,code);
    await page.evaluate(()=>document.fonts.ready);
    await page.screenshot({path:`test-results/${code}-dashboard-desktop.png`,fullPage:true});
  }
});
