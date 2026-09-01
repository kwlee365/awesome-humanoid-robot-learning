import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

/**
 * Generated, machine-maintained narrative for a research category.
 * One file per README category, written and updated by the maintenance run.
 */
const topics = defineCollection({
  loader: glob({ base: './src/content/topics', pattern: '**/*.md' }),
  schema: z.object({
    category: z.string(),
    title: z.string(),
    summary: z.string(),
    updated: z.string(),
  }),
});

export const collections = { topics };
