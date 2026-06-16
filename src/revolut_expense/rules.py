"""YAML rules loader: parse, validate, and compile Rule objects from a rules file."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from revolut_expense.errors import RulesConfigError
from revolut_expense.schema import Category

# ---------------------------------------------------------------------------
# Matcher dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExactMatch:
    """Matcher that compares the normalised transaction description by exact equality."""

    value: str  # normalised at load time


@dataclass(frozen=True)
class RegexMatch:
    """Matcher that applies a compiled regex pattern against the normalised description."""

    pattern: re.Pattern[str]  # compiled at load time
    source: str  # original pattern string, used for dedup checks


# ---------------------------------------------------------------------------
# Rule dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """A single validated classification rule loaded from the YAML rules file."""

    matcher: ExactMatch | RegexMatch
    direction: Literal["in", "out"] | None
    category: Category
    line_number: int  # 1-based, for error messages


# ---------------------------------------------------------------------------
# Description normalisation
# ---------------------------------------------------------------------------

_HYPHEN_VARIANT_RE: re.Pattern[str] = re.compile(r"[\u2010-\u2014]")


def _normalise(text: str) -> str:
    """Normalise a description string for exact-match comparison."""
    normalised = text.strip()
    normalised = re.sub(r"\s+", " ", normalised)
    normalised = _HYPHEN_VARIANT_RE.sub("-", normalised)
    return normalised


# ---------------------------------------------------------------------------
# YAML line-number helpers
# ---------------------------------------------------------------------------


def _get_rules_sequence_node(text: str) -> yaml.SequenceNode | None:
    document = yaml.compose(text)
    if not isinstance(document, yaml.MappingNode):
        return None
    for key_node, value_node in document.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == "rules":
            if isinstance(value_node, yaml.SequenceNode):
                return value_node
            return None
    return None


def _rule_line_numbers(text: str) -> list[int]:
    try:
        seq_node = _get_rules_sequence_node(text)
    except yaml.YAMLError:
        return []
    if seq_node is None:
        return []
    return [item.start_mark.line + 1 for item in seq_node.value]


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_rules(path: Path) -> list[Rule]:
    """Load, validate, and compile rules from a YAML file at *path*.

    Returns an ordered list of Rule objects in YAML file order.

    Raises:
        RulesConfigError: on any validation or parse failure.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise RulesConfigError(f"Rules file not found: {path}")

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        line: int | None = None
        if hasattr(exc, "problem_mark") and exc.problem_mark is not None:
            line = exc.problem_mark.line + 1
        raise RulesConfigError(f"YAML parse error: {exc}", line_number=line)

    if not isinstance(data, dict) or "rules" not in data or not isinstance(data["rules"], list):
        raise RulesConfigError("Rules file must have a top-level 'rules' list")

    entries: list[object] = data["rules"]
    line_numbers = _rule_line_numbers(text)

    # Duplicate detection: (direction, matcher_key) -> [line_numbers]
    seen: dict[tuple[str | None, tuple[str, str]], list[int]] = {}
    rules: list[Rule] = []

    for idx, entry in enumerate(entries):
        line_number = line_numbers[idx] if idx < len(line_numbers) else idx + 1

        if not isinstance(entry, dict):
            raise RulesConfigError(
                f"Rule entry {idx + 1} must be a mapping", line_number=line_number
            )

        # Reject type field — Revolut rules do not support type-code filtering
        if "type" in entry:
            raise RulesConfigError(
                f"Rule at line {line_number} contains a 'type' field. "
                "Revolut rules do not support type-code filtering; "
                "please remove the 'type' field.",
                line_number=line_number,
            )

        has_match = "match" in entry
        has_regex = "match_regex" in entry

        if has_match and has_regex:
            raise RulesConfigError(
                f"Rule at line {line_number} specifies both 'match' and 'match_regex'; "
                "only one matcher is allowed",
                line_number=line_number,
            )
        if not has_match and not has_regex:
            raise RulesConfigError(
                f"Rule at line {line_number} must specify either 'match' or 'match_regex'",
                line_number=line_number,
            )

        raw_category = entry.get("category")
        if raw_category is None:
            raise RulesConfigError(
                f"Rule at line {line_number} is missing required field 'category'",
                line_number=line_number,
            )
        try:
            category = Category(raw_category)
        except ValueError:
            raise RulesConfigError(f"Unknown category: {raw_category!r}", line_number=line_number)

        raw_direction = entry.get("direction")
        direction: Literal["in", "out"] | None = None
        if raw_direction is not None:
            if raw_direction not in ("in", "out"):
                raise RulesConfigError(
                    f"Invalid direction {raw_direction!r} at line {line_number}; "
                    "must be 'in' or 'out'",
                    line_number=line_number,
                )
            direction = raw_direction

        if has_match:
            raw_value = entry["match"]
            if not isinstance(raw_value, str) or not raw_value:
                raise RulesConfigError(
                    f"'match' at line {line_number} must be a non-empty string",
                    line_number=line_number,
                )
            normalised_value = _normalise(raw_value)
            matcher: ExactMatch | RegexMatch = ExactMatch(value=normalised_value)
            matcher_key: tuple[str, str] = ("exact", normalised_value)
        else:
            raw_pattern = entry["match_regex"]
            if not isinstance(raw_pattern, str) or not raw_pattern:
                raise RulesConfigError(
                    f"'match_regex' at line {line_number} must be a non-empty string",
                    line_number=line_number,
                )
            try:
                compiled = re.compile(raw_pattern)
            except re.error as exc:
                raise RulesConfigError(
                    f"Invalid regex {raw_pattern!r}: {exc}", line_number=line_number
                )
            matcher = RegexMatch(pattern=compiled, source=raw_pattern)
            matcher_key = ("regex", raw_pattern)

        dedup_key = (direction, matcher_key)
        seen.setdefault(dedup_key, []).append(line_number)

        rules.append(
            Rule(
                matcher=matcher,
                direction=direction,
                category=category,
                line_number=line_number,
            )
        )

    duplicate_groups = [lns for lns in seen.values() if len(lns) >= 2]
    if duplicate_groups:
        violations = [f"Lines {', '.join(str(ln) for ln in group)}" for group in duplicate_groups]
        raise RulesConfigError("Duplicate rules found", violations=violations)

    return rules
