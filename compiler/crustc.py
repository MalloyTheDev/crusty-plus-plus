#!/usr/bin/env python3
"""crustc — the CRusty++ reference compiler.

Implemented milestones:

  M1  — smallest program: `fn main() -> i32 { println("..."); return 0; }`
  M2A — plain structs, struct literals, field access, `let`, integer arithmetic.
  M2B — `bool`, comparisons, `if`/`else`, and *checked* integer arithmetic
        (overflow / divide-by-zero / negation overflow abort with exit code 101).

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

KEYWORDS = {
    "fn", "return", "let", "mut", "struct", "if", "else",
    "while", "loop", "break", "continue",
}

# Single-character punctuation the implemented grammar can encounter.
PUNCT = set("(){};:,.=+-*/<>")

# Two-character tokens, checked before single-character punctuation.
TWO_CHAR = {"->", "==", "!=", "<=", ">="}


@dataclass
class Token:
    kind: str  # "ident" | "kw" | "int" | "str" | "punct" | "arrow" | "eof"
    value: str
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

        if ch in " \t\r\n":
            advance()
            continue

        # Line comments.
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                advance()
            continue

        start_line, start_col = line, col

        # Two-character tokens (-> == != <= >=).
        two = src[i : i + 2]
        if two in TWO_CHAR:
            advance(2)
            kind = "arrow" if two == "->" else "punct"
            tokens.append(Token(kind, two, start_line, start_col))
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

        # Integer literals.
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
            advance()
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
            advance()
            tokens.append(Token("str", "".join(buf), start_line, start_col))
            continue

        # Punctuation.
        if ch in PUNCT:
            advance()
            tokens.append(Token("punct", ch, start_line, start_col))
            continue

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
    value: str


@dataclass
class VarRef(Node):
    name: str


@dataclass
class FieldAccess(Node):
    obj: Node
    field_name: str


@dataclass
class Unary(Node):
    op: str  # "-"
    operand: Node


@dataclass
class Binary(Node):
    op: str  # + - * /  or  == != < <= > >=
    left: Node
    right: Node


@dataclass
class StructLit(Node):
    type_name: str
    inits: list[tuple[str, Node, int, int]]


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
class Assign(Node):
    target: Node  # validated to be a VarRef in the checker
    value: Node


@dataclass
class Return(Node):
    value: Node


@dataclass
class If(Node):
    cond: Node
    then_branch: list[Node]
    else_branch: Optional[list[Node]]


@dataclass
class While(Node):
    cond: Node
    body: list[Node]


@dataclass
class Loop(Node):
    body: list[Node]


@dataclass
class Break(Node):
    pass


@dataclass
class Continue(Node):
    pass


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

ARITH_OPS = {"+", "-", "*", "/"}
CMP_OPS = {"==", "!=", "<", "<=", ">", ">="}


class Parser:
    def __init__(self, tokens: list[Token], path: str) -> None:
        self.tokens = tokens
        self.path = path
        self.pos = 0
        # When True, an `ident {` is NOT read as a struct literal — this lets an
        # `if` condition's trailing `{` open the block (e.g. `if ok { ... }`).
        self.no_struct_lit = False

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

    def at_punct(self, *values: str) -> bool:
        tok = self.peek()
        return tok.kind == "punct" and tok.value in values

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
        return self.expect("ident", what=what)

    def parse_struct_decl(self) -> StructDecl:
        kw = self.expect("kw", "struct", what="`struct`")
        name = self.expect("ident", what="a struct name")
        self.expect("punct", "{", what="`{`")
        fields: list[StructField] = []
        while not self.at_punct("}"):
            if self.at("eof"):
                self.expect("punct", "}", what="`}`")
            fname = self.expect("ident", what="a field name")
            self.expect("punct", ":", what="`:`")
            ftype = self.parse_type(what="a field type")
            fields.append(StructField(fname.value, ftype.value, fname.line, fname.col))
            if self.at_punct(","):
                self.advance()
            else:
                break
        self.expect("punct", "}", what="`}`")
        return StructDecl(kw.line, kw.col, name.value, fields)

    def parse_function(self) -> Func:
        kw = self.expect("kw", "fn", what="`fn`")
        name = self.expect("ident", what="a function name")
        self.expect("punct", "(", what="`(`")
        if not self.at_punct(")"):
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

        body = self.parse_block()
        return Func(kw.line, kw.col, name.value, ret_type, body)

    def parse_block(self) -> list[Node]:
        self.expect("punct", "{", what="`{`")
        body: list[Node] = []
        while not self.at_punct("}"):
            if self.at("eof"):
                self.expect("punct", "}", what="`}`")
            body.append(self.parse_statement())
        self.expect("punct", "}", what="`}`")
        return body

    def parse_statement(self) -> Node:
        if self.at("kw", "let"):
            return self.parse_let()
        if self.at("kw", "return"):
            return self.parse_return()
        if self.at("kw", "if"):
            return self.parse_if()
        if self.at("kw", "while"):
            return self.parse_while()
        if self.at("kw", "loop"):
            return self.parse_loop()
        if self.at("kw", "break"):
            kw = self.advance()
            self.expect("punct", ";", what="`;`")
            return Break(kw.line, kw.col)
        if self.at("kw", "continue"):
            kw = self.advance()
            self.expect("punct", ";", what="`;`")
            return Continue(kw.line, kw.col)
        return self.parse_expr_or_assign_stmt()

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

    def parse_if(self) -> If:
        kw = self.expect("kw", "if", what="`if`")
        saved = self.no_struct_lit
        self.no_struct_lit = True
        cond = self.parse_expr()
        self.no_struct_lit = saved
        then_branch = self.parse_block()
        else_branch: Optional[list[Node]] = None
        if self.at("kw", "else"):
            self.advance()
            if self.at("kw", "if"):
                else_branch = [self.parse_if()]
            else:
                else_branch = self.parse_block()
        return If(kw.line, kw.col, cond, then_branch, else_branch)

    def parse_while(self) -> While:
        kw = self.expect("kw", "while", what="`while`")
        saved = self.no_struct_lit
        self.no_struct_lit = True
        cond = self.parse_expr()
        self.no_struct_lit = saved
        body = self.parse_block()
        return While(kw.line, kw.col, cond, body)

    def parse_loop(self) -> Loop:
        kw = self.expect("kw", "loop", what="`loop`")
        body = self.parse_block()
        return Loop(kw.line, kw.col, body)

    def parse_expr_or_assign_stmt(self) -> Node:
        # A statement that starts with an expression is either an assignment
        # (`place = expr;`) or a bare expression statement (a `println` call).
        expr = self.parse_expr()
        if self.at_punct("="):
            eq = self.advance()
            value = self.parse_expr()
            self.expect("punct", ";", what="`;`")
            return Assign(eq.line, eq.col, expr, value)
        self.expect("punct", ";", what="`;`")
        return ExprStmt(expr.line, expr.col, expr)

    # Precedence: equality < relational < add/sub < mul/div < unary < postfix
    def parse_expr(self) -> Node:
        return self.parse_equality()

    def parse_equality(self) -> Node:
        node = self.parse_relational()
        while self.at_punct("==", "!="):
            op = self.advance()
            right = self.parse_relational()
            node = Binary(op.line, op.col, op.value, node, right)
        return node

    def parse_relational(self) -> Node:
        node = self.parse_add()
        while self.at_punct("<", "<=", ">", ">="):
            op = self.advance()
            right = self.parse_add()
            node = Binary(op.line, op.col, op.value, node, right)
        return node

    def parse_add(self) -> Node:
        node = self.parse_mul()
        while self.at_punct("+", "-"):
            op = self.advance()
            right = self.parse_mul()
            node = Binary(op.line, op.col, op.value, node, right)
        return node

    def parse_mul(self) -> Node:
        node = self.parse_unary()
        while self.at_punct("*", "/"):
            op = self.advance()
            right = self.parse_unary()
            node = Binary(op.line, op.col, op.value, node, right)
        return node

    def parse_unary(self) -> Node:
        if self.at_punct("-"):
            op = self.advance()
            operand = self.parse_unary()
            return Unary(op.line, op.col, "-", operand)
        return self.parse_postfix()

    def parse_postfix(self) -> Node:
        node = self.parse_primary()
        while self.at_punct("."):
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
            saved = self.no_struct_lit
            self.no_struct_lit = False  # struct literals are fine inside parentheses
            inner = self.parse_expr()
            self.no_struct_lit = saved
            self.expect("punct", ")", what="`)`")
            return inner
        if tok.kind == "ident":
            self.advance()
            if self.at_punct("{") and not self.no_struct_lit:
                return self.parse_struct_lit(tok)
            if self.at_punct("("):
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
        while not self.at_punct("}"):
            fname = self.expect("ident", what="a field name")
            self.expect("punct", ":", what="`:`")
            value = self.parse_expr()
            inits.append((fname.value, value, fname.line, fname.col))
            if self.at_punct(","):
                self.advance()
            else:
                break
        self.expect("punct", "}", what="`}`")
        return StructLit(name.line, name.col, name.value, inits)

    def parse_call(self, callee: Token) -> Call:
        self.expect("punct", "(", what="`(`")
        args: list[Node] = []
        if not self.at_punct(")"):
            args.append(self.parse_expr())
            while self.at_punct(","):
                self.advance()
                args.append(self.parse_expr())
        self.expect("punct", ")", what="`)`")
        return Call(callee.line, callee.col, callee.value, args)


# ---------------------------------------------------------------------------
# Type checker. Types: "i32", "bool", "()" (unit), or a struct name.
# ---------------------------------------------------------------------------

I32 = "i32"
BOOL = "bool"
UNIT = "()"


def loop_has_break(stmts: list[Node]) -> bool:
    """True if `stmts` contains a `break` that targets the enclosing loop.

    Breaks inside a *nested* `while`/`loop` bind to that inner loop, so we do
    not descend into them; we do descend into `if`/`else`.
    """
    for stmt in stmts:
        if isinstance(stmt, Break):
            return True
        if isinstance(stmt, If):
            if loop_has_break(stmt.then_branch):
                return True
            if stmt.else_branch is not None and loop_has_break(stmt.else_branch):
                return True
    return False


def block_returns(stmts: list[Node]) -> bool:
    """Conservatively true if executing `stmts` never falls through the end.

    Counts as "does not fall through": a `return`; an `if`/`else` where both
    branches do not fall through; a `loop` with no `break` targeting it (it
    either returns or runs forever). A `while` may always fall through, so it
    never counts. `break`/`continue` do not return from the function.
    """
    for stmt in stmts:
        if isinstance(stmt, Return):
            return True
        if isinstance(stmt, Loop) and not loop_has_break(stmt.body):
            return True
        if isinstance(stmt, If) and stmt.else_branch is not None:
            if block_returns(stmt.then_branch) and block_returns(stmt.else_branch):
                return True
    return False


class Checker:
    def __init__(self, program: Program, path: str) -> None:
        self.program = program
        self.path = path
        self.structs: dict[str, StructDecl] = {}
        # name -> (type, is_mut)
        self.scope: dict[str, tuple[str, bool]] = {}
        self.loop_depth = 0

    def run(self) -> Func:
        self.collect_structs()
        return self.check_main()

    def collect_structs(self) -> None:
        for decl in self.program.structs:
            seen: set[str] = set()
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
                seen.add(fld.name)
            self.structs[decl.name] = decl
        for decl in self.program.structs:
            for fld in decl.fields:
                if fld.type_name == I32:
                    continue
                if fld.type_name in self.structs:
                    raise Diagnostic(
                        "CRX0015",
                        "struct-typed fields are not supported yet",
                        self.path,
                        fld.line,
                        fld.col,
                        "struct fields must be `i32`",
                    )
                raise Diagnostic(
                    "CRX0021",
                    f"unknown type `{fld.type_name}`",
                    self.path,
                    fld.line,
                    fld.col,
                    "struct field types must be `i32`",
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

        self.check_block(main.body)
        if not block_returns(main.body):
            raise Diagnostic(
                "CRX0011",
                "`main` must return an `i32` on every path",
                self.path,
                main.line,
                main.col,
                "add a `return` (e.g. `return 0;`)",
            )
        return main

    def check_block(self, stmts: list[Node]) -> None:
        # Block scoping: bindings introduced here do not escape the block.
        saved = dict(self.scope)
        for stmt in stmts:
            self.check_stmt(stmt)
        self.scope = saved

    def check_stmt(self, stmt: Node) -> None:
        if isinstance(stmt, Let):
            self.check_let(stmt)
        elif isinstance(stmt, Assign):
            self.check_assign(stmt)
        elif isinstance(stmt, Return):
            self.check_return(stmt)
        elif isinstance(stmt, If):
            self.check_if(stmt)
        elif isinstance(stmt, While):
            self.check_while(stmt)
        elif isinstance(stmt, Loop):
            self.check_loop(stmt)
        elif isinstance(stmt, Break):
            if self.loop_depth == 0:
                raise Diagnostic(
                    "CRX0033",
                    "`break` outside of a loop",
                    self.path,
                    stmt.line,
                    stmt.col,
                    "`break` is only valid inside `while` or `loop`",
                )
        elif isinstance(stmt, Continue):
            if self.loop_depth == 0:
                raise Diagnostic(
                    "CRX0034",
                    "`continue` outside of a loop",
                    self.path,
                    stmt.line,
                    stmt.col,
                    "`continue` is only valid inside `while` or `loop`",
                )
        elif isinstance(stmt, ExprStmt):
            self.check_expr_stmt(stmt)
        else:  # pragma: no cover
            raise Diagnostic(
                "CRX0015", "unsupported statement", self.path, stmt.line, stmt.col
            )

    def check_assign(self, stmt: Assign) -> None:
        target = stmt.target
        if not isinstance(target, VarRef):
            if isinstance(target, FieldAccess):
                raise Diagnostic(
                    "CRX0032",
                    "assignment to a struct field is not supported yet",
                    self.path,
                    target.line,
                    target.col,
                    "only `name = expr;` to a local variable is supported",
                )
            raise Diagnostic(
                "CRX0032",
                "invalid assignment target",
                self.path,
                target.line,
                target.col,
                "the left-hand side must be a local variable name",
            )
        if target.name not in self.scope:
            raise Diagnostic(
                "CRX0027",
                f"unknown variable `{target.name}`",
                self.path,
                target.line,
                target.col,
                "declare it with `let` before assigning to it",
            )
        declared, is_mut = self.scope[target.name]
        if not is_mut:
            raise Diagnostic(
                "CRX0031",
                f"cannot assign to immutable variable `{target.name}`",
                self.path,
                target.line,
                target.col,
                f"declare it as `let mut {target.name}: ...`",
            )
        actual = self.infer(stmt.value)
        if actual != declared:
            raise Diagnostic(
                "CRX0014",
                f"type mismatch: `{target.name}` is `{declared}` "
                f"but the assigned value has type `{actual}`",
                self.path,
                stmt.value.line,
                stmt.value.col,
            )

    def check_while(self, stmt: While) -> None:
        cond_type = self.infer(stmt.cond)
        if cond_type != BOOL:
            raise Diagnostic(
                "CRX0030",
                f"`while` condition must be `bool`, found `{cond_type}`",
                self.path,
                stmt.cond.line,
                stmt.cond.col,
                "use a comparison, e.g. `while i < n { ... }`",
            )
        self.loop_depth += 1
        self.check_block(stmt.body)
        self.loop_depth -= 1

    def check_loop(self, stmt: Loop) -> None:
        self.loop_depth += 1
        self.check_block(stmt.body)
        self.loop_depth -= 1

    def check_if(self, stmt: If) -> None:
        cond_type = self.infer(stmt.cond)
        if cond_type != BOOL:
            raise Diagnostic(
                "CRX0030",
                f"`if` condition must be `bool`, found `{cond_type}`",
                self.path,
                stmt.cond.line,
                stmt.cond.col,
                "use a comparison, e.g. `if x < y { ... }`",
            )
        self.check_block(stmt.then_branch)
        if stmt.else_branch is not None:
            self.check_block(stmt.else_branch)

    def resolve_type(self, name: str, line: int, col: int) -> str:
        if name == I32:
            return I32
        if name == BOOL:
            return BOOL
        if name in self.structs:
            return name
        raise Diagnostic(
            "CRX0021",
            f"unknown type `{name}`",
            self.path,
            line,
            col,
            "known types: `i32`, `bool`, and declared struct types",
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
        self.scope[stmt.name] = (declared, stmt.is_mut)

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
            return self.scope[expr.name][0]
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
            for fld in self.structs[obj_type].fields:
                if fld.name == expr.field_name:
                    return fld.type_name
            raise Diagnostic(
                "CRX0025",
                f"struct `{obj_type}` has no field `{expr.field_name}`",
                self.path,
                expr.line,
                expr.col,
            )
        if isinstance(expr, Unary):
            operand = self.infer(expr.operand)
            if operand != I32:
                raise Diagnostic(
                    "CRX0028",
                    f"unary `-` requires an `i32` operand, found `{operand}`",
                    self.path,
                    expr.operand.line,
                    expr.operand.col,
                )
            return I32
        if isinstance(expr, Binary):
            return self.infer_binary(expr)
        if isinstance(expr, StructLit):
            return self.infer_struct_lit(expr)
        if isinstance(expr, StrLit):
            raise Diagnostic(
                "CRX0015",
                "string values are only supported as `println` arguments yet",
                self.path,
                expr.line,
                expr.col,
            )
        if isinstance(expr, Call):
            self.check_println(expr)
            return UNIT
        raise Diagnostic(  # pragma: no cover
            "CRX0015", "unsupported expression", self.path, expr.line, expr.col
        )

    def infer_binary(self, expr: Binary) -> str:
        left = self.infer(expr.left)
        right = self.infer(expr.right)
        if expr.op in ARITH_OPS:
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
        # Comparison operator.
        if left != I32 or right != I32:
            bad = expr.left if left != I32 else expr.right
            raise Diagnostic(
                "CRX0029",
                f"comparison `{expr.op}` requires `i32` operands, "
                f"found `{left}` and `{right}`",
                self.path,
                bad.line,
                bad.col,
            )
        return BOOL

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

ARITH_HELPER = {"+": "add", "-": "sub", "*": "mul", "/": "div"}

# Runtime helper definitions. Emitted only when referenced; `panic` is pulled in
# by any checked helper. Order here is the emission order.
HELPER_DEFS: dict[str, str] = {
    "panic": (
        "static void crx_panic(const char *msg) {\n"
        '    fprintf(stderr, "panic: %s\\n", msg);\n'
        "    exit(101);\n"
        "}"
    ),
    "add": (
        "static int32_t crx_checked_add_i32(int32_t a, int32_t b) {\n"
        "    int64_t r = (int64_t)a + (int64_t)b;\n"
        '    if (r < INT32_MIN || r > INT32_MAX) crx_panic("i32 addition overflow");\n'
        "    return (int32_t)r;\n"
        "}"
    ),
    "sub": (
        "static int32_t crx_checked_sub_i32(int32_t a, int32_t b) {\n"
        "    int64_t r = (int64_t)a - (int64_t)b;\n"
        '    if (r < INT32_MIN || r > INT32_MAX) crx_panic("i32 subtraction overflow");\n'
        "    return (int32_t)r;\n"
        "}"
    ),
    "mul": (
        "static int32_t crx_checked_mul_i32(int32_t a, int32_t b) {\n"
        "    int64_t r = (int64_t)a * (int64_t)b;\n"
        '    if (r < INT32_MIN || r > INT32_MAX) crx_panic("i32 multiplication overflow");\n'
        "    return (int32_t)r;\n"
        "}"
    ),
    "div": (
        "static int32_t crx_checked_div_i32(int32_t a, int32_t b) {\n"
        '    if (b == 0) crx_panic("i32 division by zero");\n'
        '    if (a == INT32_MIN && b == -1) crx_panic("i32 division overflow");\n'
        "    return a / b;\n"
        "}"
    ),
    "neg": (
        "static int32_t crx_checked_neg_i32(int32_t a) {\n"
        '    if (a == INT32_MIN) crx_panic("i32 negation overflow");\n'
        "    return -a;\n"
        "}"
    ),
}


def c_type(t: str) -> str:
    if t == I32:
        return "int32_t"
    if t == BOOL:
        return "bool"
    return t  # struct name -> its typedef


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


class Emitter:
    def __init__(self, program: Program, main: Func, source_path: str) -> None:
        self.program = program
        self.main = main
        self.source_path = source_path
        self.includes: set[str] = set()
        self.helpers: set[str] = set()

    def use_checked(self, helper: str) -> None:
        self.helpers.add(helper)
        self.helpers.add("panic")
        self.includes |= {"stdint.h", "stdio.h", "stdlib.h"}

    def expr(self, node: Node) -> str:
        if isinstance(node, IntLit):
            return str(int(node.value))
        if isinstance(node, VarRef):
            return node.name
        if isinstance(node, FieldAccess):
            return f"{self.expr(node.obj)}.{node.field_name}"
        if isinstance(node, Unary):  # only "-"
            self.use_checked("neg")
            return f"crx_checked_neg_i32({self.expr(node.operand)})"
        if isinstance(node, Binary):
            if node.op in ARITH_HELPER:
                name = ARITH_HELPER[node.op]
                self.use_checked(name)
                return f"crx_checked_{name}_i32({self.expr(node.left)}, {self.expr(node.right)})"
            return f"({self.expr(node.left)} {node.op} {self.expr(node.right)})"
        if isinstance(node, StructLit):
            parts = ", ".join(
                f".{fname} = {self.expr(value)}" for fname, value, _, _ in node.inits
            )
            return f"({node.type_name}){{ {parts} }}"
        if isinstance(node, StrLit):
            return c_string_literal(node.value)
        raise AssertionError(f"cannot emit expression {node!r}")  # pragma: no cover

    def stmt(self, node: Node, indent: int) -> list[str]:
        pad = "    " * indent
        if isinstance(node, Let):
            self.includes.add("stdbool.h" if node.declared_type == BOOL else "stdint.h")
            return [f"{pad}{c_type(node.declared_type)} {node.name} = {self.expr(node.value)};"]
        if isinstance(node, Assign):
            assert isinstance(node.target, VarRef)
            return [f"{pad}{node.target.name} = {self.expr(node.value)};"]
        if isinstance(node, Return):
            return [f"{pad}return {self.expr(node.value)};"]
        if isinstance(node, While):
            lines = [f"{pad}while ({self.expr(node.cond)}) {{"]
            for s in node.body:
                lines += self.stmt(s, indent + 1)
            lines.append(f"{pad}}}")
            return lines
        if isinstance(node, Loop):
            lines = [f"{pad}for (;;) {{"]
            for s in node.body:
                lines += self.stmt(s, indent + 1)
            lines.append(f"{pad}}}")
            return lines
        if isinstance(node, Break):
            return [f"{pad}break;"]
        if isinstance(node, Continue):
            return [f"{pad}continue;"]
        if isinstance(node, ExprStmt) and isinstance(node.expr, Call):
            self.includes.add("stdio.h")
            arg = node.expr.args[0]
            assert isinstance(arg, StrLit)
            return [f"{pad}puts({c_string_literal(arg.value)});"]
        if isinstance(node, If):
            lines = [f"{pad}if ({self.expr(node.cond)}) {{"]
            for s in node.then_branch:
                lines += self.stmt(s, indent + 1)
            if node.else_branch is not None:
                lines.append(f"{pad}}} else {{")
                for s in node.else_branch:
                    lines += self.stmt(s, indent + 1)
            lines.append(f"{pad}}}")
            return lines
        raise AssertionError(f"cannot emit statement {node!r}")  # pragma: no cover

    def emit(self) -> str:
        body_lines: list[str] = []
        for s in self.main.body:
            body_lines += self.stmt(s, 1)

        struct_lines: list[str] = []
        for decl in self.program.structs:
            self.includes.add("stdint.h")
            struct_lines.append(f"typedef struct {decl.name} {{")
            for fld in decl.fields:
                struct_lines.append(f"    {c_type(fld.type_name)} {fld.name};")
            struct_lines.append(f"}} {decl.name};")
            struct_lines.append("")

        helper_lines: list[str] = []
        for name in HELPER_DEFS:  # fixed order
            if name in self.helpers:
                helper_lines.append(HELPER_DEFS[name])
                helper_lines.append("")

        lines: list[str] = []
        lines.append(f"/* Generated by crustc (CRusty++ v0.1) from {self.source_path} */")
        lines.append("/* Do not edit by hand. */")
        for header in sorted(self.includes):
            lines.append(f"#include <{header}>")
        lines.append("")
        lines.extend(helper_lines)
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
    return Emitter(program, main, path).emit()


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
