import { expect, test } from "@playwright/test";

test("live text journey uses Langflow and preserves schema 2.0", async ({ page }) => {
  test.skip(process.env.FAKTAIN_LIVE_SMOKE !== "1", "Requires configured local backend, Langflow and 9Router");
  test.setTimeout(120000);
  await page.goto("/verifikasi");
  await page.getByRole("textbox", { name: "Teks berita" }).fill(
    "Indonesia memproklamasikan kemerdekaan pada 17 Agustus 1945.",
  );
  const response = page.waitForResponse((r) => r.url().endsWith("/analyze") && r.request().method() === "POST");
  await page.getByRole("button", { name: "VERIFIKASI SEKARANG" }).click();
  const result = await (await response).json();
  expect(result.schema_version).toBe("2.0");
  expect(result.orchestration).toBe("langflow");
  expect(result.claims.length).toBeGreaterThan(0);
  expect(result.limitations.join(" ")).not.toMatch(/tidak tersedia|tidak valid|habis/);
  await expect(page.getByRole("region", { name: "Hasil verifikasi" })).toBeVisible();
  await expect(page.getByText("Skor Kredibilitas")).toHaveCount(0);
});

for (const sample of [
  { name: "Prabowo", text: "Prabowo adalah presiden Indonesia ke-8", verdicts: ["SUPPORTED"] },
  { name: "Gibran", text: "gibran adalah wakil presiden indonesia", verdicts: ["SUPPORTED"] },
  { name: "MBG", text: "gibran meeminta siswa untuk stop mbg dan bawa bekal", verdicts: ["SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "MISLEADING"] },
]) {
  test(`live ${sample.name} claim shows validated evidence from Langflow`, async ({ page }) => {
    test.skip(process.env.FAKTAIN_LIVE_SMOKE !== "1", "Requires configured local backend, Langflow and 9Router");
    test.setTimeout(120000);
    await page.goto("/verifikasi");
    await page.getByRole("textbox", { name: "Teks berita" }).pressSequentially(
      sample.text,
    );
    const response = page.waitForResponse((r) => r.url().endsWith("/analyze") && r.request().method() === "POST");
    await page.getByRole("button", { name: "VERIFIKASI SEKARANG" }).click();
    const result = await (await response).json();
    expect(result.schema_version).toBe("2.0");
    expect(result.orchestration).toBe("langflow");
    expect(result.claims).toHaveLength(1);
    expect(sample.verdicts).toContain(result.verdict);
    expect(result.claims[0].claim.toLowerCase()).toBe(sample.text.toLowerCase());
    const evidenceItems = [...result.claims[0].supporting_evidence, ...result.claims[0].contradicting_evidence];
    expect(evidenceItems.length).toBeGreaterThan(0);
    await expect(page.getByRole("region", { name: "Hasil verifikasi" })).toBeVisible();
    for (const evidence of evidenceItems) {
      await expect(page.locator("blockquote").filter({ hasText: evidence.excerpt }).first()).toBeVisible();
      await expect(page.getByRole("link", { name: evidence.title, exact: true }).first()).toHaveAttribute("href", evidence.url);
    }
  });
}
