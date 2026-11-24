import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const articles = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/articles' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    market: z.enum(['us', 'gb', 'ca', 'au', 'in', 'ae', 'global']),
    slug: z.string(),
    primaryKeyword: z.string(),
    secondaryKeywords: z.array(z.string()).default([]),
    intent: z.enum(['informational', 'template', 'tool', 'comparison']),
    cluster: z.string().default('General'),
    published: z.coerce.date(),
    updated: z.coerce.date(),
    lastReviewed: z.coerce.date(),
    reviewBy: z.coerce.date().optional(),
    faq: z.array(z.object({ q: z.string(), a: z.string() })).default([]),
    sources: z.array(z.object({ title: z.string(), url: z.string().url() })).default([]),
    hreflangGroup: z.string().optional(),
  }),
});

export const collections = { articles };
