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


test('settings manages audited role assignments', async ({ page }) => {
  let submittedRoles: string[] = [];
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://127.0.0.1:8000');
    document.cookie = 'zsme_csrf=test-csrf; Path=/';
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user_id: 'admin-1',
        tenant_id: 'tenant-1',
        organization_id: 'org-1',
        organization_currency: 'THB',
        organization_timezone: 'Asia/Bangkok',
        email: 'admin@example.com',
        display_name: 'Admin',
        roles: ['ADMIN'],
        permissions: ['organization:read', 'organization:write'],
      }),
    });
  });
  await page.route('**/v1/access/users', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'admin-1',
          email: 'admin@example.com',
          display_name: 'Admin',
          organization_id: 'org-1',
          is_active: true,
          roles: [{ id: 'admin-role', name: 'ADMIN', permissions: ['organization:write'], is_system: true }],
        },
        {
          id: 'operator-1',
          email: 'operator@example.com',
          display_name: 'Operator',
          organization_id: 'org-1',
          is_active: true,
          roles: [],
        },
      ]),
    });
  });
  await page.route('**/v1/access/roles', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'viewer-role', name: 'VIEWER', permissions: ['reports:read'], is_system: false },
      ]),
    });
  });
  await page.route('**/v1/access/users/operator-1/roles', async (route) => {
    submittedRoles = (await route.request().postDataJSON()).role_ids;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'operator-1',
        email: 'operator@example.com',
        display_name: 'Operator',
        organization_id: 'org-1',
        is_active: true,
        roles: [{ id: 'viewer-role', name: 'VIEWER', permissions: ['reports:read'], is_system: false }],
      }),
    });
  });

  await page.goto('/settings');
  const viewer = page.getByRole('checkbox', { name: /VIEWER/ });
  await expect(viewer).toBeVisible();
  await viewer.check();
  await page.getByRole('button', { name: 'Save roles' }).click();

  await expect.poll(() => submittedRoles).toEqual(['viewer-role']);
  await expect(page.getByText(/Operator · operator@example.com · VIEWER/)).toBeVisible();
});
