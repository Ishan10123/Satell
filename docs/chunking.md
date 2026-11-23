# Chunking

The chunking module consumes normalized segment records and source provenance. It emits deterministic chunk identifiers, typed text or code segments, token counts, heading paths, page references, and parent-child links.

## Strategies

- `fixed_size` slices at a configurable character window and character overlap.
- `token_based` uses a caller-supplied tokenizer's encode/decode methods and token window overlap.
- `recursive` tries paragraph, line, sentence, and whitespace boundaries before token windows.
- `heading_aware` packs adjacent segments under the token budget without crossing heading changes.
- `semantic` uses a caller-supplied local similarity function to split adjacent segments below a configured threshold. It is only a hook until an embedding model and similarity evaluation are available.
- `parent_child` creates larger heading-aware parent chunks and smaller child chunks with explicit links.

Code segments remain typed as code and preserve indentation. Oversized code is split at line boundaries where possible; an overlong code line remains intact and is marked oversized. Page numbers and headings are retained on each chunk. Chunk IDs are deterministic for the document, content, strategy, and position.

## Current benchmark limits

`benchmark_chunking_strategies` reports elapsed time, chunk count, average and maximum token count, and oversized chunk count. These are implementation measurements only; they do not measure retrieval precision, recall, MRR, or nDCG. There is no curated retrieval evaluation set or model tokenizer installed in this phase. Tests use a synthetic character tokenizer solely for deterministic behavior checks. No chunk size or strategy has been selected for production.

The values in `configs/chunking.json` are experimental starting points. Replace the tokenizer adapter with the tokenizer associated with the chosen local embedding model before comparing token budgets. Then benchmark retrieval quality and latency on a reviewed evaluation set. Semantic splitting remains disabled unless a local similarity model is supplied and demonstrates improvement.

No real corpus was parsed, normalized, or chunked. The authorization gate remains closed.