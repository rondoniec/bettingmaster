"""Tipsport.sk scraper that parses the league listing HTML.

Tipsport's REST API endpoints (`/rest/offer/v3/sports/COMPETITION/{id}/matches`
etc.) are now blocked or moved, but the league page renders all matches
inline as `<span data-m="<id>">Team A - Team B</span>` plus 1x2 odds in
sibling spans. This scraper:

  - Loads `/kurzy/futbal/futbal-muzi/<slug>-<competition_id>` in patchright
    Chrome under Xvfb (the only configuration that passes Cloudflare's
    bot-scoring).
  - Parses match rows with embedded odds straight from the DOM.
  - Caches per-match odds so the round-robin scheduler's
    scrape_odds_for_raw_match path can serve them without a second navigate.

Why an isolated thread: APScheduler's worker threads sometimes carry a
running asyncio loop that patchright's sync API refuses to share. Spawning
a fresh `concurrent.futures.ThreadPoolExecutor` thread for every Playwright
session sidesteps that — each new Python thread starts with empty asyncio
threadlocal state.
"""

from __future__ import annotations

import concurrent.futures
import logging
import tempfile
from datetime import datetime, timedelta, UTC
from typing import Optional

from bettingmaster.config import settings
from bettingmaster.scrapers.base import BaseScraper, RawMatch, RawOdds

logger = logging.getLogger(__name__)


# Hardcoded URL slug per Tipsport competition id. Discovered via
# /rest/offer/v6/sports tree (each COMPETITION node carries a `url` field).
COMPETITION_URL_SLUGS: dict[str, str] = {
    "118": "1-anglicka-liga-118",
    "140": "1-spanielska-liga-140",
}


# JS executed inside the loaded page to extract matches + 1x2 odds.
_EXTRACT_JS = r"""
() => {
  const matches = [];
  const seen = new Set();
  document.querySelectorAll("span[data-m]").forEach(nameSpan => {
    const id = nameSpan.getAttribute("data-m");
    if (!id || seen.has(id)) return;
    seen.add(id);

    const text = (nameSpan.textContent || "").trim();
    const sep = text.indexOf(" - ");
    if (sep < 0) return;
    const home = text.slice(0, sep).trim();
    const away = text.slice(sep + 3).trim();

    // Walk up to find the row container that holds 3 odds spans for this match.
    let row = nameSpan;
    let oddsValues = [];
    let detailHref = null;
    for (let depth = 0; depth < 10; depth++) {
      row = row?.parentElement;
      if (!row) break;
      const numericSpans = Array.from(row.querySelectorAll("span")).filter(s => {
        const t = (s.textContent || "").trim();
        return /^[0-9]+\.[0-9]{2}$/.test(t);
      });
      // Check anchor for match URL while we're here.
      const anchor = row.querySelector(`a[href*="${id}"]`);
      if (anchor && !detailHref) {
        detailHref = anchor.getAttribute("href");
      }
      if (numericSpans.length === 3 || numericSpans.length === 2) {
        oddsValues = numericSpans.map(s => parseFloat(s.textContent.trim()));
        break;
      }
    }

    matches.push({
      external_id: id,
      home_team: home,
      away_team: away,
      odds_1x2: oddsValues,
      detail_href: detailHref,
    });
  });
  return matches;
}
"""


def _scrape_competition(
    competition_id: str,
    proxy_url: str | None,
    headless: bool,
    channel: str,
) -> list[dict]:
    """Run a fresh Playwright session in this thread and return raw match dicts."""
    slug = COMPETITION_URL_SLUGS.get(competition_id)
    if not slug:
        logger.warning("[tipsport_html] No URL slug for competition %s", competition_id)
        return []

    try:
        from patchright.sync_api import sync_playwright
    except ImportError:
        from playwright.sync_api import sync_playwright

    user_data_dir = tempfile.mkdtemp(prefix="tipsport-html-")
    context_kwargs: dict = {
        "user_data_dir": user_data_dir,
        "channel": channel,
        "headless": headless,
        "locale": "sk-SK",
        "no_viewport": True,
    }
    if proxy_url:
        context_kwargs["proxy"] = {"server": proxy_url}

    url = f"https://www.tipsport.sk/kurzy/futbal/futbal-muzi/{slug}"

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(**context_kwargs)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
            except Exception:
                logger.warning("[tipsport_html] networkidle timeout for %s, trying anyway", url)
            page.wait_for_timeout(2000)
            try:
                matches = page.evaluate(_EXTRACT_JS)
            except Exception:
                logger.exception("[tipsport_html] DOM extraction failed for %s", url)
                return []
            html = page.content()
            n_data_m = html.count("data-m=")
            logger.info(
                "[tipsport_html] competition=%s scraped %d matches from %s (html=%d bytes, data-m=%d)",
                competition_id,
                len(matches or []),
                url,
                len(html),
                n_data_m,
            )
            return matches or []
        finally:
            try:
                context.close()
            except Exception:
                pass


class TipsportScraper(BaseScraper):
    BOOKMAKER = "tipsport"
    BASE_URL = "https://www.tipsport.sk"

    def __init__(self, db_session, http_client=None):
        super().__init__(db_session, http_client)
        # Cache populated by scrape_matches, consumed by scrape_odds_for_raw_match.
        self._odds_cache: dict[str, list[RawOdds]] = {}
        self._url_cache: dict[str, str] = {}

    def _run_in_fresh_thread(self, competition_id: str) -> list[dict]:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(
                _scrape_competition,
                competition_id,
                settings.tipsport_proxy_url,
                settings.tipsport_headless,
                settings.tipsport_browser_channel or "chrome",
            )
            return future.result(timeout=120)
        except Exception:
            logger.exception("[tipsport_html] thread crashed for %s", competition_id)
            return []
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def scrape_matches(self, league_external_id: str) -> list[RawMatch]:
        raw = self._run_in_fresh_thread(str(league_external_id))
        if not raw:
            return []

        # Tipsport listing doesn't carry a parseable kickoff time; default to
        # "now + 1h" so the round-robin doesn't drop matches as out of scope.
        # Football-data.org status sync corrects start times for known fixtures.
        approx_start = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)

        out: list[RawMatch] = []
        for entry in raw:
            ext = entry.get("external_id")
            home = entry.get("home_team") or ""
            away = entry.get("away_team") or ""
            if not ext or not home or not away:
                continue
            detail_href = entry.get("detail_href") or f"/zapas/{ext}"
            full_url = (
                detail_href
                if detail_href.startswith("http")
                else f"{self.BASE_URL}{detail_href}"
            )
            self._url_cache[ext] = full_url

            odds_1x2 = entry.get("odds_1x2") or []
            cached: list[RawOdds] = []
            if len(odds_1x2) == 3:
                for selection, value in zip(("home", "draw", "away"), odds_1x2):
                    cached.append(
                        RawOdds(
                            match_external_id=ext,
                            market="1x2",
                            selection=selection,
                            odds=float(value),
                            url=full_url,
                        )
                    )
            elif len(odds_1x2) == 2:
                # Some live rows show only home/away (no draw); skip — partial.
                pass
            self._odds_cache[ext] = cached

            out.append(
                RawMatch(
                    external_id=str(ext),
                    home_team=home,
                    away_team=away,
                    league_external_id=str(league_external_id),
                    start_time=approx_start,
                    status="prematch",
                    url=full_url,
                )
            )
        return out

    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        return self._odds_cache.get(str(match_external_id), [])

    def scrape_odds_for_raw_match(self, raw_match: RawMatch) -> list[RawOdds]:
        return self._odds_cache.get(str(raw_match.external_id), [])

    def close(self):
        self._odds_cache.clear()
        self._url_cache.clear()
        super().close()
