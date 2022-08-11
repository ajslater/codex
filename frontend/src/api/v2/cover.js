import { ROOT_PATH } from "./base";

const COVER_PATH_PREFIX = ROOT_PATH + "api/v2/c";

export const getCoverSource = (pk, updatedAt) => {
  return pk
    ? `${COVER_PATH_PREFIX}/${pk}/cover.webp?${updatedAt}`
    : window.CODEX.MISSING_COVER;
};
