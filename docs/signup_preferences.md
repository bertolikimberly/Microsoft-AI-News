# Signup Preferences — Registration Flow

> Companion to [personas_and_features.md](./personas_and_features.md) (§3 — the original preference-controls proposal) and [feature_endpoints.md](./feature_endpoints.md) (F1/F2 — the endpoints that read/write these).
> Defines exactly what a new user selects during registration, in what order, and what each choice maps to.
> Taxonomy values are owned by [sources.json](../sources.json) `metadata.tags_taxonomy`; slugs are derived from labels by `tag_slug()` in [seed.py](../backend/app/seed.py).
> Status: **draft proposal** — supersedes the 5-control list in personas_and_features.md §3.

---

## 1. Flow overview

Registration is **two steps**:

| Step | Tier | Selections | Can skip? |
|---|---|---|---|
| 1 | **Compulsory** | Role · Topics · Sources · Frequency | No — user cannot finish registration without them |
| 2 | **Skippable refine** | Business · Regulation & Policy · Regional · Tone & Length | Yes — one **Skip** button; sensible defaults applied |

Design principles:

- **Role is asked first** — it is one tap, and it drives smart defaults for everything after it (see §4).
- **Skip means "no filter", not "match nothing"** — an empty selection in Step 2 is treated as a wildcard (include everything, don't penalise), never as "exclude all".
- **UI labels ≠ taxonomy labels** — the screen shows friendly text; the stored value is always the `slug`, which links back to the article tags.

---

## 2. Step 1 — Compulsory selections

### 2.1 Role — *single-select, asked first*

Question: **"Pick the one that best describes you."** Single-select (radio buttons or cards, not chips). Stored as a single value.

| UI label (shown to user) | Stored `slug` | Taxonomy label (`sources.json`) |
|---|---|---|
| Engineer (technical depth) | `for_engineers_technical_depth` | For engineers (technical depth) |
| Business & Sales | `for_business_sales` | For business & sales |
| Legal & Compliance | `for_legal_compliance` | For legal & compliance |
| Executive (strategic) | `for_executives_strategic` | For executives (strategic) |
| Researcher | `for_researchers` | For researchers |

> The `sources.json` labels are written from the *article's* point of view ("For engineers"); the registration UI re-frames them as first-person identity labels. The `slug` is unchanged, so it still matches article tags.

### 2.2 Topics — *multi-select, at least one required*

Question: **"Which topics do you want to follow?"** Multi-select chips. The user must pick **≥ 1**.

| `slug` | Label |
|---|---|
| `artificial_intelligence_ml` | Artificial Intelligence & ML |
| `cybersecurity` | Cybersecurity |
| `cloud_infrastructure` | Cloud & Infrastructure |
| `software_development` | Software Development |
| `hardware_chips` | Hardware & Chips |
| `data_privacy` | Data & Privacy |
| `quantum_computing` | Quantum Computing |
| `robotics_automation` | Robotics & Automation |
| `fintech_payments` | Fintech & Payments |
| `health_biotech` | Health & Biotech |
| `clean_tech_sustainability` | Clean Tech & Sustainability |
| `space_satellites` | Space & Satellites |
| `metaverse_xr` | Metaverse & XR |

### 2.3 Sources — *opt-out*

Question: **"We've picked a default set of sources. Mute any you don't want."** Shown as an opt-out list: every curated source is on by default; the user un-checks (mutes) the ones they don't want. Stored as the list of *muted* source ids. Source list comes from the `/sources` endpoint, backed by `sources.json`.

### 2.4 Frequency — *single-select*

Question: **"How often do you want your digest?"** Single-select.

| Value | Meaning |
|---|---|
| `daily` | One digest every day |
| `weekdays` | One digest Mon–Fri |
| `weekly` | One digest per week (delivery day/time tweakable later in settings) |

---

## 3. Step 2 — Skippable refine selections

All of Step 2 can be skipped with one button. If skipped, each dimension is treated as **no filter** (wildcard). The user can set any of these later in the preferences screen.

### 3.1 Business — *multi-select, skippable*

| `slug` | Label |
|---|---|
| `ma_funding` | M&A & Funding |
| `ipo_markets` | IPO & Markets |
| `big_tech_faang_microsoft` | Big Tech (FAANG+Microsoft) |
| `startups_venture` | Startups & Venture |
| `layoffs_hiring` | Layoffs & Hiring |
| `earnings_revenue` | Earnings & Revenue |

### 3.2 Regulation & Policy — *multi-select, skippable*

| `slug` | Label |
|---|---|
| `ai_regulation` | AI Regulation |
| `data_protection_gdpr_dpdp_lgpd` | Data Protection (GDPR, DPDP, LGPD) |
| `antitrust_competition` | Antitrust & Competition |
| `export_controls_sanctions` | Export Controls & Sanctions |
| `digital_infrastructure_policy` | Digital Infrastructure Policy |
| `cybersecurity_policy` | Cybersecurity Policy |
| `platform_regulation` | Platform Regulation |

### 3.3 Regional — *multi-select, skippable*

| `slug` | Label |
|---|---|
| `north_america` | North America |
| `europe` | Europe |
| `greater_china` | Greater China |
| `asia_pacific` | Asia Pacific |
| `india` | India |
| `latin_america` | Latin America |
| `middle_east_africa` | Middle East & Africa |

> Suggestion: default `regional` to the user's own region rather than showing it blank.

### 3.4 Tone & Length — *tweak, pre-filled from Role*

These are not blank questions — they arrive **pre-filled from the Role choice** (see §4). The user only adjusts them if the default is wrong.

| Field | Options |
|---|---|
| `tone` | `technical` · `business` · `executive` |
| `length` | `short` · `standard` · `deep` |

> The taxonomy's `seniority` dimension (`Deep dive (IC level)` / `Brief (exec level)`) is **not** a separate question — it maps onto `length`, which Role already defaults.

---

## 4. Role-driven smart defaults

Picking a Role pre-fills the rest so Step 2 becomes "confirm or tweak", not "decide from scratch". **Proposed** defaults (tune before locking):

| Role | `tone` | `length` | `frequency` | Pre-ticked Step-2 chips |
|---|---|---|---|---|
| Engineer | `technical` | `standard` | `daily` | — |
| Business & Sales | `business` | `standard` | `weekly` | Business: all |
| Legal & Compliance | `business` | `standard` | `weekly` | Regulation & Policy: all |
| Executive | `executive` | `short` | `weekly` | — |
| Researcher | `technical` | `deep` | `daily` | — |

All pre-ticked values remain fully editable — they are defaults, not locks.

---

## 5. Mapping to the preferences API

These selections are persisted via `PUT /me/preferences` (see [feature_endpoints.md](./feature_endpoints.md) F2).

| Signup selection | Preferences field | Type |
|---|---|---|
| Role | `role` | single slug |
| Topics | `topics` | list of slugs |
| Sources (muted) | `muted_sources` | list of source ids |
| Frequency | `frequency` | enum |
| Business | `business_tags` | list of slugs |
| Regulation & Policy | `regulation_tags` | list of slugs |
| Regional | `regions` | list of slugs |
| Tone | `tone` | enum |
| Length | `length` | enum |

Every value submitted is checked against the taxonomy from `/tags` (see [feature_endpoints.md](./feature_endpoints.md) F2) — unknown slugs are rejected.

---

## 6. Open items

- [ ] Confirm the role-driven default values in §4 with the LLM Engineer (tone/length feed prompt templates) and the persona owner.
- [ ] Confirm ranking treats an empty Step-2 dimension as a wildcard, not an exclusion (§3 principle).
- [ ] Decide whether `regional` defaults to the user's detected region.
- [ ] Coordinate with Frontend Dev 1 — this two-step flow supersedes the single-list proposal in personas_and_features.md §3.
