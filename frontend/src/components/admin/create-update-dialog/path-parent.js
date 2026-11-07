/*
 * Whether ``potentialChildPath`` is ``path`` or inside it. Shared by the
 * library form's path rules and the folder tree, which disables the
 * folders an existing library already covers.
 */
export const isPathParent = (path, potentialChildPath) => {
  // Normalize the paths to avoid issues with different directory separator characters
  path = path.replaceAll("\\", "/");
  potentialChildPath = potentialChildPath.replaceAll("\\", "/");

  // Ensure that both paths end with a slash to avoid false positives
  if (!path.endsWith("/")) {
    path += "/";
  }
  if (!potentialChildPath.endsWith("/")) {
    potentialChildPath += "/";
  }

  // Check if the potential child path starts with the parent path
  return potentialChildPath.startsWith(path);
};
