// Copies the single structured metadata source (../data/papers.json) into the
// site build tree. This is a build artefact, never a second source of truth:
// src/generated/ is git-ignored and regenerated on every `npm run build`.
import { mkdirSync, copyFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..', '..');
const out = resolve(here, '..', 'src', 'generated');

mkdirSync(out, { recursive: true });

const copies = [
  ['data/papers.json', 'papers.json'],
  ['data/review-queue.json', 'review-queue.json'],
];

for (const [from, to] of copies) {
  const src = resolve(repoRoot, from);
  if (!existsSync(src)) {
    throw new Error(
      `missing ${from} - run "python3 scripts/parse_readme.py" (and validate.py) first`,
    );
  }
  copyFileSync(src, resolve(out, to));
}

// Reading status is written by the site itself rather than by the parser, and a
// checkout that has never synced one legitimately has no file yet - so this one
// is optional, and its absence means "nothing marked" rather than an error.
const readingStatus = resolve(repoRoot, 'data/reading-status.json');
if (existsSync(readingStatus)) {
  copyFileSync(readingStatus, resolve(out, 'reading-status.json'));
} else {
  writeFileSync(
    resolve(out, 'reading-status.json'),
    JSON.stringify({ version: 1, updated: null, statuses: {} }, null, 2) + '\n',
  );
}

// A tiny build stamp so pages can show when the data was last regenerated.
const papers = JSON.parse(readFileSync(resolve(out, 'papers.json'), 'utf8'));
writeFileSync(
  resolve(out, 'build-info.json'),
  JSON.stringify(
    { paperCount: papers.papers.length, builtAt: new Date().toISOString().slice(0, 10) },
    null,
    2,
  ) + '\n',
);

console.log(`synced ${papers.papers.length} paper records into site/src/generated/`);
