import { HTTP } from "@/api/v4/base";

/*
 * Composite bootstrap endpoint. One round trip returns
 *   {
 *     user: { id, username, email, isStaff, isSuperuser } | null,
 *     adminFlags: { needs Documentation },
 *     permissions: { isStaff, isSuperuser },
 *     version: { installed, latest, outdated, docker, dockerHub },
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
  HTTP.put("/auth/timezone", {
    timezone: new Intl.DateTimeFormat().resolvedOptions().timeZone,
  });

export const updatePassword = (credentials) =>
  HTTP.post("/auth/password/change", credentials);

export const sendResetPasswordLink = (login) =>
  HTTP.post("/auth/password/reset", { login });

export const resetPassword = (payload) =>
  HTTP.post("/auth/password/reset/confirm", payload);

/*
 * API keys: named, scoped credentials for apps and devices. Only the create
 * response carries the key itself.
 */
export const getApiKeys = () => HTTP.get("/auth/keys");
export const createApiKey = ({ name, scope }) =>
  HTTP.post("/auth/keys", { name, scope });
export const deleteApiKey = (pk) => HTTP.delete(`/auth/keys/${pk}`);

// The URLs of the APIs this visitor may use. Never cached.
export const getApiUrls = () =>
  HTTP.get("/api-urls", { params: { ts: Date.now() } });
