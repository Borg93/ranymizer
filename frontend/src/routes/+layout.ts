// Pure SPA: prerender index.html, but everything runs client-side.
// All API calls happen at runtime so SSR would just slow first paint.
export const prerender = true;
export const ssr = false;
