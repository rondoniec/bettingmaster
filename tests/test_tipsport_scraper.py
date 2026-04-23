from bettingmaster.scrapers.tipsport import _detect_access_issue


def test_detect_access_issue_flags_cloudflare_challenge():
    assert (
        _detect_access_issue(
            403,
            {"cf-mitigated": "challenge"},
            "<title>Ověření</title>",
        )
        == "Cloudflare challenge"
    )


def test_detect_access_issue_flags_missing_session():
    assert (
        _detect_access_issue(
            401,
            {},
            '{"errorCode":"SESSION_DOES_NOT_EXIST"}',
        )
        == "session bootstrap failed"
    )


def test_detect_access_issue_flags_blocked_error_page():
    assert (
        _detect_access_issue(
            403,
            {},
            "<title>Chyba</title>",
        )
        == "request blocked"
    )
