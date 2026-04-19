import Link from "next/link";

import { getMatchDetail, getMatchesByLeague } from "@/lib/api";
import { BOOKMAKER_ORDER, getBookmakerDisplay } from "@/lib/constants";
import { formatFullDate, formatOdds } from "@/lib/utils";

export const dynamic = "force-dynamic";

const TARGET_LEAGUE_ID = "ucl";
const TARGET_TEAMS = ["Bayern Munich", "Real Madrid"] as const;

type TeamOutcome = {
  bookmaker: string;
  url?: string;
  scrapedAt: string;
  homeOdds?: number;
  awayOdds?: number;
  hasOdds: boolean;
};

async function loadTestMatch() {
  const matches = await getMatchesByLeague(TARGET_LEAGUE_ID);
  const targetMatch = matches.find((match) => {
    const teams = [match.home_team, match.away_team].sort();
    return teams[0] === TARGET_TEAMS.slice().sort()[0] && teams[1] === TARGET_TEAMS.slice().sort()[1];
  });

  if (!targetMatch) {
    return null;
  }

  const detail = await getMatchDetail(targetMatch.id);
  const companyRows: TeamOutcome[] = BOOKMAKER_ORDER.map((bookmaker) => {
    const homeEntry = detail.odds.find(
      (entry) => entry.bookmaker === bookmaker && entry.market === "1x2" && entry.selection === "home"
    );
    const awayEntry = detail.odds.find(
      (entry) => entry.bookmaker === bookmaker && entry.market === "1x2" && entry.selection === "away"
    );
    const latestEntry = [homeEntry, awayEntry]
      .filter((entry) => entry !== undefined)
      .sort((left, right) => right.scraped_at.localeCompare(left.scraped_at))[0];

    return {
      bookmaker,
      homeOdds: homeEntry?.odds,
      awayOdds: awayEntry?.odds,
      url: homeEntry?.url ?? awayEntry?.url,
      scrapedAt: latestEntry?.scraped_at ?? "",
      hasOdds: homeEntry !== undefined || awayEntry !== undefined,
    };
  });

  return { detail, companyRows };
}

export default async function TestPage() {
  const data = await loadTestMatch();

  if (!data) {
    return (
      <div className="space-y-6">
        <section className="rounded-[2rem] border border-slate-200 bg-white px-6 py-8 shadow-[0_24px_70px_-44px_rgba(15,23,42,0.45)] sm:px-8">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
            Test Page
          </p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">
            Real Madrid vs Bayern Munich
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
            The requested UCL match is not available in the current local scrape yet.
          </p>
        </section>
      </div>
    );
  }

  const { detail, companyRows } = data;
  const activeRows = companyRows.filter((row) => row.hasOdds);
  const inactiveRows = companyRows.filter((row) => !row.hasOdds);

  return (
    <div className="space-y-8">
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(245,166,35,0.18),_transparent_30%),linear-gradient(180deg,_#ffffff,_#fffaf1)] px-6 py-8 shadow-[0_24px_70px_-44px_rgba(15,23,42,0.45)] sm:px-8">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-600">
          Test Page
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">
          Real Madrid vs Bayern Munich
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          Live scraped UCL snapshot with only two outcomes per bookmaker: the Bayern Munich win and
          the Real Madrid win prices from the `1x2` market.
        </p>
        <div className="mt-6 flex flex-wrap items-center gap-3 text-sm text-slate-600">
          <span className="rounded-full bg-white/90 px-3 py-1.5 shadow-sm">
            Stored fixture: {detail.home_team} vs {detail.away_team}
          </span>
          <span className="rounded-full bg-white/90 px-3 py-1.5 shadow-sm">
            Kickoff: {formatFullDate(detail.start_time)}
          </span>
          <span className="rounded-full bg-white/90 px-3 py-1.5 shadow-sm">
            Live on this match: {activeRows.length}/{companyRows.length} bookmakers
          </span>
          <Link
            href={`/match/${detail.id}?market=1x2`}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-950"
          >
            Open full match page
          </Link>
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              Active bookmakers
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
              Real prices for this fixture
            </h2>
          </div>
          <p className="text-sm text-slate-500">
            Showing every scraped bookmaker that currently has `1x2` odds for this match.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {activeRows.map((row) => {
            const bookmaker = getBookmakerDisplay(row.bookmaker);

            return (
              <article
                key={row.bookmaker}
                className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-[0_18px_45px_-32px_rgba(15,23,42,0.45)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                      Bookmaker
                    </p>
                    <h2 className="mt-2 text-2xl font-semibold" style={{ color: bookmaker.color }}>
                      {bookmaker.displayName}
                    </h2>
                  </div>
                  <span
                    className="rounded-full px-3 py-1 text-xs font-semibold"
                    style={{ backgroundColor: bookmaker.bgColor, color: bookmaker.color }}
                  >
                    2 outcomes
                  </span>
                </div>

                <div className="mt-5 grid gap-3">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                      {detail.home_team}
                    </p>
                    <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
                      {row.homeOdds !== undefined ? formatOdds(row.homeOdds) : "-"}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                      {detail.away_team}
                    </p>
                    <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
                      {row.awayOdds !== undefined ? formatOdds(row.awayOdds) : "-"}
                    </p>
                  </div>
                </div>

                <div className="mt-5 flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-500">
                    {row.scrapedAt ? `Updated ${formatFullDate(row.scrapedAt)}` : "Latest snapshot"}
                  </p>
                  {row.url ? (
                    <a
                      href={row.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-slate-700 transition hover:text-slate-950"
                    >
                      Visit bookmaker
                    </a>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
            Scraper coverage
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
            Tracked bookmakers not on this fixture yet
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            These sources are part of the scraping stack too, but this Madrid match does not have
            a stored `1x2` snapshot from them right now.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {inactiveRows.map((row) => {
          const bookmaker = getBookmakerDisplay(row.bookmaker);

          return (
            <article
              key={row.bookmaker}
              className="rounded-[1.75rem] border border-dashed border-slate-300 bg-slate-50/80 p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    Bookmaker
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold" style={{ color: bookmaker.color }}>
                    {bookmaker.displayName}
                  </h2>
                </div>
                <span
                  className="rounded-full px-3 py-1 text-xs font-semibold"
                  style={{ backgroundColor: bookmaker.bgColor, color: bookmaker.color }}
                >
                  Waiting for odds
                </span>
              </div>

              <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-sm leading-6 text-slate-600">
                  No `1x2` price is stored for this exact match yet. As soon as the scraper saves
                  one, it will appear here next to the active bookmakers.
                </p>
              </div>
            </article>
          );
          })}
        </div>
      </section>
    </div>
  );
}
