import assert from "node:assert/strict";
import { test } from "node:test";

import { shouldShowFailureReason } from "./application_list_failure_reason.js";

test("shows failure reason for screening failures", () => {
  assert.equal(
    shouldShowFailureReason({
      status: "screening_failed",
      push_status: "none",
      failure_reason: "解析失败",
    }),
    true
  );
});

test("shows failure reason for feishu push failures on passed applications", () => {
  assert.equal(
    shouldShowFailureReason({
      status: "passed",
      push_status: "failed",
      failure_reason: "阶段: file_send；错误码: 999",
    }),
    true
  );
});

test("hides failure reason when there is no failure detail", () => {
  assert.equal(
    shouldShowFailureReason({
      status: "passed",
      push_status: "failed",
      failure_reason: "",
    }),
    false
  );
});
