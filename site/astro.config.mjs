// @ts-check
import { defineConfig } from 'astro/config';

// Deployed with GitHub Pages from the `kwlee365` fork, so the site lives under
// https://kwlee365.github.io/awesome-humanoid-robot-learning/
// `SITE_BASE=/` lets a custom domain or a local preview override the sub-path.
const base = process.env.SITE_BASE ?? '/awesome-humanoid-robot-learning';

export default defineConfig({
  site: process.env.SITE_URL ?? 'https://kwlee365.github.io',
  base,
  trailingSlash: 'ignore',
  build: { format: 'directory' },
  markdown: {
    shikiConfig: { theme: 'github-light' },
  },
});
