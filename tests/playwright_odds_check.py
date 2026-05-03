"""
Playwright odds sanity checker.

Fetches live match data from the backend API, captures UI screenshots via
Playwright, then asks Claude (sonnet-4-6 via `claude -p`) to spot bugs.

Usage:
    python tests/playwright_odds_check.py [--base-url http://192.168.1.101]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright


BASE_URL_DEFAULT = "http://192.168.1.101"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
SCREENSHOT_DIR = Path("/tmp/bm_playwright_screenshots")
CLAUDE_MODEL = "claude-sonnet-4-6"

# Heuristic: draw odds should never be lower than the lower of home/away
# odds by more than this factor (accounts for genuinely tight matches).
DRAW_MIN_FACTOR = 0.75


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

def fetch_best_odds(backend: str) -> list[dict]:
    r = requests.get(f"{backend}/api/matches/best-odds", timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_match_detail(backend: str, match_id: str) -> dict:
    r = requests.get(f"{backend}/api/matches/{match_id}", timeout=10)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Rule-based checks (no AI)
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str   # "error" | "warning"
    match: str
    rule: str
    detail: str


def rule_check_1x2(match: dict) -> list[Issue]:
    """Sanity-check 1x2 best-odds selections for a single match."""
    issues: list[Issue] = []
    label = f"{match['home_team']} vs {match['away_team']}"
    sels = {s["selection"]: s for s in match.get("selections", [])}

    home_s = sels.get("home")
    draw_s = sels.get("draw")
    away_s = sels.get("away")

    for sel_name, sel in sels.items():
        v = sel["odds"]
        if v < 1.01:
            issues.append(Issue("error", label, "odds_below_minimum",
                                f"{sel_name}={v} ({sel['bookmaker']}) — impossible odds"))
        if v > 50:
            issues.append(Issue("warning", label, "odds_very_high",
                                f"{sel_name}={v} ({sel['bookmaker']}) — suspiciously high"))

    if home_s and away_s and draw_s:
        h, a, d = home_s["odds"], away_s["odds"], draw_s["odds"]
        min_win = min(h, a)
        # Draw should never be cheaper than the heavy favorite by >25%
        if d < min_win * DRAW_MIN_FACTOR:
            issues.append(Issue("error", label, "draw_odds_too_low",
                                f"draw={d} but min(home,away)={min_win:.2f} — "
                                f"draw cheaper than either win outcome"))

        # Home and away suspiciously identical (possible swap)
        if abs(h - a) < 0.05 and h < 2.0:
            issues.append(Issue("warning", label, "home_away_identical_low",
                                f"home={h} away={a} — identical and < 2.0, possible swap"))

        # Implied probability > 100% by a very large margin (surebet or error)
        ip = (1 / h) + (1 / d) + (1 / a)
        if ip > 1.5:
            issues.append(Issue("error", label, "implied_prob_too_high",
                                f"implied_prob={ip:.2f} — massive overround, likely parsing error"))

    return issues


# ---------------------------------------------------------------------------
# Playwright UI checks
# ---------------------------------------------------------------------------

def capture_ui_odds(frontend: str) -> dict:
    """Open homepage + each match card; return {match_id: screenshot_path, ...} plus raw text."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    captured: dict[str, dict] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # Homepage
        page.goto(frontend, wait_until="networkidle", timeout=30000)
        homepage_shot = SCREENSHOT_DIR / "homepage.png"
        page.screenshot(path=str(homepage_shot), full_page=True)
        homepage_text = page.inner_text("body")

        # Collect match card links
        match_links = page.query_selector_all("a[href*='/match/']")
        hrefs = list({el.get_attribute("href") for el in match_links if el.get_attribute("href")})

        captured["__homepage__"] = {
            "screenshot": str(homepage_shot),
            "text_sample": homepage_text[:3000],
        }

        for href in hrefs[:6]:  # cap at 6 match pages
            match_id = href.rstrip("/").split("/")[-1]
            full_url = f"{frontend}{href}"
            try:
                page.goto(full_url, wait_until="networkidle", timeout=20000)
                shot_path = SCREENSHOT_DIR / f"match_{match_id}.png"
                page.screenshot(path=str(shot_path), full_page=True)
                text = page.inner_text("body")
                captured[match_id] = {
                    "url": full_url,
                    "screenshot": str(shot_path),
                    "text_sample": text[:4000],
                }
            except Exception as e:
                captured[match_id] = {"url": full_url, "error": str(e)}

        browser.close()

    return captured


# ---------------------------------------------------------------------------
# Claude AI analysis
# ---------------------------------------------------------------------------

def ask_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", "--model", CLAUDE_MODEL, "--dangerously-skip-permissions"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return f"[claude error: {result.stderr.strip()}]"
    return result.stdout.strip()


def build_claude_prompt(matches: list[dict], rule_issues: list[Issue], ui_captures: dict) -> str:
    matches_json = json.dumps(
        [
            {
                "match": f"{m['home_team']} vs {m['away_team']}",
                "league": m.get("league_id", ""),
                "kickoff": m.get("start_time", ""),
                "status": m.get("status", ""),
                "bookmakers": m.get("bookmakers", []),
                "best_odds": {s["selection"]: {"odds": s["odds"], "bookmaker": s["bookmaker"]}
                              for s in m.get("selections", [])},
            }
            for m in matches
        ],
        indent=2,
    )

    rule_text = "\n".join(
        f"  [{i.severity.upper()}] {i.match} — {i.rule}: {i.detail}"
        for i in rule_issues
    ) or "  (none)"

    ui_text = "\n\n".join(
        f"=== {k} ===\n{v.get('text_sample', v.get('error', ''))[:1500]}"
        for k, v in ui_captures.items()
    )

    return textwrap.dedent(f"""
        You are a QA engineer reviewing a football odds-comparison site called BettingMaster.
        The site scrapes odds from Slovak bookmakers (Fortuna, DOXXbet, Nike, Tipsport, Tipos)
        and Polymarket, normalises them, and shows best odds per outcome.

        ## Backend API data (best odds per match right now)

        {matches_json}

        ## Rule-based issues already detected

        {rule_text}

        ## Raw UI text captured by Playwright

        {ui_text}

        ---

        Your job: identify ALL likely bugs, wrong odds, or suspicious values.
        Focus on:
        1. Odds that are implausible for the match context (e.g. Man City away at 2.75 when
           they are a strong favourite — real value should be ~1.50).
        2. Home/away odds appearing swapped.
        3. Draw odds below the favourite's win odds.
        4. Missing outcomes (e.g. only 2 of 3 selections present).
        5. Bookmaker attribution errors (wrong bookmaker credited).
        6. Freshness issues (data older than 30 minutes for a live/upcoming match).
        7. UI rendering bugs visible in the text (broken labels, NaN, undefined, %, wrong currency).

        For each issue: state MATCH | FIELD | OBSERVED | EXPECTED | LIKELY CAUSE.
        Be concise. If everything looks correct, say so explicitly.
    """).strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE_URL_DEFAULT)
    parser.add_argument("--skip-playwright", action="store_true",
                        help="Skip browser capture (API + rule checks only)")
    parser.add_argument("--skip-claude", action="store_true",
                        help="Skip Claude AI analysis (rule checks only)")
    args = parser.parse_args()

    backend = f"{args.base_url}:{BACKEND_PORT}"
    frontend = f"{args.base_url}:{FRONTEND_PORT}"

    print(f"Backend:  {backend}")
    print(f"Frontend: {frontend}")
    print()

    # 1. Fetch API data
    print("Fetching best odds from API...")
    try:
        matches = fetch_best_odds(backend)
    except Exception as e:
        print(f"ERROR: could not reach backend: {e}")
        return 1
    print(f"  {len(matches)} matches found")

    # 2. Rule-based checks
    print("\nRunning rule-based checks...")
    all_issues: list[Issue] = []
    for m in matches:
        all_issues.extend(rule_check_1x2(m))

    if all_issues:
        print(f"  {len(all_issues)} issue(s) found:")
        for issue in all_issues:
            print(f"    [{issue.severity.upper()}] {issue.match} — {issue.rule}: {issue.detail}")
    else:
        print("  No rule violations.")

    # 3. Playwright UI capture
    ui_captures: dict = {}
    if not args.skip_playwright:
        print(f"\nCapturing UI via Playwright ({frontend})...")
        try:
            ui_captures = capture_ui_odds(frontend)
            shots = [v["screenshot"] for v in ui_captures.values() if "screenshot" in v]
            print(f"  Captured {len(shots)} screenshot(s) → {SCREENSHOT_DIR}")
        except Exception as e:
            print(f"  WARNING: Playwright capture failed: {e}")

    # 4. Claude analysis
    if not args.skip_claude:
        print(f"\nAsking Claude {CLAUDE_MODEL} to analyse...")
        prompt = build_claude_prompt(matches, all_issues, ui_captures)
        analysis = ask_claude(prompt)
        print("\n" + "=" * 70)
        print("CLAUDE ANALYSIS")
        print("=" * 70)
        print(analysis)
        print("=" * 70)
    else:
        print("\n(Claude analysis skipped)")

    return 1 if any(i.severity == "error" for i in all_issues) else 0


if __name__ == "__main__":
    sys.exit(main())
