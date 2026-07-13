export const getDeepLinkedApplicationId = (route) => {
  const rawValue = route?.query?.application_id;
  if (Array.isArray(rawValue)) {
    return rawValue[0] || "";
  }
  return rawValue || "";
};

export const findApplicationByDeepLink = (applications, applicationId) => {
  if (!applicationId) {
    return null;
  }
  return applications.find((item) => String(item.id) === String(applicationId)) || null;
};
