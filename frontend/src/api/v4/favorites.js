import { HTTP } from "@/api/v4/base";

// ``collection`` is the collection name (publishers/series/comics/…) — the
// favorites endpoint speaks the collection vocabulary directly.
export const getFavorites = () => HTTP.get("/favorites");

export const addFavorite = (collection, pk) =>
  HTTP.put(`/favorites/${collection}/${pk}`);

export const removeFavorite = (collection, pk) =>
  HTTP.delete(`/favorites/${collection}/${pk}`);
