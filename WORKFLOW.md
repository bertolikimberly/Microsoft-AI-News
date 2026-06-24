# Team Workflow

## Branch rules

- Never push directly to `main`
- Always pull before starting anything
- One branch per person per feature — keep them short-lived (finish, PR, merge same day)
- One person per file/component at a time — if two people need to touch the same file, stagger it

## Every time you start work

```bash
git checkout main
git pull
git checkout -b feat/your-feature
```

## When you're done

```bash
git push origin feat/your-feature
# Open a PR on GitHub → someone reviews → merge → next person pulls main
```

---

## What's left (priority order)

| # | Task | Notes |
|---|---|---|
| 1 | Wire email input in AuthGate to real magic-link | `frontend/src/components/auth/AuthGate.tsx` — currently always hits `dev-login` regardless of input |
| 2 | GitHub Actions cron for auto-ingest | Add `.github/workflows/ingest-cron.yml` — calls `POST /internal/run-ingest` on a schedule (e.g. every 6 hours) |
| 3 | Dashboard topic chips / badges on article cards | Visual context on `frontend/src/components/dashboard/DashboardView.tsx` |
| 4 | Azure deployment | Backend → Container Apps, Frontend → Storage static website (francecentral or swedencentral only — Static Web Apps unavailable in those regions) |

See `plan.md` for full details on each item.

---

## Getting help from Claude

For any task above, open Claude Code and say what you want to work on. Claude can implement it start-to-finish and open the PR — you just review and merge.

Make sure to always start from a fresh `main` before asking Claude to start a feature.
