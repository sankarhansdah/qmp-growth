import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://quotationmaker.pro',
  trailingSlash: 'always',
  build: { format: 'directory' },
  integrations: [sitemap()],
});
