import { getReaderBasePath } from "./common";

const COVER_MAP = {
  p: "publisher",
  i: "imprint",
  s: "series",
  v: "volume",
  a: "story-arc",
  f: "folder",
  c: "missing-cover",
};

export const getCoverSource = (pk, mtime, group) => {
  let src;
  if (pk) {
    const basePath = getReaderBasePath(pk);
    src = `${basePath}/cover.webp?ts=${mtime}`;
    if (group) {
      src += `&group=${group}`;
    }
  } else {
    const name = COVER_MAP[group];
    src = window.CODEX.STATIC + "img/" + name + ".svg";
  }
  return src;
};
