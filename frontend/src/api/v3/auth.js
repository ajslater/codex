import { serializeParams } from "@/api/v3/common";

import { HTTP } from "./base";

const getAdminFlags = async () => {
  return await HTTP.get("/auth/flags/");
};

const get_tz = () => new Intl.DateTimeFormat().resolvedOptions().timeZone;

const updateTimezone = async () => {
  const data = {
    timezone: get_tz(),
  };
  return await HTTP.put("/auth/timezone/", data);
};

const register = async (credentials) => {
  credentials.login = credentials.username;
  return await HTTP.post("/auth/register/", credentials);
};

const login = async (credentials) => {
  credentials.login = credentials.username;
  return await HTTP.post("/auth/login/", credentials);
};

const getProfile = async () => {
  const params = serializeParams();
  return await HTTP.get("/auth/profile/", { params });
};

const logout = async () => {
  return await HTTP.post("/auth/logout/");
};

const updatePassword = async (credentials) => {
  return await HTTP.post("/auth/change-password/", credentials);
};

const getToken = async () => {
  return await HTTP.get("/auth/token/");
};

const updateToken = async () => {
  return await HTTP.put("/auth/token/");
};

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
