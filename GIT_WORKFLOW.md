# Git & GitHub Guide for This Project

Welcome! This doc explains what GitHub is, how to set it up, and the workflow we use
for this repo.

## 1. What is GitHub, actually?

- **Git** is a tool that tracks every change made to the files in a folder (a
  "repository," or "repo"). It keeps a full history, so you can always see who
  changed what, when, and roll back if needed.
- **GitHub** hosts a copy of that folder on a server ("the remote"), so everyone's
  local copy can stay in sync. Your laptop has a full local copy (with full history)
  that you periodically **push** (upload your changes) and **pull** (download
  others' changes) to/from GitHub.
- Think of it like a shared Google Doc, except: instead of everyone editing the same
  live file, each person edits their own copy on a separate **branch**, and changes
  only merge into the shared version after someone else reviews them. This avoids
  people overwriting each other's work.

## 2. One-time setup: SSH key

SSH keys let your laptop authenticate with GitHub without typing a password every
time.

1. Check if you already have one:
   ```
   ls -al ~/.ssh
   ```
   If you see `id_ed25519.pub` (or `id_rsa.pub`), you can skip to step 3.

2. Generate a new key (replace with your GitHub email):
   ```
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```
   Press Enter to accept the default file location. Set a passphrase or leave it
   blank (your choice).

3. Copy your public key to the clipboard:
   ```
   pbcopy < ~/.ssh/id_ed25519.pub
   ```
   (On Windows/Linux, open the `.pub` file in a text editor and copy it manually.)

4. Add it to GitHub:
   - Go to GitHub → click your profile photo → **Settings** → **SSH and GPG keys** →
     **New SSH key**.
   - Paste the key, give it a title (e.g. "My Laptop"), and save.

5. Test the connection:
   ```
   ssh -T git@github.com
   ```
   You should see: `Hi <username>! You've successfully authenticated...`

6. Clone the repo using the SSH URL (not HTTPS):
   ```
   git clone git@github.com:leotyang/DSO_585_project.git
   ```

## 3. Copying file paths (Mac and PC)

You'll frequently need to paste a file or folder's path — e.g. to `cd` into the repo,
or to point a command at a specific file. Instead of typing it out, use your OS's
built-in shortcut:

**Mac (Finder):**
- Right-click the file/folder → hold `Option` → the menu item **"Copy [name]"**
  changes to **"Copy as Pathname"**. Click it to copy the full absolute path.
- Alternative: select the file, then press `Cmd+Option+C`.
- Alternative: just drag the file/folder from Finder directly into a Terminal
  window — it inserts the full path at the cursor.

**PC (File Explorer):**
- Hold `Shift` and right-click the file/folder → click **"Copy as path"**.
- (Some Windows versions show this without needing to hold `Shift` — just
  right-click.)
- Paste with `Ctrl+V`; note it'll be wrapped in quotes, which is fine for most
  commands.

## 4. Commonly used commands

| Command | What it does |
|---|---|
| `git status` | Shows what's changed in your working folder vs. the last commit. Run this often. |
| `git pull` | Downloads the latest changes from GitHub into your current branch. |
| `git branch` | Lists your local branches; shows which one you're on. |
| `git checkout -b my-branch-name` | Creates a new branch and switches to it. |
| `git checkout my-branch-name` | Switches to an existing branch. |
| `git add <file>` or `git add .` | Stages changes (marks them to be included in the next commit). `.` stages everything. |
| `git commit -m "short message"` | Saves a snapshot of your staged changes with a description. |
| `git push` | Uploads your commits to GitHub. First time on a new branch, use `git push -u origin my-branch-name`. |
| `git log` | Shows commit history. |
| `git diff` | Shows line-by-line changes not yet staged. |

A typical day-to-day sequence:
```
git pull                          # get latest changes
git checkout -b leo/add-eda       # create your own branch
# ... make edits ...
git add .
git commit -m "Add exploratory data analysis notebook"
git push -u origin leo/add-eda
```

## 5. Branching strategy for this project

- `main` — the production/final branch. Nobody commits to this directly.
- `dev` — the shared working branch. All personal branches merge here first, and
  `dev` merges into `main` only when the project is in a stable state.
- Personal branches — one per person (or per feature), branched off `dev`. Naming
  convention: `<yourname>/<short-description>`, e.g. `leo/data-cleaning`,
  `sam/model-tuning`.

**Why personal branches?** If everyone edited `dev` directly, one person's
half-finished or broken code could block or break everyone else's work. Branches let
you experiment freely without affecting the shared codebase until your work is
reviewed and ready.

## 6. What is a Pull Request (PR)?

A **Pull Request** is a request to merge your branch's changes into another branch
(here, `dev`), along with a review step before that happens.

Why not just merge directly? Two reasons:
1. **A second set of eyes catches mistakes** — bugs, unclear code, accidental file
   changes — before they land in the shared branch.
2. **It creates a discussion + record.** The PR page shows exactly what changed
   (a "diff"), lets teammates leave comments on specific lines, and keeps a
   permanent history of why a change was made.

### How to open a PR

1. Make sure your branch is pushed to GitHub (`git push`).
2. Go to the repo on GitHub — you'll usually see a banner "Compare & pull request"
   for your recently pushed branch. Click it. (Or go to the **Pull requests** tab →
   **New pull request**.)
3. Set:
   - **base branch**: `dev` (what you're merging *into*)
   - **compare branch**: your personal branch (what you're merging *from*)
4. Add a clear title and description: what you changed and why. Screenshots or
   sample output are helpful if relevant.
5. Click **Create pull request**.
6. Assign a teammate as **Reviewer** (or just tag them / message them) and ask them
   to review.

### Reviewing a PR (for the reviewer)

1. Open the PR → **Files changed** tab to see the diff.
2. Read through the changes. Leave comments on specific lines if something looks
   off, unclear, or could be improved (click the `+` next to a line).
3. If it looks good: click **Review changes** → **Approve**.
4. If changes are needed: **Review changes** → **Request changes**, with comments
   explaining what to fix. The author updates their branch and pushes again — the PR
   updates automatically.
5. Once approved, the author (or reviewer) clicks **Merge pull request** to merge
   into `dev`.

### Best practices

- Keep PRs small and focused (one feature/fix at a time) — easier to review.
- Write a descriptive commit message and PR description; explain the "why," not just
  the "what."
- Pull the latest `dev` into your branch before opening a PR, to catch conflicts
  early:
  ```
  git checkout dev
  git pull
  git checkout my-branch-name
  git merge dev
  ```
- Don't merge your own PR without a review unless it's trivial (e.g. a typo fix) and
  the team has agreed that's fine.
- Delete your branch after it's merged (GitHub offers a button for this) to keep
  things tidy.

## 7. Quick end-to-end example

```
git checkout dev
git pull
git checkout -b leo/add-visualizations
# ... do work, save files ...
git add .
git commit -m "Add correlation heatmap and pairplot"
git push -u origin leo/add-visualizations
# Open PR on GitHub: base = dev, compare = leo/add-visualizations
# Teammate reviews, requests changes or approves
# Once approved -> Merge pull request
```
