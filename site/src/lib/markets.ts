export type Market = 'us' | 'gb' | 'ca' | 'au' | 'in' | 'ae' | 'global';

export const SITE = 'https://quotationmaker.pro';

export const markets: Record<Market, { path: string; name: string; lang: string; hreflang: string; docTerm: string }> = {
  global: { path: '', name: 'Global', lang: 'en', hreflang: 'en', docTerm: 'quote' },
  us: { path: 'us', name: 'United States', lang: 'en-US', hreflang: 'en-US', docTerm: 'estimate' },
  gb: { path: 'uk', name: 'United Kingdom', lang: 'en-GB', hreflang: 'en-GB', docTerm: 'quote' },
  ca: { path: 'ca', name: 'Canada', lang: 'en-CA', hreflang: 'en-CA', docTerm: 'quote' },
  au: { path: 'au', name: 'Australia', lang: 'en-AU', hreflang: 'en-AU', docTerm: 'quote' },
  in: { path: 'in', name: 'India', lang: 'en-IN', hreflang: 'en-IN', docTerm: 'quotation' },
  ae: { path: 'ae', name: 'UAE', lang: 'en', hreflang: 'en-AE', docTerm: 'quotation' },
};

export const hubMarkets = (Object.keys(markets) as Market[]).filter((m) => m !== 'global');

export const marketByPath = (p: string): Market | undefined =>
  hubMarkets.find((m) => markets[m].path === p);

export const articleUrl = (market: Market, slug: string) =>
  `/${markets[market].path ? markets[market].path + '/' : ''}${slug}/`;

export const abs = (path: string) => SITE + path;
