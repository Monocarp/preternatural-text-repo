# Seed Data Files

This folder contains **seed copies** of mutable data files. These are used ONLY on fresh deployments when the persistent disk is empty.

## How It Works

1. When the backend starts, `initialize_data_files()` in `state.py` checks if data files exist
2. If a file is missing, it copies from `seeds/` to the main `data/` folder
3. Once copied, the file in `data/` becomes the live version that gets modified

## Files

| Seed File | Target | Purpose |
|-----------|--------|---------|
| `codex_tree.seed.json` | `../codex_tree.json` | Category hierarchy |
| `stories_dict.seed.json` | `../stories_dict.json` | Story metadata cache |
| `pending_stories.seed.json` | `../pending_stories.json` | Processing queue |

## Updating Seeds

Seeds should only be updated when:
- Adding a new book that should be included in fresh deployments
- Changing the initial category structure
- Major migrations

**DO NOT** copy production data back to seeds unless intentional.

## Why This Pattern?

Previously, all data files were tracked in git. This caused problems:
- Local code changes would overwrite production data
- `git checkout` of data files was required before every push
- Race conditions between github_sync and local commits

Now:
- Data files live on Render's persistent disk (not in git)
- Seeds provide initial state only
- Production changes stay on production
- Code deploys don't touch data
