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

    // Walk up to find the row container that holds the odds for this match.
    // Tipsport renders 1x2 odds as buttons / spans with numeric text.
    let row = nameSpan;
    let oddsValues = [];
    let detailHref = null;
    for (let depth = 0; depth < 10; depth++) {
      row = row?.parentElement;
      if (!row) break;
      // Anchor with match URL.
      const anchor = row.querySelector(`a[href*="${id}"]`);
      if (anchor && !detailHref) {
        detailHref = anchor.getAttribute("href");
      }
      // Collect odds values: require decimal point so integer outcome labels
      // ("1", "2") are excluded — only real odds like "1.50", "4.20" match.
      const candidates = Array.from(row.querySelectorAll("span, div, button"))
        .map(el => (el.textContent || "").trim())
        .filter(t => /^[0-9]+\.[0-9]{1,3}$/.test(t))
        .map(t => parseFloat(t))
        .filter(v => v >= 1.01 && v <= 100);
      // Dedup adjacent identical values caused by nested span+div pairs.
      const unique = [];
      for (const v of candidates) {
        if (unique.length === 0 || unique[unique.length - 1] !== v) unique.push(v);
      }
      if (unique.length >= 3) {
        oddsValues = unique.slice(0, 3);
        break;
      }
      if (unique.length === 2 && depth >= 4) {
        oddsValues = unique;
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
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception:
                logger.warning("[tipsport_html] domcontentloaded timeout for %s", url)
            try:
                page.wait_for_selector("span[data-m]", timeout=20000)
            except Exception:
                logger.warning(
                    "[tipsport_html] span[data-m] never appeared for %s",
                    url,
                )
            page.wait_for_timeout(1500)
            try:
                matches = page.evaluate(_EXTRACT_JS)
            except Exception:
                logger.exception("[tipsport_html] DOM extraction failed for %s", url)
                return []
            logger.info(
                "[tipsport_html] competition=%s scraped %d matches",
                competition_id,
                len(matches or []),
            )
            return matches or []
        finally:
            try:
                context.close()
            except Exception:
                pass


class TipsportScraper(BaseScraper):
    BOOKMAKER = "tipsport"
    CREATES_MATCHES = False  # no reliable kickoff times; only attach to existing records
    BASE_URL = "https://www.tipsport.sk"

    def __init__(self, db_session, http_client=None):
        super().__init__(db_session, http_client)
        # Cache populated by scrape_matches, consumed by scrape_odds_for_raw_match.
        self._odds_cache: dict[str, list[RawOdds]] = {}
        self._url_cache: dict[str, str] = {}

    def _run_in_fresh_thread(self, competition_id: str) -> list[dict]:
        import subprocess as _sp
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
        except concurrent.futures.TimeoutError:
            logger.warning("[tipsport_html] Playwright timed out for %s — killing chrome", competition_id)
            _sp.run(["pkill", "-9", "-f", "chrom"], capture_output=True)
            return []
        except Exception:
            logger.exception("[tipsport_html] thread crashed for %s", competition_id)
            _sp.run(["pkill", "-9", "-f", "chrom"], capture_output=True)
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

        # Known outright / non-match keywords in team name fields
        _OUTRIGHT_TOKENS = frozenset(
            ["liga", "league", "celkovo", "strelec", "strelci", "víťaz",
             "postup", "zostup", "champion", "winner", "scorer", "serie"]
        )

        def _is_outright(name: str) -> bool:
            low = name.lower()
            return any(tok in low for tok in _OUTRIGHT_TOKENS)

        out: list[RawMatch] = []
        for entry in raw:
            ext = entry.get("external_id")
            home = entry.get("home_team") or ""
            away = entry.get("away_team") or ""
            if not ext or not home or not away:
                continue
            if _is_outright(home) or _is_outright(away):
                logger.debug("[tipsport_html] skip outright: %s vs %s", home, away)
                continue
            detail_href = entry.get("detail_href") or f"/zapas/{ext}"
            full_url = (
                detail_href
                if detail_href.startswith("http")
                else f"{self.BASE_URL}{detail_href}"
            )
            self._url_cache[ext] = full_url

            odds_1x2 = entry.get("odds_1x2") or []
            logger.debug(
                "[tipsport_html] %s vs %s raw odds_1x2=%s",
                home, away, odds_1x2,
            )
            cached: list[RawOdds] = []
            if len(odds_1x2) == 3:
                # Tipsport listing order is home, away, draw (not the
                # canonical 1X2). Reorder before mapping.
                home_v, away_v, draw_v = odds_1x2
                logger.debug(
                    "[tipsport_html] %s vs %s mapped home=%.2f away=%.2f draw=%.2f",
                    home, away, home_v, away_v, draw_v,
                )
                for selection, value in (("home", home_v), ("draw", draw_v), ("away", away_v)):
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
                logger.debug("[tipsport_html] %s vs %s only 2 odds, skipping", home, away)
            else:
                logger.warning(
                    "[tipsport_html] %s vs %s unexpected odds count %d: %s",
                    home, away, len(odds_1x2), odds_1x2,
                )
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
