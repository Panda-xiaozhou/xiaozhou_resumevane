import assert from "node:assert/strict";
import { test } from "node:test";

import {
  getHrLoginRedirectLocation,
  getHrPostLoginLocation,
} from "./hr_auth_redirect.js";

test("getHrLoginRedirectLocation preserves admin deep link full path", () => {
  assert.deepEqual(
    getHrLoginRedirectLocation({
      name: "admin-job-applications",
      path: "/admin/jobs/job-1",
      fullPath: "/admin/jobs/job-1?application_id=app-1",
    }),
    {
      name: "admin-login",
      query: {
        redirect: "/admin/jobs/job-1?application_id=app-1",
      },
    }
  );
});

test("getHrPostLoginLocation returns redirect query when present", () => {
  assert.equal(
    getHrPostLoginLocation({
      query: {
        redirect: "/admin/jobs/job-1?application_id=app-1",
      },
    }),
    "/admin/jobs/job-1?application_id=app-1"
  );
});

test("getHrPostLoginLocation falls back to dashboard", () => {
  assert.equal(getHrPostLoginLocation({ query: {} }), "/admin/dashboard");
});
