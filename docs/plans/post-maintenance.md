# Post Maintenance System

**Status:** Deferred — build once post volume warrants it (~60–90 days after go-live, ~180–270 posts)

---

## Problem

As posts accumulate, two types of rot develop:

1. **Stale affiliate URLs** — Amazon products go out of stock, ASINs get deprecated, PDPs change. Dead links hurt account credibility and waste TikTok bio link real estate.
2. **Non-performing posts** — Some carousels simply don't get traction. Leaving them live dilutes the account's average engagement rate, which can suppress future posts in the algorithm.

---

## Current State of the Data

`logs/posts.json` already records every published post (written by `daemon.py:_record_post()`). Current fields:

```json
{
  "date": "2026-08-01",
  "run_id": "81ff686c",
  "account_id": "womenswear-01",
  "publish_id": "7xxx...",
  "posted_at": "2026-08-01T09:02:14"
}
```

**Gap:** Missing `product_id`, `asin`, and `affiliate_url`. These are available in `metadata` inside `_do_post()` in daemon.py at the time of posting. When building this system, add those three fields to `_record_post()` — a one-line change.

---

## Design

### Two independent maintenance jobs in `tools/maintenance.py`

#### Job 1 — Stale URL Pruner (run weekly)

For each post in `logs/posts.json` with status `live`:

1. **Check availability via Amazon PA API** (`GetItems` call, `ASIN` from stored field)
   - `Availability.Type == "Now"` → still live, skip
   - `TemporarilyUnavailable` → skip (don't delete, product may return)
   - `Unavailable` / item not found → mark stale, proceed to delete
   - Fallback if PA API not accessible: HTTP GET the affiliate URL, check for 404 or "currently unavailable" text in response (less reliable — Amazon blocks bots aggressively)

2. **Delete from TikTok** via `POST /v2/video/delete/` (same endpoint handles photo carousels)
   - Pass `publish_id`
   - On success: update `logs/posts.json` entry → `status: "deleted_stale"`, add `deleted_at`

3. **Update backlog.json** — set that product's status to `stale` so it's never re-queued

#### Job 2 — Low-Performer Pruner (run monthly, posts ≥ 14 days old only)

1. **Query TikTok metrics** via `POST /v2/video/query/` with a list of `publish_id`s
   - Returns: `view_count`, `like_count`, `share_count`, `comment_count`
   - **Note:** Basic metrics only. Completion rate and profile-visit attribution require the TikTok Research API (separate developer approval needed — apply when volume justifies it)

2. **Threshold check** (suggested defaults — tune based on actual performance data):
   - Delete if: `view_count < 500` AND `like_count < 20` AND post age > 14 days
   - Never delete posts under 30 days old regardless of metrics (early posts sometimes have delayed virality)

3. **Delete from TikTok**, update `logs/posts.json` → `status: "deleted_low_performer"`

---

## File changes when building

| File | Change |
|------|--------|
| `daemon.py` | Add `product_id`, `asin`, `affiliate_url` to `_record_post()` call and signature |
| `logs/posts.json` | Gain new fields + `status` field (default `"live"`) |
| `tools/maintenance.py` | New file — both pruner jobs, CLI flags `--stale` / `--performers` / `--all` |
| `daemon.py` | Optional: call maintenance weekly from the main loop on a day-of-week check |

---

## TikTok API notes

- **Delete endpoint:** `POST /v2/video/delete/` — confirmed works for photo carousels despite the "video" name
- **Query endpoint:** `POST /v2/video/query/` — requires `video.list` scope (same scope used for posting)
- **`auto_add_music: true` in publisher.py** is a no-op for photo carousels — video-only parameter, safe to remove when touching publisher.py next
- **Slide count:** API max is 10 slides. Optimal for completion rate is 5–7. Current 5-slide setup is correct.
- **Slide duration:** Fixed at ~3–5 seconds per slide by TikTok. Not controllable via API.
- **Music:** TikTok selects music for photo carousels internally. No API parameter to specify song, genre, or theme.

---

## When to build

Suggested trigger: **~180 posts live** (roughly 90 days at 2/day). At that point:
- Enough posts that manual URL checking is impractical
- Enough performance data to set meaningful thresholds
- Amazon product churn will have already invalidated some early posts
