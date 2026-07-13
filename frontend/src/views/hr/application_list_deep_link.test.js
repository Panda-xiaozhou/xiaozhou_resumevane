import assert from "node:assert/strict";
import { test } from "node:test";

import {
  findApplicationByDeepLink,
  getDeepLinkedApplicationId,
} from "./application_list_deep_link.js";

test("getDeepLinkedApplicationId reads application_id query string", () => {
  assert.equal(
    getDeepLinkedApplicationId({ query: { application_id: "app-1" } }),
    "app-1"
  );
});

test("findApplicationByDeepLink returns the matching application row", () => {
  const row = findApplicationByDeepLink(
    [
      { id: "app-1", candidate_name: "张三" },
      { id: "app-2", candidate_name: "李四" },
    ],
    "app-2"
  );

  assert.deepEqual(row, { id: "app-2", candidate_name: "李四" });
});

test("findApplicationByDeepLink returns null when id is absent", () => {
  assert.equal(findApplicationByDeepLink([{ id: "app-1" }], "missing"), null);
  assert.equal(findApplicationByDeepLink([{ id: "app-1" }], ""), null);
});
