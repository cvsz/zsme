import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['accounting:read', 'accounting:write'],
};

const entry = {
  id: 'entry-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  fiscal_period_id: 'period-1',
  reference: 'AR-202609-0001',
  journal_date: '2026-09-08',
  memo: 'Service invoice',
  status: 'posted',
  source_type: 'invoice',
  source_id: 'document-1',
  reversal_of_id: null,
  posted_at: '2026-09-08T10:00:00Z',
  created_at: '2026-09-08T10:00:00Z',
  lines: [
    { id: 'line-1', line_no: 1, account_code: '1100', debit: '1070.00', credit: '0.00', memo: null },
    { id: 'line-2', line_no: 2, account_code: '4000', debit: '0.00', credit: '1070.00', memo: null },
  ],
  total_debit: '1070.00',
  total_credit: '1070.00',
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

test('journal workspace loads posted entries and keeps source lineage visible', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/accounting/journal-entries**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [entry], limit: 50, offset: 0, total: 1, next_offset: null }) });
  });

  await page.goto('/accounting');

  await expect(page.getByRole('heading', { name: 'Accounting workspace', exact: true })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Posted journal entries' }).getByRole('cell', { name: /AR-202609-0001/ }).first()).toBeVisible();
  await expect(page.getByText('invoice', { exact: true })).toBeVisible();
  await expect(page.getByText('THB 1,070.00', { exact: true }).first()).toBeVisible();
});

test('journal posting sends balanced lines with an idempotency key', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestBody: Record<string, unknown> | undefined;
  let idempotencyKey = '';
  await page.route('**/v1/accounting/journal-entries**', async (route) => {
    if (route.request().method() === 'POST') {
      requestBody = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
      idempotencyKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ entry_id: 'entry-2', status: 'posted', total: '100.00', audit_event_id: 'audit-2' }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], limit: 50, offset: 0, total: 0, next_offset: null }) });
  });

  await page.goto('/accounting');
  await page.getByRole('button', { name: 'New journal entry' }).click();
  await page.locator('section[aria-labelledby="journal-create-title"]').getByLabel('Reference').fill('MANUAL-0001');
  await page.getByLabel('Source type').fill('manual');
  await page.getByLabel('Line 1 account').fill('1001');
  await page.getByLabel('Line 1 debit').fill('100');
  await page.getByLabel('Line 2 account').fill('4000');
  await page.getByLabel('Line 2 credit').fill('100');
  await page.locator('section[aria-labelledby="journal-create-title"]').getByRole('button', { name: 'Post journal entry', exact: true }).click();

  await expect(page.getByText('Journal entry posted')).toBeVisible();
  expect(requestBody).toMatchObject({
    reference: 'MANUAL-0001',
    source_type: 'manual',
    lines: [
      { account_code: '1001', debit: '100', credit: '0' },
      { account_code: '4000', debit: '0', credit: '100' },
    ],
  });
  expect(idempotencyKey).toMatch(/^journal-post-/);
});
