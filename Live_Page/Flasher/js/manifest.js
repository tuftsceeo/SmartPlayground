/**
 * Load device manifests (YAML) from manifests/*.yml
 * Parsed in-browser — no build step; works on GitHub Pages.
 */

const cache = new Map();

/**
 * Minimal YAML parser for our manifest shape only:
 *   exclude_ext: [.md, .js]
 *   sources:
 *     - repo: path/in/repo
 *       prefix: lib | ""
 *       include_ext: [.py]   # optional — whitelist
 *       exclude_ext: [.md]    # optional — extra per-source excludes
 *   exclude_dirs: [drafts]    # folders skipped, relative to each source root
 *   exclude_files: [x.py]     # exact file names skipped, in any folder
 */
export function parseManifestYaml(text) {
  const manifest = { excludeExt: [], excludeDirs: [], excludeFiles: [], sources: [] };
  let current = null;
  // "manifest.excludeExt" | "manifest.excludeDirs" | "manifest.excludeFiles"
  // | "source.excludeExt" | "source.includeExt"
  let listTarget = null;

  for (const rawLine of text.split("\n")) {
    const line = rawLine.trimEnd();
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;

    if (t === "exclude_ext:" && !line.startsWith(" ")) {
      listTarget = "manifest.excludeExt";
      continue;
    }
    if (t === "exclude_dirs:" && !line.startsWith(" ")) {
      listTarget = "manifest.excludeDirs";
      continue;
    }
    if (t === "exclude_files:" && !line.startsWith(" ")) {
      listTarget = "manifest.excludeFiles";
      continue;
    }
    if (t === "sources:") {
      listTarget = null;
      continue;
    }
    if (t.startsWith("- ") && listTarget) {
      const val = t.slice(2).trim().replace(/^["']|["']$/g, "");
      if (listTarget === "manifest.excludeExt") manifest.excludeExt.push(val);
      else if (listTarget === "manifest.excludeDirs") manifest.excludeDirs.push(val.replace(/\/$/, ""));
      else if (listTarget === "manifest.excludeFiles") manifest.excludeFiles.push(val);
      else if (listTarget === "source.excludeExt") current.excludeExt.push(val);
      else if (listTarget === "source.includeExt") {
        if (!current.includeExt) current.includeExt = [];
        current.includeExt.push(val);
      }
      continue;
    }
    if (t.startsWith("- repo:")) {
      current = {
        repoPath: t.slice("- repo:".length).trim(),
        devicePrefix: "",
        excludeExt: [],
        includeExt: null,
      };
      manifest.sources.push(current);
      listTarget = null;
      continue;
    }

    if (t.startsWith("prefix:") && current) {
      let p = t.slice("prefix:".length).trim();
      if (p === '""' || p === "''") p = "";
      else p = p.replace(/^["']|["']$/g, "");
      current.devicePrefix = p;
      listTarget = null;
      continue;
    }
    if (t === "exclude_ext:" && current) {
      listTarget = "source.excludeExt";
      continue;
    }
    if (t === "include_ext:" && current) {
      listTarget = "source.includeExt";
      continue;
    }
  }

  return manifest;
}

export function shouldIncludeFile(fileName, source, manifest) {
  const lower = fileName.toLowerCase();
  const ext = lower.includes(".") ? lower.slice(lower.lastIndexOf(".")) : "";

  const includeExt = source.includeExt;
  if (includeExt?.length) {
    return includeExt.some((e) => lower.endsWith(e.toLowerCase()));
  }

  const excludes = [
    ...(manifest.excludeExt || []),
    ...(source.excludeExt || []),
  ].map((e) => e.toLowerCase());

  if (excludes.some((e) => (e.startsWith(".") ? ext === e : lower.endsWith(e)))) {
    return false;
  }
  return true;
}

/**
 * True when a source-relative path falls in an exclude_dirs folder or its file
 * name is listed in exclude_files.
 */
export function isExcludedPath(relInSource, manifest) {
  const name = relInSource.split("/").pop();
  if ((manifest.excludeFiles || []).includes(name)) return true;
  return (manifest.excludeDirs || []).some(
    (d) => relInSource === d || relInSource.startsWith(d + "/")
  );
}

export async function loadManifest(fileName) {
  if (cache.has(fileName)) return cache.get(fileName);
  const url = new URL(`../manifests/${fileName}`, import.meta.url);
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Manifest not found: ${fileName}`);
  const parsed = parseManifestYaml(await resp.text());
  cache.set(fileName, parsed);
  return parsed;
}
