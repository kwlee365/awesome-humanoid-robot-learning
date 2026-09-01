/**
 * Reading status: the one piece of per-paper state the reader owns rather than
 * the README. Three values follow a paper through the queue - "To Find",
 * "In Progress", "Done" - and a fourth, "Decide Not To Read", takes it out of
 * the queue deliberately. Everything untouched is "not set".
 *
 * That fourth state is the site's answer to "can I just delete this paper?".
 * The list itself is the README's, shared with everyone and rebuilt twice a day
 * from it, so deleting an entry there would only invite the discovery sweep to
 * propose it again. Deciding not to read it is a judgement about your own
 * reading, it is yours, it survives, and the filter can hide those rows.
 *
 * It is kept in two places. The browser holds the fast copy: a click is written
 * to localStorage immediately, with no token and no network. The committed
 * `data/reading-status.json` holds the durable one, and the site's "Sync to
 * GitHub" button merges the browser copy into it so another device picks the
 * status up on the next deploy. Every entry carries its own timestamp, so a
 * merge never has to guess which side is newer.
 *
 * This module stays pure so both the build and the browser can import it.
 */

export const READING_STATUSES = [
  { id: 'to-find', label: 'To Find' },
  { id: 'in-progress', label: 'In Progress' },
  { id: 'done', label: 'Done' },
  { id: 'not-reading', label: 'Decide Not To Read' },
] as const;

export type ReadingStatusId = (typeof READING_STATUSES)[number]['id'];

/** `status: null` is a tombstone: the reader cleared the status at that time. */
export interface ReadingEntry {
  status: ReadingStatusId | null;
  updated: string;
}

/** Keyed by the paper's canonical slug, the same key its page URL uses. */
export type ReadingStatuses = Record<string, ReadingEntry>;

export interface ReadingStatusFile {
  version: number;
  note?: string;
  updated: string | null;
  statuses: ReadingStatuses;
}

export const READING_STATUS_VERSION = 1;
export const READING_STATUS_PATH = 'data/reading-status.json';
export const READING_STATUS_STORAGE_KEY = 'reading-status:v1';

/** Fired on `document` once every control on the page shows the current value. */
export const READING_STATUS_EVENT = 'reading-status:painted';

export const READING_STATUS_NOTE =
  'Reading status per paper slug, owned by the reader and written by the site’s ' +
  '"Sync to GitHub" button. Automation must never rewrite, reorder or delete entries here. ' +
  'An entry with "status": null is a cleared status, kept so that clearing one on a device ' +
  'also clears it on the others.';

const IDS = new Set<string>(READING_STATUSES.map((s) => s.id));

export function isReadingStatus(value: unknown): value is ReadingStatusId {
  return typeof value === 'string' && IDS.has(value);
}

export function readingStatusLabel(id: ReadingStatusId | null | ''): string {
  return READING_STATUSES.find((s) => s.id === id)?.label ?? 'Not set';
}

/**
 * Keep only well-formed entries. This file is hand-editable and is merged with
 * copies from other devices, so one bad entry must never break a page.
 */
export function sanitizeStatuses(raw: unknown): ReadingStatuses {
  const out: ReadingStatuses = {};
  const statuses = (raw as Partial<ReadingStatusFile> | null | undefined)?.statuses;
  if (!statuses || typeof statuses !== 'object') return out;
  for (const [slug, value] of Object.entries(statuses as Record<string, unknown>)) {
    if (!slug || typeof value !== 'object' || value === null) continue;
    const { status, updated } = value as Partial<ReadingEntry>;
    if (status !== null && !isReadingStatus(status)) continue;
    out[slug] = { status: status ?? null, updated: typeof updated === 'string' ? updated : '' };
  }
  return out;
}

/**
 * Merge two sets entry by entry: the newer write wins, ties go to `b`.
 * Timestamps are UTC ISO strings, so comparing them as strings compares time.
 */
export function mergeStatuses(a: ReadingStatuses, b: ReadingStatuses): ReadingStatuses {
  const out: ReadingStatuses = { ...a };
  for (const [slug, entry] of Object.entries(b)) {
    const mine = out[slug];
    if (!mine || entry.updated >= mine.updated) out[slug] = entry;
  }
  return out;
}

/**
 * Shape the set for committing. Slugs are sorted so the file's diff only ever
 * shows what actually changed; tombstones are kept, because dropping them is
 * what would make a cleared status come back on the next sync.
 */
export function toReadingStatusFile(
  statuses: ReadingStatuses,
  updated: string | null,
): ReadingStatusFile {
  const sorted: ReadingStatuses = {};
  for (const slug of Object.keys(statuses).sort()) sorted[slug] = statuses[slug]!;
  return {
    version: READING_STATUS_VERSION,
    note: READING_STATUS_NOTE,
    updated,
    statuses: sorted,
  };
}
