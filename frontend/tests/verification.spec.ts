import { expect, test } from "@playwright/test";

const result = {
  schema_version: "2.0", input_type: "text", verdict: "SUPPORTED",
  reasoning: "Satu klaim didukung oleh sumber yang ditemukan.",
  claims: [{ claim: "Indonesia merdeka 17 Agustus 1945", verdict: "SUPPORTED",
    reasoning: "Tanggal tercantum pada sumber.",
    supporting_evidence: [{ source_id: "S1", title: "Arsip sejarah",
      url: "https://example.com/arsip", excerpt: "Proklamasi berlangsung pada 17 Agustus 1945." }],
    contradicting_evidence: [], limitations: [] }],
  limitations: ["Kebenaran sumber tetap perlu ditinjau manusia."], orchestration: "native",
};

test("text submission renders claim-linked evidence without a score", async ({ page }) => {
  await page.route("**/analyze", async (route) => {
    expect(route.request().postDataJSON()).toEqual({ text: "Indonesia merdeka 17 Agustus 1945" });
    await route.fulfill({ json: result });
  });
  await page.goto("/verifikasi");
  await page.getByRole("textbox", { name: "Teks berita" }).fill("Indonesia merdeka 17 Agustus 1945");
  await page.getByRole("button", { name: "VERIFIKASI SEKARANG" }).click();
  await expect(page.getByRole("link", { name: "Arsip sejarah" })).toHaveAttribute("href", "https://example.com/arsip");
  await expect(page.getByText("Proklamasi berlangsung pada 17 Agustus 1945.")).toBeVisible();
  await expect(page.getByText("Kebenaran sumber tetap perlu ditinjau manusia.")).toBeVisible();
  await expect(page.getByText("Skor Kredibilitas")).toHaveCount(0);
});

test("image upload includes caption and shows OCR plus insufficiency", async ({ page }) => {
  await page.route("**/analyze", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.text).toBe("Banjir hari ini");
    expect(body.image_data_url).toMatch(/^data:image\/png;base64,/);
    await route.fulfill({ json: { ...result, input_type: "image", verdict: "INSUFFICIENT_EVIDENCE", claims: [],
      image_context: { verdict: "INSUFFICIENT_EVIDENCE", reasoning: "Asal foto belum ditemukan.",
        ocr_text: "BANJIR HARI INI", visual_description: "Jalan tergenang air.", evidence: [],
        limitations: ["Konteks waktu belum dapat dipastikan."] } } });
  });
  await page.goto("/verifikasi");
  await page.getByRole("button", { name: "Verifikasi Timpa Teks" }).click();
  await page.getByLabel("Gambar atau screenshot").setInputFiles({ name: "screenshot.png", mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBXYAAAAASUVORK5CYII=", "base64") });
  await expect(page.getByAltText("Pratinjau gambar yang akan diverifikasi")).toBeVisible();
  await page.getByLabel("Caption atau klaim (opsional)").fill("Banjir hari ini");
  await page.getByRole("button", { name: "VERIFIKASI SEKARANG" }).click();
  await expect(page.getByText("BANJIR HARI INI", { exact: true })).toBeVisible();
  await expect(page.getByText("Konteks waktu belum dapat dipastikan.")).toBeVisible();
});

test("URL submission and rate-limit errors remain usable", async ({ page }) => {
  await page.route("**/analyze", async (route) => {
    expect(route.request().postDataJSON()).toEqual({ url: "https://example.com/artikel" });
    await route.fulfill({ status: 429, json: { detail: "Batas analisis tercapai. Coba lagi nanti." } });
  });
  await page.goto("/verifikasi");
  await page.getByRole("button", { name: "URL Artikel" }).click();
  await page.getByLabel("URL artikel").fill("https://example.com/artikel");
  await page.getByRole("button", { name: "VERIFIKASI SEKARANG" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Batas analisis tercapai" })).toBeVisible();
});

test("Google News feed category and article summary UI are preserved", async ({ page }) => {
  await page.route("**/news?**", (route) => route.fulfill({ json: { articles: [{
    id: "n1", title: "Berita Indonesia untuk pengujian", link: "https://example.com/news",
    source: "Media uji", published: "", summary: null, image_url: null,
  }], last_updated: "2026-10-09T00:00:00Z" } }));
  await page.route("**/news/n1/summarize", (route) => route.fulfill({ json: {
    id: "n1", title: "Berita Indonesia untuk pengujian", source: "Media uji",
    original_url: "https://example.com/news", summary: "Ringkasan isi berita asli untuk pengujian.",
  } }));
  await page.goto("/news");
  await page.getByRole("tab", { name: "Teknologi", exact: true }).click();
  await page.getByRole("button", { name: /Ringkas AI/ }).first().click();
  await expect(page.getByText("Ringkasan isi berita asli untuk pengujian.")).toBeVisible();
  await expect(page.getByRole("link", { name: /BACA ARTIKEL ASLI/ })).toHaveAttribute("href", "https://example.com/news");
});
