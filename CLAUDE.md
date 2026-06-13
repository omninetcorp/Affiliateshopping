# CLAUDE.md

## Project Purpose

Two-phase fully automated TikTok affiliate carousel pipeline.

**Phase 1 — Product Research Agent:** Discovers products from Amazon and TikTok Shop
by niche, scores each for affiliate potential, and populates a production backlog.

**Phase 2 — Slideshow Production Pipeline:** Consumes the backlog, generates AI model
carousel slides via local ComfyUI (RTX 5090), assembles with text overlays using Pillow,
and posts to the correct niche TikTok account via the TikTok Content Posting API.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│  PHASE 1 — PRODUCT RESEARCH AGENT                        │
│                                                          │
│  Searches Amazon PA API + TikTok Shop per niche          │
│         ↓                                                │
│  Scores each product (affiliate %, popularity, visual)   │
│         ↓                                                │
│  Writes: products/{id}.json + entry in backlog.json      │
└──────────────────────────┬───────────────────────────────┘
                           │  backlog.json
                           ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 2 — SLIDESHOW PRODUCTION PIPELINE                 │
│                                                          │
│  Backlog Manager → picks highest-scored queued product   │
│         ↓                                                │
│  Model Selector → picks model, tracks rotation           │
│         ↓                                                │
│  Template Selector → builds per-slide prompts            │
│         ↓                                                │
│  Image Generator → ComfyUI (local RTX 5090)              │
│         ↓                                                │
│  Slide Assembler → text overlays, CTA slides (Pillow)    │
│         ↓                                                │
│  QA Agent → validates slides before publish              │
│         ↓                                                │
│  Publisher → TikTok Content Posting API                  │
└─────────────────────────────────────────────────────────┘
```

---

## Key Rules

- NEVER post more than `daily_post_limit` per account (config.yaml)
- NEVER reuse same model within last 5 posts on same account (rotation_log.json)
- ALWAYS pick only `queued` entries from backlog
- ALWAYS update backlog status: queued → in_progress → ready_to_post → published/failed
- ComfyUI must be running at http://localhost:8188 before Phase 2 starts
- All config lives in config.yaml — never hardcode niche names, limits, or credentials

---

## Running the Pipeline

```bash
# Phase 1 — discover products and fill backlog
python phase1/research_agent.py

# Phase 2 — generate one carousel (optionally specify niche)
python pipeline/orchestrator.py
python pipeline/orchestrator.py womens-swimwear

# Publish a ready carousel
python pipeline/publisher.py output/<run_id>/metadata.json
```

---

## Credentials (set in .env file)

```
AMAZON_ACCESS_KEY
AMAZON_SECRET_KEY
AMAZON_PARTNER_TAG
AMAZON_REGION
ANTHROPIC_API_KEY
TIKTOK_ACCESS_TOKEN_SWIMWEAR_01
TIKTOK_ACCESS_TOKEN_KITCHEN_01
TIKTOK_ACCESS_TOKEN_BEAUTY_01
```

---

## Directory Roles

| Directory | Role |
|---|---|
| `products/` | Phase 1 output — one JSON per product. Never edit manually. |
| `backlog.json` | Queue. Phase 1 appends. Phase 2 reads + updates status. |
| `templates/` | Slide prompt templates per niche. Edit to tune image style. |
| `characters/` | Model pool. Edit catalog.json to add/remove models. |
| `accounts/` | TikTok account configs. Edit to add accounts or change proxies. |
| `assets/` | Scratch space — auto-generated per run. Safe to delete. |
| `output/` | Final carousel packages ready to upload. Keep until confirmed posted. |
| `phase1/` | Product Research Agent scripts. |
| `pipeline/` | Phase 2 production pipeline scripts. |

---

## Slide Formats

**single-product** (default) — 5–7 slides for one product. One affiliate link.
**roundup** — 8 slides featuring 3–5 products on a theme. Multiple affiliate links.

---

## Image Generation & Platform Export

### Generation resolution
ComfyUI generates at **768×1344** (SDXL-native bucket, close to 9:16). Do NOT change this
back to 832×1216 — that caused ~21% vertical stretch when upscaling to 1080×1920.

### Platform export
After generation, `orchestrator.py` runs `_resize_cover()` to export each slide to every
platform in `PLATFORM_SIZES`. Current platforms:

| Platform | Size | Output path |
|----------|------|-------------|
| tiktok | 1080×1920 (9:16) | `output/{run_id}/tiktok/slide_NN.jpg` |
| pinterest | 1000×1500 (2:3) | `output/{run_id}/pinterest/slide_NN.jpg` |

**To add a new platform:** add one entry to `PLATFORM_SIZES` in `pipeline/orchestrator.py`.
The rest of the pipeline (export loop, QA validation, directory creation) handles it automatically.

### metadata.json slides format
`slides` is a **dict**, not a list:
```json
{
  "slides": {
    "tiktok": ["output/{run_id}/tiktok/slide_01.jpg", ...],
    "pinterest": ["output/{run_id}/pinterest/slide_01.jpg", ...]
  }
}
```
`publisher.py` reads `slides["tiktok"]` for TikTok posting. `qa_agent.py` validates each
platform against its own expected dimensions. Both handle the legacy list format for old runs.

### TikTok carousel notes (do not re-research these)
- Slide duration: ~3–5 sec per slide, fixed by TikTok — no API control
- Music: TikTok picks music for photo carousels internally — `auto_add_music` is video-only, no-op for carousels
- API slide limit: 10 max (native app allows 35, but API caps at 10)
- Optimal slide count: 5–7 for best completion rate

---

## Niches (config.yaml)

| Niche ID | Account | Template |
|---|---|---|
| womens-swimwear | swimwear-01 | swimwear-beach-v1 |
| kitchen-gadgets | kitchen-01 | kitchen-gadget-v1 |
| beauty-tools | beauty-01 | beauty-tools-v1 |

---

## Implementation Plan

Full step-by-step build plan: `docs/plans/2026-06-11-tiktok-affiliate-pipeline.md`
