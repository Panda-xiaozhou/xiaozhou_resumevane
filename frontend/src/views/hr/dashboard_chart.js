const trendDatePattern = /^(?:\d{4}-)?(\d{2})-(\d{2})(?:[T\s].*)?$/;

const formatTrendDateLabel = (date, days) => {
  if (days < 30) {
    return date;
  }

  if (typeof date !== "string") {
    return date;
  }

  const match = date.match(trendDatePattern);
  if (!match) {
    return date;
  }

  return match[2];
};

export { formatTrendDateLabel };
