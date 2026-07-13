const fallbackPath = "/admin/dashboard";

export const getHrLoginRedirectLocation = (to) => ({
  name: "admin-login",
  query: {
    redirect: to?.fullPath || fallbackPath,
  },
});

export const getHrPostLoginLocation = (route) => {
  const redirect = route?.query?.redirect;
  const value = Array.isArray(redirect) ? redirect[0] : redirect;
  if (typeof value === "string" && value.startsWith("/admin") && value !== "/admin") {
    return value;
  }
  return fallbackPath;
};
