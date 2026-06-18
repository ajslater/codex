import { HTTP } from "@/api/v4/base";

/*
 * Composite bootstrap endpoint. One round trip returns
 *   {
 *     user: { id, username, email, isStaff, isSuperuser } | null,
 *     adminFlags: { needs Documentation },
 *     permissions: { isStaff, isSuperuser },
 *     version: { installed, latest, warning },
 *   }
 */
export const getSession = () => HTTP.get("/session");

export const getCSRF = () => HTTP.get("/auth/csrf");

export const register = (credentials) =>
  HTTP.post("/auth/register", {
    ...credentials,
    login: credentials.username,
  });

export const login = (credentials) =>
  HTTP.post("/auth/login", { ...credentials, login: credentials.username });

export const logout = () => HTTP.post("/auth/logout");

export const getProfile = () => HTTP.get("/auth/profile");
export const updateProfile = (profile) => HTTP.patch("/auth/profile", profile);

export const updateTimezone = () =>
  HTTP.patch("/auth/profile", {
    timezone: new Intl.DateTimeFormat().resolvedOptions().timeZone,
  });

export const updatePassword = (credentials) =>
  HTTP.post("/auth/password/change", credentials);

export const sendResetPasswordLink = (login) =>
  HTTP.post("/auth/password/reset", { login });

export const resetPassword = (payload) =>
  HTTP.post("/auth/password/reset/confirm", payload);

export const getToken = () => HTTP.get("/auth/token");
export const updateToken = () => HTTP.put("/auth/token");
