"""Entry point of the Pac-Man game."""

import sys
from typing import Any

from parsing import ParseError, Parser


class GameEngine:
    """Owns the validated configuration and runs the game."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Store the validated configuration."""
        self.config: dict[str, Any] = config

    def run(self) -> None:
        """Start the game (placeholder for now)."""
        print(self.config)


def main() -> int:
    """Check the arguments, load the config, run the game.

    Returns:
        The process exit code (0 on success, 1 on any error).
    """
    try:
        if len(sys.argv) != 2:
            print(
                "Usage: python3 pac-man.py <config.json>", file=sys.stderr
            )
            return 1

        path = sys.argv[1]
        if not path.lower().endswith(".json"):
            print(f"ERROR: '{path}' is not a .json file", file=sys.stderr)
            return 1

        config = Parser().parse(path)
        GameEngine(config).run()
    except ParseError as e:
        print(e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: unexpected failure: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())