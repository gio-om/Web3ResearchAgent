"""
Cross-check node: verifies consistency across data sources.
This is the key differentiating feature of the system.
"""
import structlog

log = structlog.get_logger()


def _make_flag(flag_type: str, category: str, message: str, source: str, severity: int = 5) -> dict:
    return {
        "type": flag_type,
        "category": category,
        "message": message,
        "source": source,
        "severity_score": severity,
    }


async def cross_check_node(state: dict) -> dict:
    """
    Cross-verifies data from aggregator, documentation, social, and team agents.
    Generates RiskFlags for inconsistencies.
    """
    project_name = state.get("project_name", "")
    log.info("cross_check.start", project=project_name)

    aggregator_data = state.get("aggregator_data", {})
    documentation_data = state.get("documentation_data", {})
    social_data = state.get("social_data", {})
    team_data = state.get("team_data", {})

    flags = []

    # --- 1. Tokenomics: aggregator vs documentation ---
    agg_vesting = (aggregator_data.get("cryptorank", {}) or {}).get("vesting", []) or []
    doc_vesting = documentation_data.get("vesting_schedules", []) or []

    if agg_vesting and doc_vesting:
        # Check total supply consistency
        agg_supply = (aggregator_data.get("cryptorank", {}) or {}).get("project", {}).get("total_supply")
        doc_supply = documentation_data.get("total_supply")
        if agg_supply and doc_supply:
            diff_pct = abs(agg_supply - doc_supply) / max(agg_supply, doc_supply) * 100
            if diff_pct > 5:
                flags.append(_make_flag(
                    "red", "tokenomics",
                    f"Total supply mismatch: aggregator {agg_supply:,.0f} vs whitepaper {doc_supply:,.0f} ({diff_pct:.1f}% diff)",
                    "Cryptorank vs Documentation",
                    severity=8,
                ))

    # Check if vesting schedules are suspiciously short
    for schedule in doc_vesting:
        cliff = schedule.get("cliff_months", 0) or 0
        vesting = schedule.get("vesting_months", 0) or 0
        category = schedule.get("category", "Unknown")
        tge = schedule.get("tge_unlock_pct", 0) or 0

        if category.lower() in ("team", "founders") and vesting < 12:
            flags.append(_make_flag(
                "red", "tokenomics",
                f"Short vesting for {category}: only {vesting} months (best practice: 24+ months)",
                "Documentation",
                severity=7,
            ))
        if tge > 20 and category.lower() in ("investors", "private"):
            flags.append(_make_flag(
                "yellow", "tokenomics",
                f"High TGE unlock for {category}: {tge}% (creates sell pressure at launch)",
                "Documentation",
                severity=5,
            ))

    # --- 2. Investors: aggregator vs social confirmation ---
    funding_rounds = (aggregator_data.get("cryptorank", {}) or {}).get("funding_rounds", []) or []
    kol_mentions = social_data.get("kol_mentions", []) or []
    kol_text = " ".join(kol_mentions).lower()

    for round_data in funding_rounds:
        investors = round_data.get("investors", []) if isinstance(round_data, dict) else []
        for investor in investors:
            investor_lower = investor.lower()
            if investor_lower not in kol_text and len(investors) > 0:
                # Investor mentioned but not confirmed via social
                pass  # This is expected — not all investors tweet about deals

    # Check for suspiciously high investor ROI (dump risk)
    # coingecko now has flat structure from CoinGeckoClient.get_market_data()
    coingecko = aggregator_data.get("coingecko", {}) or {}
    current_price = coingecko.get("current_price_usd") or 0
    if current_price and funding_rounds:
        for round_data in funding_rounds:
            if isinstance(round_data, dict) and round_data.get("token_price"):
                roi = current_price / round_data["token_price"]
                if roi > 50:
                    flags.append(_make_flag(
                        "yellow", "investors",
                        f"Investors in {round_data.get('round_type', 'early')} round have {roi:.0f}x ROI — high sell pressure risk",
                        "Cryptorank + CoinGecko",
                        severity=6,
                    ))

    # --- 3. Team: site vs verified ---
    team_members = team_data.get("members", []) or []
    team_flags = team_data.get("flags", []) or []
    for tf in team_flags:
        flags.append({
            "type": tf.get("type", "yellow"),
            "category": "team",
            "message": tf.get("message", ""),
            "source": "Team verification",
            "severity_score": 7 if tf.get("type") == "red" else 4,
        })

    # --- 4. Social quality signals ---
    followers = social_data.get("followers_count", 0) or 0
    engagement = social_data.get("engagement_rate", 0) or 0
    sentiment = social_data.get("sentiment_score", 0) or 0
    bot_signals = social_data.get("bot_activity_signals", []) or []

    if followers > 50_000 and engagement < 0.001:
        flags.append(_make_flag(
            "red", "social",
            f"Very low engagement rate ({engagement:.4f}) for {followers:,} followers — possible bot audience",
            "Twitter analysis",
            severity=7,
        ))
    if bot_signals:
        flags.append(_make_flag(
            "yellow", "social",
            f"Bot activity signals detected: {'; '.join(bot_signals[:2])}",
            "Twitter analysis",
            severity=5,
        ))
    if sentiment < -0.3:
        flags.append(_make_flag(
            "red", "social",
            f"Negative community sentiment (score: {sentiment:.2f})",
            "Twitter sentiment analysis",
            severity=6,
        ))
    elif sentiment > 0.5:
        flags.append(_make_flag(
            "green", "social",
            f"Strong positive community sentiment (score: {sentiment:.2f})",
            "Twitter sentiment analysis",
            severity=0,
        ))

    # --- 5. FDV / MCap ratio check ---
    fdv = coingecko.get("fdv_usd") or 0
    mcap = coingecko.get("market_cap_usd") or 0
    if fdv and mcap and mcap > 0:
        ratio = fdv / mcap
        if ratio > 10:
            flags.append(_make_flag(
                "red", "tokenomics",
                f"FDV/MCap ratio is {ratio:.1f}x — most tokens still locked, large inflation ahead",
                "CoinGecko",
                severity=7,
            ))
        elif ratio > 5:
            flags.append(_make_flag(
                "yellow", "tokenomics",
                f"High FDV/MCap ratio ({ratio:.1f}x) — significant token unlocks expected",
                "CoinGecko",
                severity=4,
            ))

    log.info("cross_check.done", project=project_name, flags_count=len(flags))

    return {
        **state,
        "cross_check_results": flags,
    }
