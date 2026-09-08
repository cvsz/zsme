import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['partner:read', 'partner:write'],
};

const partner = {
  id: 'partner-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  partner_code: 'CUS-0001',
  partner_type: 'customer',
  display_name: 'Siam Craft Co., Ltd.',
  legal_name: 'Siam Craft Company Limited',
  tax_id: '0105559000001',
  tax_branch: '00000',
  email: 'finance@siamcraft.example',
  phone: '+66 2 000 0000',
  payment_terms_days: 30,
  credit_limit: '100000.00',
  is_active: true,
  version: 1,
  tags: ['priority'],
  addresses: [],
};

async function configureConnectedWorkspace(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://api.test');
    window.sessionStorage.setItem('zsme-access-token', 'session-token');
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(adminUser) });
  });
}

test('partner directory loads connected tenant records', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/partners*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([partner]) });
  });

  await page.goto('/partners');

  await expect(page.getByRole('heading', { name: 'Customers & vendors' })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'CUS-0001' })).toBeVisible();
  await expect(page.getByText('Siam Craft Co., Ltd.')).toBeVisible();
  await expect(page.getByText('No partners yet')).toHaveCount(0);
});

test('partner directory reports a safe API failure', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/partners*', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/problem+json',
      body: JSON.stringify({ status: 503, code: 'service_unavailable', detail: 'temporary outage' }),
    });
  });

  await page.goto('/partners');

  await expect(page.getByRole('alert', { name: 'Partner data needs attention' })).toContainText('Partner data is unavailable');
  await expect(page.getByRole('button', { name: 'Retry partner load' })).toBeVisible();
});

test('partner creation sends an idempotency key and updates the directory', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestBody: Record<string, unknown> | undefined;
  let idempotencyKey = '';
  await page.route('**/v1/partners*', async (route) => {
    if (route.request().method() === 'POST') {
      requestBody = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
      idempotencyKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          ...partner,
          id: 'partner-2',
          partner_code: 'VEN-0001',
          partner_type: 'vendor',
          display_name: 'Bangkok Supply Co.',
          payment_terms_days: 45,
        }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/partners');
  await page.getByRole('button', { name: 'Add partner' }).click();
  await page.getByLabel('Partner code').fill('VEN-0001');
  await page.getByLabel('Partner name').fill('Bangkok Supply Co.');
  await page.getByLabel('Partner type', { exact: true }).selectOption('vendor');
  await page.getByLabel('Tax ID').fill('0105559000002');
  await page.getByRole('button', { name: 'Create partner', exact: true }).click();

  await expect(page.getByText('Partner created')).toBeVisible();
  await expect(page.getByRole('cell', { name: 'VEN-0001' })).toBeVisible();
  expect(requestBody).toMatchObject({
    partner_code: 'VEN-0001',
    partner_type: 'vendor',
    display_name: 'Bangkok Supply Co.',
    tax_id: '0105559000002',
  });
  expect(idempotencyKey).toMatch(/^partner-create-/);
});

test('partner lifecycle actions send optimistic versions and preserve audit-safe archive behavior', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let updateBody: Record<string, unknown> | undefined;
  let updateKey = '';
  let archiveBody: Record<string, unknown> | undefined;
  let archiveKey = '';
  await page.route('**/v1/partners**', async (route) => {
    if (route.request().method() === 'PATCH') {
      updateBody = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
      updateKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...partner, display_name: 'Siam Craft Holdings', version: 2 }) });
      return;
    }
    if (route.request().method() === 'POST' && route.request().url().endsWith('/archive')) {
      archiveBody = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
      archiveKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...partner, display_name: 'Siam Craft Holdings', is_active: false, version: 3 }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([partner]) });
  });

  await page.goto('/partners');
  await page.getByRole('button', { name: 'Edit' }).click();
  await page.getByLabel('Partner name').fill('Siam Craft Holdings');
  await page.getByRole('button', { name: 'Save partner', exact: true }).click();

  await expect(page.getByText('Partner updated')).toBeVisible();
  await expect(page.getByText('Siam Craft Holdings', { exact: true })).toBeVisible();
  expect(updateBody).toMatchObject({ expected_version: 1, display_name: 'Siam Craft Holdings' });
  expect(updateKey).toMatch(/^partner-update-/);

  await page.getByRole('button', { name: 'Archive' }).click();
  await expect(page.getByRole('alert', { name: /Archive CUS-0001/ })).toBeVisible();
  await page.getByRole('button', { name: 'Confirm archive' }).click();

  await expect(page.getByText('Partner archived')).toBeVisible();
  expect(archiveBody).toEqual({ expected_version: 2 });
  expect(archiveKey).toMatch(/^partner-archive-/);
  await expect(page.getByRole('button', { name: 'Archive' })).toHaveCount(0);
});
