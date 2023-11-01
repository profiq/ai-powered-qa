import { test, expect } from "@playwright/test";

test("My example test name", async ({ page }) => {
  await page.goto("https://dev.app.serenityapp.com");
  await page
    .locator("input[name='email']")
    .fill("viktor.nawrath+tester@profiq.com");
  await page.locator("input[name='password']").fill("TestPassword!");
  await page.click(
    "button[data-testid='SignInPage-submit'] >> visible=1 >> nth=0",
    { strict: false, timeout: 3000 }
  );
  await page
    .locator("div[contenteditable='true']")
    .fill("This is a test message.");
  await page.click("button[data-testid='SendMessage'] >> visible=1 >> nth=0", {
    strict: false,
    timeout: 3000,
  });
  await page.click(
    "div[data-testid='AppBar-my-account-button'] >> visible=1 >> nth=0",
    { strict: false, timeout: 3000 }
  );
  await page.click(
    "li[data-testid='AppBar-log-out-BasicMenuItem'] >> visible=1 >> nth=0",
    { strict: false, timeout: 3000 }
  );
});
