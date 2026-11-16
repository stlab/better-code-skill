# Operation Costs: A Design Reference

These figures summarize selected estimates from
[IT Hare / 6it: Infographics, Operation Costs in CPU Clock Cycles][source].
They are historical, hardware-dependent illustrations of relative costs, not
measurements of the current target or promises about modern processors.

Use them to avoid unnecessary work when equally clear designs are available.
Do not use them to justify more complicated code, weaker safety guarantees, or
performance claims without measurement.

## Approximate Costs

| Operation | CPU cycles reported in the article | Conditions and limitations |
|---|---:|---|
| Simple register ALU operation | Around 1; throughput can be below 1 | Independent operations can overlap. Sub-cycle throughput is not sub-cycle latency. |
| Integer multiplication | 1-7 | Operand width and processor matter. |
| Integer division | 12-44 | Operand width and processor matter. |
| L1 / L2 / L3 cache read | 4 / 12 / 44 | Representative Skylake figures; shared cache lines can cost more. |
| Branch misprediction | 10-20 | Prediction behavior and pipeline vary. |
| Main-memory read | Around 180 | Based on about 60 ns at 3 GHz, not a universal latency. |
| CAS / atomic read-modify-write | 15-30 | The cited estimate assumes a single core and data already in L1; not a contention estimate. |
| Small-object heap allocation/deallocation | 200-500 | Allocator-dependent estimate, excluding downstream locality penalties. |
| Kernel call | 1,000-1,500 or more | Varies by operation and OS; not the cost of every API call. |
| Thread context switch | Around 2,000 direct | Cache effects are separate and can dominate, reaching millions of cycles in the cited workloads. |

## Implications for Code

- Favor compact storage and locality. An extra dependent memory access can cost
  more than several arithmetic operations, especially outside the cache.
- Avoid unnecessary allocations and intermediate collections. Allocator time is
  only part of their cost; scattered objects also affect cache behavior.
- Avoid unnecessary indirection and dynamic dispatch. Their cost depends on
  prediction, locality, inlining opportunities, and call frequency; there is no
  universal fixed virtual-call penalty.
- Prefer ownership and higher-level concurrency over shared-state coordination.
  A cached atomic estimate says nothing about contention, cache-line bouncing,
  NUMA placement, blocking, or wakeup costs.
- Keep work appropriately coarse-grained. Scheduling and context switching can
  outweigh tiny tasks, but this does not justify blocking or busy-waiting.
- Do not replace a clear branch or division with a clever transformation based
  only on this table. Compilers, dependencies, and actual inputs affect the
  result.

## Reading the Numbers Correctly

Latency, reciprocal throughput, and end-to-end elapsed time are different
quantities. Do not add the rows as though operations always execute serially.
Out-of-order execution, memory-level parallelism, vectorization, and compiler
optimization change how costs combine.

Cache and memory figures describe particular access conditions, not arbitrary
container operations. Mutexes, condition variables, actors, queues, and futures
have no single cost inferable from this table. Their implementations may allocate
or synchronize internally; using a higher-level mechanism is an ownership and
correctness decision, not a claim that its implementation is free.

For consequential choices, profile a representative optimized build on the
target hardware with realistic inputs and concurrency. Separate direct costs
from indirect cache effects, and measure throughput and tail latency as
appropriate. Preserve contracts, safety, and security settings.

[source]: https://6it.dev/blog/infographics-operation-costs-in-cpu-clock-cycles-741
