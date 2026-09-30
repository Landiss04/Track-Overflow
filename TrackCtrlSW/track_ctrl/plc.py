"""The wayside PLC language: tokenize, parse, compile and scan.

Every value in the language is a single boolean, per REQ-FUNC-066. That
restriction is what makes the program checkable: there is no arithmetic
to overflow and no state to carry between scans except what the program
writes to its own outputs.

Grammar, one statement per line::

    // comment to end of line
    VAR_IN   NAME [NAME ...]
    VAR_OUT  NAME [NAME ...]
    NAME := expression

    expression := or_expr
    or_expr    := xor_expr (OR xor_expr)*
    xor_expr   := and_expr (XOR and_expr)*
    and_expr   := unary (AND unary)*
    unary      := NOT unary | primary
    primary    := '(' expression ')' | NAME | 0 | 1

A declaration may use a range shorthand, written either as a spaced
``OCC_A .. OCC_L`` or a tight ``SUG_SPEED_0..3``. Both expand over the
trailing letter or number run.

A scan evaluates assignments top to bottom, exactly once, like a real
PLC scan cycle. Reading a name that was never declared and has not yet
been assigned this scan yields ``False`` and raises a warning: an
undefined read must not be able to produce a permissive output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping

#: Severities a diagnostic can carry. An ``error`` blocks compilation.
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

_KEYWORDS = frozenset({"VAR_IN", "VAR_OUT", "AND", "OR", "NOT", "XOR"})

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TOKEN_RE = re.compile(r"\s*(\(|\)|:=|\.\.|[A-Za-z_][A-Za-z0-9_]*|[01])")


class PlcSyntaxError(Exception):
    """Raised for a malformed statement, with the source line number."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


@dataclass(frozen=True)
class Diagnostic:
    """One compiler message, shown in the editor's parser pane."""

    severity: str
    line: int
    message: str

    def format(self) -> str:
        """Render as a single terminal line."""
        return f"{self.severity.upper():<7} line {self.line:>3}  {self.message}"


# --- expression tree -------------------------------------------------

@dataclass(frozen=True)
class Literal:
    """A constant ``0`` or ``1``."""

    value: bool

    def evaluate(self, scope: "_Scope") -> bool:
        """Return the constant."""
        return self.value

    def names(self) -> frozenset[str]:
        """Return the names this expression reads."""
        return frozenset()


@dataclass(frozen=True)
class Reference:
    """A read of a declared input, or of a name assigned earlier."""

    name: str
    line: int

    def evaluate(self, scope: "_Scope") -> bool:
        """Return the current value, defaulting an unknown read low."""
        return scope.read(self.name, self.line)

    def names(self) -> frozenset[str]:
        """Return the names this expression reads."""
        return frozenset({self.name})


@dataclass(frozen=True)
class Not:
    """Logical negation."""

    operand: "Expression"

    def evaluate(self, scope: "_Scope") -> bool:
        """Return the inverted operand."""
        return not self.operand.evaluate(scope)

    def names(self) -> frozenset[str]:
        """Return the names this expression reads."""
        return self.operand.names()


@dataclass(frozen=True)
class BinaryOp:
    """``AND``, ``OR`` or ``XOR`` over two operands."""

    operator: str
    left: "Expression"
    right: "Expression"

    def evaluate(self, scope: "_Scope") -> bool:
        """Return the combined operands.

        Both sides are evaluated even when the result is already
        decided, so an undefined-read warning is raised the same way on
        every scan regardless of input values.
        """
        left = self.left.evaluate(scope)
        right = self.right.evaluate(scope)
        if self.operator == "AND":
            return left and right
        if self.operator == "OR":
            return left or right
        return left != right

    def names(self) -> frozenset[str]:
        """Return the names this expression reads."""
        return self.left.names() | self.right.names()


Expression = Literal | Reference | Not | BinaryOp


@dataclass(frozen=True)
class Assignment:
    """One ``NAME := expression`` statement."""

    target: str
    expression: Expression
    line: int


class _Scope:
    """Values visible to one scan, plus the warnings it raised."""

    def __init__(self, inputs: Mapping[str, bool]) -> None:
        self.values: dict[str, bool] = dict(inputs)
        self.undefined_reads: list[Diagnostic] = []

    def read(self, name: str, line: int) -> bool:
        """Return a value, defaulting an undefined read to ``False``."""
        if name in self.values:
            return self.values[name]
        self.undefined_reads.append(
            Diagnostic(
                SEVERITY_WARNING,
                line,
                f"{name} was never declared or assigned; read as 0",
            )
        )
        self.values[name] = False
        return False

    def write(self, name: str, value: bool) -> None:
        """Store an assignment result."""
        self.values[name] = value


@dataclass
class ScanResult:
    """What one pass of a program produced."""

    values: dict[str, bool] = field(default_factory=dict)
    warnings: list[Diagnostic] = field(default_factory=list)

    def outputs(self, names: tuple[str, ...]) -> dict[str, bool]:
        """Return just the declared outputs, defaulting missing to 0."""
        return {name: self.values.get(name, False) for name in names}


@dataclass(frozen=True)
class Program:
    """A compiled, executable PLC program."""

    source: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    assignments: tuple[Assignment, ...]
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def boolean_count(self) -> int:
        """Total distinct booleans the program touches."""
        names: set[str] = set(self.inputs) | set(self.outputs)
        for assignment in self.assignments:
            names.add(assignment.target)
            names |= assignment.expression.names()
        return len(names)

    @property
    def line_count(self) -> int:
        """Source lines, as shown in the editor gutter."""
        return len(self.source.splitlines())

    def scan(self, inputs: Mapping[str, bool]) -> ScanResult:
        """Run one scan cycle over ``inputs`` and return every value.

        The program is pure: nothing in ``self`` is mutated, so the
        same compiled program can be scanned against live inputs and
        against a sandbox copy without the two interfering.
        """
        scope = _Scope(inputs)
        for assignment in self.assignments:
            scope.write(
                assignment.target, assignment.expression.evaluate(scope)
            )
        return ScanResult(values=scope.values, warnings=scope.undefined_reads)


# --- parsing ---------------------------------------------------------

class _ExpressionParser:
    """Recursive-descent parser for one expression on one line."""

    def __init__(self, text: str, line: int) -> None:
        self.tokens = _tokenize_expression(text, line)
        self.line = line
        self.position = 0

    def parse(self) -> Expression:
        """Parse the whole expression and require it to be consumed."""
        expression = self._parse_or()
        if self.position < len(self.tokens):
            raise PlcSyntaxError(
                self.line, f"unexpected {self.tokens[self.position]!r}"
            )
        return expression

    def _peek(self) -> str | None:
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def _take(self) -> str:
        token = self._peek()
        if token is None:
            raise PlcSyntaxError(self.line, "expression ended early")
        self.position += 1
        return token

    def _parse_or(self) -> Expression:
        left = self._parse_xor()
        while self._peek() == "OR":
            self._take()
            left = BinaryOp("OR", left, self._parse_xor())
        return left

    def _parse_xor(self) -> Expression:
        left = self._parse_and()
        while self._peek() == "XOR":
            self._take()
            left = BinaryOp("XOR", left, self._parse_and())
        return left

    def _parse_and(self) -> Expression:
        left = self._parse_unary()
        while self._peek() == "AND":
            self._take()
            left = BinaryOp("AND", left, self._parse_unary())
        return left

    def _parse_unary(self) -> Expression:
        if self._peek() == "NOT":
            self._take()
            return Not(self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> Expression:
        token = self._take()
        if token == "(":
            inner = self._parse_or()
            if self._peek() != ")":
                raise PlcSyntaxError(self.line, "missing closing parenthesis")
            self._take()
            return inner
        if token in ("0", "1"):
            return Literal(token == "1")
        if token in _KEYWORDS:
            raise PlcSyntaxError(
                self.line, f"{token} cannot be used as a value"
            )
        if _NAME_RE.fullmatch(token):
            return Reference(token, self.line)
        raise PlcSyntaxError(self.line, f"unexpected {token!r}")


def _tokenize_expression(text: str, line: int) -> list[str]:
    """Split an expression into tokens, upper-casing operators."""
    tokens: list[str] = []
    position = 0
    while position < len(text):
        if text[position].isspace():
            position += 1
            continue
        match = _TOKEN_RE.match(text, position)
        if match is None:
            raise PlcSyntaxError(line, f"cannot read {text[position]!r}")
        token = match.group(1)
        position = match.end()
        upper = token.upper()
        tokens.append(upper if upper in _KEYWORDS else token)
    return tokens


def _expand_declaration(parts: list[str], line: int) -> list[str]:
    """Expand ``A .. L`` and ``NAME_0..3`` ranges in a declaration."""
    joined = " ".join(parts)
    # Normalise the tight form so both spellings take the same path.
    joined = re.sub(r"\s*\.\.\s*", " .. ", joined)
    tokens = joined.split()

    names: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "..":
            if not names or index + 1 >= len(tokens):
                raise PlcSyntaxError(line, "range needs a start and an end")
            names.pop()
            start = tokens[index - 1]
            end = tokens[index + 1]
            names.extend(_expand_range(start, end, line))
            index += 2
            continue
        names.append(token)
        index += 1

    for name in names:
        if not _NAME_RE.fullmatch(name):
            raise PlcSyntaxError(line, f"{name!r} is not a valid name")
    return names


def _expand_range(start: str, end: str, line: int) -> list[str]:
    """Expand one ``start .. end`` pair over its trailing run.

    ``end`` may repeat the whole name (``OCC_A .. OCC_L``) or give only
    the differing tail (``SUG_SPEED_0 .. 3``).
    """
    match = re.fullmatch(r"(.*?)([A-Za-z]|\d+)", start)
    if match is None:
        raise PlcSyntaxError(line, f"{start!r} cannot start a range")
    prefix, first = match.group(1), match.group(2)

    tail = end[len(prefix):] if end.startswith(prefix) else end
    if not tail:
        raise PlcSyntaxError(line, f"{end!r} cannot end a range")

    if first.isdigit() and tail.isdigit():
        low, high = int(first), int(tail)
        if high < low:
            raise PlcSyntaxError(line, f"range {start}..{end} runs backwards")
        return [f"{prefix}{value}" for value in range(low, high + 1)]

    if len(first) == 1 and len(tail) == 1 and first.isalpha() and tail.isalpha():
        low, high = ord(first.upper()), ord(tail.upper())
        if high < low:
            raise PlcSyntaxError(line, f"range {start}..{end} runs backwards")
        return [f"{prefix}{chr(value)}" for value in range(low, high + 1)]

    raise PlcSyntaxError(line, f"range {start}..{end} is not letters or digits")


def compile_program(source: str) -> Program:
    """Compile PLC source, collecting every diagnostic it produces.

    Parsing continues past a bad line so the programmer sees all the
    errors at once. A program with any error-severity diagnostic must
    not be committed; ``has_errors`` reports that.
    """
    inputs: list[str] = []
    outputs: list[str] = []
    assignments: list[Assignment] = []
    diagnostics: list[Diagnostic] = []
    assigned: set[str] = set()

    for number, raw_line in enumerate(source.splitlines(), start=1):
        text = raw_line.split("//", 1)[0].strip()
        if not text:
            continue

        try:
            head, _, rest = text.partition(" ")
            keyword = head.upper()

            if keyword in ("VAR_IN", "VAR_OUT"):
                names = _expand_declaration(rest.split(), number)
                if not names:
                    raise PlcSyntaxError(number, f"{keyword} declares nothing")
                target = inputs if keyword == "VAR_IN" else outputs
                for name in names:
                    if name in inputs or name in outputs:
                        diagnostics.append(
                            Diagnostic(
                                SEVERITY_WARNING,
                                number,
                                f"{name} is declared more than once",
                            )
                        )
                        continue
                    target.append(name)
                continue

            target_name, separator, expression_text = text.partition(":=")
            if not separator:
                raise PlcSyntaxError(
                    number, "statement is not a declaration or an assignment"
                )

            target_name = target_name.strip()
            if not _NAME_RE.fullmatch(target_name):
                raise PlcSyntaxError(
                    number, f"{target_name!r} is not a valid assignment target"
                )
            if target_name in inputs:
                raise PlcSyntaxError(
                    number, f"{target_name} is an input and cannot be assigned"
                )
            if target_name in assigned:
                diagnostics.append(
                    Diagnostic(
                        SEVERITY_WARNING,
                        number,
                        f"{target_name} is assigned more than once; "
                        "the last assignment in the scan wins",
                    )
                )
            if not expression_text.strip():
                raise PlcSyntaxError(number, "assignment has no expression")

            expression = _ExpressionParser(expression_text, number).parse()
            assignments.append(Assignment(target_name, expression, number))
            assigned.add(target_name)

        except PlcSyntaxError as error:
            diagnostics.append(
                Diagnostic(SEVERITY_ERROR, error.line, error.message)
            )

    for name in outputs:
        if name not in assigned:
            diagnostics.append(
                Diagnostic(
                    SEVERITY_WARNING,
                    0,
                    f"output {name} is declared but never assigned; "
                    "it will hold at 0",
                )
            )

    return Program(
        source=source,
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        assignments=tuple(assignments),
        diagnostics=tuple(diagnostics),
    )


def has_errors(diagnostics: tuple[Diagnostic, ...]) -> bool:
    """Return whether any diagnostic blocks a commit."""
    return any(item.severity == SEVERITY_ERROR for item in diagnostics)
