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
  for (const route of ['/dashboard', '/partners', '/accounting', '/sales', '/settings']) {
    await page.goto(route);
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('body')).not.toContainText('404');
  }
});
