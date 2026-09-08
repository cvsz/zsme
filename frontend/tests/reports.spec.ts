import { expect, test, type Page } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['reports:read'],
};

const report = {
  from_date: '2026-01-01',
  to_date: '2026-12-31',
  rows: [
    { account_code: '1001', account_name: 'Operating bank', account_type: 'asset', debit: '1070.00', credit: '0.00', balance: '1070.00' },
    { account_code: '4000', account_name: 'Revenue', account_type: 'revenue', debit: '0.00', credit: '1070.00', balance: '-1070.00' },
  ],
  total_debit: '1070.00',
  total_credit: '1070.00',
};

const profitLoss = {
  from_date: '2026-01-01',
  to_date: '2026-12-31',
  rows: [
    { account_code: '4000', account_name: 'Revenue', amount: '1070.00' },
    { account_code: '5100', account_name: 'Operating expense', amount: '370.00' },
  ],
  total_revenue: '1070.00',
  total_expenses: '370.00',
  net_income: '700.00',
};

const balanceSheet = {
  as_of: '2026-12-31',
  assets: [{ account_code: '1001', account_name: 'Operating bank', amount: '1070.00' }],
  liabilities: [{ account_code: '2100', account_name: 'Accounts payable', amount: '370.00' }],
  equity: [],
  total_assets: '1070.00',
  total_liabilities: '370.00',
  total_equity: '700.00',
  net_income: '700.00',
  total_liabilities_and_equity: '1070.00',
};

const generalLedger = {
  from_date: '2026-01-01',
  to_date: '2026-12-31',
  rows: [{ entry_id: 'entry-1', reference: 'REPORT-001', journal_date: '2026-09-08', account_code: '1001', memo: 'Customer receipt', source_type: 'manual', debit: '1070.00', credit: '0.00' }],
  total_debit: '1070.00',
  total_credit: '1070.00',
};

const aged = {
  as_of: '2026-12-31',
  document_type: 'sales_invoice',
  rows: [{ document_id: 'document-1', document_number: 'INV-001', partner_id: 'partner-1', issue_date: '2026-11-01', due_date: '2026-11-30', total: '1070.00', allocated: '0.00', outstanding: '1070.00', bucket: '1_30' }],
  bucket_totals: { current: '0.00', '1_30': '1070.00', '31_60': '0.00', '61_90': '0.00', over_90: '0.00' },
  current_total: '0.00',
  overdue_total: '1070.00',
  total_outstanding: '1070.00',
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

test('trial balance loads posted ledger data with date scope and totals', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestedUrl = '';
  await page.route('**/v1/reports/trial-balance**', async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(report) });
  });

  await page.goto('/reports/trial-balance');

  await expect(page.getByRole('heading', { name: 'Reports & insights', exact: true })).toBeVisible();
  await expect(page.getByText('Operating bank', { exact: true })).toBeVisible();
  await expect(page.getByText('THB 1,070.00', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('Balanced', { exact: true })).toBeVisible();
  expect(requestedUrl).toContain('from_date=2026-01-01');
  expect(requestedUrl).toContain('to_date=2026-12-31');
});

test('trial balance date controls reload the server report contract', async ({ page }) => {
  await configureConnectedWorkspace(page);
  const requestedUrls: string[] = [];
  await page.route('**/v1/reports/trial-balance**', async (route) => {
    requestedUrls.push(route.request().url());
    const url = new URL(route.request().url());
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...report, from_date: url.searchParams.get('from_date'), to_date: url.searchParams.get('to_date') }) });
  });

  await page.goto('/reports/trial-balance');
  await page.getByLabel('From date').fill('2026-04-01');
  await page.getByLabel('To date').fill('2026-06-30');
  await page.getByRole('button', { name: 'Run report' }).click();

  await expect.poll(() => requestedUrls.at(-1) || '').toContain('from_date=2026-04-01');
  expect(requestedUrls.at(-1)).toContain('to_date=2026-06-30');
});

test('profit and loss loads its dedicated server-derived contract', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestedUrl = '';
  await page.route('**/v1/reports/profit-loss**', async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(profitLoss) });
  });

  await page.goto('/reports/profit-loss');
  await expect(page.getByRole('heading', { name: 'Profit & loss', exact: true })).toBeVisible();
  await expect(page.getByText('Revenue', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('THB 700.00', { exact: true }).first()).toBeVisible();
  expect(requestedUrl).toContain('from_date=2026-01-01');
  expect(requestedUrl).toContain('to_date=2026-12-31');
});

test('balance sheet, general ledger and ageing pages use dedicated contracts', async ({ page }) => {
  await configureConnectedWorkspace(page);
  const requestedUrls: string[] = [];
  await page.route('**/v1/reports/**', async (route) => {
    const url = new URL(route.request().url());
    requestedUrls.push(url.toString());
    const body = url.pathname.endsWith('/balance-sheet')
      ? balanceSheet
      : url.pathname.endsWith('/general-ledger')
        ? generalLedger
        : { ...aged, document_type: url.pathname.endsWith('/aged-payable') ? 'vendor_bill' : 'sales_invoice' };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });

  await page.goto('/reports/balance-sheet');
  await expect(page.getByText('Operating bank', { exact: true })).toBeVisible();
  await expect(page.getByLabel('As-of date')).toBeVisible();
  await page.getByLabel('As-of date').fill('2026-11-30');
  await page.getByRole('button', { name: 'Run report' }).click();
  await expect.poll(() => requestedUrls.at(-1) || '').toContain('as_of=2026-11-30');

  await page.goto('/reports/general-ledger');
  await expect(page.getByText('REPORT-001', { exact: true })).toBeVisible();

  await page.goto('/reports/aged-receivable');
  await expect(page.getByText('INV-001', { exact: true })).toBeVisible();
  await page.goto('/reports/aged-payable');
  await expect(page.getByText('1–30 days', { exact: true })).toBeVisible();
});
