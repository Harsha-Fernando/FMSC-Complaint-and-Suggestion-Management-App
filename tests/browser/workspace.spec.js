const {test, expect} = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
async function login(page, role) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Email or registration number').fill(`${role}@test.example`);
  await page.getByLabel('Password', {exact:true}).fill('Browser-Test-2026!');
  await page.getByRole('button', {name:'Sign in', exact:true}).click();
  await expect(page.locator('.utility-bar')).toBeVisible();
}
async function logout(page) {
  await page.locator('.account-menu summary').click();
  await page.getByRole('button', {name:'Sign out', exact:true}).click();
}
async function choose(page, label, text) {
  const control = page.getByRole('combobox', {name:label, exact:true});
  await control.click();
  await page.getByRole('option', {name:text, exact:true}).click();
  await expect(control).toContainText(text);
}

for (const role of ['student', 'lecturer', 'admin', 'authority', 'management', 'sysadmin']) {
  test(`${role}: accessible workspace and appropriate navigation`, async ({page}) => {
    const errors=[]; page.on('pageerror', error => errors.push(error.message));
    await login(page, role);
    await expect(page.getByRole('navigation', {name:'Main', exact:true})).toBeVisible();
    if (['student','lecturer'].includes(role)) {
      await expect(page.getByRole('link', {name:'Submit a case', exact:true}).first()).toBeVisible();
      await expect(page.getByRole('link', {name:'Authorities', exact:true})).toHaveCount(0);
    }
    if (role==='authority') await expect(page.getByRole('heading', {name:'Facilities Unit', exact:true})).toBeVisible();
    if (role==='management') await expect(page.getByRole('link', {name:'Authorities', exact:true})).toHaveCount(0);
    if (role==='sysadmin') await expect(page.getByRole('link', {name:'Users', exact:true})).toBeVisible();
    const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    expect(result.violations).toEqual([]);
    expect(errors).toEqual([]);
    const gradients=await page.locator('body').evaluate(body => [...body.querySelectorAll('*')].filter(node => /gradient\(/i.test(getComputedStyle(node).backgroundImage)).map(node => node.tagName));
    expect(gradients).toEqual([]);
  });
}

test('custom dropdown supports keyboard, Escape, typeahead and form values', async ({page}) => {
  await login(page, 'student');
  await page.goto('/cases/new/');
  const category=page.getByRole('combobox', {name:'Category', exact:true});
  await category.focus();
  await page.keyboard.press('ArrowDown');
  await expect(category).toHaveAttribute('aria-expanded','true');
  await page.keyboard.press('End');
  await page.keyboard.press('Enter');
  await expect(category).toContainText('IT services');
  await expect(page.locator('select[name=category] option:checked')).toHaveText('IT services');
  await category.click();
  await page.keyboard.press('Home');
  await page.keyboard.press('Escape');
  await expect(category).toHaveAttribute('aria-expanded','false');
  await expect(category).toContainText('IT services');
  await category.focus();
  await page.keyboard.type('fac');
  await page.keyboard.press('Enter');
  await expect(category).toContainText('Facilities');
  const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(result.violations).toEqual([]);
});

test('real lifecycle: submit, manually assign, solve and close across accounts', async ({page}) => {
  await login(page, 'student');
  await page.goto('/cases/new/');
  await page.getByLabel('Complaint', {exact:true}).check();
  await choose(page, 'Category', 'Facilities');
  await page.getByLabel('Location', {exact:true}).fill('Building C, room 4');
  await page.getByLabel('Short title', {exact:true}).fill('Browser workflow: damaged desk');
  await page.getByLabel('Description', {exact:true}).fill('The desk surface is damaged and needs repair.');
  await page.locator('input[name=images]').setInputFiles({name:'evidence.png', mimeType:'image/png', buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==', 'base64')});
  await page.getByLabel('I confirm').check();
  await page.getByRole('button', {name:'Submit case',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Browser workflow: damaged desk'})).toBeVisible();
  const casePath=new URL(page.url()).pathname;
  await expect(page.getByText('Not assigned yet', {exact:true})).toBeVisible();
  await logout(page);
  await login(page,'authority');
  await expect(page.getByRole('link', {name:'Browser workflow: damaged desk'})).toHaveCount(0);
  await logout(page);
  await login(page,'admin');
  await page.goto(casePath);
  await choose(page,'Assign to','Facilities Unit');
  await page.getByRole('button',{name:'Assign case',exact:true}).click();
  await logout(page);
  await login(page,'authority');
  await page.getByRole('link',{name:'Browser workflow: damaged desk'}).click();
  await choose(page,'New status','Solved');
  await page.getByLabel('Resolution note', {exact:true}).fill('Damaged desk repaired and checked.');
  await page.getByRole('button', {name:'Save progress',exact:true}).click();
  await expect(page.getByText('Damaged desk repaired and checked.',{exact:true}).first()).toBeVisible();
  await logout(page);
  await login(page,'admin');
  await page.goto(casePath);
  await page.getByRole('button',{name:'Close case',exact:true}).click();
  await expect(page.locator('.case-head .status')).toContainText('Closed');
});

test('mobile navigation and layouts fit a narrow viewport', async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await login(page,'admin');
  await page.getByRole('button',{name:'Toggle navigation'}).click();
  await expect(page.getByRole('navigation',{name:'Main',exact:true})).toBeVisible();
});

test('mobile menu keyboard dismissal and no page overflow', async ({page}) => {
  await login(page,'admin');
  await page.setViewportSize({width:390,height:844});
  const toggle=page.getByRole('button',{name:'Toggle navigation'});
  await expect(page.locator('.sidebar')).not.toBeVisible();
  await toggle.click();
  await expect(page.locator('.sidebar')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(toggle).toBeFocused();
  await expect(page.locator('.sidebar')).not.toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/admin-mobile.png', fullPage:true});
});

test('reduced motion and no-JavaScript forms remain usable', async ({browser}) => {
  const context=await browser.newContext({javaScriptEnabled:false, reducedMotion:'reduce'});
  const page=await context.newPage();
  await login(page,'student');
  await page.goto('/cases/new/');
  await expect(page.locator('select[name=category]')).toBeVisible();
  await page.locator('select[name=category]').selectOption({label:'Facilities'});
  await expect(page.getByRole('button',{name:'Submit case',exact:true})).toBeEnabled();
  await context.close();
});

test('live notification badge refreshes from server response', async ({page}) => {
  await login(page,'lecturer');
  await page.route('**/notifications/summary/', route => route.fulfill({json:{unread_count:2}}));
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByRole('link',{name:'Notifications, 2 unread',exact:true})).toBeVisible();
  await expect(page.locator('.notification-dot')).toBeVisible();
});

test('desktop dashboard review and screenshot', async ({page}) => {
  await page.setViewportSize({width:1440,height:1000});
  await login(page,'admin');
  await expect(page.locator('.filter-panel')).not.toHaveAttribute('open','');
  await page.locator('.filter-panel summary').click();
  await expect(page.getByRole('combobox',{name:'Authority',exact:true})).toBeVisible();
  await page.locator('.filter-panel summary').click();
  await page.screenshot({path:'test-results/admin-desktop.png',fullPage:true});
});

 test('invalid submission keeps data and focuses an error', async ({page}) => {
  await login(page,'student');
  await page.goto('/cases/new/');
  await page.getByLabel('Short title',{exact:true}).fill('Preserve this title');
  await page.getByRole('button',{name:'Submit case',exact:true}).click();
  await expect(page.getByLabel('Short title',{exact:true})).toHaveValue('Preserve this title');
  await expect(page.locator('.errorlist').first()).toBeVisible();
  expect(await page.locator('.has-error').evaluateAll(nodes => nodes.some(node => node.contains(document.activeElement)))).toBe(true);
});

test('reference dashboard charts and quick actions use real scoped data', async ({page}) => {
  await page.setViewportSize({width:1536,height:1024});
  await login(page,'student');
  await expect(page.getByRole('heading',{name:'Cases overview',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Case status trend',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Quick actions',exact:true})).toBeVisible();
  await expect(page.locator('.metric-card')).toHaveCount(4);
  await expect(page.getByRole('link',{name:'Submit a complaint',exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'View reports',exact:true})).toHaveCount(0);
  await page.locator('.chart-data summary').click();
  await expect(page.getByRole('table',{name:'Daily case activity'})).toBeVisible();
  await expect(page.locator('.chart-data tbody tr')).toHaveCount(7);
  await page.locator('.chart-data summary').click();
  await page.screenshot({path:'test-results/reference-student-desktop.png',fullPage:true});
  await page.getByRole('link',{name:'Submit a suggestion',exact:true}).click();
  await expect(page.getByLabel('Suggestion',{exact:true})).toBeChecked();
});

test('desktop navigation collapses without disabling dashboard controls', async ({page}) => {
  await login(page,'admin');
  const toggle=page.getByRole('button',{name:'Toggle navigation',exact:true});
  await expect(toggle).toHaveAttribute('aria-expanded','true');
  await toggle.click();
  await expect(page.locator('.sidebar')).not.toBeVisible();
  await expect(toggle).toHaveAttribute('aria-expanded','false');
  await expect(page.getByRole('heading',{name:'Case status trend',exact:true})).toBeVisible();
  await toggle.click();
  await expect(page.locator('.sidebar')).toBeVisible();
});

test('submission fills content width with accessible toggle buttons', async ({page}) => {
  await page.setViewportSize({width:1440,height:1000});
  await login(page,'student');
  await page.goto('/cases/new/');
  await expect(page.getByText('A little detail.',{exact:false})).toHaveCount(0);
  const form=await page.locator('.submission-form').boundingBox();
  const main=await page.locator('main').boundingBox();
  expect(form.width).toBeGreaterThan(main.width-80);
  await page.getByLabel('Suggestion',{exact:true}).check();
  await expect(page.getByLabel('Suggestion',{exact:true})).toBeChecked();
  await expect(page.getByLabel('Complaint',{exact:true})).not.toBeChecked();
  await page.getByLabel('Urgent',{exact:true}).check();
  await expect(page.getByLabel('Urgent',{exact:true})).toBeChecked();
  await page.getByLabel('Urgent',{exact:true}).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByLabel('Normal',{exact:true})).toBeChecked();
  const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(result.violations).toEqual([]);
  await page.screenshot({path:'test-results/submission-flat-desktop.png',fullPage:true});
});

test('sort buttons change ordering parameters and preserve filters', async ({page}) => {
  await login(page,'admin');
  await page.goto('/reports/?priority=normal');
  const controls=page.getByRole('navigation',{name:'Sort cases',exact:true});
  await expect(controls.getByRole('link',{name:'Newest',exact:true})).toHaveAttribute('aria-current','true');
  await controls.getByRole('link',{name:'Oldest',exact:true}).click();
  await expect(page).toHaveURL(/sort=submitted_at/);
  expect(new URL(page.url()).searchParams.get('priority')).toBe('normal');
  await expect(controls.getByRole('link',{name:'Oldest',exact:true})).toHaveAttribute('aria-current','true');
  await controls.getByRole('link',{name:'Urgent first',exact:true}).click();
  await expect(page).toHaveURL(/sort=-priority/);
  await expect(controls.getByRole('link',{name:'Urgent first',exact:true})).toHaveAttribute('aria-current','true');
});

test('flat colours on authentication, submission and reports', async ({page}) => {
  async function noGradients() {
    const gradients=await page.locator('body').evaluate(body => [...body.querySelectorAll('*')].flatMap(node => ['', '::before', '::after'].map(pseudo => ({tag:node.tagName, image:getComputedStyle(node,pseudo||null).backgroundImage}))).filter(item => /gradient\(/i.test(item.image)));
    expect(gradients).toEqual([]);
  }
  await page.goto('/accounts/login/');
  await noGradients();
  await login(page,'student');
  await page.goto('/cases/new/');
  await noGradients();
  await logout(page);
  await login(page,'admin');
  await page.goto('/reports/');
  await noGradients();
});

test('dashboard and charts reflect a new database submission on reload', async ({page}) => {
  await login(page,'student');
  const totalBefore=Number(await page.locator('.metric-value').first().textContent());
  const submissionsBefore=Number(await page.locator('.chart-data tbody tr').last().locator('td').first().textContent());
  await page.goto('/cases/new/');
  await page.getByLabel('Complaint',{exact:true}).check();
  await choose(page,'Category','Facilities');
  await page.getByLabel('Location',{exact:true}).fill('Library');
  await page.getByLabel('Short title',{exact:true}).fill('Verify database-backed dashboard');
  await page.getByLabel('Description',{exact:true}).fill('A real test submission for chart updates.');
  await page.getByLabel('I confirm').check();
  await page.getByRole('button',{name:'Submit case',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Verify database-backed dashboard',exact:true})).toBeVisible();
  await page.goto('/');
  await expect(page.locator('.metric-value').first()).toHaveText(String(totalBefore+1));
  await expect(page.locator('.donut-center strong')).toHaveText(String(totalBefore+1));
  await expect(page.locator('.chart-data tbody tr').last().locator('td').first()).toHaveText(String(submissionsBefore+1));
});
