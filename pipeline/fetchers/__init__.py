"""One module per data source.

Each exposes ``fetch(...) -> payload`` and ``normalize(payload) -> SeriesData``;
the payload is what gets stored in the raw cache, so a cached payload can always be normalized again."""
