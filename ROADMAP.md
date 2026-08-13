# Roadmap

OLAP-focused backlog (batch ingest, segment lifecycle — not point writes).
Design context for most of this: [`ARCHITECTURE.md`](ARCHITECTURE.md), especially the invariants in §7.

## Correctness

- Aggregate `ORDER BY` on string group keys — `PostAggregator` still uses `* ±1`; reuse `sort_keys`
- `COUNT(DISTINCT)` across segments — hold decoded values in the set, not per-segment dict IDs
- Typed columns — stop string-coercing everything; fix float/`NaN`, bool, numeric sort/agg

## Feature

- Richer WHERE — ranges, `IN`, inequality; column vs column filters
- Append-on-ingest — a second `ingest` into a table should add a segment, not overwrite one
- Segment layout for many segments — `<table>/segments/seg_XXXXXX/`, discovered by listing or a small `_meta.json`; flat dirs keep loading as a one-segment table
- Segment pruning / routing — open only segments that can match (bounds in metadata)
- Partition-by composite key — Druid-like chunks e.g. `(ts, userId)` for locality + pruning
- HAVING — once post-agg path is solid
- More aggs — `MIN`/`MAX`
- Approx `COUNT(DISTINCT)` — swap the exact decoded set for a mergeable HLL sketch once cardinality hurts; document that distinct becomes approximate, keep exact behind a flag for contrast
- Gorilla-style codecs — delta-of-delta / XOR float encoding for timestamp + metric columns
- Compaction — CLI or background job: K small segments → one new segment with fresh local dictionaries, swapped into the table atomically

## Performance

- Parallel segment fan-out — thread/process pool over `table.segments` inside `QueryExecutor` only; processors and merge stay unaware of it
- N-way merge in `NonAggregateFinalizer` — replace concat-then-sort of local top-K
- Sorted N-way merge for aggregates — emit partial groups in key order and stream the merge, for lower peak memory on high-cardinality `GROUP BY`
- Single-segment GROUP BY decode fast path — skip decode+rehash when `len(segments) == 1`
- Cache hot column metadata / bitmap lookups — `segment.py` TODO
- Bit-pack the encoded list — `ceil(log2(uniq))` bits per row instead of a flat int32, trading arithmetic addressing for size

## Test

- Land non-agg multi-seg / expression `ORDER BY` tests — unstaged `test_segment_integration_non_aggregate.py`
- Merge property tests — split one segment's work into two artificial partials, merge, and compare against the whole-segment result for `COUNT`/`SUM`/`AVG`/`DISTINCT`
- Ingest-twice-then-query test, once append-on-ingest exists

## Refactor

- Package split — `engine/` → `segment_processing/` → storage, with `parsing/` alongside; dependency arrow points one way only (see `ARCHITECTURE.md` §7.2)
- Retire the dead `SegmentColumn.deserialize` / `decode` / `_get_dictionary` paths

## Deferred

- Joins, subqueries / CTEs — not soon
- Global on-disk dictionary
- Distributed broker / historical split
- Schema evolution, catalog service
