import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['tax:read', 'tax:write'],
};

const vatRule = {
  id: 'tax-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  tax_type: 'vat',
  code: 'VAT7',
  name: 'Value added tax 7%',
  rate: '7.00',
  effective_from: '2026-01-01',
  effective_to: null,
  is_active: true,
  version: 1,
};

async function configureConnectedWorkspace(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://127.0.0.1:8000');
    window.sessionStorage.setItem('zsme-access-token', 'session-token');
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(adminUser) });
  });
}

test('tax workbench loads organization rules and effective dates', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/tax/rates**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([vatRule]) });
  });

  await page.goto('/tax');

  await expect(page.getByRole('heading', { name: 'Tax configuration', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'VAT7', exact: true })).toBeVisible();
  await expect(page.getByText('Value added tax 7%', { exact: true })).toBeVisible();
  await expect(page.getByText('7.00%', { exact: true })).toBeVisible();
});

test('tax rule creation sends an idempotent effective-dated request', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestBody: Record<string, unknown> | undefined;
  let idempotencyKey = '';
  await page.route('**/v1/tax/rates**', async (route) => {
    if (route.request().method() === 'POST') {
      requestBody = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
      idempotencyKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ ...vatRule, id: 'tax-2', code: 'VAT0', name: 'Zero-rated VAT', rate: '0.00' }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/tax');
  await page.getByRole('button', { name: 'Add tax rule' }).click();
  await page.getByLabel('Tax code').fill('VAT0');
  await page.getByLabel('Tax rule name').fill('Zero-rated VAT');
  await page.getByLabel('Rate (%)').fill('0');
  await page.locator('section[aria-labelledby="create-tax-title"]').getByRole('button', { name: 'Create tax rule', exact: true }).click();

  await expect(page.getByText('Tax rule created')).toBeVisible();
  expect(requestBody).toMatchObject({ tax_type: 'vat', code: 'VAT0', name: 'Zero-rated VAT', rate: '0' });
  expect(idempotencyKey).toMatch(/^tax-rate-create-/);
});
