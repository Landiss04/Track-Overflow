"""The wayside PLC language: Boolean-only programs, compiled and scanned.

The language is the one the software Track Controller defined, so one
program file runs on either variant (REQ-INTF-009). This implementation
is written separately from that one: the variants share a language, not
code, which keeps the two implementations diverse.

One statement per line::

    // a comment runs to the end of the line
    VAR_IN   OCC_1 .. OCC_20         names the wayside feeds the program
    VAR_OUT  SW_12 AUTH_1..20        names the program drives
    NAME := expression

    expression := xor_expr { OR xor_expr }
    xor_expr   := and_expr { XOR and_expr }
    and_expr   := unary { AND unary }
    unary      := NOT unary | primary
    primary    := ( expression ) | NAME | 0 | 1

Every value is a single bit (REQ-FUNC-051). Keywords are case-blind,
names are not. A declaration may give a range, ``OCC_1 .. OCC_20`` or
``AUTH_1..20``, over a trailing number or letter.

A scan runs the assignments top to bottom, once. A name that is neither
an input nor assigned earlier in the scan reads as 0. ``NOT`` of such a
name is 1, so the compiler warns about every such read in advance.

Each statement is compiled twice, by different algorithms. Channel A
parses by recursive descent and walks the tree. Channel B parses with
the shunting-yard algorithm and runs postfix code on a stack. The
wayside runs both on every scan and treats any disagreement as a vital
fault.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from typing import Mapping, Union

ERROR = "error"
WARNING = "warning"

_DECLARATIONS = ("VAR_IN", "VAR_OUT")
_OPERATORS = ("AND", "OR", "XOR", "NOT")
_KEYWORDS = frozenset(_DECLARATIONS + _OPERATORS)
#: Binary precedence for channel B; NOT binds tighter than any of them.
_PRECEDENCE = {"OR": 1, "XOR": 2, "AND": 3}

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_TOKEN = re.compile(
    r"\s*(?:(?P<assign>:=)|(?P<range>\.\.)|(?P<paren>[()])"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<number>\d+)(?![A-Za-z_])|(?P<bad>\S))"
)
_RANGE_START = re.compile(r"(?P<prefix>.*?)(?P<run>\d+|[A-Za-z])\Z")


@dataclass(frozen=True)
class Diagnostic:
    """One compiler message."""

    severity: str
    line: int
    message: str

    def __str__(self) -> str:
        where = f"line {self.line}" if self.line else "program"
        return f"{self.severity.capitalize()}, {where}: {self.message}"


class _SyntaxProblem(Exception):
    """A statement cannot be read; carries the line it is on."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(message)
        self.line = line
        self.message = message


# ------------------------------------------------------------------ #
# Tokens
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class _Token:
    kind: str   # assign | range | paren | name | number | keyword
    text: str

    @property
    def is_bit(self) -> bool:
        return self.kind == "number" and self.text in ("0", "1")


def _tokenize(text: str, line: int) -> list[_Token]:
    tokens: list[_Token] = []
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:
            break   # only trailing whitespace is left
        position = match.end()
        kind = match.lastgroup
        value = match.group(kind) if kind else ""
        if kind == "bad":
            raise _SyntaxProblem(line, f"cannot read {value!r}")
        if kind == "name" and value.upper() in _KEYWORDS:
            tokens.append(_Token("keyword", value.upper()))
        elif kind is not None:
            tokens.append(_Token(kind, value))
    return tokens


# ------------------------------------------------------------------ #
# Channel A: recursive descent to a tree, evaluated recursively
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class Constant:
    value: bool


@dataclass(frozen=True)
class Read:
    name: str


@dataclass(frozen=True)
class Negate:
    operand: Node


@dataclass(frozen=True)
class Combine:
    operator: str
    left: Node
    right: Node


Node = Union[Constant, Read, Negate, Combine]


class _TreeParser:
    def __init__(self, tokens: list[_Token], line: int) -> None:
        self._tokens = tokens
        self._line = line
        self._at = 0

    def parse(self) -> Node:
        node = self._binary(0)
        if self._at < len(self._tokens):
            raise _SyntaxProblem(
                self._line, f"unexpected {self._tokens[self._at].text!r}"
            )
        return node

    def _peek(self) -> _Token | None:
        return self._tokens[self._at] if self._at < len(self._tokens) else None

    def _next(self) -> _Token:
        token = self._peek()
        if token is None:
            raise _SyntaxProblem(self._line, "the expression ends too soon")
        self._at += 1
        return token

    def _binary(self, level: int) -> Node:
        # Levels 0, 1, 2 are OR, XOR, AND; level 3 is a unary term.
        if level == 3:
            return self._unary()
        operator = ("OR", "XOR", "AND")[level]
        node = self._binary(level + 1)
        while True:
            token = self._peek()
            if token is None or token.kind != "keyword":
                return node
            if token.text != operator:
                return node
            self._next()
            node = Combine(operator, node, self._binary(level + 1))

    def _unary(self) -> Node:
        token = self._peek()
        if token == _Token("keyword", "NOT"):
            self._next()
            return Negate(self._unary())
        return self._primary()

    def _primary(self) -> Node:
        token = self._next()
        if token.kind == "paren" and token.text == "(":
            node = self._binary(0)
            closing = self._next()
            if closing.kind != "paren" or closing.text != ")":
                raise _SyntaxProblem(self._line, "a ( is never closed")
            return node
        if token.is_bit:
            return Constant(token.text == "1")
        if token.kind == "number":
            raise _SyntaxProblem(
                self._line, f"{token.text} is not a value; use 0 or 1"
            )
        if token.kind == "name":
            return Read(token.text)
        if token.kind == "keyword":
            raise _SyntaxProblem(
                self._line, f"{token.text} cannot be used as a value"
            )
        raise _SyntaxProblem(self._line, f"unexpected {token.text!r}")


def _evaluate(node: Node, scope: _Scope) -> bool:
    if isinstance(node, Constant):
        return node.value
    if isinstance(node, Read):
        return scope.read(node.name)
    if isinstance(node, Negate):
        return not _evaluate(node.operand, scope)
    left = _evaluate(node.left, scope)
    right = _evaluate(node.right, scope)
    if node.operator == "AND":
        return left and right
    if node.operator == "OR":
        return left or right
    return left != right


def _tree_reads(node: Node) -> list[str]:
    if isinstance(node, Read):
        return [node.name]
    if isinstance(node, Negate):
        return _tree_reads(node.operand)
    if isinstance(node, Combine):
        return _tree_reads(node.left) + _tree_reads(node.right)
    return []


# ------------------------------------------------------------------ #
# Channel B: shunting-yard to postfix code, run on a stack
# ------------------------------------------------------------------ #

# ("push", "1") pushes a constant, ("load", NAME) a variable, and
# ("op", OPERATOR) applies NOT, AND, OR or XOR to the stack top.
Instruction = tuple[str, str]


def _postfix(tokens: list[_Token], line: int) -> tuple[Instruction, ...]:
    code: list[Instruction] = []
    pending: list[str] = []
    for token in tokens:
        if token.is_bit:
            code.append(("push", token.text))
        elif token.kind == "name":
            code.append(("load", token.text))
        elif token.kind == "keyword" and token.text == "NOT":
            pending.append("NOT")
        elif token.kind == "keyword" and token.text in _PRECEDENCE:
            rank = _PRECEDENCE[token.text]
            while pending and pending[-1] != "(" and (
                pending[-1] == "NOT" or _PRECEDENCE[pending[-1]] >= rank
            ):
                code.append(("op", pending.pop()))
            pending.append(token.text)
        elif token.kind == "paren" and token.text == "(":
            pending.append("(")
        elif token.kind == "paren" and token.text == ")":
            while pending and pending[-1] != "(":
                code.append(("op", pending.pop()))
            if not pending:
                raise _SyntaxProblem(line, "a ) has no matching (")
            pending.pop()
        else:
            raise _SyntaxProblem(line, f"unexpected {token.text!r}")
    while pending:
        operator = pending.pop()
        if operator == "(":
            raise _SyntaxProblem(line, "a ( is never closed")
        code.append(("op", operator))
    _check_stack(code, line)
    return tuple(code)


def _check_stack(code: list[Instruction], line: int) -> None:
    # Postfix code is well formed only if every operator has its
    # operands and exactly one value is left at the end.
    depth = 0
    for kind, value in code:
        if kind in ("push", "load"):
            depth += 1
        elif value == "NOT":
            if depth < 1:
                raise _SyntaxProblem(line, "NOT has nothing to negate")
        else:
            if depth < 2:
                raise _SyntaxProblem(line, f"{value} is missing an operand")
            depth -= 1
    if depth != 1:
        raise _SyntaxProblem(line, "operands are missing an operator")


def _run_postfix(code: tuple[Instruction, ...], scope: _Scope) -> bool:
    stack: list[bool] = []
    for kind, value in code:
        if kind == "push":
            stack.append(value == "1")
        elif kind == "load":
            stack.append(scope.read(value))
        elif value == "NOT":
            stack.append(not stack.pop())
        else:
            right = stack.pop()
            left = stack.pop()
            if value == "AND":
                stack.append(left and right)
            elif value == "OR":
                stack.append(left or right)
            else:
                stack.append(left != right)
    return stack.pop()


# ------------------------------------------------------------------ #
# Programs
# ------------------------------------------------------------------ #

class _Scope:
    """The values one channel can see during one scan."""

    def __init__(self, inputs: Mapping[str, bool]) -> None:
        self.values: dict[str, bool] = dict(inputs)

    def read(self, name: str) -> bool:
        # An undefined read is 0; the compiler has warned about it.
        return self.values.get(name, False)


@dataclass(frozen=True)
class Statement:
    """One ``NAME := expression``, compiled for both channels."""

    target: str
    tree: Node
    code: tuple[Instruction, ...]
    line: int


@dataclass(frozen=True)
class Program:
    """A compiled PLC program. Scanning never changes it."""

    source: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    statements: tuple[Statement, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        """Diagnostics that stop the program from being loaded."""
        return tuple(d for d in self.diagnostics if d.severity == ERROR)

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        """Diagnostics that do not stop the program from loading."""
        return tuple(d for d in self.diagnostics if d.severity == WARNING)

    @property
    def assigned(self) -> frozenset[str]:
        """Every name some statement assigns."""
        return frozenset(statement.target for statement in self.statements)

    @property
    def boolean_count(self) -> int:
        """Distinct Boolean variables the program declares or uses."""
        names = set(self.inputs) | set(self.outputs)
        for statement in self.statements:
            names.add(statement.target)
            names.update(_tree_reads(statement.tree))
        return len(names)

    @property
    def checksum(self) -> str:
        """CRC-32 of the source text, as ``XXXX-XXXX``."""
        value = zlib.crc32(self.source.encode("utf-8")) & 0xFFFFFFFF
        text = f"{value:08X}"
        return f"{text[:4]}-{text[4:]}"

    def scan_a(self, inputs: Mapping[str, bool]) -> dict[str, bool]:
        """Channel A: run every statement by walking its tree."""
        scope = _Scope({name: inputs[name] for name in self.inputs})
        for statement in self.statements:
            scope.values[statement.target] = _evaluate(statement.tree, scope)
        return {name: scope.read(name) for name in self.outputs}

    def scan_b(self, inputs: Mapping[str, bool]) -> dict[str, bool]:
        """Channel B: run every statement's postfix code on a stack."""
        scope = _Scope({name: inputs[name] for name in self.inputs})
        for statement in self.statements:
            scope.values[statement.target] = _run_postfix(
                statement.code, scope
            )
        return {name: scope.read(name) for name in self.outputs}


def compile_program(source: str) -> Program:
    """Compile PLC source, collecting every problem rather than stopping.

    The result always exists; a program whose ``errors`` is not empty
    must not be loaded.
    """
    inputs: list[str] = []
    outputs: list[str] = []
    statements: list[Statement] = []
    diagnostics: list[Diagnostic] = []

    for number, raw in enumerate(source.splitlines(), start=1):
        text = raw.split("//", 1)[0].strip()
        if not text:
            continue
        try:
            tokens = _tokenize(text, number)
            head = tokens[0]
            if head.kind == "keyword" and head.text in _DECLARATIONS:
                names = _declared_names(tokens[1:], number)
                target = inputs if head.text == "VAR_IN" else outputs
                for name in names:
                    if name in inputs or name in outputs:
                        diagnostics.append(Diagnostic(
                            WARNING, number,
                            f"{name} is declared more than once",
                        ))
                    else:
                        target.append(name)
                continue
            statements.append(_statement(tokens, number, inputs))
        except _SyntaxProblem as problem:
            diagnostics.append(
                Diagnostic(ERROR, problem.line, problem.message)
            )

    diagnostics.extend(_usage_warnings(inputs, outputs, statements))
    return Program(
        source=source,
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        statements=tuple(statements),
        diagnostics=tuple(diagnostics),
    )


def _statement(
    tokens: list[_Token], line: int, inputs: list[str]
) -> Statement:
    if len(tokens) < 2 or tokens[1].kind != "assign":
        raise _SyntaxProblem(
            line, "a line must be VAR_IN, VAR_OUT or NAME := expression"
        )
    target = tokens[0]
    if target.kind != "name":
        raise _SyntaxProblem(line, f"{target.text!r} cannot be assigned")
    if target.text in inputs:
        raise _SyntaxProblem(
            line, f"{target.text} is an input and cannot be assigned"
        )
    expression = tokens[2:]
    if not expression:
        raise _SyntaxProblem(line, f"{target.text} := has no expression")
    tree = _TreeParser(expression, line).parse()
    code = _postfix(expression, line)
    if sorted(_tree_reads(tree)) != sorted(
        value for kind, value in code if kind == "load"
    ):
        raise _SyntaxProblem(line, "the two channels read this differently")
    return Statement(target=target.text, tree=tree, code=code, line=line)


def _declared_names(tokens: list[_Token], line: int) -> list[str]:
    names: list[str] = []
    at = 0
    while at < len(tokens):
        token = tokens[at]
        if token.kind == "range":
            if not names or at + 1 >= len(tokens):
                raise _SyntaxProblem(line, ".. needs a name on each side")
            end = tokens[at + 1]
            if end.kind not in ("name", "number"):
                raise _SyntaxProblem(line, f"{end.text!r} cannot end a range")
            names.extend(_expand(names.pop(), end.text, line))
            at += 2
            continue
        if token.kind != "name":
            raise _SyntaxProblem(line, f"{token.text!r} cannot be declared")
        names.append(token.text)
        at += 1
    if not names:
        raise _SyntaxProblem(line, "the declaration names nothing")
    return names


def _expand(start: str, end: str, line: int) -> list[str]:
    # "OCC_1 .. OCC_20" and "OCC_1..20" both expand over the run.
    match = _RANGE_START.match(start)
    if match is None:
        raise _SyntaxProblem(line, f"{start} cannot start a range")
    prefix, first = match.group("prefix"), match.group("run")
    repeats_prefix = end.startswith(prefix) and end != prefix
    last = end[len(prefix):] if repeats_prefix else end
    if first.isdigit() and last.isdigit():
        low, high = int(first), int(last)
        if high < low:
            raise _SyntaxProblem(line, f"{start} .. {end} runs backwards")
        return [f"{prefix}{value}" for value in range(low, high + 1)]
    if (
        first.isalpha()
        and len(last) == 1
        and last.isalpha()
        and first.isupper() == last.isupper()
    ):
        low, high = ord(first), ord(last)
        if high < low:
            raise _SyntaxProblem(line, f"{start} .. {end} runs backwards")
        return [f"{prefix}{chr(value)}" for value in range(low, high + 1)]
    raise _SyntaxProblem(line, f"{start} .. {end} is not a range")


def _usage_warnings(
    inputs: list[str], outputs: list[str], statements: list[Statement]
) -> list[Diagnostic]:
    warnings: list[Diagnostic] = []
    defined = set(inputs)
    assigned_lines: dict[str, int] = {}
    reported: set[str] = set()
    for statement in statements:
        for name in _tree_reads(statement.tree):
            if name not in defined and name not in reported:
                reported.add(name)
                warnings.append(Diagnostic(
                    WARNING, statement.line,
                    f"{name} is read before anything sets it; it reads as 0",
                ))
        if statement.target in assigned_lines:
            warnings.append(Diagnostic(
                WARNING, statement.line,
                f"{statement.target} is assigned again; the last "
                "assignment wins",
            ))
        assigned_lines[statement.target] = statement.line
        defined.add(statement.target)
    for name in outputs:
        if name not in assigned_lines:
            warnings.append(Diagnostic(
                WARNING, 0, f"output {name} is never assigned; it stays 0"
            ))
    return warnings
