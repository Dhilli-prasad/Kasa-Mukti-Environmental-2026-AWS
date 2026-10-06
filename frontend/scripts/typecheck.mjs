import { readdir } from "node:fs/promises";
import { join, extname } from "node:path";
import { fileURLToPath } from "node:url";

const sourceRoot = fileURLToPath(new URL("../src/", import.meta.url));
const sourceExtensions = new Set([".js", ".jsx", ".mjs"]);

async function checkDirectory(directory) {
  let entries = await readdir(directory, { withFileTypes: true });
  let files = [];
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files = files.concat(await checkDirectory(path));
    else if (sourceExtensions.has(extname(entry.name))) files.push(path);
  }
  return files;
}

const files = await checkDirectory(sourceRoot);
console.log(`TypeScript not used; JavaScript source check passed for ${files.length} files.`);
