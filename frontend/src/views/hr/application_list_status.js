const applicationStatusMetaMap = {
  pending: {
    label: "待筛选",
    tagType: "info",
  },
  processing: {
    label: "筛选中",
    tagType: "warning",
  },
  passed: {
    label: "已通过",
    tagType: "success",
  },
  pending_review: {
    label: "待复审",
    tagType: "warning",
  },
  rejected: {
    label: "未通过",
    tagType: "danger",
  },
};

const pushStatusMetaMap = {
  none: {
    label: "未推送",
    tagType: "info",
  },
  pushing: {
    label: "推送中",
    tagType: "warning",
  },
  pushed: {
    label: "已推送",
    tagType: "success",
  },
  failed: {
    label: "推送失败",
    tagType: "danger",
  },
};

export const getApplicationStatusMeta = (status) =>
  applicationStatusMetaMap[status] || {
    label: status || "-",
    tagType: "info",
  };

export const getPushStatusMeta = (status) => {
  if (!status) {
    return null;
  }

  return pushStatusMetaMap[status] || {
    label: status,
    tagType: "info",
  };
};
