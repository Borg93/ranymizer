# Tauri Command: Expose a Rust Function to Svelte

Tauri commands are how the Svelte frontend calls into Rust. You define a function in Rust, register it, then call it from Svelte via `invoke('command_name', { args })`. Arguments and return values are serialized via `serde`.

## Workflow

### Step 1: Decide the signature

Ask the user (or infer from context):

- **Command name** — snake_case in Rust, the same string is passed to `invoke()`. Example: `read_file`.
- **Arguments** — types serializable by serde. The Rust parameter name maps to the JS object key (Tauri lowercases it: Rust `file_path` ↔ JS `filePath` unless `#[tauri::command(rename_all = "snake_case")]` is set).
- **Return type** — serializable. For fallible operations, use `Result<T, E>` where `E` implements `serde::Serialize`.
- **Async or sync** — use `async fn` if the command does I/O, network, or anything that shouldn't block the main thread.

### Step 2: Write the Rust command

Open `src-tauri/src/lib.rs` (or a dedicated module like `src-tauri/src/commands.rs` for larger projects).

**Simple sync example:**

```rust
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}
```

**Async example with error handling:**

```rust
#[tauri::command]
async fn read_file(path: String) -> Result<String, String> {
    tokio::fs::read_to_string(&path)
        .await
        .map_err(|e| e.to_string())
}
```

**Custom error type** (cleaner for projects with several fallible commands):

```rust
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Utf8(#[from] std::string::FromUtf8Error),
}

impl serde::Serialize for Error {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_str(&self.to_string())
    }
}

#[tauri::command]
fn read(path: String) -> Result<String, Error> {
    Ok(String::from_utf8(std::fs::read(path)?)?)
}
```

If using this pattern, add to `src-tauri/Cargo.toml`:

```toml
thiserror = "2"
```

### Step 3: Register the command

In `src-tauri/src/lib.rs`, add the command to `invoke_handler`:

```rust
tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![greet, read_file])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
```

`generate_handler!` is a macro — list all commands inside it, separated by commas.

### Step 4: Call from Svelte

```svelte
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';

  let name = $state('');
  let result = $state('');
  let error = $state('');

  async function handleGreet() {
    error = '';
    try {
      result = await invoke<string>('greet', { name });
    } catch (e) {
      error = String(e);
    }
  }
</script>

<input bind:value={name} placeholder="Your name" />
<button onclick={handleGreet}>Greet</button>

{#if result}<p>{result}</p>{/if}
{#if error}<p class="text-red-500">{error}</p>{/if}
```

The second argument to `invoke` is an object whose keys map to Rust parameter names (camelCase in JS by default — see Step 1 about `rename_all`).

### Step 5: Type the contract

For larger codebases, define the command contract in one place to avoid drift between Rust and TypeScript:

```ts
// src/lib/tauri/commands.ts
import { invoke } from '@tauri-apps/api/core';

export const greet = (name: string) =>
  invoke<string>('greet', { name });

export const readFile = (path: string) =>
  invoke<string>('read_file', { path });
```

Now the frontend imports `greet` and `readFile` and gets full type checking. If your project ships many commands, consider [`tauri-specta`](https://github.com/specta-rs/tauri-specta), which auto-generates TypeScript bindings from Rust signatures.

### Step 6: Add permissions if needed

Most simple commands work out of the box. Some Tauri APIs (filesystem, shell, dialog, HTTP) need explicit permissions in `src-tauri/capabilities/default.json`. If the user's command uses `tauri_plugin_fs` or similar, add the matching permission:

```json
{
  "permissions": [
    "core:default",
    "fs:default",
    "fs:allow-read-text-file"
  ]
}
```

### Step 7: Verify

```bash
bun run check
bun run tauri dev
```

Trigger the command from the UI. Errors propagate as rejected promises — `await invoke(...)` either resolves with the return value or throws.

### Step 8: Tell the user what they got

- A registered command callable from JS via `invoke('<name>', { ... })`.
- The pattern for adding more: write a `#[tauri::command]` fn → add it to `generate_handler!` → call it from Svelte.
- For projects with many commands, factor them into a `commands` module and expose typed wrappers from `src/lib/tauri/commands.ts`.

## Common patterns

### Returning a stream of events instead of one response

For long-running operations (progress, logs, multi-step jobs), prefer events over a single command call:

```rust
use tauri::Emitter;

#[tauri::command]
async fn long_job(window: tauri::Window) -> Result<(), String> {
    for i in 0..=100 {
        window.emit("progress", i).map_err(|e| e.to_string())?;
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;
    }
    Ok(())
}
```

Listen on the Svelte side:

```ts
import { listen } from '@tauri-apps/api/event';
const unlisten = await listen<number>('progress', (e) => console.log(e.payload));
// later: unlisten();
```

### Accessing app state

For state shared across commands (a DB pool, a config, a long-lived client):

```rust
struct AppState { count: std::sync::Mutex<i32> }

#[tauri::command]
fn increment(state: tauri::State<AppState>) -> i32 {
    let mut count = state.count.lock().unwrap();
    *count += 1;
    *count
}

// in builder:
.manage(AppState { count: std::sync::Mutex::new(0) })
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `invoke` rejects with "command not found" | Confirm the command is in `generate_handler!` and the name in `invoke()` matches the Rust fn name exactly |
| Arguments arrive as `null` | JS key didn't match the Rust parameter — Tauri expects camelCase JS keys for snake_case Rust params unless you set `#[tauri::command(rename_all = "snake_case")]` |
| Return value isn't serializable | Add `#[derive(serde::Serialize)]` to your struct, or convert to a serializable type before returning |
| Async command never resolves | Ensure the runtime is set up — Tauri uses `tokio` under the hood; just `async fn` should work, but blocking calls inside `async` will stall it. Use `tokio::fs::*`, `tokio::time::*`, etc. |
| Errors come back as `{}` empty object | Your error type's `Serialize` impl isn't producing useful data — implement it to return a string, or use the `thiserror` + custom `Serialize` pattern in Step 2 |
