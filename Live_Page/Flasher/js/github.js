import { shouldIncludeFile } from "./manifest.js";

const GH_HEADERS = { Accept: "application/vnd.github+json" };
const CACHE_NAME = "flasher-gh-v1";

// In-memory fallback when the Cache API is unavailable (e.g. insecure context).
const memCache = new Map();

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Throw a clear, actionable error when GitHub has throttled us. A 403/429 with
 * X-RateLimit-Remaining: 0 means the unauthenticated 60 req/hour bucket is empty.
 */
function rateLimitError(resp) {
  const remaining = resp.headers.get("X-RateLimit-Remaining");
  if ((resp.status === 403 || resp.status === 429) && remaining === "0") {
    const reset = Number(resp.headers.get("X-RateLimit-Reset"));
    let when = "shortly";
    if (reset) {
      const mins = Math.max(1, Math.ceil((reset * 1000 - Date.now()) / 60000));
      when = `in ~${mins} min`;
    }
    return new Error(`GitHub rate limit reached — try again ${when}.`);
  }
  return null;
}

function isRetryableStatus(resp) {
  if (resp.status === 429 || resp.status >= 500) return true;
  // 403 from the API is usually rate limiting; retry only if it looks transient
  // (not the hard "remaining: 0" case, which we surface immediately).
  if (resp.status === 403 && resp.headers.get("X-RateLimit-Remaining") !== "0") return true;
  return false;
}

/**
 * fetch() with exponential backoff + jitter. Retries on network errors and
 * retryable statuses (429, 5xx, transient 403). Surfaces a clear error when the
 * rate-limit bucket is exhausted. Returns the final Response otherwise.
 */
async function fetchWithRetry(url, opts = {}, { retries = 3 } = {}) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    if (attempt > 0) {
      const delay = 400 * 2 ** (attempt - 1) + Math.floor(Math.random() * 200);
      await sleep(delay);
    }
    try {
      const resp = await fetch(url, opts);
      const limit = rateLimitError(resp);
      if (limit) throw limit;
      if (resp.ok || !isRetryableStatus(resp)) return resp;
      lastErr = new Error(`HTTP ${resp.status} for ${url}`);
    } catch (e) {
      // A thrown rateLimitError should not be retried — re-throw immediately.
      if (e instanceof Error && e.message.startsWith("GitHub rate limit")) throw e;
      lastErr = e;
    }
  }
  throw lastErr || new Error(`Failed to fetch ${url}`);
}

/**
 * Cache-first fetch for immutable (SHA-pinned) URLs. Stores the response in the
 * Cache API so repeated flashes of the same commit hit the network only once.
 * Returns the response text. Throws on non-OK responses (after retries).
 */
async function cachedText(url, opts = {}) {
  let cache = null;
  if (typeof caches !== "undefined") {
    try {
      cache = await caches.open(CACHE_NAME);
    } catch {
      cache = null;
    }
  }

  if (cache) {
    const hit = await cache.match(url);
    if (hit) return hit.text();
  } else if (memCache.has(url)) {
    return memCache.get(url);
  }

  const resp = await fetchWithRetry(url, opts);
  if (!resp.ok) throw new Error(`HTTP ${resp.status} for ${url}`);

  if (cache) {
    await cache.put(url, resp.clone());
  } else {
    memCache.set(url, await resp.clone().text());
  }
  return resp.text();
}

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

function rawFileUrl(owner, name, sha, repoPath) {
  const encodedPath = repoPath.split("/").map(encodeURIComponent).join("/");
  return `https://raw.githubusercontent.com/${owner}/${name}/${sha}/${encodedPath}`;
}

/**
 * Resolve a branch/tag/ref to its immutable commit + tree SHAs. This call stays
 * always-fresh (it's how we detect a new commit on a branch); everything keyed
 * off these SHAs is cached.
 */
async function resolveRef(repo, ref) {
  const { owner, repo: name } = repo;
  const resp = await fetchWithRetry(
    `https://api.github.com/repos/${owner}/${name}/commits/${encodeURIComponent(ref)}`,
    { headers: GH_HEADERS }
  );
  if (!resp.ok) throw new Error(`GitHub ref "${ref}" not found (${resp.status})`);
  const data = await resp.json();
  return { commitSha: data.sha, treeSha: data.commit.tree.sha };
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
  const resp = await fetchWithRetry(apiUrl, { headers: GH_HEADERS });
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
        fetchedFiles[deviceRel] = await cachedText(
          item.download_url || toRawUrl(item.html_url)
        );
        count++;
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
    const { commitSha, treeSha } = await resolveRef(repo, ref);
    // Trees response is keyed by the immutable treeSha, so it's cached across flashes.
    const treeJson = await cachedText(
      `https://api.github.com/repos/${owner}/${name}/git/trees/${treeSha}?recursive=1`,
      { headers: GH_HEADERS }
    );
    const tree = JSON.parse(treeJson);
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
        // SHA-pinned + cached: missing file is a hard error, never silently skipped.
        fetchedFiles[deviceRel] = await cachedText(
          rawFileUrl(owner, name, commitSha, item.path)
        );
        break;
      }
    }

    if (Object.keys(fetchedFiles).length === 0) {
      throw new Error("No files matched manifest on this branch");
    }
    return fetchedFiles;
  } catch (treesErr) {
    // Don't fall back on rate limiting — the Contents API makes even more calls.
    if (treesErr.message.startsWith("GitHub rate limit")) throw treesErr;
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
    const resp = await fetchWithRetry(apiUrl, { headers: GH_HEADERS });
    if (!resp.ok) throw new Error(`GitHub API ${resp.status} for ${src.repoPath}`);
    const items = await resp.json();
    if (!Array.isArray(items)) throw new Error(`Unexpected response for ${src.repoPath}`);

    for (const item of items) {
      if (item.type === "file") {
        if (!shouldIncludeFile(item.name, src, manifest)) continue;
        const deviceRel = joinDevicePath(prefix, item.name);
        onProgress?.(deviceRel);
        fetchedFiles[deviceRel] = await cachedText(
          item.download_url || toRawUrl(item.html_url)
        );
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
