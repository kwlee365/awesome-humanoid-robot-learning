/**
 * Browser-side store for reading status. One module instance per page, shared by
 * every script that imports it, so the controls, the filters and the sync bar
 * always read the same state. See `lib/reading-status.ts` for the data model.
 */
import baselineFile from '../generated/reading-status.json';
import {
  mergeStatuses,
  READING_STATUS_STORAGE_KEY as KEY,
  READING_STATUS_VERSION,
  sanitizeStatuses,
  type ReadingStatuses,
  type ReadingStatusId,
} from './reading-status';

/** What the last deploy shipped: the committed file as it stood at build time. */
export const baseline: ReadingStatuses = sanitizeStatuses(baselineFile);

function readLocal(): ReadingStatuses {
  try {
    return sanitizeStatuses(JSON.parse(localStorage.getItem(KEY) ?? 'null'));
  } catch {
    return {};
  }
}

// Start from the deployed file and let anything newer in this browser win, so a
// status synced from another device shows up here without a manual step.
let statuses: ReadingStatuses = mergeStatuses(baseline, readLocal());

const listeners = new Set<() => void>();

function write(): void {
  try {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        version: READING_STATUS_VERSION,
        updated: new Date().toISOString(),
        statuses,
      }),
    );
  } catch {
    /* private mode or a full quota: the page still works, this visit just
       cannot remember anything. Better than throwing on a click. */
  }
}

function notify(): void {
  for (const fn of listeners) fn();
}

export function allStatuses(): ReadingStatuses {
  return statuses;
}

export function statusOf(slug: string): ReadingStatusId | null {
  return statuses[slug]?.status ?? null;
}

export function setStatus(slug: string, status: ReadingStatusId | null): void {
  statuses = { ...statuses, [slug]: { status, updated: new Date().toISOString() } };
  write();
  notify();
}

/** Adopt a merged set after a sync, without restamping every entry as new. */
export function replaceStatuses(next: ReadingStatuses): void {
  statuses = next;
  write();
  notify();
}

export function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

// Another tab of this site is the same store; keep the two in step.
window.addEventListener('storage', (event) => {
  if (event.key !== KEY) return;
  statuses = mergeStatuses(baseline, readLocal());
  notify();
});
