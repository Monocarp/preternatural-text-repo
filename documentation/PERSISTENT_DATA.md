# Persistent Data Architecture

**Last Updated:** 2025-12-02

## Problem Statement

Previously, all data files (`codex_tree.json`, `stories_dict.json`, FAISS indexes, etc.) were tracked in git. This caused a critical issue:

1. User makes changes in production (category assignments, story edits, etc.)
2. `github_sync.py` commits these changes to the `main` branch
3. Developer makes code changes locally, pushes to `main`
4. **Production data is overwritten** by whatever was in the developer's local copy

Even using `git checkout data/codex_tree.json` before pushing doesn't reliably solve this due to race conditions and timing issues.

## Solution: Persistent Disk + Seed Files

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GIT REPOSITORY                           │
│                                                                  │
│  data/seeds/                    (TRACKED - initial data)        │
│  ├── codex_tree.seed.json                                       │
│  ├── stories_dict.seed.json                                     │
│  ├── pending_stories.seed.json                                  │
│  ├── stories.faiss                                              │
│  ├── stories.faiss.map.json                                     │
│  └── books/                                                     │
│      └── {book_slug}/                                           │
│          ├── story_positions.seed.json                          │
│          └── stories_meta.seed.json                             │
│                                                                  │
│  data/*.json, data/*.faiss      (NOT TRACKED - in .gitignore)  │
│  books/*/story_positions.json   (NOT TRACKED - in .gitignore)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ git pull
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RENDER DEPLOYMENT                           │
│                                                                  │
│  /opt/render/project/src/       (ephemeral - code from git)     │
│  ├── backend/                                                    │
│  ├── frontend/                                                   │
│  └── data/seeds/                (seed files from git)           │
│                                                                  │
│  /var/data/                     (PERSISTENT DISK - survives     │
│  ├── codex_tree.json            deploys)                        │
│  ├── stories_dict.json                                          │
│  ├── stories.faiss                                              │
│  └── ...                                                        │
└─────────────────────────────────────────────────────────────────┘
```

### How It Works

1. **On Startup**: `state.py` calls `initialize_data_files()`
2. **For each data file**: If it doesn't exist on the persistent disk, copy from `seeds/`
3. **Production changes**: Written to persistent disk, never overwritten by deploys
4. **github_sync.py**: Can be removed or kept for backup purposes only

## Render Setup Instructions

### Step 1: Create a Persistent Disk

1. Go to your Render service dashboard
2. Click on your backend service
3. Go to **Disks** section
4. Click **Add Disk**
5. Configure:
   - **Name**: `data-disk`
   - **Mount Path**: `/var/data`
   - **Size**: 1 GB (plenty for JSON + FAISS indexes)

### Step 2: Update Environment Variables

Add these to your Render service:

```
DATA_DIR=/var/data
```

### Step 3: Update state.py (Optional)

If you want to use a custom data directory, update `state.py`:

```python
import os

# In AppState.__init__():
data_dir_override = os.getenv("DATA_DIR")
if data_dir_override:
    self.data_dir = Path(data_dir_override)
else:
    self.data_dir = ROOT_DIR / "data"
```

### Step 4: Initial Data Migration

On first deploy with the new disk:

1. The disk will be empty
2. `initialize_data_files()` will copy seeds to the disk
3. All subsequent deploys will use the persistent data

To migrate existing production data:

```bash
# SSH into Render (if available) or use a one-time script
# Copy current data files to the new disk location
cp /opt/render/project/src/data/codex_tree.json /var/data/
cp /opt/render/project/src/data/stories_dict.json /var/data/
# ... etc
```

## Creating Seed Files

### One-Time Setup (Run Locally)

After setting up the persistent disk architecture, create initial seeds from your current data:

```powershell
cd data

# Create JSON seeds (add .seed to filename)
Copy-Item codex_tree.json seeds/codex_tree.seed.json
Copy-Item stories_dict.json seeds/stories_dict.seed.json
Copy-Item pending_stories.json seeds/pending_stories.seed.json

# Create FAISS seeds
Copy-Item stories.faiss seeds/stories.faiss
Copy-Item "stories.faiss.map.json" "seeds/stories.faiss.map.json"

# Create book seeds
mkdir seeds/books/christian_mysticism_vol_iv
Copy-Item ../books/christian_mysticism_vol_iv/story_positions.json seeds/books/christian_mysticism_vol_iv/story_positions.seed.json
# ... repeat for other books
```

### Updating Seeds

Only update seeds when:
- Adding a new book that should be in fresh deployments
- Major category structure changes
- Database schema migrations

**Do NOT** routinely copy production data back to seeds.

## Removing Files from Git Tracking

After confirming the new architecture works:

```bash
# Stop tracking data files (keeps local copies)
git rm --cached data/codex_tree.json
git rm --cached data/stories_dict.json
git rm --cached data/pending_stories.json
git rm --cached data/stories.faiss
git rm --cached "data/stories.faiss.map.json"
git rm --cached books/*/story_positions.json
git rm --cached books/*/stories_meta.json

# Commit the removal
git add .gitignore
git commit -m "chore: stop tracking mutable data files - use persistent disk"
git push
```

## FAQ

### Q: What happens if I need to add a new book?

1. Add the book's static files (`Full_Text.md`, `Stories.md`, `grouped_index.md`) to `books/{slug}/`
2. Create seed files for `story_positions.json` and `stories_meta.json`
3. Commit and push
4. On deploy, the seed files will be copied to the persistent disk

### Q: How do I backup production data?

Option 1: Keep `github_sync.py` running - it will commit changes to a branch (not main)
Option 2: Set up scheduled backups to S3/GCS
Option 3: Render disk snapshots

### Q: What if I need to reset to seed data?

SSH into Render (or use a management endpoint) and delete the files:

```bash
rm /var/data/codex_tree.json
# Restart the service - it will re-copy from seeds
```

### Q: Can I still test locally?

Yes! Your local `data/` files are untracked but still present. The seed mechanism only kicks in when files are missing.

## Rollback Plan

If this architecture causes issues:

1. Remove files from `.gitignore`
2. Copy production data locally
3. Commit the data files
4. Revert `state.py` changes
5. Remove the Render disk
