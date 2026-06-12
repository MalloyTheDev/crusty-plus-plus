#!/usr/bin/env python3
"""crustc — the CRusty++ reference compiler.

Milestone M1: compile the smallest valid CRusty++ program end-to-end to portable
C. The accepted language is the strict M1 subset documented in
`compiler/README.md` — just enough to compile `examples/hello.crust`:

    fn main() -> i32 {
        println("...");
        return 0;
    }

Everything beyond that subset is intentionally rejected with a diagnostic rather
than parsed, so the compiler never silently accepts more than M1 defines.

Pipeline:  source -> lexer -> parser -> AST -> type checker -> C emitter

Implementation language: Python 3 (standard library only). No dependencies.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import NoReturn, Optional


# ---------------------------------------------------------------------------
# Diagnostics
#
# Frozen diagnostic shape (compiler/README.md -> Diagnostics):
#   error[CRXNNNN]: <short message>
#    --> <path>:<line>:<col>
#   help: <one-line suggestion>          (optional)
#
# Tests assert on the error CODE and the (line, col) SPAN, not the prose.
# ---------------------------------------------------------------------------


class Diagnostic(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        path: str,
        line: int,
        col: int,
        help_text: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.line = line
        self.col = col
        self.help_text = help_text

    def render(self) -> str:
        out = [
            f"error[{self.code}]: {self.message}",
            f" --> {self.path}:{self.line}:{self.col}",
        ]
        if self.help_text:
            out.append(f"help: {self.help_text}")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

KEYWORDS = {"fn", "return"}

# Single- and double-character punctuation the M1 grammar can encounter.
PUNCT = {"(", ")", "{", "}", ";", ","}


@dataclass
class Token:
    kind: str  # "ident" | "kw" | "int" | "str" | "punct" | "arrow" | "eof"
    value: str  # lexeme, or decoded text for "str", or digits for "int"
    line: int
    col: int


def tokenize(src: str, path: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(src)
    line = 1
    col = 1

    def advance(count: int = 1) -> None:
        nonlocal i, line, col
        for _ in range(count):
            if i < n and src[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = src[i]

        # Whitespace.
        if ch in " \t\r\n":
            advance()
            continue

        # Line comments: // ... to end of line.
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                advance()
            continue

        start_line, start_col = line, col

        # Arrow ->.
        if ch == "-" and i + 1 < n and src[i + 1] == ">":
            advance(2)
            tokens.append(Token("arrow", "->", start_line, start_col))
            continue

        # Identifiers / keywords.
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            advance(j - i)
            kind = "kw" if word in KEYWORDS else "ident"
            tokens.append(Token(kind, word, start_line, start_col))
            continue

        # Integer literals (with optional '_' separators).
        if ch.isdigit():
            j = i
            while j < n and (src[j].isdigit() or src[j] == "_"):
                j += 1
            digits = src[i:j].replace("_", "")
            advance(j - i)
            tokens.append(Token("int", digits, start_line, start_col))
            continue

        # String literals with escapes \n \t \\ \".
        if ch == '"':
            advance()  # opening quote
            buf: list[str] = []
            while i < n and src[i] != '"':
                c = src[i]
                if c == "\n":
                    raise Diagnostic(
                        "CRX0002",
                        "unterminated string literal",
                        path,
                        start_line,
                        start_col,
                        "string literals may not span multiple lines in v0.1",
                    )
                if c == "\\":
                    if i + 1 >= n:
                        break
                    esc = src[i + 1]
                    mapping = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}
                    if esc not in mapping:
                        raise Diagnostic(
                            "CRX0001",
                            f"unknown escape sequence '\\{esc}'",
                            path,
                            line,
                            col,
                            "v0.1 supports \\n \\t \\\\ and \\\"",
                        )
                    buf.append(mapping[esc])
                    advance(2)
                    continue
                buf.append(c)
                advance()
            if i >= n:
                raise Diagnostic(
                    "CRX0002",
                    "unterminated string literal",
                    path,
                    start_line,
                    start_col,
                    'add a closing "',
                )
            advance()  # closing quote
            tokens.append(Token("str", "".join(buf), start_line, start_col))
            continue

        # Punctuation.
        if ch in PUNCT:
            advance()
            tokens.append(Token("punct", ch, start_line, start_col))
            continue

        # Anything else is a lexical error.
        raise Diagnostic(
            "CRX0001",
            f"unexpected character '{ch}'",
            path,
            start_line,
            start_col,
        )

    tokens.append(Token("eof", "", line, col))
    return tokens


# ---------------------------------------------------------------------------
# AST (kept deliberately tiny for M1)
# ---------------------------------------------------------------------------


@dataclass
class Node:
    line: int
    col: int


@dataclass
class StrLit(Node):
    value: str


@dataclass
class IntLit(Node):
    value: str  # raw digits, no separators


@dataclass
class Call(Node):
    callee: str
    args: list[Node]


@dataclass
class ExprStmt(Node):
    expr: Node


@dataclass
class Return(Node):
    value: Node


@dataclass
class Func(Node):
    name: str
    ret_type: Optional[str]  # e.g. "i32", or None for unit
    body: list[Node] = field(default_factory=list)


@dataclass
class Program(Node):
    funcs: list[Func] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser — recursive descent over the strict M1 grammar.
# ---------------------------------------------------------------------------


class Parser:
    def __init__(self, tokens: list[Token], path: str) -> None:
        self.tokens = tokens
        self.path = path
        self.pos = 0

    # -- token helpers ------------------------------------------------------

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind != "eof":
            self.pos += 1
        return tok

    def at(self, kind: str, value: Optional[str] = None) -> bool:
        tok = self.peek()
        return tok.kind == kind and (value is None or tok.value == value)

    def expect(self, kind: str, value: Optional[str] = None, *, what: str) -> Token:
        tok = self.peek()
        if tok.kind != kind or (value is not None and tok.value != value):
            shown = tok.value if tok.kind != "eof" else "end of file"
            raise Diagnostic(
                "CRX0003",
                f"expected {what}, found '{shown}'",
                self.path,
                tok.line,
                tok.col,
            )
        return self.advance()

    # -- grammar ------------------------------------------------------------

    def parse_program(self) -> Program:
        first = self.peek()
        funcs: list[Func] = []
        while not self.at("eof"):
            funcs.append(self.parse_function())
        return Program(first.line, first.col, funcs)

    def parse_function(self) -> Func:
        kw = self.expect("kw", "fn", what="`fn`")
        name = self.expect("ident", what="a function name")
        self.expect("punct", "(", what="`(`")
        # M1: no parameters.
        if not self.at("punct", ")"):
            tok = self.peek()
            raise Diagnostic(
                "CRX0015",
                "function parameters are not supported in M1",
                self.path,
                tok.line,
                tok.col,
                "M1 only compiles `fn main() -> i32`",
            )
        self.expect("punct", ")", what="`)`")

        ret_type: Optional[str] = None
        if self.at("arrow"):
            self.advance()
            type_tok = self.expect("ident", what="a return type")
            ret_type = type_tok.value

        self.expect("punct", "{", what="`{`")
        body: list[Node] = []
        while not self.at("punct", "}"):
            if self.at("eof"):
                self.expect("punct", "}", what="`}`")  # raises a clean diagnostic
            body.append(self.parse_statement())
        self.expect("punct", "}", what="`}`")
        return Func(kw.line, kw.col, name.value, ret_type, body)

    def parse_statement(self) -> Node:
        if self.at("kw", "return"):
            return self.parse_return()
        return self.parse_expr_stmt()

    def parse_return(self) -> Return:
        kw = self.advance()
        value = self.parse_expr()
        self.expect("punct", ";", what="`;`")
        return Return(kw.line, kw.col, value)

    def parse_expr_stmt(self) -> ExprStmt:
        expr = self.parse_expr()
        self.expect("punct", ";", what="`;`")
        return ExprStmt(expr.line, expr.col, expr)

    def parse_expr(self) -> Node:
        tok = self.peek()
        if tok.kind == "str":
            self.advance()
            return StrLit(tok.line, tok.col, tok.value)
        if tok.kind == "int":
            self.advance()
            return IntLit(tok.line, tok.col, tok.value)
        if tok.kind == "ident":
            self.advance()
            if self.at("punct", "("):
                return self.parse_call(tok)
            raise Diagnostic(
                "CRX0015",
                "variables and bare identifiers are not supported in M1",
                self.path,
                tok.line,
                tok.col,
                "M1 supports string literals, integer literals, and `println(...)`",
            )
        raise Diagnostic(
            "CRX0003",
            f"expected an expression, found '{tok.value or 'end of file'}'",
            self.path,
            tok.line,
            tok.col,
        )

    def parse_call(self, callee: Token) -> Call:
        self.expect("punct", "(", what="`(`")
        args: list[Node] = []
        if not self.at("punct", ")"):
            args.append(self.parse_expr())
            while self.at("punct", ","):
                self.advance()
                args.append(self.parse_expr())
        self.expect("punct", ")", what="`)`")
        return Call(callee.line, callee.col, callee.value, args)


# ---------------------------------------------------------------------------
# Type checker — validates the M1 subset.
# ---------------------------------------------------------------------------


def check(program: Program, path: str) -> Func:
    main: Optional[Func] = None
    for fn in program.funcs:
        if fn.name == "main":
            main = fn
        else:
            raise Diagnostic(
                "CRX0015",
                f"only `main` is supported in M1 (found function `{fn.name}`)",
                path,
                fn.line,
                fn.col,
                "M1 compiles a single `fn main() -> i32`",
            )

    if main is None:
        last = program.funcs[-1] if program.funcs else None
        line = last.line if last else 1
        col = last.col if last else 1
        raise Diagnostic(
            "CRX0010",
            "program has no `main` function",
            path,
            line,
            col,
            "add `fn main() -> i32 { ... }`",
        )

    if main.ret_type != "i32":
        raise Diagnostic(
            "CRX0011",
            "`main` must have signature `fn main() -> i32`",
            path,
            main.line,
            main.col,
            "change the return type to `-> i32`",
        )

    saw_return = False
    for stmt in main.body:
        if isinstance(stmt, ExprStmt):
            check_call_stmt(stmt.expr, path)
        elif isinstance(stmt, Return):
            check_return(stmt, path)
            saw_return = True
        else:  # pragma: no cover - parser only yields the two above
            raise Diagnostic(
                "CRX0015",
                "unsupported statement in M1",
                path,
                stmt.line,
                stmt.col,
            )

    if not saw_return:
        raise Diagnostic(
            "CRX0011",
            "`main` must return an `i32`",
            path,
            main.line,
            main.col,
            "add `return 0;`",
        )

    return main


def check_call_stmt(expr: Node, path: str) -> None:
    if not isinstance(expr, Call):
        raise Diagnostic(
            "CRX0015",
            "only `println(...)` calls are supported as statements in M1",
            path,
            expr.line,
            expr.col,
        )
    if expr.callee != "println":
        raise Diagnostic(
            "CRX0012",
            f"unknown function `{expr.callee}`",
            path,
            expr.line,
            expr.col,
            "M1 only provides the `println` prelude function",
        )
    if len(expr.args) != 1:
        raise Diagnostic(
            "CRX0013",
            f"`println` takes 1 argument but {len(expr.args)} were given",
            path,
            expr.line,
            expr.col,
            "call it as `println(\"...\")`",
        )
    arg = expr.args[0]
    if not isinstance(arg, StrLit):
        raise Diagnostic(
            "CRX0014",
            "`println` expects a `str` argument",
            path,
            arg.line,
            arg.col,
            "pass a string literal, e.g. `println(\"hello\")`",
        )


def check_return(stmt: Return, path: str) -> None:
    if not isinstance(stmt.value, IntLit):
        raise Diagnostic(
            "CRX0014",
            "`main` must return an `i32` value",
            path,
            stmt.value.line,
            stmt.value.col,
            "return an integer literal, e.g. `return 0;`",
        )
    # Integer literal is context-typed to i32 here; range-check it.
    value = int(stmt.value.value)
    if not (-(2**31) <= value <= 2**31 - 1):
        raise Diagnostic(
            "CRX0014",
            f"integer literal {value} does not fit in `i32`",
            path,
            stmt.value.line,
            stmt.value.col,
        )


# ---------------------------------------------------------------------------
# C emitter — readable, portable C.
# ---------------------------------------------------------------------------


def c_string_literal(value: str) -> str:
    """Encode a CRusty++ str value as a C string literal."""
    out = ['"']
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif 32 <= ord(ch) < 127:
            out.append(ch)
        else:
            out.append(f"\\x{ord(ch):02x}")
    out.append('"')
    return "".join(out)


def emit_c(main: Func, source_path: str) -> str:
    lines: list[str] = []
    lines.append(
        f"/* Generated by crustc (CRusty++ v0.1, M1) from {source_path} */"
    )
    lines.append("/* Do not edit by hand. */")
    lines.append("#include <stdio.h>")
    lines.append("")
    lines.append("int main(void) {")
    for stmt in main.body:
        if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, Call):
            arg = stmt.expr.args[0]
            assert isinstance(arg, StrLit)
            # println(str) lowers to puts(), which appends a newline.
            lines.append(f"    puts({c_string_literal(arg.value)});")
        elif isinstance(stmt, Return):
            assert isinstance(stmt.value, IntLit)
            lines.append(f"    return {int(stmt.value.value)};")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def compile_to_c(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    tokens = tokenize(src, path)
    program = Parser(tokens, path).parse_program()
    main = check(program, path)
    return emit_c(main, path)


def fail(diag: Diagnostic) -> NoReturn:
    print(diag.render(), file=sys.stderr)
    sys.exit(1)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crustc",
        description="CRusty++ reference compiler (M1).",
    )
    parser.add_argument("input", help="path to a .crust source file")
    parser.add_argument("--emit-c", metavar="PATH", help="write generated C to PATH")
    parser.add_argument(
        "--build", metavar="PATH", help="compile to an executable at PATH via the system C compiler"
    )
    parser.add_argument(
        "--run", action="store_true", help="run the built executable (implies --build)"
    )
    args = parser.parse_args(argv)

    try:
        c_source = compile_to_c(args.input)
    except Diagnostic as diag:
        fail(diag)

    if not args.emit_c and not args.build and not args.run:
        sys.stdout.write(c_source)
        return 0

    if args.emit_c:
        with open(args.emit_c, "w", encoding="utf-8") as fh:
            fh.write(c_source)

    exe_path = args.build
    if args.run and not exe_path:
        exe_path = os.path.join(tempfile.gettempdir(), "crust_a.out")

    if exe_path:
        cc = os.environ.get("CC", "cc")
        with tempfile.NamedTemporaryFile(
            "w", suffix=".c", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(c_source)
            c_file = tmp.name
        try:
            subprocess.run([cc, c_file, "-o", exe_path], check=True)
        finally:
            os.unlink(c_file)

    if args.run:
        assert exe_path is not None
        result = subprocess.run([exe_path])
        return result.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
