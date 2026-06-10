import { shouldIncludeFile } from "./manifest.js";

const GH_HEADERS = { Accept: "application/vnd.github+json" };

export function toRawUrl(url) {
  url = url.trim();
  if (url.includes("raw.githubusercontent.com")) return url;
  url = url.replace("https://github.com/", "https://raw.githubusercontent.com/");
  url = url.replace("/blob/", "/");
  return url;
}

function joinDevicePath(prefix, relInRepo) {
  if (!prefix) return relInRepo;
  if (!relInRepo) return prefix;
  return `${prefix}/${relInRepo}`;
}

function normalizeSources(manifest) {
  return manifest.sources.map((s) => ({
    ...s,
    repoPath: s.repoPath.replace(/\/$/, ""),
    devicePrefix: s.devicePrefix ?? "",
  }));
}

function rawFileUrl(owner, name, ref, repoPath) {
  const encodedPath = repoPath.split("/").map(encodeURIComponent).join("/");
  return `https://raw.githubusercontent.com/${owner}/${name}/${encodeURIComponent(ref)}/${encodedPath}`;
}

async function getTreeSha(repo, ref) {
  const { owner, repo: name } = repo;
  const resp = await fetch(
    `https://api.github.com/repos/${owner}/${name}/commits/${encodeURIComponent(ref)}`,
    { headers: GH_HEADERS }
  );
  if (!resp.ok) throw new Error(`GitHub ref "${ref}" not found (${resp.status})`);
  const data = await resp.json();
  return data.commit.tree.sha;
}

/** Fallback recursive contents API (used if trees API fails). */
async function fetchFolderRecursive(
  apiUrl,
  devicePrefix,
  source,
  manifest,
  fetchedFiles,
  { log, onProgress }
) {
  const resp = await fetch(apiUrl, { headers: GH_HEADERS });
  if (!resp.ok) {
    log?.(`  ⚠ API ${resp.status} for ${apiUrl}`, "err");
    return 0;
  }
  const items = await resp.json();
  if (!Array.isArray(items)) return 0;

  let count = 0;
  for (const item of items) {
    const relInFolder = item.name;
    const deviceRel = joinDevicePath(devicePrefix, relInFolder);
    if (item.type === "file") {
      if (!shouldIncludeFile(item.name, source, manifest)) {
        log?.(`  ⊘ skipping ${deviceRel}`, "dim");
        continue;
      }
      onProgress?.(deviceRel);
      try {
        const r = await fetch(item.download_url || toRawUrl(item.html_url));
        if (r.ok) {
          fetchedFiles[deviceRel] = await r.text();
          count++;
        }
      } catch (e) {
        log?.(`  ⚠ ${e.message}`, "err");
      }
    } else if (item.type === "dir" && item.url) {
      const subPrefix = joinDevicePath(devicePrefix, item.name);
      const subSource = { ...source, devicePrefix: subPrefix };
      log?.(`  📁 ${subPrefix}/`, "dim");
      count += await fetchFolderRecursive(
        item.url,
        subPrefix,
        subSource,
        manifest,
        fetchedFiles,
        { log, onProgress }
      );
    }
  }
  return count;
}

/**
 * Fetch files defined by a device manifest (manifests/*.yml).
 * Returns { [deviceRelativePath]: content }.
 */
export async function fetchManifestFiles(repo, ref, manifest, { log, onProgress } = {}) {
  const { owner, repo: name } = repo;
  const fetchedFiles = {};
  const sources = normalizeSources(manifest);

  try {
    const treeSha = await getTreeSha(repo, ref);
    const treeResp = await fetch(
      `https://api.github.com/repos/${owner}/${name}/git/trees/${treeSha}?recursive=1`,
      { headers: GH_HEADERS }
    );
    if (!treeResp.ok) throw new Error(`GitHub trees API ${treeResp.status}`);
    const tree = await treeResp.json();
    if (!tree.tree) throw new Error("Unexpected trees API response");

    for (const item of tree.tree) {
      if (item.type !== "blob") continue;
      for (const src of sources) {
        if (item.path !== src.repoPath && !item.path.startsWith(src.repoPath + "/")) continue;
        const fileName = item.path.split("/").pop();
        if (!shouldIncludeFile(fileName, src, manifest)) {
          log?.(`  ⊘ skipping ${item.path}`, "dim");
          break;
        }
        const relInRepo = item.path.slice(src.repoPath.length).replace(/^\//, "");
        const deviceRel = joinDevicePath(src.devicePrefix, relInRepo);
        onProgress?.(deviceRel);
        log?.(`  📄 ${item.path} → ${deviceRel}`, "dim");
        const r = await fetch(rawFileUrl(owner, name, ref, item.path));
        if (!r.ok) {
          log?.(`  ⚠ HTTP ${r.status} for ${item.path}`, "err");
          break;
        }
        fetchedFiles[deviceRel] = await r.text();
        break;
      }
    }

    if (Object.keys(fetchedFiles).length === 0) {
      throw new Error("No files matched manifest on this branch");
    }
    return fetchedFiles;
  } catch (treesErr) {
    log?.(`  ⚠ Trees API failed (${treesErr.message}), falling back…`, "warn");
    return fetchManifestFilesFallback(repo, ref, manifest, { log, onProgress });
  }
}

async function fetchManifestFilesFallback(repo, ref, manifest, { log, onProgress } = {}) {
  const { owner, repo: name } = repo;
  const fetchedFiles = {};

  for (const src of manifest.sources) {
    const apiUrl = `https://api.github.com/repos/${owner}/${name}/contents/${src.repoPath}?ref=${encodeURIComponent(ref)}`;
    log?.(`📦 Fetching ${src.repoPath}/ …`, "dim");
    const prefix = src.devicePrefix || "";
    const resp = await fetch(apiUrl, { headers: GH_HEADERS });
    if (!resp.ok) throw new Error(`GitHub API ${resp.status} for ${src.repoPath}`);
    const items = await resp.json();
    if (!Array.isArray(items)) throw new Error(`Unexpected response for ${src.repoPath}`);

    for (const item of items) {
      if (item.type === "file") {
        if (!shouldIncludeFile(item.name, src, manifest)) continue;
        const deviceRel = joinDevicePath(prefix, item.name);
        onProgress?.(deviceRel);
        const r = await fetch(item.download_url || toRawUrl(item.html_url));
        if (r.ok) fetchedFiles[deviceRel] = await r.text();
      } else if (item.type === "dir" && item.url) {
        const subPrefix = joinDevicePath(prefix, item.name);
        await fetchFolderRecursive(
          item.url,
          subPrefix,
          { ...src, devicePrefix: subPrefix },
          manifest,
          fetchedFiles,
          { log, onProgress }
        );
      }
    }
  }

  if (Object.keys(fetchedFiles).length === 0) {
    throw new Error("No files fetched from GitHub");
  }
  return fetchedFiles;
}

/** @deprecated use fetchManifestFiles */
export const fetchSourcesForDevice = (repo, ref, sources, opts) =>
  fetchManifestFiles(repo, ref, { sources, excludeExt: [".md", ".js"] }, opts);

export async function listBranchesAndTags(repo) {
  const { owner, repo: name } = repo;
  const base = `https://api.github.com/repos/${owner}/${name}`;
  const [branchResp, tagResp] = await Promise.all([
    fetch(`${base}/branches?per_page=100`, { headers: GH_HEADERS }),
    fetch(`${base}/tags?per_page=100`, { headers: GH_HEADERS }),
  ]);
  const branches = branchResp.ok ? (await branchResp.json()).map((b) => b.name) : [];
  const tags = tagResp.ok ? (await tagResp.json()).map((t) => t.name) : [];
  return [...new Set([...branches, ...tags])].sort();
}
