# Personas & Features — Tech Intelligence Newsletter

> Phase 1 deliverable, Backend Dev 1 (Product/Architecture Lead).
> Draft v0.1 — iterate before locking.
> Anchored on [Specs.md](../Specs.md).

---

## 1. Target Audience

**MVP audience:** Microsoft employees who need to stay current on tech news (AI, cloud, devtools, competitive intel) but don't have time to read 20 sources a day.

**Why personas matter here:** Specs.md leaves "which preferences do we expose at registration?" as an open question. Personas drive that answer — different roles need different controls. They also drive feature priority: the chatbot's "dig deeper" flow is mission-critical for some personas and a nice-to-have for others.

---

## 2. Personas

Four personas, in priority order (P0 = must serve well at MVP; P1 = serve adequately; P2 = post-MVP).

### P0 — "Priya", Senior Software Engineer (Azure / AI Platform)

| | |
|---|---|
| **Role** | IC6-ish engineer building infra/AI services |
| **Goals** | Track AI model releases, infra trends, competitor moves (AWS/GCP), security advisories |
| **Pain points** | Drowning in newsletters; misses important launches; can't tell signal from hype |
| **News habits** | Skims 5-10 sources weekly; deep-reads 1-2 articles/day; uses HN, Twitter, vendor blogs |
| **Preferences** | Daily digest, technical tone, longer summaries (~5 sentences), citations critical, AI + infra topics |
| **Chatbot use** | "What's new in vLLM this week?" / "Compare AWS Bedrock and Azure AI Foundry's pricing." Deep follow-ups. |
| **Success metric** | Catches a major release within 24h; can explore a topic without leaving the product |

### P0 — "Marcus", Product Manager (Copilot / M365)

| | |
|---|---|
| **Role** | PM owning a feature area in a Copilot or M365 product |
| **Goals** | Competitive intel, customer-facing announcements, market trends, what analysts are saying |
| **Pain points** | Needs to brief execs on Mondays; spends Sunday catching up; hard to find non-tech-press analyst takes |
| **News habits** | Scans headlines daily; reads analyst pieces; follows competitor product blogs |
| **Preferences** | Weekly digest (Mon AM), business/exec tone, mid-length summaries, business-impact framing, competitive topics |
| **Chatbot use** | "What did Google announce at I/O that affects Copilot?" / "Summarize this week's analyst coverage of OpenAI." |
| **Success metric** | Walks into Monday standup with the week's competitive landscape already mapped |

### P1 — "Jen", Director of Engineering

| | |
|---|---|
| **Role** | M2 / Director overseeing multiple eng teams |
| **Goals** | Strategic-level signal only — major shifts, M&A, regulation, hiring market |
| **Pain points** | Has zero time; current digests are too long and too technical |
| **News habits** | Reads top-of-inbox in 5 minutes; delegates depth to ICs |
| **Preferences** | Weekly digest, executive tone, very short summaries (1-2 sentences), strategic + regulatory topics |
| **Chatbot use** | Rare — mostly "what should I know about X before this meeting?" |
| **Success metric** | One scan in the morning replaces 4 newsletter subscriptions |

### P2 — "Alex", AI Research Scientist (MSR)

| | |
|---|---|
| **Role** | Researcher, technical depth obsessed |
| **Goals** | Track papers, model releases, benchmark results |
| **Pain points** | News summaries are too shallow; loses citation chain to original paper |
| **News habits** | arXiv, Twitter, conf proceedings |
| **Preferences** | Daily digest, academic tone, paper citations preserved, AI/ML-only topics |
| **Chatbot use** | "Which papers this week cite RWKV?" — citation graph navigation |
| **Success metric** | Doesn't need to leave for arXiv to validate a claim |

*Post-MVP because: paper-grade citation fidelity requires academic-source ingestion (arXiv, ACL Anthology, etc.) which is a separate licensing/parsing track from press-RSS.*

---

## 3. Features (MVP)

Mapped to Specs.md MVP requirements. Each row = one feature with persona priority.

| # | Feature | Specs.md tie | Priya | Marcus | Jen | MVP? |
|---|---|---|---|---|---|---|
| F1 | **Employee registration** (Microsoft email + identity check) | §1 Registration | ✅ | ✅ | ✅ | **MVP** |
| F2 | **Preferences UI** (topics, sources, frequency, tone, length) | §1 Personalization | ✅ | ✅ | ✅ | **MVP** |
| F3 | **Email digest generation** (ranked, deduped, summarized, cited) | §2 Push | ✅ | ✅ | ✅ | **MVP** |
| F4 | **Configurable cadence** (daily / weekly; choice of delivery day/time) | §2 Push | daily | weekly | weekly | **MVP** |
| F5 | **Chatbot — grounded Q&A with citations** | §3 Pull | ✅ | ✅ | ✅ | **MVP** |
| F6 | **Chatbot — follow-ups & "dig deeper"** | §3 Pull | ✅ critical | ✅ | nice-to-have | **MVP** |
| F7 | **Chatbot — story comparison** ("compare X vs Y") | §3 Pull | ✅ | ✅ critical | — | **MVP** |
| F8 | **Read the digest in-app** (linked from email; same content rendered as web) | implied by §2 + §3 sharing infra | ✅ | ✅ | — | **MVP** |
| F9 | **Preferences edit + unsubscribe** | implied by §1 | ✅ | ✅ | ✅ | **MVP** |
| F10 | **Feedback signal** (thumbs up/down per item — feeds ranking) | implied by §3 eval | ✅ | ✅ | — | MVP-stretch |
| F11 | **Language selection** | open question in Specs.md | — | — | — | **post-MVP** |
| F12 | **Saved articles / read-later** | not in Specs.md | — | — | — | **post-MVP** |

### Preference controls exposed at registration (proposal — answers Specs.md open Q)

1. **Topics** — multi-select chip list, ~12 fixed taxonomy (AI/ML, Cloud, Security, DevTools, Data, Hardware, Regulation/Policy, M&A, Open Source, Research, Mobile, Enterprise)
2. **Sources** — opt-out only (we curate a default set in Phase 1; user can mute sources later)
3. **Frequency** — daily / weekdays / weekly (default: weekly)
4. **Length** — short (1-2 sentences) / standard (3-5) / deep (paragraph)
5. **Tone** — technical / business / executive

*Deliberately omitting at registration:* language (en-only at MVP), delivery time (sensible default; tweak in settings), source allowlist (too much choice up-front).

---

## 4. Non-Goals (MVP)

To keep scope honest:

- No native mobile app (mobile-web only — Frontend Dev 1's mobile-first wireframes cover this)
- No team/group digests — individual users only
- No content generation beyond summary + chat (no auto-tweet, no Slack bot)
- No external sharing primitives (Phase 2)
- No non-English sources
- No paid-tier sources at MVP (licensing complexity — Specs.md compliance topic)

---

## 5. Open Questions Carried Forward

> These feed the architecture diagram + API design tasks.

- [ ] **Employee verification mechanism** — Entra ID SSO? Email-domain check? Affects auth design.
- [ ] **Per-user data retention** — How long do we keep chat logs? GDPR open Q from Specs.md.
- [ ] **Feedback storage** — Is F10 a ranking input from day 1, or fire-and-forget for eval only?
- [ ] **Chatbot session memory** — Per-conversation only, or persistent user-level context?
- [ ] **Digest vs. chat shared index** — Specs.md §"system architecture" says they should share infra. Confirm one news index serves both retrieval paths.

---

## 6. Next Steps (Phase 1 dependencies)

- **Architecture diagram** (next task) — should reflect the MVP feature set above
- **API structure** — endpoints fall out of F1–F9 directly
- **Auth & user management** — answered by employee-verification decision above
- **Coordinate with Frontend Dev 1** — preference controls in §3 drive registration wireframes
- **Coordinate with LLM Engineer** — tone/length preferences (F2) must map to prompt templates
- **Coordinate with Data Engineer 2** — F10 feedback signal design
