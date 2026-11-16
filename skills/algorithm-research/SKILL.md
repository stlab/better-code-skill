---
name: algorithm-research
description: >
  Companion skill to the Anthropic superpower skill. Triggers automatically
  after an implementation plan has been produced for any coding task. Use this
  skill whenever an implementation plan, technical design, or architectural
  breakdown exists and you are about to begin writing code. Performs a focused
  research pass to identify standard algorithms, known data structures, and
  well-established library solutions that could replace or simplify custom
  implementation work. Always invoke this skill between the implementation
  planning phase and the coding phase — even if the plan seems straightforward,
  even if the task feels routine. Skipping this step risks reinventing
  well-solved problems.
---

# Algorithm Research — Implementation Companion

Run this pass **after** implementation planning and **before** writing any code.
The goal is a concise research note that feeds directly into the coding phase.

---

## Step 1: Decompose the Plan into Sub-problems

Read the implementation plan and extract each distinct computational sub-problem.
For each one, write a one-line description in plain terms — strip away domain
language and reduce to what the computation actually does.

Examples of good decompositions:
- "rank items by a composite score" → weighted sort
- "find all nodes reachable from a starting node" → graph traversal
- "avoid recomputing expensive results for the same input" → memoization / caching
- "merge N sorted streams into one" → k-way merge
- "check whether any two intervals overlap" → interval sweep

---

## Step 2: Pattern-match Against Known Algorithm Families

For each sub-problem, check it against these families. Mark any that apply.

**Sorting & Ordering**
- Simple sort, stable sort, topological sort, partial sort (nth-element), argsort

**Searching & Lookup**
- Binary search, interpolation search, hash lookup, trie lookup, bloom filter

**Graph & Tree**
- BFS, DFS, Dijkstra, A*, Bellman-Ford, Floyd-Warshall
- Union-Find / Disjoint Set, spanning tree (Kruskal / Prim)
- Tree traversals, lowest common ancestor, segment tree, fenwick tree

**Dynamic Programming & Recursion**
- Memoization, tabulation, divide & conquer
- Classic shapes: knapsack, LCS, edit distance, coin change, interval DP

**String & Sequence**
- Sliding window, two pointers, prefix sums
- KMP, Rabin-Karp, suffix array, Aho-Corasick

**Geometry & Spatial**
- Convex hull, sweep line, R-tree / k-d tree, quadtree

**Probability & Sampling**
- Reservoir sampling, Fisher-Yates shuffle, consistent hashing

**Concurrency & Coordination**
- Producer-consumer, work-stealing queue, compare-and-swap patterns

**Data Structure Fits**
- Stack, queue, deque, heap / priority queue
- Monotonic stack / queue, LRU cache, skip list

If a sub-problem matches nothing above, note it explicitly as **custom logic** —
that is useful signal, not a failure.

---

## Step 3: Identify Standard Library & OSS Coverage

For each matched pattern, check whether a well-maintained implementation already
exists in:

1. **Language stdlib** — built-ins, standard collections, itertools, etc.
2. **Canonical ecosystem library** — numpy, scipy, networkx, Boost, Guava,
   Apache Commons, etc. (pick what's relevant to the project's language/stack)
3. **Well-known OSS** — a widely-used package that is effectively the community
   standard for this problem

For each candidate, note:
- Library name + specific function / class
- License (flag anything non-permissive)
- Any meaningful limitation (e.g. "doesn't support weighted edges",
  "O(n²) for n > 10k")

---

## Step 4: Complexity Sanity Check

For each sub-problem — whether covered by a library or custom — estimate:

| Sub-problem | Expected input size | Acceptable complexity | Candidate complexity | Pass? |
|---|---|---|---|---|
| … | … | … | … | ✓ / ✗ / ? |

Flag any mismatch. If a known algorithm exists but has the wrong complexity
profile for the expected scale, say so and note whether a better variant exists.

---

## Step 5: Produce the Research Note

Write a compact note (aim for under 300 words) structured as:

```
## Algorithm Research Note

### Covered by stdlib / OSS
- <sub-problem>: use <library.function> — <one-line rationale>

### Covered by known algorithm (implement directly)
- <sub-problem>: <algorithm name> — <one-line rationale, complexity>

### Custom logic (no standard match)
- <sub-problem>: <brief description of why it's custom>

### Complexity flags
- <any mismatches or scale concerns>

### Recommendation
<1–3 sentences summarising the most important findings and what to do with them>
```

This note is the handoff to the coding phase. The coding phase should treat
anything in "Covered by stdlib / OSS" as a strong default — prefer the known
implementation unless there is a concrete reason not to.

---

## Notes on Scope

- **Don't gold-plate.** If the implementation plan is small and all sub-problems
  are trivially simple (e.g. a single linear scan), say so briefly and move on.
  The research pass should be proportional to the complexity of the plan.
- **Don't block on uncertainty.** If you can't confidently identify an algorithm
  match, mark it as custom logic and proceed. A wrong match is worse than no match.
- **This is research, not commitment.** The coding phase can override any
  recommendation here if context warrants it. The note is input, not a contract.
