#!/usr/bin/env python3
"""crustc — the CRusty++ reference compiler.

Implemented milestones:

  M1  — the smallest valid program: `fn main() -> i32 { println("..."); return 0; }`
  M2A — plain data structs, struct literals, field access, `let` bindings, and
        integer arithmetic (no I/O dependency, no control flow). Target example:
        `examples/m2_structs.crust`.

Anything beyond the implemented subset is rejected with a diagnostic rather than
parsed, so the compiler never silently accepts more than the spec defines.

Pipeline:  source -> lexer -> parser -> AST -> type checker -> C emitter

Implementation language: Python 3 (standard library only). No dependencies.
Backend: emits portable C, then (optionally) invokes the system C compiler.
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

KEYWORDS = {"fn", "return", "let", "mut", "struct"}

# Single-character punctuation the implemented grammar can encounter.
PUNCT = set("(){};:,.=+-*/")


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

        # Arrow -> (checked before '-' punctuation).
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
# AST
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
class VarRef(Node):
    name: str


@dataclass
class FieldAccess(Node):
    obj: Node
    field_name: str


@dataclass
class Binary(Node):
    op: str  # + - * /
    left: Node
    right: Node


@dataclass
class StructLit(Node):
    type_name: str
    inits: list[tuple[str, Node, int, int]]  # (field, value, line, col)


@dataclass
class Call(Node):
    callee: str
    args: list[Node]


@dataclass
class ExprStmt(Node):
    expr: Node


@dataclass
class Let(Node):
    name: str
    is_mut: bool
    declared_type: str
    value: Node


@dataclass
class Return(Node):
    value: Node


@dataclass
class StructField:
    name: str
    type_name: str
    line: int
    col: int


@dataclass
class StructDecl(Node):
    name: str
    fields: list[StructField]


@dataclass
class Func(Node):
    name: str
    ret_type: Optional[str]
    body: list[Node] = field(default_factory=list)


@dataclass
class Program(Node):
    structs: list[StructDecl] = field(default_factory=list)
    funcs: list[Func] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser — recursive descent.
# ---------------------------------------------------------------------------


class Parser:
    def __init__(self, tokens: list[Token], path: str) -> None:
        self.tokens = tokens
        self.path = path
        self.pos = 0

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
        structs: list[StructDecl] = []
        funcs: list[Func] = []
        while not self.at("eof"):
            if self.at("kw", "struct"):
                structs.append(self.parse_struct_decl())
            elif self.at("kw", "fn"):
                funcs.append(self.parse_function())
            else:
                tok = self.peek()
                raise Diagnostic(
                    "CRX0003",
                    f"expected `struct` or `fn`, found '{tok.value or 'end of file'}'",
                    self.path,
                    tok.line,
                    tok.col,
                )
        return Program(first.line, first.col, structs, funcs)

    def parse_type(self, *, what: str) -> Token:
        # M2A types are simple identifiers: `i32` or a struct name.
        return self.expect("ident", what=what)

    def parse_struct_decl(self) -> StructDecl:
        kw = self.expect("kw", "struct", what="`struct`")
        name = self.expect("ident", what="a struct name")
        self.expect("punct", "{", what="`{`")
        fields: list[StructField] = []
        while not self.at("punct", "}"):
            if self.at("eof"):
                self.expect("punct", "}", what="`}`")
            fname = self.expect("ident", what="a field name")
            self.expect("punct", ":", what="`:`")
            ftype = self.parse_type(what="a field type")
            fields.append(StructField(fname.value, ftype.value, fname.line, fname.col))
            if self.at("punct", ","):
                self.advance()
            else:
                break
        self.expect("punct", "}", what="`}`")
        return StructDecl(kw.line, kw.col, name.value, fields)

    def parse_function(self) -> Func:
        kw = self.expect("kw", "fn", what="`fn`")
        name = self.expect("ident", what="a function name")
        self.expect("punct", "(", what="`(`")
        if not self.at("punct", ")"):
            tok = self.peek()
            raise Diagnostic(
                "CRX0015",
                "function parameters are not supported yet",
                self.path,
                tok.line,
                tok.col,
                "the current milestones compile only `fn main() -> i32`",
            )
        self.expect("punct", ")", what="`)`")

        ret_type: Optional[str] = None
        if self.at("arrow"):
            self.advance()
            ret_type = self.parse_type(what="a return type").value

        self.expect("punct", "{", what="`{`")
        body: list[Node] = []
        while not self.at("punct", "}"):
            if self.at("eof"):
                self.expect("punct", "}", what="`}`")
            body.append(self.parse_statement())
        self.expect("punct", "}", what="`}`")
        return Func(kw.line, kw.col, name.value, ret_type, body)

    def parse_statement(self) -> Node:
        if self.at("kw", "let"):
            return self.parse_let()
        if self.at("kw", "return"):
            return self.parse_return()
        return self.parse_expr_stmt()

    def parse_let(self) -> Let:
        kw = self.advance()
        is_mut = False
        if self.at("kw", "mut"):
            self.advance()
            is_mut = True
        name = self.expect("ident", what="a variable name")
        self.expect("punct", ":", what="`:`")
        declared = self.parse_type(what="a type annotation")
        self.expect("punct", "=", what="`=`")
        value = self.parse_expr()
        self.expect("punct", ";", what="`;`")
        return Let(kw.line, kw.col, name.value, is_mut, declared.value, value)

    def parse_return(self) -> Return:
        kw = self.advance()
        value = self.parse_expr()
        self.expect("punct", ";", what="`;`")
        return Return(kw.line, kw.col, value)

    def parse_expr_stmt(self) -> ExprStmt:
        expr = self.parse_expr()
        self.expect("punct", ";", what="`;`")
        return ExprStmt(expr.line, expr.col, expr)

    # Expression precedence: add/sub (loosest) -> mul/div -> postfix `.` -> primary
    def parse_expr(self) -> Node:
        return self.parse_add()

    def parse_add(self) -> Node:
        node = self.parse_mul()
        while self.at("punct", "+") or self.at("punct", "-"):
            op = self.advance()
            right = self.parse_mul()
            node = Binary(op.line, op.col, op.value, node, right)
        return node

    def parse_mul(self) -> Node:
        node = self.parse_postfix()
        while self.at("punct", "*") or self.at("punct", "/"):
            op = self.advance()
            right = self.parse_postfix()
            node = Binary(op.line, op.col, op.value, node, right)
        return node

    def parse_postfix(self) -> Node:
        node = self.parse_primary()
        while self.at("punct", "."):
            self.advance()
            fname = self.expect("ident", what="a field name")
            node = FieldAccess(fname.line, fname.col, node, fname.value)
        return node

    def parse_primary(self) -> Node:
        tok = self.peek()
        if tok.kind == "str":
            self.advance()
            return StrLit(tok.line, tok.col, tok.value)
        if tok.kind == "int":
            self.advance()
            return IntLit(tok.line, tok.col, tok.value)
        if tok.kind == "punct" and tok.value == "(":
            self.advance()
            inner = self.parse_expr()
            self.expect("punct", ")", what="`)`")
            return inner
        if tok.kind == "ident":
            self.advance()
            if self.at("punct", "{"):
                return self.parse_struct_lit(tok)
            if self.at("punct", "("):
                return self.parse_call(tok)
            return VarRef(tok.line, tok.col, tok.value)
        raise Diagnostic(
            "CRX0003",
            f"expected an expression, found '{tok.value or 'end of file'}'",
            self.path,
            tok.line,
            tok.col,
        )

    def parse_struct_lit(self, name: Token) -> StructLit:
        self.expect("punct", "{", what="`{`")
        inits: list[tuple[str, Node, int, int]] = []
        while not self.at("punct", "}"):
            fname = self.expect("ident", what="a field name")
            self.expect("punct", ":", what="`:`")
            value = self.parse_expr()
            inits.append((fname.value, value, fname.line, fname.col))
            if self.at("punct", ","):
                self.advance()
            else:
                break
        self.expect("punct", "}", what="`}`")
        return StructLit(name.line, name.col, name.value, inits)

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
# Type checker
#
# Types are represented as strings: "i32", "()" (unit), or a struct name.
# ---------------------------------------------------------------------------

I32 = "i32"
UNIT = "()"


class Checker:
    def __init__(self, program: Program, path: str) -> None:
        self.program = program
        self.path = path
        self.structs: dict[str, StructDecl] = {}
        self.scope: dict[str, str] = {}

    def run(self) -> Func:
        self.collect_structs()
        return self.check_main()

    def collect_structs(self) -> None:
        for decl in self.program.structs:
            seen: dict[str, StructField] = {}
            for fld in decl.fields:
                if fld.name in seen:
                    raise Diagnostic(
                        "CRX0020",
                        f"duplicate field `{fld.name}` in struct `{decl.name}`",
                        self.path,
                        fld.line,
                        fld.col,
                        "each struct field must have a unique name",
                    )
                seen[fld.name] = fld
            self.structs[decl.name] = decl
        # Validate field types after all struct names are known.
        for decl in self.program.structs:
            for fld in decl.fields:
                if fld.type_name == I32:
                    continue
                if fld.type_name in self.structs:
                    raise Diagnostic(
                        "CRX0015",
                        "struct-typed fields are not supported in M2A",
                        self.path,
                        fld.line,
                        fld.col,
                        "M2A struct fields must be `i32`",
                    )
                raise Diagnostic(
                    "CRX0021",
                    f"unknown type `{fld.type_name}`",
                    self.path,
                    fld.line,
                    fld.col,
                    "M2A field types must be `i32`",
                )

    def check_main(self) -> Func:
        main: Optional[Func] = None
        for fn in self.program.funcs:
            if fn.name == "main":
                main = fn
            else:
                raise Diagnostic(
                    "CRX0015",
                    f"only `main` is supported yet (found function `{fn.name}`)",
                    self.path,
                    fn.line,
                    fn.col,
                    "the current milestones compile a single `fn main() -> i32`",
                )

        if main is None:
            last = self.program.funcs[-1] if self.program.funcs else None
            line = last.line if last else 1
            col = last.col if last else 1
            raise Diagnostic(
                "CRX0010",
                "program has no `main` function",
                self.path,
                line,
                col,
                "add `fn main() -> i32 { ... }`",
            )

        if main.ret_type != I32:
            raise Diagnostic(
                "CRX0011",
                "`main` must have signature `fn main() -> i32`",
                self.path,
                main.line,
                main.col,
                "change the return type to `-> i32`",
            )

        saw_return = False
        for stmt in main.body:
            if isinstance(stmt, Let):
                self.check_let(stmt)
            elif isinstance(stmt, Return):
                self.check_return(stmt)
                saw_return = True
            elif isinstance(stmt, ExprStmt):
                self.check_expr_stmt(stmt)
            else:  # pragma: no cover
                raise Diagnostic(
                    "CRX0015",
                    "unsupported statement",
                    self.path,
                    stmt.line,
                    stmt.col,
                )

        if not saw_return:
            raise Diagnostic(
                "CRX0011",
                "`main` must return an `i32`",
                self.path,
                main.line,
                main.col,
                "add `return 0;`",
            )
        return main

    def resolve_type(self, name: str, line: int, col: int) -> str:
        if name == I32:
            return I32
        if name in self.structs:
            return name
        raise Diagnostic(
            "CRX0021",
            f"unknown type `{name}`",
            self.path,
            line,
            col,
            "M2A knows `i32` and declared struct types",
        )

    def check_let(self, stmt: Let) -> None:
        declared = self.resolve_type(stmt.declared_type, stmt.line, stmt.col)
        actual = self.infer(stmt.value)
        if actual != declared:
            raise Diagnostic(
                "CRX0014",
                f"type mismatch: `{stmt.name}` is declared `{declared}` "
                f"but its initializer has type `{actual}`",
                self.path,
                stmt.value.line,
                stmt.value.col,
            )
        self.scope[stmt.name] = declared

    def check_return(self, stmt: Return) -> None:
        actual = self.infer(stmt.value)
        if actual != I32:
            raise Diagnostic(
                "CRX0014",
                f"`main` must return `i32`, found `{actual}`",
                self.path,
                stmt.value.line,
                stmt.value.col,
                "return an `i32` value, e.g. `return 0;`",
            )

    def check_expr_stmt(self, stmt: ExprStmt) -> None:
        expr = stmt.expr
        if not isinstance(expr, Call):
            raise Diagnostic(
                "CRX0015",
                "only `println(...)` calls are supported as bare statements",
                self.path,
                expr.line,
                expr.col,
            )
        self.check_println(expr)

    def check_println(self, call: Call) -> None:
        if call.callee != "println":
            raise Diagnostic(
                "CRX0012",
                f"unknown function `{call.callee}`",
                self.path,
                call.line,
                call.col,
                "the only prelude function implemented is `println`",
            )
        if len(call.args) != 1:
            raise Diagnostic(
                "CRX0013",
                f"`println` takes 1 argument but {len(call.args)} were given",
                self.path,
                call.line,
                call.col,
                'call it as `println("...")`',
            )
        arg = call.args[0]
        if not isinstance(arg, StrLit):
            raise Diagnostic(
                "CRX0014",
                "`println` expects a `str` argument",
                self.path,
                arg.line,
                arg.col,
                'pass a string literal, e.g. `println("hello")`',
            )

    def infer(self, expr: Node) -> str:
        if isinstance(expr, IntLit):
            # Context-typed; defaults to i32 (the only integer type in M2A).
            value = int(expr.value)
            if not (-(2**31) <= value <= 2**31 - 1):
                raise Diagnostic(
                    "CRX0014",
                    f"integer literal {value} does not fit in `i32`",
                    self.path,
                    expr.line,
                    expr.col,
                )
            return I32
        if isinstance(expr, VarRef):
            if expr.name not in self.scope:
                raise Diagnostic(
                    "CRX0027",
                    f"unknown variable `{expr.name}`",
                    self.path,
                    expr.line,
                    expr.col,
                    "declare it with `let` before use",
                )
            return self.scope[expr.name]
        if isinstance(expr, FieldAccess):
            obj_type = self.infer(expr.obj)
            if obj_type not in self.structs:
                raise Diagnostic(
                    "CRX0026",
                    f"cannot access field `{expr.field_name}` on non-struct type "
                    f"`{obj_type}`",
                    self.path,
                    expr.line,
                    expr.col,
                )
            decl = self.structs[obj_type]
            for fld in decl.fields:
                if fld.name == expr.field_name:
                    return fld.type_name
            raise Diagnostic(
                "CRX0025",
                f"struct `{obj_type}` has no field `{expr.field_name}`",
                self.path,
                expr.line,
                expr.col,
            )
        if isinstance(expr, Binary):
            left = self.infer(expr.left)
            right = self.infer(expr.right)
            if left != I32 or right != I32:
                bad = expr.left if left != I32 else expr.right
                raise Diagnostic(
                    "CRX0028",
                    f"arithmetic `{expr.op}` requires `i32` operands, "
                    f"found `{left}` and `{right}`",
                    self.path,
                    bad.line,
                    bad.col,
                )
            return I32
        if isinstance(expr, StructLit):
            return self.infer_struct_lit(expr)
        if isinstance(expr, StrLit):
            # `str` values are not first-class until M3; only println accepts them.
            raise Diagnostic(
                "CRX0015",
                "string values are only supported as `println` arguments yet",
                self.path,
                expr.line,
                expr.col,
            )
        if isinstance(expr, Call):
            # A call in value position: println returns unit, nothing else exists.
            self.check_println(expr)
            return UNIT
        raise Diagnostic(  # pragma: no cover
            "CRX0015",
            "unsupported expression",
            self.path,
            expr.line,
            expr.col,
        )

    def infer_struct_lit(self, lit: StructLit) -> str:
        if lit.type_name not in self.structs:
            raise Diagnostic(
                "CRX0022",
                f"unknown struct type `{lit.type_name}`",
                self.path,
                lit.line,
                lit.col,
                "declare it with `struct` before constructing it",
            )
        decl = self.structs[lit.type_name]
        declared_names = [f.name for f in decl.fields]
        given: dict[str, Node] = {}
        for fname, value, line, col in lit.inits:
            if fname not in declared_names:
                raise Diagnostic(
                    "CRX0024",
                    f"struct `{lit.type_name}` has no field `{fname}`",
                    self.path,
                    line,
                    col,
                )
            if fname in given:
                raise Diagnostic(
                    "CRX0024",
                    f"field `{fname}` specified more than once",
                    self.path,
                    line,
                    col,
                )
            given[fname] = value
        for fld in decl.fields:
            if fld.name not in given:
                raise Diagnostic(
                    "CRX0023",
                    f"missing field `{fld.name}` in `{lit.type_name}` literal",
                    self.path,
                    lit.line,
                    lit.col,
                )
            actual = self.infer(given[fld.name])
            if actual != fld.type_name:
                raise Diagnostic(
                    "CRX0014",
                    f"field `{fld.name}` expects `{fld.type_name}`, found `{actual}`",
                    self.path,
                    given[fld.name].line,
                    given[fld.name].col,
                )
        return lit.type_name


# ---------------------------------------------------------------------------
# C emitter — readable, portable C.
# ---------------------------------------------------------------------------


def c_type(t: str) -> str:
    return "int32_t" if t == I32 else t  # struct names map to their typedef


def c_string_literal(value: str) -> str:
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


def emit_expr(expr: Node) -> str:
    if isinstance(expr, IntLit):
        return str(int(expr.value))
    if isinstance(expr, VarRef):
        return expr.name
    if isinstance(expr, FieldAccess):
        return f"{emit_expr(expr.obj)}.{expr.field_name}"
    if isinstance(expr, Binary):
        return f"({emit_expr(expr.left)} {expr.op} {emit_expr(expr.right)})"
    if isinstance(expr, StructLit):
        parts = ", ".join(
            f".{fname} = {emit_expr(value)}" for fname, value, _, _ in expr.inits
        )
        return f"({expr.type_name}){{ {parts} }}"
    if isinstance(expr, StrLit):
        return c_string_literal(expr.value)
    raise AssertionError(f"cannot emit expression {expr!r}")  # pragma: no cover


def emit_c(program: Program, main: Func, source_path: str) -> str:
    includes: set[str] = set()
    body_lines: list[str] = []

    for stmt in main.body:
        if isinstance(stmt, Let):
            includes.add("stdint.h")
            body_lines.append(
                f"    {c_type(stmt.declared_type)} {stmt.name} = "
                f"{emit_expr(stmt.value)};"
            )
        elif isinstance(stmt, Return):
            body_lines.append(f"    return {emit_expr(stmt.value)};")
        elif isinstance(stmt, ExprStmt) and isinstance(stmt.expr, Call):
            includes.add("stdio.h")
            arg = stmt.expr.args[0]
            assert isinstance(arg, StrLit)
            body_lines.append(f"    puts({c_string_literal(arg.value)});")

    struct_lines: list[str] = []
    for decl in program.structs:
        includes.add("stdint.h")
        struct_lines.append(f"typedef struct {decl.name} {{")
        for fld in decl.fields:
            struct_lines.append(f"    {c_type(fld.type_name)} {fld.name};")
        struct_lines.append(f"}} {decl.name};")
        struct_lines.append("")

    lines: list[str] = []
    lines.append(f"/* Generated by crustc (CRusty++ v0.1) from {source_path} */")
    lines.append("/* Do not edit by hand. */")
    for header in sorted(includes):
        lines.append(f"#include <{header}>")
    lines.append("")
    lines.extend(struct_lines)
    lines.append("int main(void) {")
    lines.extend(body_lines)
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
    main = Checker(program, path).run()
    return emit_c(program, main, path)


def fail(diag: Diagnostic) -> NoReturn:
    print(diag.render(), file=sys.stderr)
    sys.exit(1)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crustc", description="CRusty++ reference compiler."
    )
    parser.add_argument("input", help="path to a .crust source file")
    parser.add_argument("--emit-c", metavar="PATH", help="write generated C to PATH")
    parser.add_argument(
        "--build",
        metavar="PATH",
        help="compile to an executable at PATH via the system C compiler",
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
