import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AgentReviewNotice } from "./AgentReviewNotice";

test("is absent when nothing is waiting", () => {
  const { container } = render(
    <MemoryRouter>
      <AgentReviewNotice count={0} />
    </MemoryRouter>,
  );
  expect(container).toBeEmptyDOMElement();
});

test("links to the filtered list with the count", () => {
  render(
    <MemoryRouter>
      <AgentReviewNotice count={4} />
    </MemoryRouter>,
  );
  const link = screen.getByRole("link");
  expect(link).toHaveAttribute("href", "/items?needs_agent_review=true");
  expect(link).toHaveTextContent("4 items have agent changes awaiting your eye");
});
