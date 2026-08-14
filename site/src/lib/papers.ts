import raw from '../generated/papers.json';
import buildInfo from '../generated/build-info.json';
import { normalizeTitle, slugify } from './slug';

/** One line of README.md, lifted into structured form by scripts/parse_readme.py. */
export interface ReadmeRecord {
  id: string;
  slug: string;
  key: string;
  title: string;
  alt_venue: string | null;
  authors: string[];
  primary_category: string;
  tags: string[];
  paper_url: string | null;
  project_url: string | null;
  code_url: string | null;
  video_url: string | null;
  dataset_url: string | null;
  doi: string | null;
  arxiv_id: string | null;
  open_source: boolean;
  real_robot: boolean | null;
  abstract: string | null;
  abstract_source: string | null;
  overview: string | null;
  verified_on: string | null;
  related: string[];
  readme_order: number;
  readme_line: string;
  extra_links: { label: string; url: string }[];
  venue: string;
  venue_raw: string;
  year: number | null;
  month: number | null;
  first_public_date: string | null;
  publication_status: string;
  norm_title: string;
}

/**
 * One *research record*. A paper that the README lists in several sections
 * (allowed when it genuinely spans topics) collapses into a single record with
 * several categories, so the site never shows the same work as two papers.
 */
export interface Paper {
  slug: string;
  /** Other slugs this record was known by (title variants merged into one work). */
  aliases: string[];
  title: string;
  authors: string[];
  categories: string[];
  tags: string[];
  paperUrl: string | null;
  projectUrl: string | null;
  codeUrl: string | null;
  videoUrl: string | null;
  datasetUrl: string | null;
  extraLinks: { label: string; url: string }[];
  doi: string | null;
  arxivId: string | null;
  venue: string;
  venueRaw: string;
  altVenue: string | null;
  year: number | null;
  month: number | null;
  firstPublicDate: string | null;
  publicationStatus: string;
  openSource: boolean;
  realRobot: boolean | null;
  abstract: string | null;
  abstractSource: string | null;
  overview: string | null;
  verifiedOn: string | null;
  related: string[];
  readmeLines: string[];
  normTitle: string;
}

export const CATEGORY_ORDER = [
  'Loco-Manipulation and Whole-Body-Control',
  'Manipulation',
  'Teleoperation',
  'Locomotion',
  'Safety-Critical Control',
  'Navigation',
  'State Estimation',
  'Sim-to-Real',
  'Hardware Design',
  'Simulation Benchmark',
  'Physics-Based Character Animation',
  'Human Motion Analysis and Synthesis',
];

const records = (raw as { papers: ReadmeRecord[] }).papers;

function identity(r: ReadmeRecord): string {
  if (r.arxiv_id) return `arxiv:${r.arxiv_id}`;
  if (r.doi) return `doi:${r.doi.toLowerCase()}`;
  return `title:${r.norm_title}`;
}

function dateValue(r: { year: number | null; month: number | null }): number {
  return (r.year ?? 0) * 12 + (r.month ?? 0);
}

function merge(group: ReadmeRecord[]): Paper {
  // Anchor on the entry with the richest link set, then the earliest date.
  const anchor = [...group].sort((a, b) => {
    const score = (r: ReadmeRecord) =>
      (r.paper_url ? 4 : 0) + (r.project_url ? 2 : 0) + (r.code_url ? 1 : 0);
    return score(b) - score(a) || dateValue(a) - dateValue(b);
  })[0]!;
  const earliest = [...group]
    .filter((r) => r.year !== null)
    .sort((a, b) => dateValue(a) - dateValue(b))[0];
  const first = (pick: (r: ReadmeRecord) => string | null) =>
    group.map(pick).find((v) => v !== null && v !== undefined) ?? null;

  const categories: string[] = [];
  for (const r of group) if (!categories.includes(r.primary_category)) categories.push(r.primary_category);

  return {
    slug: anchor.slug,
    aliases: [...new Set(group.map((r) => r.slug))].filter((s) => s !== anchor.slug),
    title: anchor.title,
    authors: group.flatMap((r) => r.authors).filter((v, i, a) => a.indexOf(v) === i),
    categories: categories.sort(
      (a, b) => CATEGORY_ORDER.indexOf(a) - CATEGORY_ORDER.indexOf(b),
    ),
    tags: group.flatMap((r) => r.tags).filter((v, i, a) => a.indexOf(v) === i),
    paperUrl: first((r) => r.paper_url),
    projectUrl: first((r) => r.project_url),
    codeUrl: first((r) => r.code_url),
    videoUrl: first((r) => r.video_url),
    datasetUrl: first((r) => r.dataset_url),
    extraLinks: group.flatMap((r) => r.extra_links),
    doi: first((r) => r.doi),
    arxivId: first((r) => r.arxiv_id),
    venue: (earliest ?? anchor).venue,
    venueRaw: (earliest ?? anchor).venue_raw,
    altVenue: first((r) => r.alt_venue),
    year: (earliest ?? anchor).year,
    month: (earliest ?? anchor).month,
    firstPublicDate: (earliest ?? anchor).first_public_date,
    publicationStatus: (earliest ?? anchor).publication_status,
    openSource: group.some((r) => r.open_source),
    realRobot: group.map((r) => r.real_robot).find((v) => v !== null) ?? null,
    abstract: first((r) => r.abstract),
    abstractSource: first((r) => r.abstract_source),
    overview: first((r) => r.overview),
    verifiedOn: first((r) => r.verified_on),
    related: group.flatMap((r) => r.related).filter((v, i, a) => a.indexOf(v) === i),
    readmeLines: group.map((r) => r.readme_line),
    normTitle: anchor.norm_title,
  };
}

function buildPapers(): Paper[] {
  const groups = new Map<string, ReadmeRecord[]>();
  for (const r of records) {
    const key = identity(r);
    const bucket = groups.get(key);
    if (bucket) bucket.push(r);
    else groups.set(key, [r]);
  }

  const merged = [...groups.values()].map(merge);

  // Guarantee unique, stable URLs even when two different works slugify alike.
  const seen = new Map<string, number>();
  for (const p of merged) {
    const base = p.slug || slugify(p.title);
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    p.slug = n === 0 ? base : `${base}-${n + 1}`;
  }
  // An alias must never collide with a real page or with another alias.
  const taken = new Set(merged.map((p) => p.slug));
  for (const p of merged) {
    p.aliases = p.aliases.filter((a) => !taken.has(a) && (taken.add(a), true));
  }
  return merged;
}

export const papers: Paper[] = buildPapers();

export const paperBySlug = new Map(papers.map((p) => [p.slug, p]));

export function sortNewestFirst(list: Paper[]): Paper[] {
  return [...list].sort((a, b) => {
    const d = dateValue(b) - dateValue(a);
    if (d !== 0) return d;
    return (b.arxivId ?? '').localeCompare(a.arxivId ?? '');
  });
}

export function papersInCategory(category: string): Paper[] {
  return sortNewestFirst(papers.filter((p) => p.categories.includes(category)));
}

export interface CategoryInfo {
  name: string;
  slug: string;
  count: number;
}

export const categories: CategoryInfo[] = (() => {
  const names = new Set(papers.flatMap((p) => p.categories));
  // README order first, then anything new the README grows later.
  const ordered = [
    ...CATEGORY_ORDER.filter((c) => names.has(c)),
    ...[...names].filter((c) => !CATEGORY_ORDER.includes(c)).sort(),
  ];
  return ordered.map((name) => ({
    name,
    slug: slugify(name),
    count: papersInCategory(name).length,
  }));
})();

export const categoryBySlug = new Map(categories.map((c) => [c.slug, c]));

export function formatDate(p: Pick<Paper, 'year' | 'month'>): string {
  if (p.year === null) return 'undated';
  if (p.month === null) return String(p.year);
  return `${p.year}.${String(p.month).padStart(2, '0')}`;
}

export const stats = {
  ...buildInfo,
  researchRecords: papers.length,
  readmeEntries: records.length,
  openSource: papers.filter((p) => p.openSource).length,
  categories: categories.length,
};

const STOPWORDS = new Set(
  ('a an and are as at be by for from in into is its of on or the to via with without ' +
    'towards toward through learning robot robots robotic humanoid using use based').split(' '),
);

function contentWords(title: string): Set<string> {
  return new Set(
    normalizeTitle(title)
      .split(' ')
      .filter((w) => w.length > 2 && !STOPWORDS.has(w)),
  );
}

const wordCache = new Map<string, Set<string>>();
function wordsOf(p: Paper): Set<string> {
  let w = wordCache.get(p.slug);
  if (!w) {
    w = contentWords(p.title);
    wordCache.set(p.slug, w);
  }
  return w;
}

/**
 * "Related papers in this repository" is a computed suggestion, not an editorial
 * claim: it ranks other records by shared category and overlapping title terms.
 */
export function relatedPapers(paper: Paper, limit = 6): Paper[] {
  const mine = wordsOf(paper);
  if (mine.size === 0) return [];
  const scored = papers
    .filter((p) => p.slug !== paper.slug)
    .map((p) => {
      const theirs = wordsOf(p);
      let shared = 0;
      for (const w of mine) if (theirs.has(w)) shared++;
      const catOverlap = p.categories.filter((c) => paper.categories.includes(c)).length;
      const score = shared * 2 + catOverlap;
      return { p, score, shared };
    })
    .filter((s) => s.shared >= 2)
    .sort((a, b) => b.score - a.score || Math.abs((a.p.year ?? 0) - (paper.year ?? 0)) - Math.abs((b.p.year ?? 0) - (paper.year ?? 0)));
  return scored.slice(0, limit).map((s) => s.p);
}

export const GITHUB_REPO = 'kwlee365/awesome-humanoid-robot-learning';
export const GITHUB_BRANCH = 'main';

export function editOnGitHub(path: string): string {
  return `https://github.com/${GITHUB_REPO}/edit/${GITHUB_BRANCH}/${path}`;
}

export function createOnGitHub(path: string, template: string): string {
  const dir = path.slice(0, path.lastIndexOf('/'));
  const filename = path.slice(path.lastIndexOf('/') + 1);
  return (
    `https://github.com/${GITHUB_REPO}/new/${GITHUB_BRANCH}/${dir}` +
    `?filename=${encodeURIComponent(filename)}&value=${encodeURIComponent(template)}`
  );
}
