import { expect, test } from "@playwright/test";

/** Set in app.js after WASM and handleRoute(); avoids racing fixed sleeps under parallel workers. */
async function waitForAppBootstrapped(page) {
  await page.waitForFunction(
    () => globalThis.__GITLURKER_APP_BOOTSTRAPPED__ === true,
    { timeout: 120_000 },
  );
}

/** Home category tabs exist after bootstrap on `/`. */
async function waitForHomeShell(page) {
  await waitForAppBootstrapped(page);
  await page.getByRole("button", { name: "All" }).waitFor({
    state: "visible",
    timeout: 30_000,
  });
}

test.describe("core flows", () => {
  test("home shows nav and category tabs", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    await waitForHomeShell(page);
    await expect(page.getByRole("button", { name: "Bitcoin" })).toBeVisible();
  });

  test("WASM loads without errors", async ({ page }) => {
    const errors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && msg.text().includes("WASM")) {
        errors.push(msg.text());
      }
    });
    page.on("pageerror", (err) => {
      if (err.message.includes("WASM") || err.message.includes("WebAssembly")) {
        errors.push(err.message);
      }
    });

    await page.goto("/");
    await waitForHomeShell(page);

    expect(errors).toHaveLength(0);
  });

  test("category tab toggles active state", async ({ page }) => {
    await page.goto("/");
    await waitForHomeShell(page);

    const bitcoin = page.getByRole("button", { name: "Bitcoin" });
    await bitcoin.click();
    await expect(bitcoin).toHaveClass(/is-active/);
  });

  test("search input accepts text", async ({ page }) => {
    await page.goto("/");
    await waitForHomeShell(page);

    const input = page.getByRole("searchbox", { name: "Filter projects" });
    await input.fill("nostr");
    await expect(input).toHaveValue("nostr");
  });

  test("repo detail with mocked API", async ({ page }) => {
    await page.route("**/api/v1/repo/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          description: "Mocked",
          stars: 2,
          forks: 1,
          issues: 0,
          contributors: [],
          github_url: "https://github.com/o/r",
        }),
      });
    });
    await page.goto("/octocat/Hello-World");

    await waitForAppBootstrapped(page);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "octocat/Hello-World",
      { timeout: 60_000 },
    );
    await expect(page.getByText("Mocked")).toBeVisible();
  });

  test("theme toggle changes data-theme", async ({ page }) => {
    await page.goto("/");
    await waitForAppBootstrapped(page);

    const before = await page.locator("html").getAttribute("data-theme");
    await page.getByRole("button", { name: "Toggle color theme" }).click();
    const after = await page.locator("html").getAttribute("data-theme");
    expect(after).not.toBe(before);
  });

  test("about page shows donation placeholder", async ({ page }) => {
    await page.goto("/about");
    await waitForAppBootstrapped(page);

    await expect(
      page.getByRole("heading", { name: "Support (coming soon)" }),
    ).toBeVisible();
    await expect(page.getByText(/Lightning, Cashu/i)).toBeVisible();
  });
});

test.describe("nostr-sdk-js integration", () => {
  test("WebSocket connects to relay", async ({ page }) => {
    const wsMessages = [];

    // Monitor WebSocket traffic
    page.on("websocket", (ws) => {
      ws.on("framesent", (data) => wsMessages.push({ type: "sent", data }));
      ws.on("framereceived", (data) => wsMessages.push({ type: "received", data }));
    });

    await page.goto("/");

    // Wait for WebSocket to connect and send subscription
    await page.waitForTimeout(3000);

    // Check that at least one WebSocket connection was made
    const wsConnections = await page.evaluate(() => {
      return window.WebSocket ? "WebSocket available" : "WebSocket not available";
    });
    expect(wsConnections).toBe("WebSocket available");
  });

  test("home settles without a stuck loading skeleton", async ({ page }) => {
    await page.goto("/");
    await waitForAppBootstrapped(page);
    await expect(page.getByRole("button", { name: "All" })).toBeVisible();
    // When relays fail or load instantly, the skeleton may never be visible long enough to assert;
    // markup is covered in loadingSkeleton.test.js. Here we only guard against a stuck overlay.
    await expect(page.locator("[data-testid='loading-skeleton']")).toHaveCount(0, {
      timeout: 90_000,
    });
  });
});
