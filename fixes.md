# MAI News — Bug Fix Tracker

Full audit completed 2026-06-30. Issues ordered by impact.

---

## BROKEN — Will silently fail or crash

- [ ] **1. Topic suggestions always empty**
  - File: `frontend/src/constants/data.ts`
  - Keys like `'ai_ml'` don't match backend slugs like `'artificial_intelligence_ml'`. `App.tsx` looks up `prefs.topics` in `TOPIC_SUGGESTIONS` and gets `undefined` for every entry — new chat screen shows no prompts.

- [ ] **2. User region hardcoded to 'eu'**
  - File: `frontend/src/lib/session.ts`
  - `apiUserToLocal()` hardcodes `region: 'eu'` instead of reading from the API response. User's actual region preference is ignored.

- [ ] **3. Newsletter consent reset on every save**
  - File: `frontend/src/components/preferences/PrefsDeck.tsx`
  - Always sends `newsletter_consent: false` regardless of what the user checked. Opt-in is overwritten every time preferences are saved.

- [ ] **4. Preferences don't load after login**
  - File: `frontend/src/components/App.tsx`
  - `getPreferences()` response is mapped incorrectly — `regions` is an array but code reads it as a scalar, and other fields don't propagate to local state. Dashboard shows defaults instead of user preferences after login.

- [ ] **5. Preferences save is incomplete**
  - File: `frontend/src/components/preferences/PrefsDeck.tsx`
  - `putPreferences` call omits `delivery_day`, `delivery_hour_local`, `language`, and `timezone`. Backend defaults overwrite whatever the user had set.

- [ ] **6. Chat message role mismatch**
  - File: `frontend/src/types/index.ts` + `frontend/src/components/App.tsx`
  - Backend returns `role: 'assistant'` but the frontend `ChatMessage` type uses `role: 'ai'`. There's a manual conversion in `App.tsx` but it's fragile and breaks type safety.

---

## MISSING — Feature exists on one side only

- [ ] **7. Folder editing not wired up**
  - File: `frontend/src/lib/api.ts`
  - Backend has `PATCH /me/folders/{folder_id}` but there is no `updateFolder()` function in the frontend API client. Folders cannot be renamed or edited after creation.

- [ ] **8. Source muting not implemented in frontend**
  - File: `frontend/src/lib/api.ts` + `frontend/src/components/preferences/PrefsDeck.tsx`
  - Backend accepts `muted_sources` in `PUT /me/preferences` and has a full `/sources` endpoint. Frontend never fetches available sources or sends muted ones.

- [ ] **9. Tags fetched from hardcoded constants instead of API**
  - File: `frontend/src/lib/api.ts`
  - `getTags()` is exported but never called. Frontend hardcodes tag IDs in `constants/preferences.ts` instead of pulling the live taxonomy from the backend. If the taxonomy changes in the DB, the UI won't reflect it.

---

## MISMATCH — Contract wrong between frontend and backend

- [ ] **10. Folder thread timestamps broken on Windows**
  - File: `backend/app/routers/folders.py`
  - Uses `%-d` in `strftime` which is Linux-only. On Windows (including the deployed environment) this renders literally as `%-d Jun` instead of `5 Jun`.

- [ ] **11. Folder creation sends unsplit topics**
  - File: `frontend/src/components/preferences/PrefsDeck.tsx` (folder mode)
  - Same bug as the preferences fix already applied: when creating a folder via PrefsDeck in `folderMode`, the topics array is passed flat without splitting into `topics` / `business_tags` / `regulation_tags`. Backend will 422 if any business or regulation tags are selected.

- [ ] **12. Session title set twice**
  - File: `frontend/src/components/App.tsx` + `backend/app/routers/sessions.py`
  - Frontend sets a title on session creation. Backend then overwrites it again on the first assistant reply if it detects a short/empty title. Results in a flash of the wrong title in the sidebar.

---

## Already fixed

- [x] **Preferences topics sent in wrong buckets** — `PrefsDeck.tsx` now splits `prefs.topics` into `topics`, `business_tags`, `regulation_tags` before calling `putPreferences`. Fixed 2026-06-30.
