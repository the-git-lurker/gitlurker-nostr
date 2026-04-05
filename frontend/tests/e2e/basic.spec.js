import { expect, test } from "@playwright/test";

test("home page title contains GitLurker", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/GitLurker/i);
});

test("WASM module loads successfully", async ({ page }) => {
  // This test verifies the nostr-sdk-js WASM module loads without errors
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(err.message));

  await page.goto("/");

  // Wait for WASM initialization (nostr-sdk-js requires loadWasmAsync())
  await page.waitForTimeout(2000);

  // Verify no WASM-related errors
  const wasmErrors = consoleErrors.filter(
    (e) => e.includes("WASM") || e.includes("loadWasm") || e.includes("WebAssembly")
  );
  expect(wasmErrors).toHaveLength(0);
});
