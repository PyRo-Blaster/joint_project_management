import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./button";

test("renders variant classes and fires onClick", async () => {
  const onClick = vi.fn();
  render(
    <Button variant="danger" onClick={onClick}>
      Delete
    </Button>,
  );
  const btn = screen.getByRole("button", { name: "Delete" });
  expect(btn.className).toMatch(/bg-danger/);
  await userEvent.click(btn);
  expect(onClick).toHaveBeenCalledOnce();
});
