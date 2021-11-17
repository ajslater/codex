import { ajax } from "./base";

// REST ENDPOINTS

const poll = () => {
  return ajax("post", `/poll`);
};

export default {
  poll,
};
