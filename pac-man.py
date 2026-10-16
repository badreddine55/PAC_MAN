"""Entry point of the Pac-Man game."""

import sys
from typing import Any

from parsing import ParseError, Parser


class GameEngine:
    """Owns the validated configuration and runs the game."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize Pygame, the screen, and game configuration."""
        self.config: dict[str, Any] = config
        self.current_level = 0
        self.current_width = 0
        self.current_height = 0

    def load_level(self, index: int) -> None:
        """Select a level and generate its maze."""
        # print(self.config["levels"][index])
        self.width = self.config["levels"][index]["width"]
        self.width = self.config["levels"][index]["height"]
        print(self.width)

    # def generate_maze(
    #     self, width: int, height: int, seed: int
    # ) -> None:
    #     """Generate maze data using the assigned package."""
    #     ...

    # def draw_maze(self, surface: pygame.Surface) -> None:
    #     """Draw maze walls and corridors onto a Surface."""
    #     ...

    # def draw(self) -> None:
    #     """Draw the background, maze, and other objects."""
    #     ...

    # def run(self) -> None:
    #     """Execute the main game loop."""
    #     ...


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
        game = GameEngine(config)
        game.load_level(game.current_level)
        for i in range(1, len(game.config["levels"])):
            game.load_level(i)
        # print(game.config)
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