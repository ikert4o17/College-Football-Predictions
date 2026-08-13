import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

GAMES_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "historical_games_2025.json"
)


def main():
    with GAMES_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        games = json.load(file)

    print()
    print("=" * 60)
    print("HISTORICAL GAME STRUCTURE")
    print("=" * 60)
    print()

    print(f"Total games loaded: {len(games)}")
    print()

    for game in games:
        if game.get("game_classification") == "fbs_vs_fbs":
            print("FIRST FBS VS FBS GAME:")
            print()
            print(json.dumps(
                game,
                indent=4
            ))
            print()
            print("AVAILABLE KEYS:")
            print()
            print(list(game.keys()))
            print()
            break

    print("=" * 60)


if __name__ == "__main__":
    main()
