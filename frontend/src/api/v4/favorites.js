import { HTTP } from "@/api/v4/base";

// ``group`` is the collection name (publishers/series/comics/…) — the favorites
// endpoint speaks the collection vocabulary directly.
export const getFavorites = () => HTTP.get("/favorites");

export const addFavorite = (group, pk) => HTTP.put(`/favorites/${group}/${pk}`);

export const removeFavorite = (group, pk) =>
  HTTP.delete(`/favorites/${group}/${pk}`);
