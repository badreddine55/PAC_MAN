#!/usr/bin/env python3
"""Test runner for the Pac-Man config parser.

Usage (run it from the folder that contains your parser file):
    python3 test_parser.py [module_name] [-v]

module_name: your parser file without ".py" (it must contain Parser and
             ParseError). Default: "parsing".
-v:          also print the passing cases.

Every case writes a temporary config file, then runs
Parser()._load_json() followed by Parser()._parsing_dict() and checks:
  - the printed messages (and how many lines were printed),
  - the returned dict,
  - that nothing crashed (a crash here = a traceback in the game).

If a pac-man.py exists in the same folder, a few command-line cases are
also run to make sure no traceback ever reaches the user.
"""

import argparse
import contextlib
import importlib
import io
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable

ap = argparse.ArgumentParser()
ap.add_argument("module", nargs="?", default="parsing")
ap.add_argument("-v", "--verbose", action="store_true")
ARGS = ap.parse_args()

ORIGINAL_DIR = os.getcwd()
sys.path.insert(0, ORIGINAL_DIR)
try:
    MOD = importlib.import_module(ARGS.module)
    Parser = MOD.Parser
    ParseError = MOD.ParseError
except (ImportError, AttributeError) as exc:
    print(f"Cannot import Parser/ParseError from '{ARGS.module}': {exc}")
    sys.exit(2)

P = Parser()
INT_RULES: dict[str, tuple[int, int, int]] = P.INT_RULES
DEFAULT_FILE: str = P.DEFAULT_HIGHSCORE_FILE
MIN_SIZE: int = P.MIN_SIZE
MAX_SIZE: int = P.MAX_SIZE
MIN_LEVELS: int = P.MIN_LEVELS
MAX_LEVELS: int = P.MAX_LEVELS

TMP = tempfile.mkdtemp(prefix="pacman_tests_")
COUNTER = itertools.count()
DELETE = object()
RAW = "@@RAW@@"


def default_level(i: int) -> dict[str, int]:
    """Expected default level for a 0-based index (growing sizes)."""
    size = min(MAX_SIZE, 15 + 2 * i)
    return {"width": size, "height": size}


DEFAULT_LEVELS = [default_level(i) for i in range(MIN_LEVELS)]

BASE: dict[str, Any] = {
    "highscore_filename": "highscores.json",
    "lives": 3,
    "pacgum": 42,
    "points_per_pacgum": 10,
    "points_per_super_pacgum": 50,
    "points_per_ghost": 200,
    "seed": 42,
    "level_max_time": 90,
    "ghost_edible_duration": 8,
    "ghost_respawn_delay": 5,
    "levels": DEFAULT_LEVELS,
}


def make(**kw: Any) -> str:
    """Valid config text with some keys overridden or deleted."""
    d = dict(BASE)
    for k, v in kw.items():
        if v is DELETE:
            d.pop(k, None)
        else:
            d[k] = v
    return json.dumps(d, indent=4)


def make_raw(key: str, literal: str) -> str:
    """Valid config where `key` is replaced by a raw JSON literal."""
    return make(**{key: RAW}).replace(f'"{RAW}"', literal)


def levels_with(index: int, entry: Any) -> list[Any]:
    """Ten default levels with one entry replaced."""
    lv: list[Any] = [dict(x) for x in DEFAULT_LEVELS]
    lv[index] = entry
    return lv


@dataclass
class Case:
    """One test case."""

    name: str
    content: str | bytes | None = None
    path: str | None = None
    setup: Callable[[], None] | None = None
    skip_if_root: bool = False
    error: str | None = None            # expected ParseError substring
    msgs: list[str] = field(default_factory=list)
    n_lines: int | None = None          # exact number of printed lines
    expect: dict[str, Any] = field(default_factory=dict)
    check: Callable[[dict[str, Any]], bool] | None = None
    desc: str = ""


# ----------------------------------------------------------------------
# Case builders
# ----------------------------------------------------------------------

def int_cases() -> list[Case]:
    cs: list[Case] = []
    bad_types = [
        ("string", '"three"'), ("numeric string", '"3"'),
        ("float", "3.5"), ("float 1e2", "1e2"), ("float 3.0", "3.0"),
        ("true", "true"), ("false", "false"), ("null", "null"),
        ("list", "[3]"), ("object", "{}"), ("empty string", '""'),
    ]
    for key, (default, lo, hi) in INT_RULES.items():
        cs.append(Case(
            f"int:{key} missing", make(**{key: DELETE}),
            msgs=[f"missing key '{key}'"], n_lines=1,
            expect={key: default}))
        for label, lit in bad_types:
            cs.append(Case(
                f"int:{key} {label}", make_raw(key, lit),
                msgs=[f"'{key}'", "expected an integer"], n_lines=1,
                expect={key: default}))
        for label, v in [("below min", lo - 1), ("above max", hi + 1),
                         ("huge", 99999999999999999999)]:
            cs.append(Case(
                f"int:{key} {label} ({v})", make(**{key: v}),
                msgs=[f"'{key}'", "out of range"], n_lines=1,
                expect={key: default}))
        for label, v in [("min", lo), ("max", hi)]:
            cs.append(Case(
                f"int:{key} boundary {label} ({v})", make(**{key: v}),
                n_lines=0, expect={key: v}))
    return cs


def filename_cases() -> list[Case]:
    cs: list[Case] = []
    key = "highscore_filename"

    def bad(label: str, value: Any, part: str, group: str = "fn") -> None:
        cs.append(Case(
            f"{group}:{label}", make(**{key: value}),
            msgs=[f"'{key}'", part], n_lines=1,
            expect={key: DEFAULT_FILE}))

    def good(label: str, value: Any, final: str) -> None:
        cs.append(Case(
            f"fn:accepted {label}", make(**{key: value}),
            n_lines=0, expect={key: final}))

    cs.append(Case(
        "fn:key missing", make(**{key: DELETE}),
        msgs=[f"missing key '{key}'"], n_lines=1,
        expect={key: DEFAULT_FILE}))

    for label, v in [("int", 123), ("float", 1.5), ("zero", 0),
                     ("true", True), ("false", False), ("null", None),
                     ("list", ["a.json"]), ("object", {})]:
        bad(f"wrong type {label}", v, "expected a string")

    for label, v in [("empty", ""), ("spaces", "   "),
                     ("tab+newline", "\t\n")]:
        bad(label, v, "name is empty")

    bad("256 chars", "a" * 251 + ".json", "longer than 255")
    good("255 chars", "a" * 250 + ".json", "a" * 250 + ".json")

    for label, v in [("null byte", "scores\u0000.json"),
                     ("inner tab", "sc\tores.json"),
                     ("inner newline", "sc\nores.json"),
                     ("DEL char", "scores\u007f.json")]:
        bad(label, v, "control characters")

    # --- path policy (delete these if you chose another policy) ---
    for v in ["/etc/scores.json", "/scores.json", "/tmp/a.json"]:
        bad(f"absolute {v}", v, "absolute paths", "fn-policy")
    for v in ["../scores.json", "data/../../x.json", "data/../scores.json"]:
        bad(f"dotdot {v}", v, "'..' is not allowed", "fn-policy")

    for v in ["scores.txt", "scores", "data/", ".json",
              "scores.json.bak", "scores.jsonl"]:
        bad(f"extension {v!r}", v, "must end with '.json'")

    def mk_dir() -> None:
        os.makedirs("dir_named.json", exist_ok=True)

    cs.append(Case(
        "fn:existing directory", make(**{key: "dir_named.json"}),
        setup=mk_dir, msgs=[f"'{key}'", "is a directory"], n_lines=1,
        expect={key: DEFAULT_FILE}))

    good("plain", "highscores.json", "highscores.json")
    good("subfolder", "data/highscores.json", "data/highscores.json")
    good("uppercase ext", "scores.JSON", "scores.JSON")
    good("spaces stripped", "  scores.json  ", "scores.json")
    good("tab/newline stripped", "\tscores.json\n", "scores.json")
    good("./ prefix", "./scores.json", "./scores.json")
    good("space inside", "my scores.json", "my scores.json")
    good("unicode", "scores_\u00e9.json", "scores_\u00e9.json")
    good("hidden file", ".scores.json", ".scores.json")
    good("folder not created yet", "not_created_yet/scores.json",
         "not_created_yet/scores.json")
    good("hash inside name", "a#b.json", "a#b.json")
    return cs


def levels_cases() -> list[Case]:
    cs: list[Case] = []
    rng = f"[{MIN_SIZE}, {MAX_SIZE}]"

    cs.append(Case(
        "levels:key missing", make(levels=DELETE),
        msgs=["missing key 'levels'"], n_lines=1,
        expect={"levels": DEFAULT_LEVELS}))

    for label, v, tname in [("string", "none", "str"), ("int", 5, "int"),
                            ("null", None, "NoneType"),
                            ("object", {}, "dict")]:
        cs.append(Case(
            f"levels:not a list ({label})", make(levels=v),
            msgs=["'levels'", "expected a list", tname], n_lines=1,
            expect={"levels": DEFAULT_LEVELS}))

    cs.append(Case(
        "levels:empty list", make(levels=[]),
        msgs=["'levels'", "list is empty"], n_lines=1,
        expect={"levels": DEFAULT_LEVELS}))

    three = [{"width": 21, "height": 19}, {"width": 23, "height": 21},
             {"width": 25, "height": 25}]
    cs.append(Case(
        "levels:3 valid -> padded to 10", make(levels=three),
        msgs=["only 3 levels given"], n_lines=1,
        expect={"levels": three + DEFAULT_LEVELS[3:]}))

    ten = [{"width": 21 + i, "height": 20 + i} for i in range(10)]
    cs.append(Case(
        "levels:10 custom valid", make(levels=ten), n_lines=0,
        expect={"levels": ten}))

    fifty = [{"width": 21, "height": 21} for _ in range(MAX_LEVELS)]
    cs.append(Case(
        f"levels:exactly {MAX_LEVELS}", make(levels=fifty), n_lines=0,
        expect={"levels": fifty}))
    for n in (MAX_LEVELS + 1, MAX_LEVELS + 10):
        many = [{"width": 21, "height": 21} for _ in range(n)]
        cs.append(Case(
            f"levels:{n} -> truncated", make(levels=many),
            msgs=[f"keeping the first {MAX_LEVELS}"], n_lines=1,
            expect={"levels": many[:MAX_LEVELS]}))

    for idx in (0, 6):
        d = default_level(idx)
        for label, v in [("number", 5), ("null", None), ("string", "x"),
                         ("list", []), ("bool", True)]:
            cs.append(Case(
                f"levels:level {idx + 1} not an object ({label})",
                make(levels=levels_with(idx, v)),
                msgs=[f"level {idx + 1}", "expected an object",
                      f"Using default {d['width']}x{d['height']}"],
                n_lines=1, expect={"levels": DEFAULT_LEVELS}))

    d2 = default_level(2)
    cs.append(Case(
        "levels:level 3 missing width",
        make(levels=levels_with(2, {"height": 15})),
        msgs=["level 3", "missing 'width'"], n_lines=1,
        expect={"levels": levels_with(
            2, {"width": d2["width"], "height": 15})}))
    cs.append(Case(
        "levels:level 3 missing height",
        make(levels=levels_with(2, {"width": 15})),
        msgs=["level 3", "missing 'height'"], n_lines=1,
        expect={"levels": levels_with(
            2, {"width": 15, "height": d2["height"]})}))
    cs.append(Case(
        "levels:level 3 empty object",
        make(levels=levels_with(2, {})),
        msgs=["level 3", "missing 'width'", "missing 'height'"],
        n_lines=2, expect={"levels": DEFAULT_LEVELS}))

    d1 = default_level(1)
    for label, v in [("numeric string", "15"), ("float", 15.5),
                     ("true", True), ("null", None), ("list", [15])]:
        cs.append(Case(
            f"levels:level 2 width wrong type ({label})",
            make(levels=levels_with(1, {"width": v, "height": 17})),
            msgs=["level 2", "'width' expected an integer"], n_lines=1,
            expect={"levels": DEFAULT_LEVELS}))
        cs.append(Case(
            f"levels:level 2 height wrong type ({label})",
            make(levels=levels_with(1, {"width": 17, "height": v})),
            msgs=["level 2", "'height' expected an integer"], n_lines=1,
            expect={"levels": DEFAULT_LEVELS}))

    for label, v in [("below min", MIN_SIZE - 1), ("above max", MAX_SIZE + 1),
                     ("negative", -5), ("zero", 0), ("huge", 100000)]:
        cs.append(Case(
            f"levels:level 2 width out of range ({label} {v})",
            make(levels=levels_with(1, {"width": v, "height": 17})),
            msgs=["level 2", "'width'", "out of range", rng], n_lines=1,
            expect={"levels": levels_with(
                1, {"width": d1["width"], "height": 17})}))

    cs.append(Case(
        "levels:boundaries min/max accepted",
        make(levels=levels_with(
            0, {"width": MIN_SIZE, "height": MAX_SIZE})),
        n_lines=0,
        expect={"levels": levels_with(
            0, {"width": MIN_SIZE, "height": MAX_SIZE})}))
    cs.append(Case(
        "levels:both width and height bad",
        make(levels=levels_with(0, {"width": 100000, "height": 2})),
        msgs=["level 1", "'width'", "'height'", "out of range"],
        n_lines=2, expect={"levels": DEFAULT_LEVELS}))
    cs.append(Case(
        "levels:extra key inside a level ignored",
        make(levels=levels_with(
            0, {"width": 15, "height": 15, "banana": 1})),
        n_lines=0, expect={"levels": DEFAULT_LEVELS}))

    mixed_in = [{"width": 21, "height": 17},
                {"width": "x", "height": 19},
                {"width": 25, "height": 25}] + DEFAULT_LEVELS[3:]
    mixed_out = [{"width": 21, "height": 17},
                 {"width": d1["width"], "height": 19},
                 {"width": 25, "height": 25}] + DEFAULT_LEVELS[3:]
    cs.append(Case(
        "levels:mixed good/bad/good (only the bad one is fixed)",
        make(levels=mixed_in), msgs=["level 2", "'width'"], n_lines=1,
        expect={"levels": mixed_out}))
    return cs


def file_cases() -> list[Case]:
    cs: list[Case] = []

    cs.append(Case("file:missing file", path="does_not_exist.json",
                   error="not found"))

    def mk_dir() -> None:
        os.makedirs("some_dir", exist_ok=True)

    cs.append(Case("file:path is a directory", path="some_dir",
                   setup=mk_dir, error="directory"))
    cs.append(Case("file:empty file", content="", error="empty"))
    cs.append(Case("file:only whitespace", content="  \n\t\n",
                   error="empty"))
    cs.append(Case("file:only comments", content="# a\n# b\n   # c\n",
                   error="empty"))
    cs.append(Case("file:binary / not UTF-8",
                   content=b"\xff\xfe\x00\x80\x81", error="decode"))

    def mk_unreadable() -> None:
        with open("unreadable.json", "w", encoding="utf-8") as f:
            f.write("{}")
        os.chmod("unreadable.json", 0)

    cs.append(Case("file:permission denied", path="unreadable.json",
                   setup=mk_unreadable, skip_if_root=True,
                   error="permission"))
    return cs


def json_cases() -> list[Case]:
    cs: list[Case] = []
    syntax = [
        ("trailing comma", '{ "lives": 3, }'),
        ("missing comma", '{"lives": 3 "seed": 4}'),
        ("single quotes", "{'lives': 3}"),
        ("unquoted key", "{lives: 3}"),
        ("unclosed object", '{"lives": 3'),
        ("unterminated string", '{"lives": "abc}'),
        ("python True", '{"lives": True}'),
        ("python None", '{"lives": None}'),
        ("value without key", '{3}'),
        ("garbage", "hello world"),
    ]
    for label, text in syntax:
        cs.append(Case(f"json:{label}", content=text,
                       error="Invalid JSON"))
    for label, lit in [("leading zeros 007", "007"), ("plus sign +3", "+3"),
                       ("hex 0x10", "0x10")]:
        cs.append(Case(f"json:{label}", content=make_raw("lives", lit),
                       error="Invalid JSON"))

    cs.append(Case("json:deeply nested", content="[" * 100000,
                   error="deeply"))

    for label, text in [("list", "[1, 2, 3]"), ("number", "42"),
                        ("null", "null"), ("string", '"text"'),
                        ("true", "true")]:
        cs.append(Case(f"top:top level is {label}", content=text,
                       error="JSON object"))

    for lit in ("NaN", "Infinity", "-Infinity"):
        cs.append(Case(
            f"json:{lit} as a value", content=make_raw("lives", lit),
            msgs=["'lives'", "expected an integer"], n_lines=1,
            expect={"lives": 3}))
    return cs


def comment_cases() -> list[Case]:
    cs: list[Case] = []
    cs.append(Case(
        "comment:full-line # at start and end",
        content="# hi\n" + make() + "\n# bye\n",
        n_lines=0, expect={"lives": 3}))
    cs.append(Case(
        "comment:indented #",
        content=make().replace("{", "{\n        # indented", 1),
        n_lines=0, expect={"lives": 3}))
    cs.append(Case(
        "comment:CRLF line endings",
        content=("# c\r\n" + make()).replace("\n", "\r\n"),
        n_lines=0, expect={"lives": 3}))
    cs.append(Case(
        "comment:# inside a string value is data",
        content=make(highscore_filename="a#b.json"), n_lines=0,
        expect={"highscore_filename": "a#b.json"}))
    cs.append(Case(
        "comment:JSON error keeps the real line number",
        content='# c1\n# c2\n# c3\n{\n    "lives": oops\n}\n',
        error="line 5"))
    return cs


def misc_cases() -> list[Case]:
    cs: list[Case] = []
    cs.append(Case("misc:valid baseline", make(), n_lines=0,
                   expect=dict(BASE)))
    cs.append(Case(
        "misc:all keys missing ({})", "{}", n_lines=len(INT_RULES) + 2,
        msgs=["missing key 'levels'", "missing key 'highscore_filename'"],
        expect={"lives": 3, "levels": DEFAULT_LEVELS,
                "highscore_filename": DEFAULT_FILE}))
    cs.append(Case(
        "misc:several errors reported together",
        make(lives="x", points_per_pacgum=-10, seed=None,
             level_max_time=99999),
        msgs=["'lives'", "'points_per_pacgum'", "'seed'",
              "'level_max_time'"],
        n_lines=4,
        expect={"lives": 3, "points_per_pacgum": 10, "seed": 42,
                "level_max_time": 90}))
    cs.append(Case(
        "misc:unknown keys ignored",
        make(banana=5, foo=[1, {"a": None}]), n_lines=0,
        check=lambda r: "banana" not in r and "foo" not in r,
        desc="unknown keys must not appear in the result"))
    dup = make().replace('"lives": 3,', '"lives": 3,\n    "lives": 5,')
    cs.append(Case("misc:duplicate key (last one wins)", dup, n_lines=0,
                   expect={"lives": 5}))
    return cs


def build_cases() -> list[Case]:
    return (file_cases() + json_cases() + comment_cases() + misc_cases()
            + int_cases() + filename_cases() + levels_cases())


# ----------------------------------------------------------------------
# Running and checking
# ----------------------------------------------------------------------

def invariants(result: dict[str, Any] | None) -> list[str]:
    """What the rest of the game relies on: a result is always valid."""
    if result is None:
        return ["no result returned"]
    probs: list[str] = []
    for key, (_, lo, hi) in INT_RULES.items():
        v = result.get(key)
        if type(v) is not int or not (lo <= v <= hi):
            probs.append(f"invariant: {key}={v!r} is not a valid int")
    fn = result.get("highscore_filename")
    if not isinstance(fn, str) or not fn.lower().endswith(".json"):
        probs.append(f"invariant: highscore_filename={fn!r} invalid")
    lv = result.get("levels")
    if not isinstance(lv, list) or len(lv) < MIN_LEVELS:
        probs.append("invariant: levels must be a list of >= "
                     f"{MIN_LEVELS} entries")
    else:
        for i, e in enumerate(lv, start=1):
            ok = isinstance(e, dict) and all(
                type(e.get(k)) is int and MIN_SIZE <= e[k] <= MAX_SIZE
                for k in ("width", "height"))
            if not ok:
                probs.append(f"invariant: level {i} invalid: {e!r}")
                break
    return probs


def short(v: Any) -> str:
    s = repr(v)
    return s if len(s) < 160 else s[:157] + "..."


def execute(case: Case) -> tuple[str, Any, str | None, str | None]:
    path = case.path or os.path.join(TMP, f"case_{next(COUNTER)}.json")
    if case.setup:
        case.setup()
    if case.content is not None:
        if isinstance(case.content, bytes):
            with open(path, "wb") as fb:
                fb.write(case.content)
        else:
            with open(path, "w", encoding="utf-8", newline="") as ft:
                ft.write(case.content)
    buf = io.StringIO()
    result: Any = None
    error: str | None = None
    crash: str | None = None
    try:
        with contextlib.redirect_stdout(buf):
            parser = Parser()
            data = parser._load_json(path)
            result = parser._parsing_dict(data)
    except ParseError as exc:
        error = str(exc)
    except Exception as exc:  # anything else = a traceback in the game
        crash = f"{type(exc).__name__}: {exc}"
    return buf.getvalue(), result, error, crash


def evaluate(case: Case, out: str, result: Any, error: str | None,
             crash: str | None) -> list[str]:
    if crash:
        return [f"CRASH (would be a traceback): {crash}"]
    probs: list[str] = []
    lines = [ln for ln in out.splitlines() if ln.strip()]

    if case.error is not None:
        if error is None:
            probs.append(f"expected a ParseError containing "
                         f"{case.error!r}, but parsing succeeded")
            if lines:
                probs.append(f"printed: {short(lines)}")
        elif case.error.lower() not in error.lower():
            probs.append(f"error {error!r} does not contain "
                         f"{case.error!r}")
        return probs
    if error is not None:
        return [f"unexpected ParseError: {error}"]

    for m in case.msgs:
        if m not in out:
            probs.append(f"message part not found: {m!r}")
    if case.n_lines is not None and len(lines) != case.n_lines:
        probs.append(f"expected {case.n_lines} printed line(s), "
                     f"got {len(lines)}: {short(lines)}")
    for k, v in case.expect.items():
        got = result.get(k) if isinstance(result, dict) else None
        if got != v:
            probs.append(f"result[{k!r}] = {short(got)}, "
                         f"expected {short(v)}")
    if case.check is not None:
        try:
            if not case.check(result):
                probs.append(f"result check failed: {case.desc}")
        except Exception as exc:
            probs.append(f"result check raised {type(exc).__name__}")
    probs += invariants(result)
    return probs


def run_case(case: Case) -> tuple[str, list[str]]:
    if case.skip_if_root:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            return "SKIP", ["running as root, permissions not enforced"]
    out, result, error, crash = execute(case)
    return ("PASS", []) if not (probs := evaluate(
        case, out, result, error, crash)) else ("FAIL", probs)


# ----------------------------------------------------------------------
# Command-line cases (only if pac-man.py is next to this script)
# ----------------------------------------------------------------------

def run_cli_cases() -> list[tuple[str, str, str, list[str]]]:
    script = os.path.join(ORIGINAL_DIR, "pac-man.py")
    if not os.path.exists(script):
        return []
    for name, text in [("empty.json", ""), ("bad.json", "{ oops"),
                       ("list.json", "[1, 2, 3]")]:
        with open(name, "w", encoding="utf-8") as f:
            f.write(text)
    with open("bin.json", "wb") as fb:
        fb.write(b"\xff\xfe\x00\x80")
    os.makedirs("some_dir", exist_ok=True)

    cases: list[tuple[str, list[str]]] = [
        ("no argument", []), ("two arguments", ["a.json", "b.json"]),
        ("missing file", ["nope.json"]), ("directory", ["some_dir"]),
        ("empty file", ["empty.json"]), ("invalid json", ["bad.json"]),
        ("top level list", ["list.json"]), ("binary file", ["bin.json"]),
    ]
    rows: list[tuple[str, str, str, list[str]]] = []
    for label, args in cases:
        name = f"cli:{label}"
        try:
            proc = subprocess.run(
                [sys.executable, script, *args], cwd=TMP, timeout=10,
                capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            rows.append(("cli", name, "FAIL",
                         ["did not exit: bad input must stop cleanly "
                          "(it probably started the game)"]))
            continue
        text = proc.stdout + proc.stderr
        probs: list[str] = []
        if "Traceback" in text:
            probs.append("a Python traceback was printed")
        if not text.strip():
            probs.append("nothing printed: the user gets no message")
        rows.append(("cli", name, "FAIL" if probs else "PASS", probs))
    return rows


# ----------------------------------------------------------------------

def main() -> int:
    os.chdir(TMP)
    rows: list[tuple[str, str, str, list[str]]] = []
    try:
        for case in build_cases():
            status, probs = run_case(case)
            rows.append((case.name.split(":", 1)[0], case.name,
                         status, probs))
        rows += run_cli_cases()
    finally:
        os.chdir(ORIGINAL_DIR)
        try:
            os.chmod(os.path.join(TMP, "unreadable.json"), 0o600)
        except OSError:
            pass
        shutil.rmtree(TMP, ignore_errors=True)

    for _, name, status, probs in rows:
        if status == "FAIL" or (ARGS.verbose and status != "FAIL"):
            print(f"{status:5} {name}")
            for p in probs:
                print(f"        - {p}")

    groups: dict[str, list[int]] = {}
    for g, _, status, _ in rows:
        c = groups.setdefault(g, [0, 0, 0])
        c[{"PASS": 0, "FAIL": 1, "SKIP": 2}[status]] += 1

    print("\n=== Summary " + "=" * 40)
    print(f"{'group':12} {'pass':>5} {'fail':>5} {'skip':>5}")
    for g, (p, f, s) in groups.items():
        print(f"{g:12} {p:5} {f:5} {s:5}")
    total_f = sum(c[1] for c in groups.values())
    total_p = sum(c[0] for c in groups.values())
    print(f"{'TOTAL':12} {total_p:5} {total_f:5} "
          f"{sum(c[2] for c in groups.values()):5}")
    return 1 if total_f else 0


if __name__ == "__main__":
    sys.exit(main())