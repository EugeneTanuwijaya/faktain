import { expect, test } from "@playwright/test";

test("FAKTANYA offers news checking and a direct timpa teks upload", async ({ page }) => {
  await page.route("**/news?**", (route) => route.fulfill({ json: { articles: [], last_updated: "" } }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "FAKTANYA", exact: true }).first()).toBeVisible();
  await expect(page).toHaveTitle(/FAKTANYA/);
  await page.screenshot({ path: "test-results/faktanya-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await expect(page.getByRole("heading", { name: "FAKTANYA", exact: true }).first()).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/faktanya-mobile.png", fullPage: true });
  await page.getByRole("link", { name: "Verifikasi Timpa Teks", exact: true }).first().click();
  await expect(page.getByLabel("Gambar atau screenshot")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: "Verifikasi Timpa Teks", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Klaim yang salah belum membuktikan teks telah diedit.", { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Gambar atau screenshot")).toBeVisible();
  await page.getByRole("button", { name: "Teks Berita" }).click();
  await expect(page.getByLabel("Teks berita")).toBeVisible();
  await page.goto("/");
  await page.getByRole("link", { name: "Cek Berita", exact: true }).first().click();
  await expect(page.getByLabel("Teks berita")).toBeVisible();
});
