# Test strategy and verification

Source package validation: `python tools/build_team_handoff.py` verifies the explicit
ownership manifest, disjoint member packages, ZIP integrity, and byte-for-byte source
reconstruction. See [team workflow](team-workflow.md). Test the assembled application,
not an individual contribution overlay.

Tests are derived from the supplied proposal's acceptance criteria (11–22), six roles (§6), lifecycle (§8), notifications (§11), and privacy rules (§12). Test fixtures are isolated from working data. A test failure should lead to an application fix, not a weaker assertion. Test setup defects and environment failures are diagnosed separately from behavior failures.

## Backend

Run `.venv/bin/python manage.py test --verbosity 2` for both apps, or `python manage.py test accounts` / `python manage.py test cases` to select one app. Account tests live in `accounts/tests/`; case and cross-app workflow/privacy tests live in `cases/tests/`.

| Suite | Requirements covered |
| --- | --- |
| `test_acceptance.py` | Submission, evidence validation, unique numbers, review/assignment/rejection/reassignment, authority configuration, progress, mandatory resolution, notifications, metrics, ageing, access, reports |
| `test_workflow.py` | Lifecycle constraints, reopen/feedback, public information requests, audit history, email recipients, reminders, authentication, CSV safety |
| `test_roles.py` | Student, lecturer, administrator, authority, management, system administrator; forbidden pages/actions; attachment privacy after reassignment; no auto assignment; scoped live notification counts; real user creation |
| `test_regressions.py` | Authority counts with multiple officers; failed SMTP delivery must not be marked successful |
| `accounts/tests/test_onboarding.py` | Newly imported users can request a password setup link |
| `accounts/tests/test_account_imports.py` | Unique CPM/lecturer IDs, manual forms, full-file preview/confirm, duplicate/format checks, six-role restrictions, CSRF, stale/replayed previews, preserved records/passwords, password setup, atomic CLI dry run and an 8,000-account batch |
| `test_dashboard_data.py` | Real counts and type proportions, empty states, daily submission vs resolution dates, role/queryset scoping, filter consistency, quick-action prefills |
| `test_report_sorting.py` | Newest/oldest/urgent ordering of real records, retained category filters, safe default for invalid sort parameters |
| `test_i18n.py` | Six roles × three languages, translated validation/notifications, escaping, preference, CSRF, safe redirects, JavaScript catalogs and admin screens |
| `test_cleanup.py` | Preview is read-only; samples are archived before removal; accounts/counters/real submissions preserved; similar real submissions are not removed |

The original 55 acceptance/workflow tests remain. Added tests extend coverage rather than replace those assertions.

## Browser

Install test dependencies with `npm ci`, then `npx playwright install chromium`. Run `npm run test:ui`. Browser binaries use Playwright’s standard external cache; `PLAYWRIGHT_BROWSERS_PATH` can override it. Node dependencies and generated browser reports are local artifacts, not application source.

`tests/browser/server.py` creates a temporary database, applies migrations, creates six test accounts and minimal configuration, and serves on localhost:8765. It overrides the working database and media settings before Django initializes. The temporary directory is removed when the test server stops. SMTP is disabled there.

The browser suite exercises each role separately; it also verifies keyboard dropdown selection/cancellation/typeahead, accessible names and WCAG A/AA automated checks, real submission with evidence, manual assignment and restricted pre-assignment visibility, authority resolution and administrator closure, mobile menu/focus/overflow, native forms without JavaScript, notification count updates, validation focus, and dashboard disclosure controls. Browser traces are retained on failure. Desktop and mobile screenshots are generated in `test-results/`.

Automated accessibility checks supplement manual review; they do not certify complete WCAG compliance or replace assistive-technology user testing. The suite currently targets Chromium. Test on Safari/Firefox and real devices as part of deployment acceptance.

## Verified application fixes

Each of these was reproduced by a failing requirement-based regression before application code was changed:

1. Multiple authority officers multiplied open-case counts: fixed the distinct case aggregation.
2. Failed SMTP sends set `emailed=True`: now only successful recipient sends update the flag.
3. New system administrators created through Django admin lacked staff access: role-aware administrative permissions now match account creation.
4. CSV imports must permit password setup: imported accounts now use an explicit pending-setup flag with the normal expiring reset-link flow, keeping other unusable-password accounts excluded.

5. Mouse selection in the new custom dropdown closed the list before committing: fixed pointer focus retention.
6. Page entrance opacity temporarily reduced text contrast: the entrance now animates position while keeping text fully opaque.

## Results

25 October 2026: backend suite **93 tests passed**; Django system checks and migration consistency checks passed. **33 Chromium browser tests passed**, including the full upload → manual assignment → authority resolution → administrator closure flow. Automated WCAG checks passed for all six role landing pages and the submission form. Desktop/mobile screenshots were visually reviewed. The macOS headless-shell package crashed before testing; the suite uses the full Chromium build in headless mode instead.

Reference-layout validation also covers the chart’s accessible seven-day data table, reporter quick actions without staff-only links, suggestion prefill, and desktop navigation collapse/expand. Screenshots: `test-results/reference-student-desktop.png`, `admin-desktop.png`, and `admin-mobile.png`. These screenshots contain only temporary browser-test records.

Flat-colour/form refinement: the full backend and browser suites passed again after the guide removal, full-width submission layout, native toggle-button styling, SVG donut replacement, and sorting button styling. Browser checks verify no rendered gradients on each role landing page, authentication, submission and reports; form width, keyboard single-choice selection, accessible validation, sorting navigation/filter preservation, and database-backed chart changes after a new submission. Screenshot: `test-results/submission-flat-desktop.png`.

Language coverage: `tests/browser/languages.spec.js` adds six role/language cycles, Sinhala/Tamil mobile and desktop screenshots, accessibility checks, persistent preference, native POST fallback, network failure recovery, and unsaved text/file preservation through language switches and submission. Localized file-picker feedback is checked after each switch. Test databases remain isolated from working complaints. See [language support](languages.md).

Language-menu regression: the focused localization suite passes all 12 tests; native option names remain English, සිංහල and தமிழ் under every active language, avoiding Django’s translated language-name behavior.

### Case detail and multilingual sign-in refinement

`tests/browser/page-layout.spec.js` adds desktop heading-height/form-width checks for English, Sinhala and Tamil, mobile overflow checks, native sign-in in every language without JavaScript, and localized case-detail screenshots with automated accessibility checks. Sign-in regressions first reproduced the narrow 370px form and 285px Sinhala/Tamil display headings. The implementation widens the form and gives these scripts their own typography. Case detail checks verify top navigation, summary placement, description visibility and mobile fit. All records used by these tests are temporary.

25 October 2026 verification after this refinement: **94 backend tests and all 37 Chromium browser tests passed**, including six-role language coverage, attachment privacy and the manual assignment lifecycle. Django system checks passed. Desktop and mobile sign-in/case screenshots were visually reviewed.

Case back-navigation refinement: the case layout browser test checks that the navigation uses the shared primary-button style without underlined text. It retains native navigation and translated labels.

Back-button placement checks verify that the button sits to the right of, and vertically within, the case heading in all three desktop languages; mobile overflow checks cover wrapping.

### Compact dashboard verification

`compact-dashboard.spec.js` first reproduced a 1048px dashboard on a 900px-high screen. It now checks the complete reporter dashboard at 1440×900 with six recent cases in English, Sinhala and Tamil, plus a 1440×720 laptop viewport with one case matching the reference. Every metric, recent row and quick action remains present. The seven-day table still expands, and mobile uses natural scrolling without page overflow. Screenshots are saved as `*-dashboard-compact.png` and `*-dashboard-laptop.png`. Role/privacy and localization backend checks pass (23 tests).

25 October 2026 compact-dashboard results: **all 38 Chromium browser tests passed**, including the new desktop/laptop fit checks, all six roles, three-language accessibility, evidence privacy and manual case lifecycle. **23 role/privacy/localization backend tests passed**, and Django system checks passed. English, Sinhala and Tamil laptop screenshots and the six-case desktop preview were visually reviewed.

### CSV roster onboarding and institutional IDs

Requirement-based tests reproduced the missing upload route and identifier fields before implementation. `accounts/tests/test_account_imports.py` checks five-digit CPM values (including leading zeros), database uniqueness, case-insensitive lecturer IDs, role-specific manual forms, preview without writes, atomic confirmation, retained passwords/active state/cases, duplicate and invalid rows, changed targets, expiry, replay, CSRF and all six roles. An 8,000-row roster is validated with two lookup queries and created in batches in the isolated test database. The CLI shares the atomic validator and dry-run behavior.

`account-import.spec.js` exercises system-administrator uploads and re-imports with JavaScript enabled and disabled, English/Sinhala/Tamil desktop/mobile previews and accessible confirmation. The JavaScript-enabled run performs WCAG A/AA checks; the native run verifies the workflow without JavaScript. A valid accessibility failure exposed indistinguishable breadcrumb links; the shared admin template now underlines them.

The final backend run passes **109 tests**, including all six roles and cross-unit attachment privacy. The 8,000-account batch and actual password-reset confirmation flow also pass. Migration `accounts.0003` was applied locally after a SQLite backup; existing account, case and attachment records were compared with the backup and preserved.

Final roster-import verification: **109 backend tests and all 40 Chromium browser tests pass**. English, Sinhala and Tamil import previews, mobile layout, keyboard-accessible table scrolling and native confirmation were reviewed. Django system/migration consistency checks pass. Sinhala and Tamil server catalogs contain translations for all new strings and were compiled.

### Single-list account filtering

`accounts/tests/test_user_list.py` verifies a prominent role selector, a compact general list, all six role querysets and relevant columns, localized controls, retained search/active/department parameters, resetting pagination/sort and continued restrictions for the other five roles. These tests first failed on the missing control and the original all-column layout. `account-list.spec.js` checks dark-mode WCAG accessibility in all three languages, student/lecturer/authority columns, mobile fit and native filtering without JavaScript. CSV browser checks now inspect each ID in its corresponding role-filtered view.

Single-list refinement validation: **43 focused backend tests and all six account-list/import browser tests passed**. Coverage includes all six role filters, cross-unit privacy, CSV import, English/Sinhala/Tamil, dark mode, mobile and no-JavaScript filtering. The empty department link uncovered by accessibility testing now has a translated “Not specified” label. Django system and migration consistency checks passed; this refinement needs no migration and changes no user records.

### Conventional Django layout cleanup

The complete backend suite was run before moving code (114 tests passed). Account views were consolidated in `accounts/views.py`; case views are now explicit flat modules, including `cases/views.py`. App-owned templates moved inside their apps with case templates namespaced under `cases/`. Account regressions moved into `accounts/tests/`; browser tests and their temporary server moved into `tests/browser/`. Existing assertions and migrations are preserved.

The new `.gitignore` was checked using Git against representative source and local-data paths: secrets, SQLite sidecars, evidence, backups, dependencies and reports are ignored, while migrations, tests, lockfiles, font licences and compiled translations remain eligible for version control. A source/database backup and record/upload hash manifest were created before cleanup. Generated artifacts are removed after verification; reinstall browser tooling with `npm ci` and `npx playwright install chromium` before the next browser run.

Post-cleanup results: **114 backend tests and all 44 Chromium browser tests passed** from the new locations, including all six roles, cross-unit privacy, CSV onboarding, three-language rendering, accessibility and the manual case workflow. Django system and migration consistency checks passed. An AST comparison confirmed that moved view functions retain their original bodies, and every migration file is byte-for-byte unchanged. Existing account/case/attachment records and uploaded files match the pre-cleanup hash manifest.

Approximately **657.9 MiB** of generated browser binaries/caches, Node test dependencies and browser reports was removed, along with first-party bytecode caches. Runtime Python dependencies, the working database, evidence and private recovery backups remain. Browser reports and dependencies are regenerated by the documented setup/test commands; no screenshot artifacts are kept as project source.
