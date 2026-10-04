import json
from typing import Generator, Callable, Any


class ParseError(Exception):
    """Custom exception for parsing errors."""

    def __init__(self, cause: str) -> None:
        """Initialize ParseError with a cause message."""
        super().__init__(f"ERROR: {cause}")
        self.cause: str = cause



class Parser:
    """Parser and validator for pac-man configuration file."""

    def __init__(self) -> None:
        """Initialize parser state and expected keys with their types."""
        self.REQUIRED_KEYS: dict[str, type] = {
            "highscore_filename": str,
            "lives": int,
            "pacgum": int,
            "points_per_pacgum": int,
            "points_per_super_pacgum": int,
            "points_per_ghost": int,
            "seed": int,
            "level_max_time": int,
            "ghost_edible_duration": int,
            "ghost_respawn_delay": int,
            "levels": list,
        }
        self.INT_RULES: dict[str, tuple[int, int, int]] = {
            # key:                     (default, min, max)
            "lives":                   (3, 1, 99),
            "pacgum":                  (42, 1, 10_000),
            "points_per_pacgum":       (10, 0, 1_000_000),
            "points_per_super_pacgum": (50, 0, 1_000_000),
            "points_per_ghost":        (200, 0, 1_000_000),
            "seed":                    (42, 0, 2**31 - 1),
            "level_max_time":          (90, 1, 3600),
            "ghost_edible_duration":   (8, 1, 60),
            "ghost_respawn_delay":     (5, 1, 60),
        }

    @staticmethod
    def _strip_comments(text: str) -> str:
        lines: list[str] = []
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            elif "#" in stripped:
                lines.append(stripped.split("#", 1)[0])
            else:
                lines.append(line)
        return "\n".join(lines)
    
    def _load_json(self, path: str) -> dict[str, Any]:
        """Load a JSON file with comments and return its top-level dict.

        Args:
            path: Path to the configuration file.

        Returns:
            The parsed configuration as a dictionary.

        Raises:
            ParseError: On any file, decoding, or JSON structure error.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw: str = f.read()
        except FileNotFoundError:
            raise ParseError(f"File not found: {path}") from None
        except IsADirectoryError:
            raise ParseError(f"'{path}' is a directory, not a file") from None
        except PermissionError:
            raise ParseError(f"Permission denied: {path}") from None
        except UnicodeDecodeError:
            raise ParseError(
                f"Could not decode '{path}' as UTF-8 text"
            ) from None
        except OSError as e:
            raise ParseError(f"Could not read {path}: {e}") from None

        clean: str = self._strip_comments(raw)

        if not clean.strip():
            raise ParseError(f"Config file is empty: {path}")

        try:
            data: Any = json.loads(clean)
        except json.JSONDecodeError as e:
            raise ParseError(
                f"Invalid JSON in {path} (line {e.lineno}, "
                f"column {e.colno}): {e.msg}"
            ) from None
        except RecursionError:
            raise ParseError(f"JSON in {path} is nested too deeply") from None

        # if not isinstance(self, data, dict):
        #     raise ParseError(
        #         f"Config top level must be a JSON object, "
        #         f"got {type(data).__name__}"
        #     )
        return data   
    def _check_int(self, key: str, value: Any) -> int:
        """Return value if it is a valid int for key, else the default."""
        default, low, high = self.INT_RULES[key]

        # type() instead of isinstance(): isinstance(True, int) is True
        if type(value) is not int:
            print(
                f"[config] '{key}': expected an integer, "
                f"got {value!r}. Using default {default}"
            )
            return default
        if value < low or value > high:
            print(
                f"[config] '{key}': {value} is out of range "
                f"[{low}, {high}]. Using default {default}"
            )
            return default
        return value
    def _parsing_dict(self, data_dict: dict[str, Any]) -> dict[str, Any]:
        """Build a new dict with validated values (integer keys for now)."""
        clean: dict[str, Any] = {}
        for key, (default, _, _) in self.INT_RULES.items():
            if key not in data_dict:
                print(f"[config] missing key '{key}'. Using default {default}")
                clean[key] = default
            else:
                clean[key] = self._check_int(key, data_dict[key])

        # Later stages (skipped for now)
        # clean["highscore_filename"] = self._check_filename(data_dict)
        # clean["levels"] = self._check_levels(data_dict)

        return clean

                    
