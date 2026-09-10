import { expect, test } from '@playwright/test';

test('settings can save and verify a browser API endpoint without storing secrets', async ({ page }) => {
  await page.route('**/ready', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ready', database: 'ok' }),
    });
  });

  await page.goto('/settings');
  await page.getByLabel('API endpoint').fill('http://127.0.0.1:8000');
  await page.getByRole('button', { name: 'Save connection' }).click();
  await expect(page.getByText('Saved locally')).toBeVisible();
  await page.getByRole('button', { name: 'Test connection' }).click();
  await expect(page.getByText('Connected', { exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem('zsme-api-base-url'))).toBe('http://127.0.0.1:8000');
  expect(await page.evaluate(() => window.localStorage.getItem('password'))).toBeNull();
});
