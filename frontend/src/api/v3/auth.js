import { HTTP } from "./base";

const getAdminFlags = async () => {
  return await HTTP.get("/auth/flags/");
};

const get_tz = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

const setTimezone = async () => {
  const data = {
    timezone: get_tz(),
  };
  return await HTTP.post("/auth/timezone/", data);
};

const register = async (credentials) => {
  // This should not be neccissary TODO
  credentials.login = credentials.username;
  return await HTTP.post("/auth/register/", credentials);
};

const login = async (credentials) => {
  // This should not be neccissary TODO
  credentials.login = credentials.username;
  return await HTTP.post("/auth/login/", credentials);
};

const getProfile = async () => {
  return await HTTP.get("/auth/profile/");
};

const logout = async () => {
  return await HTTP.post("/auth/logout/");
};

const changePassword = async (credentials) => {
  return await HTTP.post("/auth/change-password/", credentials);
};

export default {
  changePassword,
  getAdminFlags,
  getProfile,
  login,
  logout,
  register,
  setTimezone,
};
