# Third-party code and data

The root MIT license covers this project's original code, documentation and
synthetic fixtures. It does not grant rights to market data, third-party code,
trademarks or external resources. Keep each applicable upstream license and
notice when redistributing third-party components.

## Dependencies

The base runtime uses the Python standard library. Optional extras and development
tools are installed separately, not vendored in the project wheel. `uv.lock` is the
exact dependency/version inventory; `python scripts/inspect_licenses.py` exports
installed license metadata against that lock without a network request.

| Direct dependency / tool | Declared upstream license / notice |
|---|---|
| yfinance | Apache-2.0 |
| PyArrow | Apache-2.0; upstream distributions carry additional bundled notices |
| NumPy | BSD-3-Clause and bundled component licenses; inspect installed metadata |
| SciPy | BSD-style and bundled component licenses; inspect full upstream notices |
| statsmodels, scikit-learn | BSD-3-Clause |
| Matplotlib | Matplotlib license and bundled notices |
| XGBoost | Apache-2.0; platform wheels may include additional runtime components |
| Streamlit (optional GUI) | Apache-2.0; installed separately, with its dependency notices |
| Hatchling, pytest, Ruff | MIT |

This table summarizes direct dependencies, not all transitive or wheel-bundled
components. The metadata report records missing packages for other platforms;
metadata detection is not a legal compatibility certification. Before distributing
a bundled environment, retain every installed distribution's license/NOTICE files
and inspect native libraries and platform-specific dependencies as well. The
project currently distributes its own source/wheel, not a bundled environment.

The 2026-10-31 publication review checked installed metadata against the lock.
Peewee 4.5.3 (a transitive data dependency) has sparse license metadata; its installed
`dist-info/licenses/LICENSE` and [upstream license](https://github.com/coleifer/peewee/blob/master/LICENSE)
contain the MIT grant. This manual check does not relicense any dependency.
GUI screenshots contain only results computed from this project's synthetic fixtures;
their crops omit local workspace paths and do not alter displayed results.

## Data and external resources

- **Yahoo / yfinance:** the software license does not license Yahoo data.
  [yfinance's official documentation](https://ranaroussi.github.io/yfinance/)
  describes a research/educational tool, directs users to Yahoo's terms and states
  that the Yahoo Finance API is intended for personal use. Check permission for
  your actual use, storage and redistribution. No Yahoo observations are shipped.
- **Nasdaq directories:** the
  [official symbol directory page](https://www.nasdaqtrader.com/trader.aspx?id=symbollookup)
  describes a current-trading-day directory and different permissions for different
  data categories (including separate Fund Network and Events data terms).
  Do not infer a blanket redistribution license or historical membership from
  current availability. Identify the exact feed and its applicable terms first.
- **Fama/French:** the
  [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
  attributes copyright to Eugene F. Fama and Kenneth R. French. Access is not a
  project MIT grant. Preserve attribution, exact source/version and units; verify
  redistribution permission before publishing original files or derived data.
  The library's historical revisions also require explicit input versions.
- Synthetic CSVs, JSON examples and plots generated from them use invented assets
  and fixed dates. No third-party images, fonts or downloaded market data are
  included in the demo or HTML index.

Raw observations, caches, real experiment exports, private accounts and credentials
belong in ignored local directories. `.gitignore` prevents common accidents; it
does not replace a review of every candidate file before a future commit/publication.
