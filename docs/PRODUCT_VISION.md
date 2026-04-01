# Product Vision

> Hypotheses and product direction. This document informs the roadmap and specs — it is not a commitment. Items here are not scheduled until they move to ROADMAP.md.

---

## What Coupette is

A personal wine sommelier that learns your palate over time.

The core loop: you discover wines via conversation, log what you drink, and the sommelier gets progressively better at recommending things you'll actually enjoy. The more you use it, the more it knows you.

Reference products:
- **Letterboxd** — personal taste as identity, logging as the primary habit, discovery as a byproduct
- **Untappd** — frictionless check-in, stats as engagement, social proof without requiring a social network
- **Perplexity** — chat as the primary surface, structured data inline in the conversation

---

## The gap in the market

| Product | Strength | Weakness |
|---------|----------|----------|
| Vivino | Large catalog, label scan | Became a marketplace, journal is secondary |
| CellarTracker | Deep logging, serious community | UI from 2005, no AI |
| Delectable | Good UX (2014) | Acquired, abandoned |
| None | — | Modern journal UX + AI sommelier that learns from your history |

The bet: nobody has combined a clean Letterboxd-style logging experience with an AI that actually uses your history to recommend better wines.

---

## Core loop

```
Discover (chat) → Log (journal) → Profile builds → Recommendations improve → Discover better wines
```

Each phase of the roadmap adds one link in this chain:

- **Journal** (Phase 11) — log wines, ratings, tasting notes
- **Taste Profile** (Phase 12) — aggregate signals into structured preferences
- **Weekly Digest** (Phase 13) — AI-curated picks delivered to your inbox/Telegram
- **Cellar** (Phase 14) — track what you have, feed signals back to the profile

---

## Differentiation

**Proprietary data flywheel** — tasting history, cellar contents, and taste profile belong to the user and to Coupette. This data is not derivable from the SAQ catalog. It is the moat.

**AI that knows you** — not just "wines you might like" based on a single rating, but a sommelier with context: your price range, your go-to regions, how adventurous you are, what you're drinking tonight.

**SAQ-native** — stock alerts, availability by store, restock notifications. Vivino doesn't know if the wine is in stock at your local SAQ.

---

## Data strategy

Current data source: SAQ public catalog (scraped via sitemap). This is the practical constraint for the Quebec market.

Architecture is source-agnostic — the RAG pipeline, journal, and taste profile work with any wine catalog. If a different data source becomes available (affiliate API, LCBO, Wine-Searcher), it can replace or supplement the SAQ data without touching the product layer.

**Go-public decision gate** (not scheduled — revisit when user base exists):
- Option A: formal SAQ data agreement
- Option B: switch to a licensable data source (Wine-Searcher API, Open Food Facts)
- Option C: ship as-is with clear attribution, accept the legal ambiguity at low traffic

This decision blocks public launch, not private/portfolio use.

---

## Monetization hypotheses

Not validated. To be tested when real users exist.

**Freemium (most natural fit)**
- Free: unlimited journal, cellar, watchlist, store alerts
- Paid (~6–9 CAD/month): AI sommelier (Claude API cost), taste profile, weekly digest
- Rationale: wine hobbyists pay for niche tools they use regularly

**Lifetime purchase**
- 59–99 CAD one-time
- Reduces friction for early adopters
- Good for bootstrapping initial revenue before recurring base is established

**Affiliation**
- "Buy this wine" links → Wine-Searcher, LCBO (if API available), Amazon Wines (FR/EU)
- Passive revenue if organic traffic grows
- Also partially solves the data licensing problem (affiliate agreements often include catalog rights)

**What not to do**
- Ads — kills the premium feel
- B2B (restaurants, SAQ) — different sales cycle, different product, distraction
- Marketplace — competing with Vivino on their turf

---

## Portfolio narrative

> "I built a RAG + intent router + real-time availability alerts on a live e-commerce catalog, with a journaling layer that feeds back into personalized AI recommendations. The SAQ catalog is the demo dataset — the architecture works with any structured product catalog."

The technical story: production RAG pipeline, hybrid search, SSE streaming, JWT + Telegram OAuth, Docker + Caddy on a VPS. Solo dev, shipped, real users.

The product story: Letterboxd for wine, with an AI that learns your palate.

---

## What this document is not

- Not a spec — shipped features are documented in `docs/specs/`
- Not a roadmap — scheduled work is in `docs/ROADMAP.md`
- Not a commitment — hypotheses here need validation before they become tasks
