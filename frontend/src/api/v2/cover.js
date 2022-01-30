import { ROOT_PATH } from "./base";

const MISSING_COVER_PATH = `${ROOT_PATH}static/img/missing_cover.png`;

export const getCoverSource = (coverPath) => {
  if (coverPath == "missing_cover.png") {
    return MISSING_COVER_PATH;
  }
  return `${ROOT_PATH}covers/${coverPath}`;
};
