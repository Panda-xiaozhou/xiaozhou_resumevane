export const shouldShowFailureReason = (row) => {
  if (!row?.failure_reason) {
    return false;
  }
  return row.status === "screening_failed" || row.push_status === "failed";
};
