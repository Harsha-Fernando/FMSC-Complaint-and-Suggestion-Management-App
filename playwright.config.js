const {defineConfig} = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/browser',
  timeout: 30000,
  workers: 1,
  use: {baseURL: 'http://127.0.0.1:8765', headless: true, channel: 'chromium', trace: 'retain-on-failure'},
  webServer: {
    command: '.venv/bin/python tests/browser/server.py',
    url: 'http://127.0.0.1:8765/accounts/login/',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
