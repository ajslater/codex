import { ROOT_PATH } from "./base";

const MISSING_COVER_PATH = ROOT_PATH + window.missingCover;
const COVER_PATH_PREFIX = ROOT_PATH + 'api/v2/c';

export const getCoverSource = (pk, updatedAt) => {
  return pk ? `${COVER_PATH_PREFIX}/${pk}/cover.webp?${updatedAt}` : MISSING_COVER_PATH;
};
