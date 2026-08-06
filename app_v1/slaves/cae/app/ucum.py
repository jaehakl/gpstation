from __future__ import annotations

import math
from typing import Any

from app.ucum_data import PREFIX_FACTORS, UNIT_CANONICAL

_ZERO_DIMENSIONS = (0, 0, 0, 0, 0, 0, 0)
_PREFIXES = tuple(sorted(PREFIX_FACTORS, key=len, reverse=True))


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.index = 0
        self.token = ""
        self.kind = "none"
        self._consume()

    def parse(self) -> tuple[float, tuple[int, ...]]:
        if not self.source:
            raise ValueError("UCUM expression is empty")
        result = self._term()
        if self.kind != "none":
            raise ValueError(f"unexpected token {self.token!r} at end of UCUM expression")
        return result

    def _consume(self) -> None:
        self.token = ""
        self.kind = "none"
        if self.index >= len(self.source):
            return

        character = self.source[self.index]
        if character in "/.()":
            self.token = character
            self.kind = {
                "/": "solidus",
                ".": "period",
                "(": "open",
                ")": "close",
            }[character]
            self.index += 1
            return
        if character == "{":
            self._annotation()
            return
        if character in "+-":
            self._signed_number()
            return
        self._general_token()

    def _annotation(self) -> None:
        start = self.index
        self.index += 1
        while self.index < len(self.source):
            character = self.source[self.index]
            if character == "}":
                self.index += 1
                self.token = self.source[start : self.index]
                self.kind = "annotation"
                return
            if ord(character) > 0x7E or ord(character) < 0x20:
                raise ValueError(f"invalid character in UCUM annotation at position {self.index}")
            self.index += 1
        raise ValueError(f"unterminated UCUM annotation at position {start}")

    def _signed_number(self) -> None:
        start = self.index
        self.index += 1
        if self.index >= len(self.source) or not self.source[self.index].isdigit():
            raise ValueError(f"UCUM sign at position {start} must be followed by a digit")
        while self.index < len(self.source) and self.source[self.index].isdigit():
            self.index += 1
        self.token = self.source[start : self.index]
        self.kind = "number"

    def _general_token(self) -> None:
        start = self.index
        has_non_digit = False
        in_bracket = False
        while self.index < len(self.source):
            character = self.source[self.index]
            if in_bracket:
                self.index += 1
                if character == "]":
                    in_bracket = False
                continue
            if character == "[":
                if self.index > start:
                    break
                in_bracket = True
                has_non_digit = True
                self.index += 1
                continue
            if character.isascii() and character.isdigit():
                if has_non_digit:
                    break
                self.index += 1
                continue
            if (
                character.isascii()
                and (
                    character.isalpha()
                    or character in {"%", "*", "^", "'", '"', "_"}
                )
            ):
                has_non_digit = True
                self.index += 1
                continue
            break

        if in_bracket:
            raise ValueError(f"unterminated UCUM bracket at position {start}")
        if self.index == start:
            raise ValueError(f"unexpected UCUM character {self.source[self.index]!r} at position {self.index}")
        self.token = self.source[start : self.index]
        self.kind = "symbol" if has_non_digit else "number"

    def _term(self) -> tuple[float, tuple[int, ...]]:
        if self.kind == "solidus":
            self._consume()
            result = self._combine((1.0, _ZERO_DIMENSIONS), self._component_or_annotation(), -1)
        else:
            result = self._component_or_annotation()

        while self.kind in {"solidus", "period"}:
            sign = -1 if self.kind == "solidus" else 1
            self._consume()
            result = self._combine(result, self._component_or_annotation(), sign)
        return result

    def _component_or_annotation(self) -> tuple[float, tuple[int, ...]]:
        if self.kind == "annotation":
            self._consume()
            return 1.0, _ZERO_DIMENSIONS
        result = self._component()
        if self.kind == "annotation":
            self._consume()
        return result

    def _component(self) -> tuple[float, tuple[int, ...]]:
        if self.kind == "number":
            value = float(int(self.token))
            self._consume()
            return value, _ZERO_DIMENSIONS
        if self.kind == "symbol":
            return self._symbol()
        if self.kind == "open":
            self._consume()
            result = self._term()
            if self.kind != "close":
                raise ValueError("UCUM expression is missing a closing parenthesis")
            self._consume()
            return result
        if self.kind == "none":
            raise ValueError("unexpected end of UCUM expression")
        raise ValueError(f"unexpected UCUM token {self.token!r}")

    def _symbol(self) -> tuple[float, tuple[int, ...]]:
        token = self.token
        self._consume()
        bracket = self.token if self.kind == "symbol" and self.token.startswith("[") else ""

        for prefix in _PREFIXES:
            if not token.startswith(prefix) or len(prefix) >= len(token):
                continue
            remainder = token[len(prefix) :]
            if bracket:
                unit = remainder + bracket
                data = UNIT_CANONICAL.get(unit)
                if data is not None and (data[2] or unit.startswith("[")):
                    self._consume()
                    return self._resolved(data, PREFIX_FACTORS[prefix])
            data = UNIT_CANONICAL.get(remainder)
            if data is not None and data[2]:
                return self._resolved(data, PREFIX_FACTORS[prefix])

        if bracket and token in PREFIX_FACTORS:
            data = UNIT_CANONICAL.get(bracket)
            if data is not None and (data[2] or bracket.startswith("[")):
                self._consume()
                return self._resolved(data, PREFIX_FACTORS[token])

        if bracket:
            data = UNIT_CANONICAL.get(token + bracket)
            if data is not None:
                self._consume()
                return self._resolved(data, 1.0)

        data = UNIT_CANONICAL.get(token)
        if data is None:
            raise ValueError(f"unknown UCUM unit {token!r}")
        return self._resolved(data, 1.0)

    def _resolved(
        self,
        data: tuple[float, tuple[int, ...], bool],
        prefix: float,
    ) -> tuple[float, tuple[int, ...]]:
        exponent = 1
        if self.kind == "number":
            exponent = int(self.token)
            self._consume()
        return (prefix * data[0]) ** exponent, tuple(value * exponent for value in data[1])

    @staticmethod
    def _combine(
        left: tuple[float, tuple[int, ...]],
        right: tuple[float, tuple[int, ...]],
        sign: int,
    ) -> tuple[float, tuple[int, ...]]:
        factor = left[0] * right[0] if sign == 1 else left[0] / right[0]
        return factor, tuple(a + sign * b for a, b in zip(left[1], right[1], strict=True))


def ucum_scale(from_unit: Any, to_unit: str) -> float:
    if (
        not isinstance(from_unit, str)
        or not from_unit
        or from_unit.strip() != from_unit
        or not isinstance(to_unit, str)
        or not to_unit
        or to_unit.strip() != to_unit
    ):
        raise ValueError("UCUM units must be non-empty strings without surrounding whitespace")
    source_factor, source_dimensions = _Parser(from_unit).parse()
    target_factor, target_dimensions = _Parser(to_unit).parse()
    if source_dimensions != target_dimensions:
        raise ValueError(f"UCUM units are not comparable: {from_unit} and {to_unit}")
    scale = source_factor / target_factor
    if not math.isfinite(scale):
        raise ValueError(f"UCUM conversion from {from_unit} to {to_unit} is not finite")
    return scale
