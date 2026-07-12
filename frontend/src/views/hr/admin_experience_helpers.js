export const buildApplicationListSummary = (applications, filters) => {
  const total = applications.length;
  const pendingCount = applications.filter((item) => item.status === "pending").length;
  const processingCount = applications.filter((item) => item.status === "processing").length;
  const activeFilterParts = [];

  if (filters.searchText?.trim()) {
    activeFilterParts.push(`关键词：${filters.searchText.trim()}`);
  }

  if (filters.filterStatus) {
    activeFilterParts.push(`状态：${filters.filterStatus}`);
  }

  return {
    total,
    pendingCount,
    resultText: total ? `筛选中 ${processingCount} 条，待筛选 ${pendingCount} 条` : "当前暂无投递记录",
    activeFilterText: activeFilterParts.length ? activeFilterParts.join(" / ") : "未启用额外筛选",
    sortHint: "同分时按投递时间倒序排列",
  };
};
