import { expect, test } from "@playwright/test";

const ADMIN = { email: "admin@example.com", password: "e2e-admin-pass-12345" };
const MEMBER = { name: "Mo Member", email: "mo@yarrow.example", password: "member-pass-12345" };

async function login(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/(dashboard|items)/);
}

test("golden path: invite -> accept -> create -> update -> drag -> dashboard", async ({ page }) => {
  // 1. Admin signs in and invites a member.
  await login(page, ADMIN.email, ADMIN.password);
  await page.goto("/admin/users");
  await page.getByRole("button", { name: /invite user/i }).click();
  await page.getByLabel("Email").fill(MEMBER.email);
  await page.getByRole("button", { name: /create invitation/i }).click();

  const inviteUrl = await page.locator("input[readonly]").inputValue();
  expect(inviteUrl).toContain("/accept-invite?token=");

  // 2. Accept the invitation (public page).
  await page.goto(inviteUrl.replace(/^https?:\/\/[^/]+/, ""));
  await page.getByLabel("Full name").fill(MEMBER.name);
  await page.getByLabel("Password", { exact: true }).fill(MEMBER.password);
  await page.getByLabel("Confirm password").fill(MEMBER.password);
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/login/);

  // 3. Member signs in and creates an item.
  await login(page, MEMBER.email, MEMBER.password);
  await page.goto("/items");
  await page.getByRole("button", { name: /new item/i }).click();
  await page.getByLabel("Title").fill("E2E stability review");
  await page.getByRole("combobox", { name: /group/i }).click();
  await page.getByRole("option", { name: "General Issues" }).click();
  await page.getByRole("button", { name: /create item/i }).click();
  await expect(page.getByText("E2E stability review")).toBeVisible();

  // 4. Open the item and post an update.
  await page.getByText("E2E stability review").click();
  await page.getByRole("tab", { name: "Updates" }).click();
  await page.getByLabel("New update body").fill("Kicked off the review");
  await page.getByRole("button", { name: /post update/i }).click();
  await expect(page.getByText("Kicked off the review")).toBeVisible();
  await page.keyboard.press("Escape");

  // 5. On the board, drag the card from Open to In progress.
  await page.goto("/board");
  const card = page.getByText("E2E stability review");
  await expect(card).toBeVisible();
  const target = page.getByRole("button", { name: /in progress/i });
  const from = await card.boundingBox();
  const to = await target.boundingBox();
  if (!from || !to) throw new Error("card or target column not found");
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  // dnd-kit's PointerSensor needs movement in steps before it activates the drag.
  await page.mouse.move(from.x + from.width / 2 + 20, from.y + from.height / 2, { steps: 5 });
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2 + 60, { steps: 10 });
  const patched = page.waitForResponse(
    (r) => /\/api\/items\/\d+$/.test(r.url()) && r.request().method() === "PATCH",
  );
  await page.mouse.up();
  await patched; // the optimistic move reached the server

  // 6. The move persisted — the items table shows the new status.
  await page.goto("/items");
  await expect(page.getByRole("row", { name: /E2E stability review/i })).toContainText(
    "In progress",
  );

  // 7. The dashboard activity feed reflects the member's work.
  await page.goto("/dashboard");
  await expect(page.getByText(/recent activity/i)).toBeVisible();
  await expect(page.getByText(MEMBER.name).first()).toBeVisible();
});
