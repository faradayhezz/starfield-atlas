# Offline catalogue data

The application ships three local, network-free catalogues under `backend/data/`.
All application coordinates are equatorial degrees. Right ascension is normalised
to `[0, 360)` and declination to `[-90, 90]`.

## OpenNGC deep-sky catalogue

`openngc.csv` is derived from the official OpenNGC snapshot distributed in
PyOngc 1.2.2. That release was published on 2026-05-01 and corresponds to
OpenNGC tag `v20260501`, commit
`36cb178a0f69dba8bfc03a99c10512831edf1c6b`.

- Source: <https://github.com/mattiaverga/OpenNGC/releases/tag/v20260501>
- Packaged source used for deterministic extraction:
  <https://pypi.org/project/PyOngc/1.2.2/>
- Licence: CC-BY-SA-4.0; full text is in
  `data/LICENSES/OPENNGC-CC-BY-SA-4.0.txt`.
- Coverage: all 13,969 main NGC/IC rows plus all 64 OpenNGC addendum rows,
  including M40 and M45; 14,033 rows total and 110 Messier labels.
- Position quality: 14,026 rows have finite coordinates. The seven rows without
  coordinates are explicitly classified `NonEx` by OpenNGC and are retained for
  catalogue completeness. The runtime intentionally skips `NonEx` and `Dup` rows.
- `mag` is V magnitude when available, otherwise B magnitude; `mag_band` records
  the choice. Angular axes are arcminutes and `pa_deg` is degrees.
- OpenNGC models the historically ambiguous M102 as a duplicate of M101. The
  dedicated `M102` row is labelled `102` in this export (instead of repeating
  `101`) so the file exposes all 110 catalogue labels; the runtime still skips
  that `Dup` row and therefore does not draw a second physical target.
- `common_name_en` preserves the upstream common-name field. A small curated set
  of 93 familiar objects also has a Chinese display name; blanks mean “not
  supplied”, not a failed match.

The required leading columns are exactly:
`name,type,ra_deg,dec_deg,major_arcmin,minor_arcmin,pa_deg,mag,messier,common_name_zh`.
Additional compact columns preserve constellation, magnitude band, English common
name, and addendum membership.

## Bright stars

`bright_stars.csv` is a lossless tabular extraction of the star table bundled in
ESA tetra3 0.1 `default_database.npz`. Its metadata identifies the source as the
Hipparcos main catalogue (`hip_main`), an apparent-magnitude ceiling of 7.0,
J2000 equinox, and positions propagated to epoch 2023.0. The original HIP,
coordinate and magnitude columns remain byte-for-byte identical as field values;
only the previously empty `hr`, `name`, and `common_name_zh` columns are enriched.

- Source software: <https://github.com/esa/tetra3>
- Catalogue citation: ESA (1997), *The Hipparcos and Tycho Catalogues*, ESA
  SP-1200; CDS I/239.
- Licence/notice: `data/LICENSES/TETRA3-APACHE-2.0.txt` and
  `data/LICENSES/HIPPARCOS-NOTICE.txt`.
- Coverage: 8,818 rows, 8,818 unique HIP identifiers, magnitude range -1.44 to
  7.00, with finite coordinates for every row.

The HR and international proper-name fields are exact identifier joins against
HYG Database v4.1, not coordinate-radius matches:

- Fixed source: `hyg/CURRENT/hygdata_v41.csv` at archived HYG commit
  `c7f7f883fe678cc7680169a50ccd7dcc49b060ce`.
- Source URL:
  <https://github.com/astronexus/HYG-Database/blob/c7f7f883fe678cc7680169a50ccd7dcc49b060ce/hyg/CURRENT/hygdata_v41.csv>
- Licence: CC BY-SA 4.0; upstream notice is copied to
  `data/LICENSES/HYG-CC-BY-SA-4.0.md`.
- All 8,818 HIP identifiers match exactly one HYG row. This fills 6,033 HR
  identifiers and 319 HYG `proper` names. No Bayer/Flamsteed designation is
  substituted into `name` when HYG's `proper` value is blank.

Traditional Chinese names are sourced from Stellarium's official Chinese
skyculture without machine translation or coordinate guessing:

- Current membership/order authority: `chinese/index.json` and the exact
  Simplified-Chinese translation `chinese/po/zh_CN.po`, Stellarium skycultures
  commit `014fbb5e59233d133c22f9811af96b67d05a95c9`.
- Exact historic labels: Stellarium release `v0.22.2`, peeled commit
  `9275de93251f2e9e6032afdf889332b9c66a248c`, file
  `skycultures/chinese/star_names.zh_CN.fab`.
- Source URLs:
  <https://github.com/Stellarium/stellarium-skycultures/tree/014fbb5e59233d133c22f9811af96b67d05a95c9/chinese>
  and
  <https://github.com/Stellarium/stellarium/blob/9275de93251f2e9e6032afdf889332b9c66a248c/skycultures/chinese/star_names.zh_CN.fab>.
- Licence: CC BY-SA 4.0; attribution and selection details are in
  `data/LICENSES/STELLARIUM-CHINESE-SKYCULTURE-NOTICE.md`.
- The current Chinese index contains 2,255 HIP identifiers in this magnitude
  subset. We use the first verbatim Simplified-Chinese label from the official
  FAB file for 2,252 of them. One later standalone entry is an exact current
  `msgid`/`msgstr` pair (`Southern Star` / `南方之星`), giving 2,253 populated
  Chinese labels in total.
- Current composite entries for HIP 38196 (`Water Level Added X`) and HIP
  106758 (`Deified Judge of Life I`) have no verbatim complete Simplified-
  Chinese label in either fixed source. They remain blank deliberately rather
  than synthesising a name from translated pieces.

## Constellation lines

`constellation_lines.json` converts the J2000 Celestial Data / d3-celestial
constellation polylines into the backend's direct `start`/`end` segment schema.

- Source: <https://github.com/dieghernan/celestial_data/blob/main/data/constellations.lines.geojson>
- Citation: Olaf Frohn and Diego Hernangómez (2023), *Celestial Data*,
  <https://doi.org/10.5281/zenodo.7561601>.
- Licence: BSD-3-Clause; full text is in
  `data/LICENSES/CELESTIAL-DATA-BSD-3-CLAUSE.txt`.
- Coverage: all 88 IAU constellation identifiers and 753 projected line
  segments. There are 89 source feature records because Serpens Caput and
  Serpens Cauda are separate features with the shared `Ser` identifier.
- The transformed source was retrieved on 2026-08-30 and is pinned by the
  artifact SHA-256 in `data/catalog_manifest.json`.

## Integrity summary

| File | Rows/items | Bytes | SHA-256 |
|---|---:|---:|---|
| `openngc.csv` | 14,033 rows | 825,060 | `bc9109ab9549fc063c2feffaf646c8b1e04a94f59ea47217c88ee6f3198bd816` |
| `bright_stars.csv` | 8,818 rows | 365,828 | `bf56aacb85750c3adb0eb6c3502acda27006b10a195c8eeee2c6ee87932a9951` |
| `constellation_lines.json` | 753 segments | 62,848 | `d079ceb22fe565e29b04f50eacfb231506c6e77618127836178373a5e0aa4679` |

The CSV files are UTF-8, comma-delimited, RFC 4180-compatible, and contain a
single header row. `catalog_manifest.json` is the machine-readable provenance
and QA record used for UI/source attribution.
