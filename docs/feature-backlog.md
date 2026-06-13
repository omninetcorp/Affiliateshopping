# Feature Backlog

Future features in rough priority order. Each has a design doc in `docs/plans/`.

---

## Next Up

### #1 — Pinterest Cross-Posting
**Doc:** `docs/plans/pinterest-publishing.md` *(to be written)*
**Build when:** Ready now — highest-leverage expansion after TikTok is stable
**Summary:** Post each carousel to Pinterest automatically alongside TikTok. Pinterest is the strongest affiliate traffic driver of all candidate platforms: the destination URL is embedded directly on the pin (no "link in bio" friction), and fashion/kitchen/beauty niches have massive high-purchase-intent audiences there. Pinterest API supports programmatic pin creation. Each slide set already exists as 1080×1920 JPEGs — same files, no reformatting needed. Use slide 1 (hero-shot) as the pin image with the affiliate URL attached directly.

**Platform comparison (affiliate link support):**
| Platform | Affiliate links | How |
|----------|----------------|-----|
| Pinterest | ✅ Direct on pin | Embedded destination URL — clicks go straight to Amazon |
| Instagram | ⚠️ Bio only | Same "link in bio" friction as TikTok |
| YouTube Shorts | ⚠️ Description | Collapsed by default, low click-through |
| Facebook | ⚠️ Post link | Organic reach too low to be worth effort |
| Snapchat | ❌ | No organic affiliate link mechanism |

---

## Deferred

### Post Maintenance System
**Doc:** `docs/plans/post-maintenance.md`
**Build when:** ~180 posts live (~90 days after go-live)
**Summary:** Weekly stale-URL pruner (checks Amazon availability, deletes dead-link posts via TikTok API) + monthly low-performer pruner (deletes posts under view/like thresholds after 14 days). Requires a small `daemon.py` change to store `asin` + `affiliate_url` in `logs/posts.json` at post time.
