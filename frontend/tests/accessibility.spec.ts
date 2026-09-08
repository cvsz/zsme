import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('dashboard has no automated accessibility violations', async ({ page }) => {
  await page.goto('/dashboard');

  const results = await new AxeBuilder({ page }).analyze();

  expect(results.violations).toEqual([]);
});

test('core workspace pages remain accessible across desktop and mobile routes', async ({ page }) => {
  test.setTimeout(240_000);
  for (const viewport of [375, 414, 768, 1024, 1440]) {
    await page.setViewportSize({ width: viewport, height: 900 });
    for (const route of ['/dashboard', '/partners', '/accounting', '/sales', '/invoices', '/bills', '/banking', '/audit', '/settings']) {
      await page.goto(route);
      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations, `${route} at ${viewport}px`).toEqual([]);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        `${route} at ${viewport}px should not overflow horizontally`,
      ).toBe(true);
    }
  }
});
