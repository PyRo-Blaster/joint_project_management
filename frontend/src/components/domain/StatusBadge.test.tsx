import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

test("labels a known status and treats null as a note", () => {
  const { rerender } = render(<StatusBadge status="in_progress" />);
  expect(screen.getByText("In progress")).toBeInTheDocument();
  rerender(<StatusBadge status={null} />);
  expect(screen.getByText("Note")).toBeInTheDocument();
});
