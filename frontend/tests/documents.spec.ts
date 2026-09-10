import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['ar:read', 'ar:write', 'ap:read', 'ap:write', 'partner:read'],
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
  email: null,
  phone: null,
  payment_terms_days: 30,
  credit_limit: '0.00',
  is_active: true,
  version: 1,
  tags: [],
  addresses: [],
};

const invoice = {
  id: 'document-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  document_type: 'sales_invoice',
  document_number: 'INV-0001',
  partner_id: 'partner-1',
  issue_date: '2026-09-08',
  due_date: '2026-10-08',
  currency_code: 'THB',
  control_account_code: '1100',
  tax_account_code: '2101',
  memo: null,
  subtotal: '1000.00',
  tax_total: '70.00',
  total: '1070.00',
  status: 'draft',
  ledger_entry_id: null,
  posted_at: null,
  version: 1,
  lines: [
    {
      id: 'line-1',
      document_id: 'document-1',
      line_no: 1,
      description: 'Implementation service',
      quantity: '1.000',
      unit_price: '1000.00',
      tax_rate: '7.00',
      net_amount: '1000.00',
      tax_amount: '70.00',
      total_amount: '1070.00',
      account_code: '4000',
    },
  ],
};

async function configureConnectedWorkspace(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://127.0.0.1:8000');
    document.cookie = 'zsme_csrf=test-csrf; Path=/';
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(adminUser) });
  });
  await page.route('**/v1/partners*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([partner]) });
  });
}

test('invoice register loads live documents and partner identity', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/ar/invoices**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([invoice]) });
  });

  await page.goto('/invoices');

  await expect(page.getByRole('heading', { name: 'Sales invoices', exact: true })).toBeVisible();
  await expect(page.getByText('INV-0001', { exact: true })).toBeVisible();
  await expect(page.getByText('Siam Craft Co., Ltd.')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Sales invoices register' }).getByText('THB 1,070.00')).toBeVisible();
});

test('invoice creation sends a tenant-scoped draft with an idempotency key', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestBody: Record<string, unknown> | undefined;
  let idempotencyKey = '';
  await page.route('**/v1/ar/invoices**', async (route) => {
    if (route.request().method() === 'POST') {
      requestBody = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
      idempotencyKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(invoice) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/invoices');
  await page.getByRole('button', { name: 'Create invoice' }).click();
  await page.getByLabel('Document number').fill('INV-0002');
  await page.getByLabel('Partner', { exact: true }).selectOption('partner-1');
  await page.getByLabel('Line description').fill('Design retainer');
  await page.getByLabel('Unit price').fill('2500');
  await page.locator('section[aria-labelledby="invoice-create-title"]').getByRole('button', { name: 'Create invoice', exact: true }).click();

  await expect(page.getByText('Draft invoice created')).toBeVisible();
  expect(requestBody).toMatchObject({
    document_number: 'INV-0002',
    partner_id: 'partner-1',
    currency_code: 'THB',
  });
  expect(idempotencyKey).toMatch(/^document-create-/);
});

test('invoice posting requires an explicit idempotent action', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let postKey = '';
  await page.route('**/v1/ar/invoices**', async (route) => {
    if (route.request().method() === 'POST') {
      postKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...invoice, status: 'posted', ledger_entry_id: 'entry-1' }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([invoice]) });
  });

  await page.goto('/invoices');
  await page.getByRole('button', { name: 'Post invoice INV-0001' }).click();

  await expect.poll(() => postKey).not.toBe('');
  await expect(page.getByText('Invoice posted')).toBeVisible();
  expect(postKey).toMatch(/^document-post-/);
});
