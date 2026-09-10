import { expect, test } from '@playwright/test';

test('login does not submit credentials when the API endpoint is missing', async ({ page }) => {
  let loginAttempted = false;
  page.on('request', (request) => {
    if (request.url().includes('/v1/auth/login')) {
      loginAttempted = true;
    }
  });

  await page.goto('/login');
  await page.getByLabel('Workspace slug').fill('demo');
  await page.getByLabel('Work email').fill('admin@example.com');
  await page.getByLabel('Password').fill('correct horse battery staple');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByText('Authentication service is not connected in this environment. No credentials were sent.')).toBeVisible();
  expect(loginAttempted).toBe(false);
});

test('configured login exchanges credentials and establishes a session', async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://127.0.0.1:8000');
  });
  await page.route('**/v1/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'session-token', token_type: 'bearer', expires_in: 1800, csrf_token: 'csrf-token' }),
    });
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user_id: 'user-1',
        tenant_id: 'tenant-1',
        organization_id: 'org-1',
        email: 'admin@example.com',
        display_name: 'Demo Admin',
        roles: ['ADMIN'],
        permissions: ['accounting:read'],
      }),
    });
  });

  await page.goto('/login');
  await page.getByLabel('Workspace slug').fill('demo');
  await page.getByLabel('Work email').fill('admin@example.com');
  await page.getByLabel('Password').fill('correct horse battery staple');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect.poll(() => page.evaluate(() => window.sessionStorage.getItem('zsme-access-token'))).toBeNull();
  await expect(page.getByText('Demo Admin')).toBeVisible();
});
