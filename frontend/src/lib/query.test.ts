import { qk } from "./query";

test("query keys are stable and hierarchical", () => {
  expect(qk.items.list({ status: ["open"] })).toEqual(["items", "list", { status: ["open"] }]);
  expect(qk.items.detail(7)).toEqual(["items", "detail", 7]);
  expect(qk.items.updates(7)).toEqual(["items", 7, "updates"]);
  expect(qk.items.history(7)).toEqual(["items", 7, "history"]);
  expect(qk.auth.me()).toEqual(["auth", "me"]);
  expect(qk.vocab.list()).toEqual(["vocab"]);
  expect(qk.users.list()).toEqual(["users"]);
});
