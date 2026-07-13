export const buildSelectedPushMessage = (payload) => {
  const parts = [`已推送 ${payload?.pushed_count || 0} 条`];
  const failedCount = payload?.failed_count || 0;
  const missingCount = payload?.missing_ids?.length || 0;
  if (failedCount) {
    parts.push(`失败 ${failedCount} 条`);
  }
  if (missingCount) {
    parts.push(`${missingCount} 条未找到或无权限`);
  }
  return parts.join("，");
};
