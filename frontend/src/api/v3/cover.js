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

export const getCoverSource = (group, cover) => {
  let src;
  if (cover?.pk) {
    const basePath = getReaderBasePath(cover.pk);
    src = `${basePath}/cover.webp?ts=${cover.mtime}`;
    if (group) {
      src += `&group=${group}`;
    }
    if (cover?.custom) {
      src += `&custom=1`;
    }
  } else {
    const name = COVER_MAP[group];
    src = window.CODEX.STATIC + "img/" + name + ".svg";
  }
  return src;
};
