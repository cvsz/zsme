import { expect, test } from '@playwright/test';

test('dashboard exposes a keyboard-navigable shell and honest empty state', async ({ page }) => {
  await page.goto('/dashboard');

  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Open search' })).toBeVisible();
  await expect(page.getByText('Data source not configured')).toBeVisible();

  await page.getByRole('button', { name: 'Open search' }).focus();
  await expect(page.getByRole('button', { name: 'Open search' })).toBeFocused();
});

test('shell has no horizontal overflow at mobile width', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/dashboard');

  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
});

test('theme switch exposes both dark and light modes', async ({ page }) => {
  await page.goto('/dashboard');
  const themeToggle = page.getByRole('button', { name: 'Switch to light theme' });

  await themeToggle.click();

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByRole('button', { name: 'Switch to dark theme' })).toBeVisible();
});

test('core workspace routes render their own page headings', async ({ page }) => {
  test.setTimeout(120_000);

  for (const route of [
    '/dashboard',
    '/partners',
    '/accounting',
    '/accounting/chart-of-accounts',
    '/accounting/periods',
    '/accounting/reconciliation',
    '/sales',
    '/invoices',
    '/bills',
    '/reports',
    '/reports/trial-balance',
    '/reports/profit-loss',
    '/reports/balance-sheet',
    '/reports/general-ledger',
    '/reports/aged-receivable',
    '/reports/aged-payable',
    '/tax',
    '/receipts',
    '/disbursements',
    '/banking',
    '/audit',
    '/settings',
  ]) {
    await page.goto(route);
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('body')).not.toContainText('404');
  }
});


test('global search returns scoped workspace results', async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://127.0.0.1:8000');
    document.cookie = 'zsme_csrf=test-csrf; Path=/';
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user_id: 'user-1',
        tenant_id: 'tenant-1',
        organization_id: 'org-1',
        organization_currency: 'THB',
        organization_timezone: 'Asia/Bangkok',
        email: 'admin@example.com',
        display_name: 'Demo Admin',
        roles: ['ADMIN'],
        permissions: ['partner:read'],
      }),
    });
  });
  await page.route('**/v1/search?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{
          kind: 'partner',
          id: 'partner-1',
          label: 'CUS-ACME · Acme Thailand',
          meta: 'customer',
          href: '/partners?search=CUS-ACME',
        }],
      }),
    });
  });

  await page.goto('/dashboard');
  await page.getByRole('button', { name: 'Open search' }).click();
  await page.getByRole('searchbox', { name: 'Search workspace' }).fill('Acme');

  await expect(page.getByText('CUS-ACME · Acme Thailand')).toBeVisible();
  await expect(page.getByText('partner · customer')).toBeVisible();
});
