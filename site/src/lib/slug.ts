/**
 * Mirror of `slugify()` in scripts/parse_readme.py so that the Python data
 * pipeline and the Astro site agree on every URL and every file name.
 */
export function slugify(input: string): string {
  const stripped = input.normalize('NFKD').replace(/[̀-ͯ]/g, '');
  const slug = stripped
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return (slug.slice(0, 80).replace(/-+$/g, '') || 'paper');
}

export function normalizeTitle(input: string): string {
  return input
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}
