from __future__ import annotations

import asyncio
import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright


CC_WORKER_PORT = int(os.environ.get("CC_WORKER_PORT", "8787"))
CC_WORKER_TOKEN = os.environ.get("CC_WORKER_TOKEN", "")


def parse_query_params(path: str) -> dict[str, str]:
    parsed = urlparse(path)
    query = parse_qs(parsed.query)
    return {key: values[0].strip() for key, values in query.items() if values}


def humanize_slug(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    special_cases = {
        "europe-middle-east-and-africa": "EMEA",
        "north-america": "Americas",
        "americas": "Americas",
        "apac-north": "APAC North",
        "apac-south": "APAC South",
    }
    if normalized in special_cases:
        return special_cases[normalized]
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", normalized) if part)


def derive_labels_from_url(
    battlefy_url: str,
    region_label: str = "",
    round_label: str = "",
    lobby_label: str = "",
) -> tuple[str | None, str | None, str | None]:
    parsed = urlparse(battlefy_url)
    query = parse_qs(parsed.query)

    derived_region = region_label.strip() or humanize_slug(query.get("region", [""])[0] or "")

    round_match = re.search(r"/round/(\d+)", parsed.path)
    derived_round = round_label.strip()
    if not derived_round and round_match:
        derived_round = f"Round {int(round_match.group(1)) + 1}"

    lobby_match = re.search(r"/match/(\d+)", parsed.path)
    derived_lobby = lobby_label.strip()
    if not derived_lobby and lobby_match:
        derived_lobby = f"Lobby {int(lobby_match.group(1)) + 1}"

    return derived_region or None, derived_round or None, derived_lobby or None


def normalized_names_match(left: str | None, right: str | None) -> bool:
    normalize = lambda value: re.sub(r"[^a-z0-9]+", "", (value or "").lower())
    normalized_left = normalize(left)
    normalized_right = normalize(right)
    if not normalized_left or not normalized_right:
        return False
    return (
        normalized_left == normalized_right
        or normalized_left in normalized_right
        or normalized_right in normalized_left
    )


async def fetch_stage_snapshot(stage_id: str) -> dict:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://battlefy.com/", wait_until="domcontentloaded", timeout=120000)
        result = await page.evaluate(
            """
            async (stageId) => {
              const urls = {
                stage: `https://api.battlefy.com/stages/${stageId}?extend[matches][top.team][players][user]=true&extend[matches][top.team][persistentTeam]=true&extend[matches][bottom.team][players][user]=true&extend[matches][bottom.team][persistentTeam]=true&extend[groups][teams]=true&extend[groups][matches][top.team][players][user]=true&extend[groups][matches][top.team][persistentTeam]=true&extend[groups][matches][bottom.team][players][user]=true&extend[groups][matches][bottom.team][persistentTeam]=true`,
                latest: `https://dtmwra1jsgyb0.cloudfront.net/stages/${stageId}/latest-round-standings`,
                ladder: `https://dtmwra1jsgyb0.cloudfront.net/stages/${stageId}/ladder-standings`
              };

              const responses = {};
              for (const [key, url] of Object.entries(urls)) {
                try {
                  const response = await fetch(url, { credentials: "include" });
                  const text = await response.text();
                  let data = null;
                  try {
                    data = JSON.parse(text);
                  } catch (error) {
                    data = text;
                  }
                  responses[key] = { status: response.status, data };
                } catch (error) {
                  responses[key] = { status: 0, error: String(error) };
                }
              }
              return responses;
            }
            """,
            stage_id,
        )
        await browser.close()
        return result


def resolve_challenger_rows(stage_snapshot: dict, target_name: str, track_by: str) -> list[dict]:
    stage_payload = stage_snapshot.get("stage", {}).get("data")
    if isinstance(stage_payload, list) and stage_payload:
        stage_payload = stage_payload[0]

    latest_rows = stage_snapshot.get("latest", {}).get("data") or []
    groups = stage_payload.get("groups", []) if isinstance(stage_payload, dict) else []
    if not latest_rows or not groups:
        return []

    team_lookup: dict[str, dict] = {}
    for group in groups:
        for team in group.get("teams", []):
            if team.get("_id"):
                team_lookup[team["_id"]] = team

    ladder_positions: dict[str, int] = {}
    ladder_payload = stage_snapshot.get("ladder", {}).get("data")
    if isinstance(ladder_payload, dict):
        for position, row in enumerate(ladder_payload.get("standings", []), start=1):
            if row.get("teamID"):
                ladder_positions[row["teamID"]] = position

    standings: list[dict] = []
    for position, row in enumerate(latest_rows, start=1):
        team_id = row.get("teamID")
        team = team_lookup.get(team_id, {})
        team_name = team.get("name") or row.get("teamName") or row.get("name") or "Unknown team"
        players = team.get("players", []) if isinstance(team.get("players"), list) else []
        player_names = []
        for player in players:
            name = player.get("inGameName") or player.get("username") or player.get("user", {}).get("username")
            if name:
                player_names.append(name)

        highlight = normalized_names_match(team_name, target_name)
        if track_by == "player":
            highlight = any(normalized_names_match(player_name, target_name) for player_name in player_names)

        standings.append(
            {
                "position": ladder_positions.get(team_id, position),
                "name": team_name,
                "short_name": team_name,
                "points": row.get("points", 0),
                "kills": row.get("wins"),
                "player_names": player_names,
                "highlight": highlight,
            }
        )

    standings.sort(key=lambda row: (row.get("position") or 9999, -(row.get("points") or 0)))
    return standings


class CCWorkerHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self.respond_json({"ok": True})
            return

        if parsed.path != "/resolve":
            self.respond_json({"message": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        if CC_WORKER_TOKEN:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {CC_WORKER_TOKEN}":
                self.respond_json({"message": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
                return

        params = parse_query_params(self.path)
        target_name = params.get("target_name", "")
        track_by = params.get("track_by", "team") or "team"
        stage_id = params.get("stage_id", "")
        battlefy_url = params.get("battlefy_url", "")
        region_label = params.get("region_label", "")
        round_label = params.get("round_label", "")
        lobby_label = params.get("lobby_label", "")

        if not target_name or not stage_id or not battlefy_url:
            self.respond_json(
                {"message": "Missing target_name, battlefy_url, or stage_id."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            snapshot = asyncio.run(fetch_stage_snapshot(stage_id))
            standings = resolve_challenger_rows(snapshot, target_name, track_by)
            if not standings:
                self.respond_json(
                    {"message": "No Challenger Circuit standings were returned for this stage."},
                    status=HTTPStatus.BAD_GATEWAY,
                )
                return

            region_label, round_label, lobby_label = derive_labels_from_url(
                battlefy_url,
                region_label,
                round_label,
                lobby_label,
            )
            payload = {
                "track_by": track_by,
                "region_label": region_label,
                "round_label": round_label,
                "lobby_label": lobby_label,
                "advance_cutoff": 10,
                "standings": standings,
            }
            self.respond_json(payload)
        except Exception as exc:  # pragma: no cover
            self.respond_json({"message": str(exc)}, status=HTTPStatus.BAD_GATEWAY)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def respond_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def run() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", CC_WORKER_PORT), CCWorkerHandler)
    print(f"CC worker listening on http://0.0.0.0:{CC_WORKER_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
