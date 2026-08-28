/**
 * The slice of the GitHub contents API that the two write-back features on this
 * site share: My Idea notes and reading-status sync.
 *
 * One token serves both. It is a fine-grained personal access token with
 * Contents: Read and write on this repository and nothing else, held in this
 * browser's local storage and sent nowhere except api.github.com. Browser only -
 * nothing here runs at build time.
 */

const API = 'https://api.github.com';

/** Named for My Idea, which introduced it. Kept so an existing token still works. */
export const GITHUB_TOKEN_KEY = 'myidea:github-pat';

export function githubToken(): string | null {
  try {
    return localStorage.getItem(GITHUB_TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Returns false when this browser refuses to store anything at all. */
export function setGithubToken(token: string): boolean {
  try {
    localStorage.setItem(GITHUB_TOKEN_KEY, token);
    return true;
  } catch {
    return false;
  }
}

export function forgetGithubToken(): void {
  try {
    localStorage.removeItem(GITHUB_TOKEN_KEY);
  } catch {
    /* nothing stored, nothing to forget */
  }
}

/**
 * A 404 comes back as a normal response, but only for a read: "the file does not
 * exist yet" is an ordinary first-write case. A 404 on a write means the token
 * cannot see this repository at all, and treating that as success would tell
 * someone their note or their reading status had been saved when it had not.
 */
export async function githubApi(
  method: string,
  endpoint: string,
  body?: unknown,
): Promise<Response> {
  const res = await fetch(`${API}${endpoint}`, {
    method,
    headers: {
      Authorization: `Bearer ${githubToken()}`,
      Accept: 'application/vnd.github+json',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 || res.status === 403) {
    throw new Error(
      'GitHub rejected the token. Check that it has not expired and that it grants ' +
        'Contents: Read and write on this repository.',
    );
  }
  if (res.status === 404 && method.toUpperCase() !== 'GET') {
    throw new Error(
      `GitHub could not find ${endpoint.split('?')[0]} to write to. A fine-grained ` +
        'token that cannot see a repository gets 404 rather than 403, so check the ' +
        "token grants Contents: Read and write on this repository.",
    );
  }
  if (!res.ok && res.status !== 404) {
    const detail = await res.text();
    throw new Error(`GitHub returned ${res.status}. ${detail.slice(0, 200)}`);
  }
  return res;
}

export function toBase64(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

export function fromBase64(b64: string): string {
  const bin = atob(b64.replace(/\s/g, ''));
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function bytesToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(bin);
}
