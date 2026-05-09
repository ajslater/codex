import { HTTP } from "@/api/v3/base";

export const getFavorites = () => HTTP.get("/favorites/");

export const addFavorite = (group, pk) =>
  HTTP.put(`/favorites/${group}/${pk}/`);

export const removeFavorite = (group, pk) =>
  HTTP.delete(`/favorites/${group}/${pk}/`);
