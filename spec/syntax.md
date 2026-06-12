# CRusty++ Syntax — Lexical and Grammatical Reference

> Status: **FREEZE-CANDIDATE**, tracking `v0.1`. Frozen alongside
> [`v0.1.md`](./v0.1.md).

This document defines the concrete syntax of CRusty++ `v0.1`: how source text is
tokenized and how tokens form programs. Semantics live in [`v0.1.md`](./v0.1.md),
[`memory-model.md`](./memory-model.md), and
[`error-handling.md`](./error-handling.md).

The grammar is written in a simple EBNF:

- `A B` — `A` followed by `B`
- `A | B` — `A` or `B`
- `A?` — optional
- `A*` — zero or more
- `A+` — one or more
- `( ... )` — grouping
- `"text"` — a literal terminal

---

## 1. Source representation

- Source files are UTF-8 and use the `.crust` extension.
- Line endings may be `\n` or `\r\n`; both are treated as a newline.
- Whitespace separates tokens and is otherwise insignificant.

## 2. Comments

```
// line comment to end of line
```

`//` begins a line comment. v0.1 has **no** block comments.

## 3. Identifiers and keywords

```
ident   = ( letter | "_" ) ( letter | digit | "_" )*
letter  = "a"…"z" | "A"…"Z"
digit   = "0"…"9"
```

Reserved keywords (may not be used as identifiers):

```
fn  let  mut  struct  return  if  else  while  loop  break  continue
true  false  as  unsafe
```

`unsafe` is **reserved** in v0.1 for forward compatibility but has no grammar or
semantics yet (see [`memory-model.md`](./memory-model.md) §6).

Predeclared names (not keywords, but provided by the language; shadowing is
discouraged and may be rejected):

- Type names: `i8`…`i64`, `u8`…`u64`, `usize`, `f64`, `bool`, `str`, `()`,
  `Option`, `Result`, `FileError`.
- Constructors: `Ok`, `Err`, `Some`, `None`.
- Prelude functions: `print`, `println`, `read_all_bytes`, `is_ok`, `is_err`,
  `unwrap`, `panic` (see [`v0.1.md`](./v0.1.md) §2.9).

## 4. Literals

```
int_lit    = digit ( digit | "_" )*
float_lit  = digit ( digit | "_" )* "." digit ( digit | "_" )* ( exponent )?
exponent   = ( "e" | "E" ) ( "+" | "-" )? digit+
bool_lit   = "true" | "false"
string_lit = '"' ( char_escape | not_quote )* '"'
char_escape = "\\" ( "n" | "t" | "\\" | '"' )
```

- Underscores in numeric literals are separators only.
- A string literal has type `str`.
- An integer literal is **context-typed**, defaulting to `i32`; a float literal
  defaults to `f64` ([`v0.1.md`](./v0.1.md) §2.2).
- String literals may not span multiple lines in v0.1.

## 5. Operators and punctuation

```
+  -  *  /  %
==  !=  <  <=  >  >=
&&  ||  !
=                       // assignment / binding
&  &mut                 // borrow operators (reserved; see memory-model.md)
:  ;  ,  .
( )  { }  [ ]  < >
->                      // function return arrow
?                       // error-propagation operator (see error-handling.md)
```

There is **no `::`** in v0.1. `[ ]` appears only in the slice *type* form `[]T`
(§6.4); there is no index expression `a[i]`. `< >` appear only in the two
built-in core-constructor type forms (§6.4); there is no general generic syntax.

Precedence, from tightest to loosest binding:

1. unary `!`, unary `-`
2. `as` (cast)
3. `*` `/` `%`
4. `+` `-`
5. `<` `<=` `>` `>=`
6. `==` `!=`
7. `&&`
8. `||`

So `as` binds **looser than unary** but **tighter than the multiplicative and
additive operators**: `-x as T` is `(-x) as T`, and `a as T + b` is
`(a as T) + b`. Parenthesize where a different grouping is intended. Casts are
left-associative (`a as i32 as u8` is `(a as i32) as u8`).

Assignment (`=`) is a statement, not an expression.

## 6. Grammar

### 6.1 Program

```
program     = item*
item        = function | struct_def
```

### 6.2 Functions

```
function    = "fn" ident "(" params? ")" ret_type? block
params      = param ( "," param )* ","?
param       = ident ":" type
ret_type    = "->" type
```

### 6.3 Structs

```
struct_def  = "struct" ident "{" fields? "}"
fields      = field ( "," field )* ","?
field       = ident ":" type
```

### 6.4 Types

```
type        = scalar_type | slice_type | core_type | "str" | "()" | ident | ref_type
scalar_type = "i8" | "i16" | "i32" | "i64"
            | "u8" | "u16" | "u32" | "u64"
            | "usize" | "f64" | "bool"
slice_type  = "[" "]" elem_type
elem_type   = "u8"                        // v0.1 only requires byte slices
core_type   = "Option" "<" type ">"
            | "Result" "<" type "," type ">"
ref_type    = "&" "mut"? type
```

- `slice_type` is restricted to `[]u8` in v0.1; the general `[]T` form is not yet
  exercised. `str` is a built-in text slice and is spelled `str`, not `[]u8`.
- `core_type` recognizes **only** `Option<...>` and `Result<...>`. This is fixed
  built-in sugar, **not** user-definable generics (see
  [`../NON_GOALS.md`](../NON_GOALS.md)).
- `ident` as a type names a previously-declared `struct` or the built-in
  `FileError`.
- `ref_type` is recognized for forward compatibility; examples and the first
  prototype do not require references ([`memory-model.md`](./memory-model.md) §6).

### 6.5 Blocks and statements

```
block       = "{" statement* "}"
statement   = let_stmt
            | assign_stmt
            | return_stmt
            | if_stmt
            | while_stmt
            | loop_stmt
            | break_stmt
            | continue_stmt
            | expr_stmt

let_stmt    = "let" "mut"? ident ":" type "=" expr ";"
assign_stmt = place "=" expr ";"
return_stmt = "return" expr? ";"
break_stmt  = "break" ";"
continue_stmt = "continue" ";"
expr_stmt   = expr ";"

place       = ident ( "." ident )*
```

A slice's `.len` is read via ordinary field access (`place = ident "." "len"`);
it is not assignable.

### 6.6 Control flow

```
if_stmt     = "if" expr block ( "else" ( if_stmt | block ) )?
while_stmt  = "while" expr block
loop_stmt   = "loop" block
```

The condition of `if` and `while` must have type `bool`.

### 6.7 Expressions

```
expr        = or_expr
or_expr     = and_expr   ( "||" and_expr )*
and_expr    = eq_expr    ( "&&" eq_expr )*
eq_expr     = rel_expr   ( ( "==" | "!=" ) rel_expr )*
rel_expr    = add_expr   ( ( "<" | "<=" | ">" | ">=" ) add_expr )*
add_expr    = mul_expr   ( ( "+" | "-" ) mul_expr )*
mul_expr    = cast_expr  ( ( "*" | "/" | "%" ) cast_expr )*
cast_expr   = unary_expr ( "as" type )*
unary_expr  = ( "!" | "-" ) unary_expr
            | postfix_expr
postfix_expr = primary ( "." ident | "?" )*
primary     = int_lit | float_lit | bool_lit | string_lit
            | ident
            | call
            | struct_lit
            | borrow
            | "(" expr ")"

call        = ident "(" args? ")"
args        = expr ( "," expr )* ","?
struct_lit  = ident "{" field_inits? "}"
field_inits = field_init ( "," field_init )* ","?
field_init  = ident ":" expr
borrow      = "&" "mut"? expr
```

The constructors `Ok`, `Err`, `Some`, and `None` are ordinary `call`s over
predeclared names (`Ok(x)`, `Err(e)`, `Some(v)`, `None()` / `None`). Postfix `?`
applies to a `Result`-typed expression ([`error-handling.md`](./error-handling.md)
§3).

## 7. What is intentionally absent

To keep the grammar small, v0.1 has **no** syntax for: user generics (`struct
Foo<T>`, `fn id<T>`), closures (`|x| ...`), `match`, `for`, index expressions
(`a[i]`), method calls (`x.f()` — `.` is field access only), block comments,
multi-line strings, attributes, namespacing (`::`), an owned `String` type, or a
`void` keyword (a value-less function omits `-> T` and returns `()`). The only
angle-bracket types are the two built-in `core_type` forms (§6.4). See
[`../NON_GOALS.md`](../NON_GOALS.md).
