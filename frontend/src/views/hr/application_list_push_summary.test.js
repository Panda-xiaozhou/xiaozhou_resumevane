import assert from "node:assert/strict";
import { test } from "node:test";

import { buildSelectedPushMessage } from "./application_list_push_summary.js";

test("buildSelectedPushMessage summarizes pushed failed and missing counts", () => {
  assert.equal(
    buildSelectedPushMessage({
      pushed_count: 2,
      failed_count: 1,
      missing_ids: ["missing"],
    }),
    "已推送 2 条，失败 1 条，1 条未找到或无权限"
  );
});

test("buildSelectedPushMessage handles all pushed result", () => {
  assert.equal(
    buildSelectedPushMessage({
      pushed_count: 3,
      failed_count: 0,
      missing_ids: [],
    }),
    "已推送 3 条"
  );
});
