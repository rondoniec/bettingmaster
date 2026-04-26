# AI Citability Analysis: Ranná Správa

**URL:** https://rannasprava.sk  
**Analysis Date:** 2026-04-14  
**Overall Citability Score: 18/100**  
**Citability Coverage:** 0% of content blocks score above 70

---

## Score Summary

| Category | Score | Weight | Weighted |
|---|---|---|---|
| Answer Block Quality | 15/100 | 30% | 4.5 |
| Passage Self-Containment | 25/100 | 25% | 6.25 |
| Structural Readability | 20/100 | 20% | 4.0 |
| Statistical Density | 10/100 | 15% | 1.5 |
| Uniqueness & Original Data | 20/100 | 10% | 2.0 |
| **Overall** | | | **18/100** |

---

## Why Score Is Low

Site is a **newsletter landing page**, not a content site. AI systems cannot cite it because:

1. **No crawlable content** — robots.txt missing (404), archive is JS-rendered, inaccessible to AI crawlers
2. **No answer blocks** — homepage contains ~350 words of marketing copy, zero informational passages
3. **No statistics with sources** — "4 200 čitateľov" is a claim, not a cited fact
4. **No indexable articles** — newsletter issues are not public web pages; AI cannot read them
5. **Slovak-only content** — limits reach to Slovak-language AI queries only

---

## Content Block Scores

| Section | Words | Answer Quality | Self-Contained | Structure | Stats | Unique | Overall |
|---|---|---|---|---|---|---|---|
| Hero ("Slovensko a svet za 5 minút") | 28 | 5 | 20 | 15 | 0 | 10 | 11 |
| Value proposition paragraph | 35 | 15 | 30 | 20 | 5 | 15 | 19 |
| Stats row (čitatelia/čas/cena) | 12 | 10 | 25 | 20 | 20 | 10 | 17 |
| Footer | 18 | 5 | 15 | 10 | 0 | 10 | 8 |

---

## Strongest Block

### Value proposition — Score: 19/100
> "Ranná Správa je denný newsletter, ktorý ti každé pracovné ráno zhrnie to najdôležitejšie — z domova aj zo sveta. Bez clickbaitu, bez zbytočností."

**Why it's the best:** Has definition pattern ("X je..."), names the subject, self-contained. Still low because no statistics, no sourced claims, too short (35 words vs optimal 134-167).

---

## Weakest Block

### Hero heading — Score: 11/100
> "Slovensko a svet za 5 minút."

**Problem:** Tagline, not an answer block. No subject definition, no facts, no context. AI cannot extract or cite this.

---

## Root Problem

rannasprava.sk is **not a content site** — it is a conversion page. AI citability tools are designed for content (blog posts, articles, guides). This site has none of that publicly accessible.

**Comparison:**
- thehustle.co publishes newsletter content as public web articles → citable
- morning.brew publishes articles → citable  
- rannasprava.sk publishes newsletters only in email → **not citable**

---

## Quick Wins to Reach 60+ Score

| Action | Citability Lift | Effort |
|---|---|---|
| 1. Publish newsletter archive as public HTML pages | +30 pts | Medium |
| 2. Add `/o-nas` about page with sourced stats on Slovak media landscape | +8 pts | Low |
| 3. Add robots.txt explicitly allowing all AI crawlers | +5 pts | 1 hour |
| 4. Add `llms.txt` describing newsletter topics and audience | +4 pts | 1 hour |
| 5. Add Organization + NewsMediaOrganization schema to homepage | +4 pts | 2 hours |
| 6. Replace "4 200 čitateľov" with a sourced/dated stat | +3 pts | Low |

---

## Strategic Recommendation

Newsletter → Web content pipeline is the only path to AI citability.

**Option A (Fast):** Auto-publish each issue as a public `/archiv/YYYY-MM-DD` page with proper headings and structured content. Archive becomes crawlable. Each issue = one citable page.

**Option B (Slow):** Build `/blog` section with evergreen Slovak news analysis. AI systems can cite these as authoritative Slovak-language sources.

**Option C (Minimal):** Add `llms.txt` + Organization schema + robots.txt. Scores reach ~35/100. AI knows you exist but cannot cite specific content.

---

## AI Crawler Access

| Crawler | Access | Notes |
|---|---|---|
| GPTBot (OpenAI) | Unknown | No robots.txt — undefined behavior |
| ClaudeBot (Anthropic) | Unknown | No robots.txt |
| PerplexityBot | Unknown | No robots.txt |
| GoogleBot | Unknown | No robots.txt |

**Priority fix:** Create `robots.txt` at `/robots.txt` explicitly allowing all crawlers. Currently 404.
