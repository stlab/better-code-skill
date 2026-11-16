---
name: contracts
description: Use when writing, editing, or reviewing declaration contracts or documentation comments for functions, methods, types, traits, concepts, or properties in any language.
---

# Better Code Contracts

Write concise, plain-English interface specifications that establish local
reasoning. Describe what a component requires and guarantees, not how its body
works. Apply these principles to public and private declarations in any language,
using the project's documentation syntax.

## Scope and Authority

Better Code governs contract semantics, safety, ownership, and test requirements.
This skill governs contract drafting and formatting; Writing governs expression.
Superpowers governs development process. These boundaries do not require
invoking the companions back from this skill.

For declaration contracts, use this skill instead of Technical Documentation's
parameter, return, and exception templates. Surrounding guides and reference-page
structure remain in Technical Documentation's scope.

When documenting existing code, verify guarantees against the established
specification and relevant implementation. A signature alone does not establish
the full contract. Report missing evidence or discrepancies for resolution;
do not invent guarantees, silently remove promised behavior, or change the API
while editing its documentation.

## Draft and Prune

Derive the full contract before pruning it:

1. Write a present-tense summary fragment ending with a period. For an operation,
   describe its primary effect and result, emphasizing mutation when both occur:
   "Removes and returns the last element." For a type, trait, concept, or property,
   describe what it is: "A resizable random-access sequence of `T`."
   Use established domain terms and notation, such as "the unit value `()`".
   Each qualifier must identify a defined, caller-visible distinction; state the
   property directly when words such as "complete" or "runtime" do not explain it.
2. Retain observable postconditions and public invariants not already captured
   by the summary or the component's established semantic model. Include
   caller-relevant ownership, aliasing, lifetime, invalidation, and concurrency
   guarantees not already supplied by that model.
3. Retain non-obvious preconditions, including semantic laws that syntax cannot
   enforce, such as strict weak ordering or regularity. Omit requirements enforced
   by the signature and requirements necessary for the summary's operation to
   have a meaning, when no alternative outcome is defined. "Removes the last
   element" implies non-empty; "Returns the `i`th element" implies a valid index.
   Keep all caller obligations needed for unsafe-operation safety explicit.
4. State caller-relevant runtime failure conditions and failure-state guarantees
   separately from successful postconditions. Do not enumerate incidental
   propagated errors or dependency error types merely because they can occur.
   An intentional absence result is a successful outcome, not necessarily an
   error: "Removes and returns the last element, or returns `None` if empty."
5. Document non-constant time and space complexity separately, defining the input
   sizes and relevant operation costs. Start with a bound in terms of the affected
   value's area or another caller-visible input measure. Distinguish auxiliary
   space from result storage, and worst-case, amortized, and expected bounds where
   needed. Follow the complexity guidance below.
6. For public APIs, include usage examples illustrating the contract, or reference
   an applicable shared example. Keep examples separate from the summary.

Pruning removes redundant wording, not guarantees. If a simple contract is
difficult to state, raise the design issue rather than hide it with brevity.

## Preconditions and Failures

Do not document unspecified behavior following a precondition violation.
Document non-obvious caller obligations without promising how violations are
detected or what happens afterwards. Safe interfaces must remain memory-safe;
unsafe-operation safety obligations must remain explicit.

If an established API promises an error or panic for an input, preserve that
observable outcome. Do not reclassify the input as an undocumented precondition
violation to shorten the comment. Untrusted input requires validation and
reported runtime errors, not caller-established validity assumptions.

## Signature and Context

Omit guarantees already enforced by the language or signature. Preserve semantic
information they do not establish: `Result` or `Option` does not explain which
inputs produce each alternative; `const` or a reference does not guarantee
logical independence; a syntactically satisfied concept does not establish its
semantic laws.

For an established value type, the summary and semantic model supply copy
equality and mutation independence; the contract needs only actual deviations,
not another paragraph restating those laws. Shared immutable code or metadata
is a representation choice, not an exception to value semantics. Keep any
observable invocation restriction on the callable interface where it applies.
An escaping borrow or an alias to mutable represented state still needs its
caller-relevant lifetime or aliasing contract.

Omit redundant phrases such as "of this struct" when the receiver is clear.
Static methods, associated functions, and module scope do not imply `self`.
Identify the source, destination, or returned reference's owner when multiple
objects could be meant. State when a result aliases caller-owned storage.

## Complexity

Use the simplest verified bound. For linear copying, identify the affected
value's area and any result storage. For replacement, include the old value;
for extraction, identify the selected child rather than the whole parent.
Put verified field-name lookup costs on the lookup operation. Add separate type
description or comparison costs when payload area alone does not bound them.
Use few input-size variables rather than a glossary of implementation steps.

Verify repeated work before claiming linearity: nested path searches can be
quadratic, and per-element type checks can repeat work on shared descriptors.
State which inputs incur a different bound and report the design issue.
Defining a variable as the total work performed does not explain its complexity.

Describe delegation through the operation's normal meaning: "Destroys the held
object." Its type's destruction cost is already implied. Add a verified bound
for built-in types or aggregates separately. Scope stronger allocation,
stack-use, or failure guarantees to the operations for which they are verified.

O(1) time and space are Better Code's default documentation convention, not
evidence about an implementation. Verify the costs before omitting a clause.
Verify initialization and steady-state paths before making allocation or
failure guarantees. Constant complexity does not imply allocation-free or
nonthrowing execution.

Base size measures on the operations actually performed. Zero-byte
representations can still require per-element work; include logical element
counts when the operation visits them. For graph-shaped inputs, count traversed
edges and peak pending work, not just distinct nodes. Memoization does not by
itself establish auxiliary space proportional only to node count.

## Invariants and Implementation Details

Put observable, caller-relevant invariants in the type's documentation. Keep
private representation relationships, such as `xs.len() == ys.len()`, in ordinary
implementation comments next to the fields or operations they constrain.
Record non-obvious maintenance constraints and their reasons there, using
`[knowledge]` when that is the project's convention. Examples include keeping
shared metadata immutable and transferring, rather than duplicating, ownership
when relocating private carriers.

Do not expose private fields, helpers, temporary states, or algorithm steps in
declaration contracts. Retain observable guarantees such as complexity and
invalidation without narrating their implementation.

## Language Formatting

Separate the summary from additional clauses with a blank documentation-comment
line. Prefer plain English to pseudo-code when equally precise.

### C++

C++ precondition violations are unsafe, including violations of conventional
reference-lifetime and mutable-reference non-aliasing obligations. Omit these
conventional obligations from individual contracts; state stronger requirements
and preserve explicit aliasing permissions and promised error outcomes.

Use the project's comment syntax, commonly `///`. Use Doxygen `\pre` and `\post`
for retained clauses when the project uses them. Write complexity as prose;
Markdown formatting is allowed inside Doxygen comments.
Put caller-relevant failure details in a separate paragraph or supported section.
An exception or `std::expected` return does not by itself determine whether an
input is a caller precondition or a reported runtime-error case.

### Rust

Use `///` and Rustdoc sections only for retained information:

- `# Preconditions`: non-obvious semantic requirements.
- `# Safety`: all caller obligations needed to prevent undefined behavior for an
  unsafe operation, including validity and aliasing requirements.
- `# Errors`: caller-relevant failure conditions for a fallible operation.
- `# Panics`: explicitly promised panic outcomes, not unspecified consequences
  of violating preconditions. Preserve established guarantees when editing.
- `# Complexity`: verified non-constant time or space bounds.

## Example

Assume the established specification guarantees that this operation removes and
returns the last element, has constant time and auxiliary-space cost, and defines
no alternative outcome for an empty sequence. Replace the implementation narrative
with its contract:

```cpp
// Before:
/// Pops the last element from the internal `data_` vector by decrementing
/// `size_` and returning the moved value.
/// \pre The vector must not be empty, otherwise behavior is undefined.
/// \post The size decreases by one and preceding elements remain unchanged.
/// Complexity: O(1) time and O(1) auxiliary space.
T pop_back();

// After:
/// Removes and returns the last element.
T pop_back();
```

Non-empty, the size decrease, and the unchanged prefix are implied by the
operation; constant complexity is the documented baseline. A version promising
an absence result on empty input needs that outcome in its summary instead.

## Common Mistakes

| Mistake | Correction |
| ------- | ---------- |
| Remove ownership or failure guarantees to shorten the comment | Prune repeated wording, not caller-relevant semantics. |
| Treat `Result`, `Option`, or references as a complete contract | State outcome conditions and ownership relationships not enforced by types. |
| Describe shared immutable representation as an exception to value semantics | Rely on the established value model; document actual mutable aliases or borrows. |
| Infer constant complexity from a missing clause | Verify the cost; the baseline is a documentation convention. |
| Document a precondition violation's panic as a guarantee | State the obligation; preserve panic behavior only when explicitly promised. |
| Copy a complexity bound from a familiar algorithm | Verify the actual bound, cost model, and auxiliary-space requirement. |
