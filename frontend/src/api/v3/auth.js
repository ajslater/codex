import { HTTP } from "@/api/v3/base";
import { serializeParams } from "@/api/v3/common";

const getAdminFlags = () => HTTP.get("/auth/flags/");

const updateTimezone = () =>
  HTTP.put("/auth/timezone/", {
    timezone: new Intl.DateTimeFormat().resolvedOptions().timeZone,
  });

// Backend reads ``login`` (django-allauth field name); the form binds to
// ``username``. Spread instead of mutating so the caller's reactive form
// state doesn't grow a stray ``login`` field.
const register = (credentials) =>
  HTTP.post("/auth/register/", { ...credentials, login: credentials.username });

const login = (credentials) =>
  HTTP.post("/auth/login/", { ...credentials, login: credentials.username });

const getProfile = () =>
  HTTP.get("/auth/profile/", { params: serializeParams() });

const logout = () => HTTP.post("/auth/logout/");

const updatePassword = (credentials) =>
  HTTP.post("/auth/change-password/", credentials);

const getToken = () => HTTP.get("/auth/token/");

const updateToken = () => HTTP.put("/auth/token/");

export default {
  updatePassword,
  getAdminFlags,
  getProfile,
  getToken,
  login,
  logout,
  register,
  updateTimezone,
  updateToken,
};
