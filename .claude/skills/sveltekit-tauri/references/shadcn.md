# shadcn: Add shadcn-svelte Components

shadcn-svelte components are added per-component via its CLI. They land directly in your source tree (in `src/lib/components/ui/`) rather than in `node_modules`, so you own and can edit them freely. This skill assumes shadcn-svelte was already configured during [bootstrap](bootstrap.md) — if `components.json` doesn't exist at the project root, do that first.

## Workflow

### Step 1: Identify the components

Determine which components the user wants. The full list is at https://shadcn-svelte.com/docs/components — common ones include `button`, `card`, `dialog`, `dropdown-menu`, `input`, `label`, `select`, `tabs`, `toast`, `tooltip`.

If the user names a feature instead of a component (e.g. "a settings page with toggles and a save button"), translate that to a component list (`switch`, `label`, `button`, probably `separator` and `card`).

### Step 2: Install via the CLI

Add components one or many at a time:

```bash
bunx shadcn-svelte@latest add button card dialog
```

The CLI:

- Resolves any peer components (e.g. `dialog` may pull in `button`).
- Copies the Svelte source into `src/lib/components/ui/<component>/`.
- Installs any extra npm packages the component needs (e.g. `bits-ui`, `lucide-svelte`, `mode-watcher`).

If the CLI prompts for `Overwrite existing components?`, answer **No** unless the user explicitly wants to discard local edits.

### Step 3: Verify the install

```bash
bun run check
```

Type errors here usually mean a dependency is missing — re-run `bun install` and check the CLI's output for skipped peer deps.

### Step 4: Use the component

Each component is exported from an `index.ts` barrel. The recommended import pattern is namespaced:

```svelte
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Button } from '$lib/components/ui/button';
</script>

<Card.Root>
  <Card.Header>
    <Card.Title>Hello</Card.Title>
    <Card.Description>A shadcn card</Card.Description>
  </Card.Header>
  <Card.Content>
    <Button>Click me</Button>
  </Card.Content>
</Card.Root>
```

Or, if you prefer flat imports:

```svelte
<script lang="ts">
  import { Card, CardHeader, CardTitle, CardContent } from '$lib/components/ui/card';
</script>
```

Both patterns work — shadcn-svelte exports the components under both names.

### Step 5: Customize

Because components live in `src/lib/components/ui/`, edits are made directly to those files. To re-skin a component globally, edit `src/app.css` — the design tokens (`--primary`, `--background`, `--radius`, etc.) cascade through every component.

To version-bump or refresh from upstream:

```bash
bunx shadcn-svelte@latest add button --overwrite
```

(Warns before clobbering local edits — review the diff first.)

### Step 6: Tell the user what they got

- Each component lives in `src/lib/components/ui/<name>/`, fully editable.
- Theme tokens are in `src/app.css` — change them once and every component updates.
- To add more components later, repeat `bunx shadcn-svelte@latest add <name>`.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `components.json not found` | The skill assumes bootstrap created it. Either run bootstrap or run `bunx shadcn-svelte@latest init` |
| Component throws "bits-ui not found" | Run `bun install` — shadcn-svelte's add command sometimes skips the peer install on slow connections |
| Component imports from `$lib/utils` but file doesn't exist | Confirm `src/lib/utils.ts` exists (created during bootstrap); if not, copy `SKILL_DIR/assets/utils.ts` |
| Styles look broken after adding a component | Ensure `app.css` is imported from `+layout.svelte` and that `tailwindcss()` is in `vite.config.ts` |
| Dark mode classes don't apply | shadcn-svelte uses the `dark` class on `<html>` — install and use `mode-watcher` to manage it: `bunx shadcn-svelte@latest add mode-watcher` |
