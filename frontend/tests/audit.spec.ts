import { expect, test } from '@playwright/test';

const adminUser = {
  user_id: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  email: 'admin@example.com',
  display_name: 'Demo Admin',
  roles: ['ADMIN'],
  permissions: ['audit:read'],
};

const event = {
  id: 'event-1',
  tenant_id: 'tenant-1',
  organization_id: 'org-1',
  actor_user_id: 'user-1',
  action: 'payment.post',
  entity_type: 'payment',
  entity_id: 'payment-1',
  correlation_id: 'corr-1',
  payload: { payment_number: 'REC-0001', password: '[REDACTED]' },
  created_at: '2026-09-08T10:00:00Z',
};

async function configureConnectedWorkspace(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('zsme-api-base-url', 'http://127.0.0.1:8000');
    window.sessionStorage.setItem('zsme-access-token', 'session-token');
  });
  await page.route('**/v1/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(adminUser) });
  });
}

test('audit explorer renders server-paginated redacted evidence', async ({ page }) => {
  await configureConnectedWorkspace(page);
  await page.route('**/v1/audit/events**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [event], limit: 50, offset: 0, total: 2, next_offset: 1 }) });
  });

  await page.goto('/audit');

  await expect(page.getByRole('heading', { name: 'Audit & activity', exact: true })).toBeVisible();
  await expect(page.getByText('payment.post', { exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: /\[REDACTED\]/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Load more events' })).toBeVisible();
});

test('audit explorer filters events through the server contract', async ({ page }) => {
  await configureConnectedWorkspace(page);
  let requestedUrl = '';
  await page.route('**/v1/audit/events**', async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], limit: 50, offset: 0, total: 0, next_offset: null }) });
  });

  await page.goto('/audit');
  await page.getByLabel('Action filter').fill('partner.create');
  await page.getByLabel('Entity type filter').fill('business_partner');
  await page.getByRole('button', { name: 'Apply audit filters' }).click();

  await expect.poll(() => requestedUrl).toContain('action=partner.create');
  expect(requestedUrl).toContain('entity_type=business_partner');
});
