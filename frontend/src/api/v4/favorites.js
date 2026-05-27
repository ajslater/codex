import { HTTP } from "@/api/v4/base";

const GROUP_TO_COLLECTION = Object.freeze({
  p: "publishers",
  i: "imprints",
  s: "series",
  v: "volumes",
  c: "comics",
  f: "folders",
  a: "arcs",
});

const _collection = (group) => GROUP_TO_COLLECTION[group] || group;

export const getFavorites = () => HTTP.get("/favorites");

export const addFavorite = (group, pk) =>
  HTTP.put(`/favorites/${_collection(group)}/${pk}`);

export const removeFavorite = (group, pk) =>
  HTTP.delete(`/favorites/${_collection(group)}/${pk}`);
