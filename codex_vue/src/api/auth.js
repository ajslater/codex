import { ajax } from "./base";

const registerEnabled = async () => {
  return await ajax("get", "/auth/register");
};

const register = async (credentials) => {
  return await ajax("post", "/auth/register", credentials);
};
const login = async (credentials) => {
  return await ajax("post", "/auth/login", credentials);
};

const me = async () => {
  return await ajax("get", "/auth/me");
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
