# CRusty++ Syntax — Lexical and Grammatical Reference

> Status: **DRAFT**, tracking `v0.1`. Frozen alongside
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
- Whitespace (spaces, tabs, newlines) separates tokens and is otherwise
  insignificant.

## 2. Comments

```
// line comment to end of line
```

- `//` begins a line comment.
- v0.1 has **no** block comments.

## 3. Identifiers and keywords

```
ident   = ( letter | "_" ) ( letter | digit | "_" )*
letter  = "a"…"z" | "A"…"Z"
digit   = "0"…"9"
```

Reserved keywords (may not be used as identifiers):

```
fn  let  mut  struct  return  if  else  while  loop  break  continue
true  false  as
```

Type names (`i8`…`i64`, `u8`…`u64`, `f64`, `bool`, `str`, `String`) and prelude
names (`println`, `print`, `panic`, …) are not keywords but are predeclared;
shadowing them is discouraged and may be rejected.

## 4. Literals

```
int_lit    = digit ( digit | "_" )*
float_lit  = digit ( digit | "_" )* "." digit ( digit | "_" )* ( exponent )?
exponent   = ( "e" | "E" ) ( "+" | "-" )? digit+
bool_lit   = "true" | "false"
string_lit = '"' ( char_escape | not_quote )* '"'
char_escape = "\\" ( "n" | "t" | "\\" | '"' )
```

- Underscores in numeric literals are separators only and carry no value.
- String literals may not span multiple lines in v0.1.

## 5. Operators and punctuation

```
+  -  *  /  %
==  !=  <  <=  >  >=
&&  ||  !
=                       // assignment / binding
&  &mut                 // borrow operators (see memory-model.md)
:  ;  ,  .
( )  { }
->                      // function return arrow
?                       // error-propagation operator (see error-handling.md)
```

Precedence, from tightest to loosest binding:

1. unary `!`, unary `-`, `as`
2. `*` `/` `%`
3. `+` `-`
4. `<` `<=` `>` `>=`
5. `==` `!=`
6. `&&`
7. `||`

Assignment (`=`) is a statement, not an expression, and does not participate in
the precedence table.

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
type        = scalar_type | "str" | "String" | ident | ref_type
scalar_type = "i8" | "i16" | "i32" | "i64"
            | "u8" | "u16" | "u32" | "u64"
            | "f64" | "bool"
ref_type    = "&" "mut"? type
```

`ident` as a type names a previously-declared `struct`. Built-in `Option`/`Result`
shapes are described in [`error-handling.md`](./error-handling.md).

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

### 6.6 Control flow

```
if_stmt     = "if" expr block ( "else" ( if_stmt | block ) )?
while_stmt  = "while" expr block
loop_stmt   = "loop" block
```

The condition of `if` and `while` must be an expression of type `bool`.

### 6.7 Expressions

```
expr        = or_expr
or_expr     = and_expr   ( "||" and_expr )*
and_expr    = eq_expr    ( "&&" eq_expr )*
eq_expr     = rel_expr   ( ( "==" | "!=" ) rel_expr )*
rel_expr    = add_expr   ( ( "<" | "<=" | ">" | ">=" ) add_expr )*
add_expr    = mul_expr   ( ( "+" | "-" ) mul_expr )*
mul_expr    = unary_expr ( ( "*" | "/" | "%" ) unary_expr )*
unary_expr  = ( "!" | "-" ) unary_expr
            | cast_expr
cast_expr   = postfix_expr ( "as" type )?
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

## 7. What is intentionally absent

To keep the grammar small, v0.1 has no syntax for: generics (`<T>`), closures
(`|x| ...`), `match`, `for`, array/index (`a[i]`), method-call (`x.f()` as
dispatch — `.` is field access only), block comments, multi-line strings, or
attributes/annotations. See [`../NON_GOALS.md`](../NON_GOALS.md).
