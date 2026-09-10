import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('dashboard has no automated accessibility violations', async ({ page }) => {
  await page.goto('/dashboard');

  const results = await new AxeBuilder({ page }).analyze();

  expect(results.violations).toEqual([]);
});

test('core workspace pages remain accessible across desktop and mobile routes', async ({ page }) => {
  // Layout is checked at five widths. Automated WCAG analysis runs at the
  // representative mobile and desktop widths because axe is intentionally
  // expensive and accessibility semantics do not change at every breakpoint.
  test.setTimeout(420_000);
  const layoutViewports = [375, 414, 768, 1024, 1440];
  const axeViewports = new Set([375, 1440]);
  const wcagTags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
  const routes = ['/dashboard', '/partners', '/accounting', '/sales', '/invoices', '/bills', '/banking', '/tax', '/audit', '/settings'];

  for (const viewport of layoutViewports) {
    await page.setViewportSize({ width: viewport, height: 900 });
    for (const route of routes) {
      await page.goto(route);
      if (axeViewports.has(viewport)) {
        const results = await new AxeBuilder({ page }).withTags(wcagTags).analyze();
        expect(results.violations, `${route} at ${viewport}px`).toEqual([]);
      }
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        `${route} at ${viewport}px should not overflow horizontally`,
      ).toBe(true);
    }
  }
});
