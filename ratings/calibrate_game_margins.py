def extract_side(game, side):
    """Extract nested home/away record."""

    value = game.get(side)

    if isinstance(value, dict):
        return value

    return {}


def extract_home_team(game):
    """Extract home team."""

    home = extract_side(
        game,
        "home"
    )

    return home.get(
        "team"
    )


def extract_away_team(game):
    """Extract away team."""

    away = extract_side(
        game,
        "away"
    )

    return away.get(
        "team"
    )


def extract_home_points(game):
    """Extract home score."""

    home = extract_side(
        game,
        "home"
    )

    return safe_float(
        home.get(
            "points"
        )
    )


def extract_away_points(game):
    """Extract away score."""

    away = extract_side(
        game,
        "away"
    )

    return safe_float(
        away.get(
            "points"
        )
    )


def extract_neutral_site(game):
    """Extract neutral-site flag."""

    return bool(
        game.get(
            "neutral_site",
            False,
        )
    )


def extract_home_classification(game):
    """Extract home classification."""

    home = extract_side(
        game,
        "home"
    )

    value = home.get(
        "classification"
    )

    if value is None:
        return None

    return str(
        value
    ).strip().lower()


def extract_away_classification(game):
    """Extract away classification."""

    away = extract_side(
        game,
        "away"
    )

    value = away.get(
        "classification"
    )

    if value is None:
        return None

    return str(
        value
    ).strip().lower()
