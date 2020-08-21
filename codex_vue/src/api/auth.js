import { ajax } from "./base";

const registerEnabled = async () => {
  return await ajax("get", "/auth/register");
};

const get_tz = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

const register = async (credentials) => {
  credentials.timezone = get_tz();
  return await ajax("post", "/auth/register", credentials);
};
const login = async (credentials) => {
  credentials.timezone = get_tz();
  return await ajax("post", "/auth/login", credentials);
};

const me = async () => {
  const data = { timezone: get_tz() };
  return await ajax("post", "/auth/me", data);
};

const logout = async () => {
  return await ajax("post", "/auth/logout");
};

export default {
  registerEnabled,
  register,
  login,
  me,
  logout,
};
