import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['banking:read', 'banking:write'],
};

const account = {
  id: 'bank-account-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  account_code: 'BANK-001',
  name: 'Operating account',
  bank_name: 'Siam Commercial Bank',
  currency_code: 'THB',
  ledger_account_code: '1001',
  is_active: true,
  version: 1,
};

const transaction = {
  id: 'bank-transaction-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  bank_account_id: 'bank-account-1',
  import_batch_id: 'batch-1',
  external_id: 'SCB-0001',
  transaction_date: '2026-09-08',
  value_date: '2026-09-08',
  description: 'Customer settlement',
  reference: 'INV-0001',
  amount: '1070.00',
  status: 'unmatched',
  matched_payment_id: null,
  reconciled_at: null,
  version: 1,
};

const postedReceipt = {
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
  status: 'posted',
  ledger_entry_id: 'entry-1',
  posted_at: '2026-09-08T10:00:00Z',
  version: 2,
  allocations: [],
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

test('banking workbench loads accounts and unmatched transactions', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/banking/accounts**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([account]) });
  });
  await page.route('**/v1/banking/transactions**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([transaction]) });
  });

  await page.goto('/banking');

  await expect(page.getByRole('heading', { name: 'Banking & reconciliation', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Bank account register' }).getByText('Operating account', { exact: true })).toBeVisible();
  await expect(page.getByText('SCB-0001', { exact: true })).toBeVisible();
  await expect(page.getByText('Customer settlement', { exact: true })).toBeVisible();
});

test('bank account creation sends an idempotent organization-scoped request', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/banking/accounts**', async (route) => {
    if (route.request().method() === 'POST') {
      expect(route.request().headers()['idempotency-key']).toMatch(/^banking-account-/);
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(account) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/v1/banking/transactions**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/banking');
  await page.getByRole('button', { name: 'Add bank account' }).click();
  await page.getByLabel('Account code').fill('BANK-001');
  await page.getByLabel('Account name').fill('Operating account');
  await page.getByLabel('Bank name').fill('Siam Commercial Bank');
  await page.getByLabel('Ledger account').fill('1001');
  await page.locator('section[aria-labelledby="create-bank-account-title"]').getByRole('button', { name: 'Create bank account', exact: true }).click();

  await expect(page.getByText('Bank account created')).toBeVisible();
});

test('statement import sends a committed batch with immutable transaction source fields', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/banking/accounts**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([account]) });
  });
  await page.route('**/v1/banking/transactions**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/v1/banking/accounts/bank-account-1/imports**', async (route) => {
    expect(route.request().headers()['idempotency-key']).toMatch(/^banking-import-/);
    const requestBody = JSON.parse(route.request().postData() || '{}') as { batch_reference: string; transactions: unknown[] };
    expect(requestBody.batch_reference).toBe('SCB-2026-09-08');
    expect(requestBody.transactions).toHaveLength(1);
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ id: 'batch-1', transaction_count: 1, transactions: [transaction] }) });
  });

  await page.goto('/banking');
  await page.getByRole('button', { name: 'Import statement' }).click();
  await page.getByLabel('Bank account', { exact: true }).selectOption('bank-account-1');
  await page.getByLabel('Batch reference').fill('SCB-2026-09-08');
  await page.getByLabel('Source name').fill('SCB CSV export');
  await page.getByLabel('Transactions JSON').fill(JSON.stringify([{ external_id: 'SCB-0001', transaction_date: '2026-09-08', description: 'Customer settlement', amount: '1070.00' }]));
  await page.locator('section[aria-labelledby="import-statement-title"]').getByRole('button', { name: 'Commit import', exact: true }).click();

  await expect(page.getByText('Statement imported')).toBeVisible();
});

test('reconciliation links an unmatched movement to a posted payment', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/banking/accounts**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([account]) });
  });
  await page.route('**/v1/banking/transactions**', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...transaction, status: 'reconciled', matched_payment_id: 'payment-1' }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([transaction]) });
  });
  await page.route('**/v1/ar/receipts**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([postedReceipt]) });
  });

  await page.goto('/banking');
  await page.getByRole('button', { name: 'Reconcile' }).click();
  await page.getByLabel('Posted payment').fill('payment-1');
  await page.locator('section[aria-labelledby="reconcile-transaction-title"]').getByRole('button', { name: 'Reconcile transaction', exact: true }).click();

  await expect(page.getByText('Transaction reconciled')).toBeVisible();
});
