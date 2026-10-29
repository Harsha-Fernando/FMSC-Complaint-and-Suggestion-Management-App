const {test,expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const url='/system-admin/accounts/user/import/';
const csv='email,first_name,last_name,role,cpm_number,lecturer_id,department\nimport.student@example.edu,Import,Student,student,01234,,Accounting\nimport.lecturer@example.edu,Import,Lecturer,lecturer,,LEC-001,Accounting\n';

for (const javaScriptEnabled of [false,true]) {
test(`system administrator imports a roster with JavaScript ${javaScriptEnabled ? 'enabled' : 'disabled'}`,async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled,viewport:{width:1440,height:900}});
  const page=await context.newPage();
  await page.goto('http://127.0.0.1:8765/accounts/login/');
  await page.locator('[name=username]').fill('sysadmin@test.example');
  await page.locator('[name=password]').fill('Browser-Test-2026!');
  await page.locator('.auth-card form:not([data-language-form]) button[type=submit]').click();
  await page.goto('http://127.0.0.1:8765/system-admin/accounts/user/');
  await page.getByRole('link',{name:'Import accounts',exact:true}).click();
  await expect(page).toHaveURL(new RegExp(url+'$'));
  for(const code of ['en','si','ta']) {
    await page.locator('[data-language-menu] summary').click();
    await page.locator(`[data-language-form] button[value=${code}]`).click();
    await expect(page.locator('html')).toHaveAttribute('lang',code);
    await expect(page.locator('[data-language-menu]')).not.toHaveAttribute('aria-busy','true');
    await page.locator('[name=csv_file]').setInputFiles({name:'roster.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});
    await page.locator('.roster-import form[enctype] button').click();
    await expect(page.locator('.roster-table tbody tr')).toHaveCount(2);
    await expect(page.locator('.roster-table')).toContainText('01234');
    await expect(page.locator('.roster-table')).toContainText('LEC-001');
    await page.evaluate(()=>document.fonts.ready);
    await page.screenshot({path:`test-results/${code}-account-import.png`,fullPage:true});
    if (javaScriptEnabled) {
      const checks=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      expect(checks.violations).toEqual([]);
    }
    await page.setViewportSize({width:390,height:844});
    await expect(page.locator('#header')).toHaveCount(1);
    await page.evaluate(()=>window.scrollTo(0,0));
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await page.screenshot({path:`test-results/${code}-account-import-mobile.png`,fullPage:true});
    await page.setViewportSize({width:1440,height:900});
  }
  await page.locator('.roster-confirm button').click();
  await expect(page).toHaveURL(/\/system-admin\/accounts\/user\/$/);
  await expect(page.locator('#result_list')).toContainText('import.student@example.edu');
  await page.locator('select[name=role__exact]').selectOption('student');
  await page.locator('.account-role-filter button').click();
  await expect(page.locator('#result_list')).toContainText('01234');
  await page.locator('select[name=role__exact]').selectOption('lecturer');
  await page.locator('.account-role-filter button').click();
  await expect(page.locator('#result_list')).toContainText('LEC-001');
  await context.close();
});

}
