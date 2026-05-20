# Bun production server with `svelte-adapter-bun`

`svelte-adapter-bun` produces a **standalone Bun HTTP server** (`build/index.js`,
launched with `bun ./build/index.js`). This is the SvelteKit adapter that
[bun.com](https://bun.com/docs/guides/ecosystem/sveltekit) recommends for
**server** deployments — not the same thing as using Bun as a package manager
(which this whole skill already does).

## When to use

Pick `svelte-adapter-bun` when:

- You want **Bun itself** to be the production HTTP server (self-hosted VM /
  container, often behind nginx).
- You need first-class **WebSockets** via Bun's `Bun.serve` (the adapter
  exposes a `websocket` hook in `hooks.server.ts`).
- You're shipping a **non-desktop** SvelteKit app and want Bun's perf as the
  runtime, not just the package manager.

## When NOT to use (important for this skill's main path)

**Do not use `svelte-adapter-bun` for the Tauri target.** Tauri embeds a
static `build/` directory in the WebView (`"frontendDist": "../build"` in
`tauri.conf.json`) — a running JS server is meaningless there and the build
will not work in a Tauri WebView. Keep `@sveltejs/adapter-static` for the
Tauri target (see [bootstrap.md](bootstrap.md), step 3).

Same rule for any static host (Hugging Face Spaces, GitHub Pages, S3,
Cloudflare Pages without functions): `adapter-static`, not `adapter-bun`.

If you want a Tauri build *and* a Bun-server build from the same repo, see
[Multi-target setup](#multi-target-tauri-and-a-bun-server-in-the-same-repo)
below.

## Install

```bash
bun add -D svelte-adapter-bun
```

Then edit `svelte.config.js`:

```js
import adapter from 'svelte-adapter-bun';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
  preprocess: vitePreprocess(),
  kit: { adapter: adapter() }
};
```

Build and run:

```bash
bun --bun run build
bun ./build/index.js   # defaults to 0.0.0.0:3000
```

Successful build prints:

```
> Using svelte-adapter-bun
  ✔ Start server with: bun ./build/index.js
```

## Adapter options

```js
adapter({
  out: 'build',          // output directory (default: 'build')
  serveAssets: true,     // serve /static + prerendered pages (default: true)
  precompress: true,     // gzip + brotli for assets (default: true)
  envPrefix: 'MY_'       // rename runtime env vars (default: '')
});
```

| Option         | Default  | Notes                                                   |
|----------------|----------|---------------------------------------------------------|
| `out`          | `'build'`| Where the server bundle is written                      |
| `serveAssets`  | `true`   | Set `false` when a CDN/nginx serves static files        |
| `precompress`  | `true`   | Pre-builds .gz/.br so requests aren't re-compressed     |
| `envPrefix`    | `''`     | Use e.g. `'MY_'` to deconflict shared environment names |

## Runtime environment variables

| Variable                    | Default     | What it does                                                                 |
|-----------------------------|-------------|------------------------------------------------------------------------------|
| `HOST`                      | `0.0.0.0`   | Bind address                                                                 |
| `PORT`                      | `3000`      | Bind port                                                                    |
| `SOCKET_PATH`               | —           | Unix domain socket; overrides `HOST`/`PORT`. Use behind nginx                |
| `ORIGIN`                    | —           | Public URL, e.g. `https://my.site`. Set this so `event.url` is correct       |
| `PROTOCOL_HEADER`           | —           | Trusted header carrying original protocol (typically `x-forwarded-proto`)    |
| `HOST_HEADER`               | —           | Trusted header carrying original host (typically `x-forwarded-host`)         |
| `ADDRESS_HEADER`            | —           | Trusted header carrying real client IP (e.g. `x-forwarded-for`)              |
| `XFF_DEPTH`                 | —           | Number of *trusted* proxies; reads from the right of `X-Forwarded-For`       |

The `*_HEADER` vars are spoofable — set them **only** when you trust the
reverse proxy in front of you. `XFF_DEPTH` exists specifically to count from
the right so a client can't spoof a left-most address.

Examples:

```bash
# Public deployment behind a load balancer
ORIGIN=https://my.site \
PROTOCOL_HEADER=x-forwarded-proto \
HOST_HEADER=x-forwarded-host \
ADDRESS_HEADER=x-forwarded-for \
XFF_DEPTH=1 \
bun ./build/index.js

# Unix socket behind nginx
SOCKET_PATH=/tmp/sveltekit.sock bun ./build/index.js
```

Bun automatically reads `.env`, `.env.local`, and `.env.development`.

## WebSocket server

The adapter wires Bun's WebSocket support through `hooks.server.ts`. Detect
the upgrade in `handle`, then export a `websocket` handler at module level:

```ts
// src/hooks.server.ts
import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
  const { request } = event;
  const url = new URL(request.url);

  const isUpgrade =
    request.headers.get('connection')?.toLowerCase().includes('upgrade') &&
    request.headers.get('upgrade')?.toLowerCase() === 'websocket' &&
    url.pathname.startsWith('/ws');

  if (isUpgrade) {
    await event.platform.server.upgrade(event.platform.request);
    return new Response(null, { status: 101 });
  }

  return resolve(event);
};

export const websocket: Bun.WebSocketHandler<undefined> = {
  open(ws) { ws.send('hello'); },
  message(ws, msg) { ws.send(msg); },
  close() {}
};
```

Type `event.platform` in `src/app.d.ts`:

```ts
declare global {
  namespace App {
    interface Platform {
      server: Bun.Server;
      request: Request;
    }
  }
}
export {};
```

Test from the CLI: `bunx wscat -c ws://localhost:3000/ws`.

## Multi-target: Tauri *and* a Bun server in the same repo

This is the realistic case for projects that already use this skill: keep
the Tauri build on `adapter-static`, add a Bun-server build for a separate
deployment. Two patterns:

### a) Build-flag adapter selection (recommended)

`svelte.config.js` picks the adapter from an env var:

```js
import staticAdapter from '@sveltejs/adapter-static';
import bunAdapter from 'svelte-adapter-bun';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const adapter =
  process.env.TARGET === 'bun'
    ? bunAdapter()
    : staticAdapter({
        pages: 'build',
        assets: 'build',
        fallback: 'index.html',
        strict: false
      });

export default { preprocess: vitePreprocess(), kit: { adapter } };
```

`package.json`:

```json
{
  "scripts": {
    "build": "vite build",
    "build:bun": "TARGET=bun vite build",
    "tauri": "tauri"
  }
}
```

Tauri's `beforeBuildCommand` stays `bun run build` (static). `bun run
build:bun` produces the Bun server in `build/`. **Do not point Tauri at a
`TARGET=bun` build.**

### b) Split routes

Keep the SPA static (`ssr = false`, `prerender = true` in the root
`+layout.ts`) for the Tauri-shared UI. Opt back into SSR only for the routes
that need WebSockets or dynamic server endpoints, in a separate route
group, and build *only those* with the Bun adapter for a server deployment.
Heavier; only worth it when you already run a Bun host.

## Decision matrix

| Target                                 | Adapter                          | Why                                                                 |
|----------------------------------------|----------------------------------|---------------------------------------------------------------------|
| **Tauri desktop**                      | `@sveltejs/adapter-static`       | WebView embeds a static `build/`; no server runtime inside the app  |
| **Hugging Face Space (static)**        | `@sveltejs/adapter-static`       | Static host; no Node/Bun runtime available                          |
| **GitHub Pages / S3 / Cloudflare Pages (no functions)** | `@sveltejs/adapter-static` | Same: static-only hosts                                             |
| **Self-hosted Bun server (VM/container)** | `svelte-adapter-bun`          | You need a process for SSR / WebSockets / private endpoints         |
| **Node.js / Vercel / Cloudflare Workers** | `adapter-node` / `-vercel` / `-cloudflare` | Runtime-specific, not Bun                            |

## References

- Bun docs — *Build an app with SvelteKit and Bun*: https://bun.com/docs/guides/ecosystem/sveltekit
- `svelte-adapter-bun` (npm + repo): https://www.npmjs.com/package/svelte-adapter-bun · https://github.com/gornostay25/svelte-adapter-bun
- SvelteKit adapters overview: https://svelte.dev/docs/kit/adapters
- Bun WebSockets API: https://bun.sh/docs/api/websockets

---

**Last verified:** 2026-05-20
