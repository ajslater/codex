import { HTTP } from "@/api/v3/base";
import { serializeParams } from "@/api/v3/common";

export const getAdminFlags = () => HTTP.get("/auth/flags/");

export const updateTimezone = () =>
  HTTP.put("/auth/timezone/", {
    timezone: new Intl.DateTimeFormat().resolvedOptions().timeZone,
  });

// Backend reads ``login`` (django-allauth field name); the form binds to
// ``username``. Spread instead of mutating so the caller's reactive form
// state doesn't grow a stray ``login`` field.
export const register = (credentials) =>
  HTTP.post("/auth/register/", { ...credentials, login: credentials.username });

export const login = (credentials) =>
  HTTP.post("/auth/login/", { ...credentials, login: credentials.username });

export const getProfile = () =>
  HTTP.get("/auth/profile/", { params: serializeParams() });

export const logout = () => HTTP.post("/auth/logout/");

export const updatePassword = (credentials) =>
  HTTP.post("/auth/change-password/", credentials);

export const getToken = () => HTTP.get("/auth/token/");

export const updateToken = () => HTTP.put("/auth/token/");
