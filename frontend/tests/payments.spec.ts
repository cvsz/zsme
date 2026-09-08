import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['ar:read', 'ar:write', 'partner:read'],
};

const partner = {
  id: 'partner-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  partner_code: 'CUS-0001',
  partner_type: 'customer',
  display_name: 'Siam Craft Co., Ltd.',
  legal_name: null,
  tax_id: null,
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

const vendorPartner = {
  ...partner,
  id: 'vendor-1',
  partner_code: 'VEN-0001',
  partner_type: 'vendor',
  display_name: 'Bangkok Supply Co.',
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
  status: 'posted',
  ledger_entry_id: 'entry-1',
  posted_at: '2026-09-08T10:00:00Z',
  version: 2,
  lines: [],
};

const bill = { ...invoice, id: 'bill-1', document_type: 'vendor_bill', document_number: 'BILL-0001', partner_id: 'vendor-1' };

const receipt = {
  id: 'payment-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  payment_type: 'receipt',
  payment_number: 'REC-0001',
  partner_id: 'partner-1',
  payment_date: '2026-09-08',
  currency_code: 'THB',
  amount: '1070.00',
  cash_account_code: '1001',
  unapplied_account_code: null,
  memo: null,
  status: 'draft',
  ledger_entry_id: null,
  posted_at: null,
  version: 1,
  allocations: [{ id: 'allocation-1', payment_id: 'payment-1', document_id: 'document-1', amount: '1070.00' }],
};

async function configureConnectedWorkspace(page: Page, kind: 'receipt' | 'disbursement' = 'receipt') {
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://api.test');
    window.sessionStorage.setItem('zsme-access-token', 'session-token');
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(adminUser) });
  });
  await page.route('**/v1/partners*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([kind === 'receipt' ? partner : vendorPartner]) });
  });
  await page.route('**/v1/ar/invoices**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([invoice]) });
  });
  await page.route('**/v1/ap/bills**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([bill]) });
  });
}

test('receipt register loads live payments and allocation identity', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/ar/receipts**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([receipt]) });
  });

  await page.goto('/receipts');

  await expect(page.getByRole('heading', { name: 'Customer receipts', exact: true })).toBeVisible();
  await expect(page.getByText('REC-0001', { exact: true })).toBeVisible();
  await expect(page.getByText('Siam Craft Co., Ltd.')).toBeVisible();
  await expect(page.getByRole('row', { name: /REC-0001/ }).getByText('THB 1,070.00').first()).toBeVisible();
});

test('receipt creation sends allocation and idempotency controls', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestBody: Record<string, unknown> | undefined;
  let idempotencyKey = '';
  await page.route('**/v1/ar/receipts**', async (route) => {
    if (route.request().method() === 'POST') {
      requestBody = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>;
      idempotencyKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(receipt) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/receipts');
  await page.getByRole('button', { name: 'Record receipt' }).click();
  await page.getByLabel('Payment number').fill('REC-0002');
  await page.getByLabel('Partner', { exact: true }).selectOption('partner-1');
  await page.getByLabel('Payment amount').fill('1070');
  await page.getByLabel('Allocate to document').selectOption('document-1');
  await page.getByLabel('Allocation amount').fill('1070');
  await page.locator('section[aria-labelledby="receipt-create-title"]').getByRole('button', { name: 'Record receipt', exact: true }).click();

  await expect(page.getByText('Draft receipt created')).toBeVisible();
  expect(requestBody).toMatchObject({
    payment_number: 'REC-0002',
    partner_id: 'partner-1',
    amount: '1070',
    allocations: [{ document_id: 'document-1', amount: '1070' }],
  });
  expect(idempotencyKey).toMatch(/^payment-create-/);
});

test('receipt posting is a separate idempotent control action', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let postKey = '';
  await page.route('**/v1/ar/receipts**', async (route) => {
    if (route.request().method() === 'POST') {
      postKey = route.request().headers()['idempotency-key'] || '';
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...receipt, status: 'posted', ledger_entry_id: 'entry-2' }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([receipt]) });
  });

  await page.goto('/receipts');
  await page.getByRole('button', { name: 'Post receipt REC-0001' }).click();

  await expect(page.getByText('Receipt posted')).toBeVisible();
  expect(postKey).toMatch(/^payment-post-/);
});

test('disbursement register uses the vendor bill and AP payment boundaries', async ({ page }) => {
  await configureConnectedWorkspace(page, 'disbursement');
  const disbursement = { ...receipt, id: 'payment-2', payment_type: 'disbursement', payment_number: 'PAY-0001', partner_id: 'vendor-1', allocations: [] };
  await page.route('**/v1/ap/disbursements**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([disbursement]) });
  });

  await page.goto('/disbursements');

  await expect(page.getByRole('heading', { name: 'Vendor disbursements', exact: true })).toBeVisible();
  await expect(page.getByText('PAY-0001', { exact: true })).toBeVisible();
  await expect(page.getByText('Bangkok Supply Co.')).toBeVisible();
});
