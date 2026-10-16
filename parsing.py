"""Configuration file parser and validator for the Pac-Man game."""

import json
import os
import sys
from pathlib import PurePath
from typing import Any, ClassVar


class ParseError(Exception):
    """Custom exception for fatal configuration errors."""

    def __init__(self, cause: str) -> None:
        """Initialize ParseError with a cause message."""
        super().__init__(f"ERROR: {cause}")
        self.cause: str = cause


class Parser:
    """Parser and validator for the pac-man configuration file.

    Fatal problems (missing file, invalid JSON, ...) raise ParseError.
    Bad or missing values never crash: a wrong type or a missing key is
    replaced by its default, a number out of range is clamped to the
    nearest limit. Every correction is reported on stderr.
    """

    # key: (default, min, max)
    INT_RULES: ClassVar[dict[str, tuple[int, int, int]]] = {
        "lives": (3, 1, 99),
        "pacgum": (42, 1, 10_000),
        "points_per_pacgum": (10, 0, 1_000_000),
        "points_per_super_pacgum": (50, 0, 1_000_000),
        "points_per_ghost": (200, 0, 1_000_000),
        "seed": (42, 0, 2**31 - 1),
        "level_max_time": (90, 1, 3600),
        "ghost_edible_duration": (8, 1, 60),
        "ghost_respawn_delay": (5, 1, 60),
    }
    DEFAULT_HIGHSCORE_FILE: ClassVar[str] = "highscores.json"
    MAX_FILENAME_LEN: ClassVar[int] = 255
    MIN_LEVELS: ClassVar[int] = 10
    MAX_LEVELS: ClassVar[int] = 50
    # TODO: test these limits with the assigned A-Maze-ing package
    # (PERFECT=False) and adjust them to what the generator supports.
    MIN_SIZE: ClassVar[int] = 9
    MAX_SIZE: ClassVar[int] = 50
    # Accepted names for the list of levels (first one is preferred).
    LEVELS_KEYS: ClassVar[tuple[str, ...]] = ("levels", "level")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse(self, path: str) -> dict[str, Any]:
        """Load and validate the config file.

        Args:
            path: Path to the configuration file.

        Returns:
            The validated configuration (every key present and valid).

        Raises:
            ParseError: If the file cannot be used at all.
        """
        return self._parsing_dict(self._load_json(path))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _warn(message: str) -> None:
        """Print a configuration warning on stderr."""
        print(f"[config] {message}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Reading the file
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_comments(text: str) -> str:
        """Blank out whole-line '#' comments, keeping line numbers."""
        lines: list[str] = []
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                lines.append("")
            else:
                lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        """Build a dict from JSON pairs, warning on duplicated keys."""
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                Parser._warn(f"duplicate key '{key}': last value is used")
            result[key] = value
        return result

    def _load_json(self, path: str) -> dict[str, Any]:
        """Load a JSON file with comments and return its top-level dict.

        An empty file (or one with only comments) gives an empty dict,
        so every key falls back to its default.

        Args:
            path: Path to the configuration file.

        Returns:
            The parsed configuration as a dictionary.

        Raises:
            ParseError: On any file, decoding, or JSON structure error.
        """
        try:
            # utf-8-sig: also accepts files saved with a BOM.
            with open(path, "r", encoding="utf-8-sig") as f:
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
        except (OSError, ValueError) as e:
            raise ParseError(f"Could not read {path}: {e}") from None

        clean: str = self._strip_comments(raw)

        if not clean.strip():
            self._warn(f"config file '{path}' is empty. Using all defaults")
            return {}

        try:
            data: Any = json.loads(
                clean, object_pairs_hook=self._no_duplicates
            )
        except json.JSONDecodeError as e:
            raise ParseError(
                f"Invalid JSON in {path} (line {e.lineno}, "
                f"column {e.colno}): {e.msg}"
            ) from None
        except RecursionError:
            raise ParseError(f"JSON in {path} is nested too deeply") from None
        except ValueError as e:
            # e.g. integers with more than 4300 digits (Python 3.11+).
            raise ParseError(f"Invalid value in {path}: {e}") from None

        if not isinstance(data, dict):
            raise ParseError(
                f"Config top level must be a JSON object, "
                f"got {type(data).__name__}"
            )
        return data

    # ------------------------------------------------------------------
    # Validating the values
    # ------------------------------------------------------------------

    def _check_int(self, key: str, value: Any) -> int:
        """Return value if valid for key; use the default."""
        default, low, high = self.INT_RULES[key]

        # type() instead of isinstance(): isinstance(True, int) is True
        if type(value) is not int:
            self._warn(
                f"'{key}': expected an integer, got {value!r}. "
                f"Using default {default}"
            )
            return default
        if value < low:
            self._warn(
                f"'{key}': {value} is below {low}. will use the default {default}"
            )
            return low
        if value > high:
            self._warn(
                f"'{key}': {value} is above {high}.  will use the default {default}"
            )
            return high
        return value

    def _check_filename(self, data_dict: dict[str, Any]) -> str:
        """Return a safe highscore file path, or the default if invalid.

        Only the shape of the name is checked here. The file is never
        created or opened; real I/O errors (missing folder, permissions)
        are handled by the highscore manager at load and save time.
        """
        key = "highscore_filename"
        default = self.DEFAULT_HIGHSCORE_FILE

        if key not in data_dict:
            self._warn(f"missing key '{key}'. Using default '{default}'")
            return default

        value: Any = data_dict[key]

        if not isinstance(value, str):
            self._warn(
                f"'{key}': expected a string, got {value!r}. "
                f"Using default '{default}'"
            )
            return default

        name = value.strip()

        if not name:
            self._warn(f"'{key}': name is empty. Using default '{default}'")
            return default

        if len(name) > self.MAX_FILENAME_LEN:
            self._warn(
                f"'{key}': name is longer than {self.MAX_FILENAME_LEN} "
                f"characters. Using default '{default}'"
            )
            return default

        # A null byte would make open() raise ValueError later.
        if any(ord(c) < 32 or ord(c) == 127 for c in name):
            self._warn(
                f"'{key}': name contains control characters. "
                f"Using default '{default}'"
            )
            return default

        path = PurePath(name)

        if path.is_absolute():
            self._warn(
                f"'{key}': absolute paths are not allowed ({name!r}). "
                f"Using default '{default}'"
            )
            return default

        if ".." in path.parts:
            self._warn(
                f"'{key}': '..' is not allowed in the path ({name!r}). "
                f"Using default '{default}'"
            )
            return default

        if path.suffix.lower() != ".json":
            self._warn(
                f"'{key}': file must end with '.json' ({name!r}). "
                f"Using default '{default}'"
            )
            return default

        if os.path.isdir(name):
            self._warn(
                f"'{key}': '{name}' is a directory, not a file. "
                f"Using default '{default}'"
            )
            return default

        # str(path) normalises things like a trailing slash.
        return str(path)

    def _default_level(self, index: int) -> dict[str, int]:
        """Return the default level for a 0-based index (sizes grow)."""
        size = min(self.MAX_SIZE, 15 + 2 * index)
        return {"width": size, "height": size}

    def _check_dimension(
        self, level_no: int, key: str, value: Any, default: int
    ) -> int:
        """Return a valid width/height: the value, clamped, or default."""
        if type(value) is not int:
            self._warn(
                f"level {level_no}: '{key}' expected an integer, "
                f"got {value!r}. Using default {default}"
            )
            return default
        if value < self.MIN_SIZE:
            self._warn(
                f"level {level_no}: '{key}' {value} is below "
                f"{self.MIN_SIZE}. Clamped to {self.MIN_SIZE}"
            )
            return self.MIN_SIZE
        if value > self.MAX_SIZE:
            self._warn(
                f"level {level_no}: '{key}' {value} is above "
                f"{self.MAX_SIZE}. Clamped to {self.MAX_SIZE}"
            )
            return self.MAX_SIZE
        return value

    def _check_levels(
        self, data_dict: dict[str, Any]
    ) -> list[dict[str, int]]:
        """Return a list of at least MIN_LEVELS valid levels."""
        defaults = [self._default_level(i) for i in range(self.MIN_LEVELS)]

        # Layer 1: the list itself (check the type BEFORE len / emptiness)
        present = [k for k in self.LEVELS_KEYS if k in data_dict]
        if not present:
            self._warn("missing key 'levels'. Using default levels")
            return defaults

        key_used = present[0]
        if len(present) > 1:
            self._warn(f"both {present} given: using '{key_used}'")

        raw: Any = data_dict[key_used]

        if not isinstance(raw, list):
            self._warn(
                f"'{key_used}': expected a list, got "
                f"{type(raw).__name__}. Using default levels"
            )
            return defaults

        if not raw:
            self._warn(f"'{key_used}': list is empty. Using default levels")
            return defaults

        if len(raw) > self.MAX_LEVELS:
            self._warn(
                f"'{key_used}': {len(raw)} levels given, "
                f"keeping the first {self.MAX_LEVELS}"
            )
            raw = raw[: self.MAX_LEVELS]

        # Layers 2 and 3: each entry, then each value
        levels: list[dict[str, int]] = []
        for i, entry in enumerate(raw):
            default = self._default_level(i)
            if not isinstance(entry, dict):
                self._warn(
                    f"level {i + 1}: expected an object, got {entry!r}. "
                    f"Using default {default['width']}x{default['height']}"
                )
                levels.append(default)
                continue

            level: dict[str, int] = {}
            for dim in ("width", "height"):
                if dim not in entry:
                    self._warn(
                        f"level {i + 1}: missing '{dim}'. "
                        f"Using default {default[dim]}"
                    )
                    level[dim] = default[dim]
                else:
                    level[dim] = self._check_dimension(
                        i + 1, dim, entry[dim], default[dim]
                    )
            levels.append(level)

        # Pad up to the minimum required by the subject
        if len(levels) < self.MIN_LEVELS:
            self._warn(
                f"only {len(levels)} levels given, "
                f"{self.MIN_LEVELS} required. Adding default levels"
            )
            for i in range(len(levels), self.MIN_LEVELS):
                levels.append(self._default_level(i))

        return levels

    def _parsing_dict(self, data_dict: dict[str, Any]) -> dict[str, Any]:
        """Build a new dict containing only validated values.

        Unknown keys are ignored. Missing or invalid values are replaced
        by their defaults (or clamped), with a message.
        """
        clean: dict[str, Any] = {}

        for key, (default, _, _) in self.INT_RULES.items():
            if key not in data_dict:
                self._warn(f"missing key '{key}'. Using default {default}")
                clean[key] = default
            else:
                clean[key] = self._check_int(key, data_dict[key])

        clean["highscore_filename"] = self._check_filename(data_dict)
        clean["levels"] = self._check_levels(data_dict)

        return clean
    
# One more thing I missed at the beginning:

# "Lines starting with # are comments and must be ignored. "
# "You may also support additional comment styles (e.g., C or C++). "
# "The exact structure is up to you, but document your keys in the README and provide robust defaults."