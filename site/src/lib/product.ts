// Mirrors data/product-facts.md. Keep in sync; do not add claims that are not in that file.
// While PACKAGE_ID is a placeholder the app is unpublished and CTAs use the waitlist variant.
export const PACKAGE_ID = '<PACKAGE_ID>'; // TODO Sankar
export const PUBLISHED = !PACKAGE_ID.startsWith('<');

export const playUrl = (campaign: string) =>
  `https://play.google.com/store/apps/details?id=${PACKAGE_ID}&utm_source=site&utm_medium=cta&utm_campaign=${encodeURIComponent(campaign)}`;
