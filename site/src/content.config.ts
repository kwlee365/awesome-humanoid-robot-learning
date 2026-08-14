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

/**
 * User-owned notes. The schema is intentionally permissive: everything is
 * optional so the file can be free-form. Automation may create a missing blank
 * file; it must never rewrite, summarise, translate, reorganise or delete one.
 */
const myIdeaSchema = z
  .object({
    title: z.string().optional(),
    updated: z.string().optional(),
    status: z.string().optional(),
    tags: z.array(z.string()).optional(),
  })
  .passthrough();

const myIdeaTopics = defineCollection({
  loader: glob({ base: './src/content/my-ideas/topics', pattern: '**/*.md' }),
  schema: myIdeaSchema,
});

const myIdeaPapers = defineCollection({
  loader: glob({ base: './src/content/my-ideas/papers', pattern: '**/*.md' }),
  schema: myIdeaSchema,
});

export const collections = { topics, myIdeaTopics, myIdeaPapers };
