# Stellar catalogue and performance — 1.3.0

Verified on Windows on 2026-09-08. The application now contains **2,552,824
stellar entries**: the existing **119,625 HYG v4.1** stars plus **2,433,199
additional AT-HYG v3.2 / Tycho-2** stars. Stars are an independent catalogue
layer, not the historical stellar records in the deep-sky catalogue.

## Source and coverage

The source is David Nash / Astronexus's
[AT-HYG v3.2 author snapshot](https://github.com/astronexus/ATHYG-Database/tree/650346e2bc57f664eb411bc5f44ffd94b8006af2),
distributed under CC BY-SA 4.0. Two complete source files contain 2,552,165
rows. Excluding the Sun and 118,965 author-supplied exact HYG cross-identifiers
leaves 2,433,199 additional TYC stars. Existing HYG coordinates, Chinese names,
and identifiers remain intact. No coordinate-distance deduplication removes
close stellar components.

The additional coordinates are J2000.0 and the magnitudes are Tycho **VT**;
existing HYG **V** magnitudes remain labelled separately. The extension includes
547,068 entries fainter than VT 12, with its faintest entry at VT 15.193.
This is **not** complete all-sky coverage to that magnitude: the
[NASA Tycho-2 reference](https://heasarc.gsfc.nasa.gov/w3browse/all/tycho2.html)
reports approximately 90% completeness at V 11.5. It is not a full Gaia DR3
catalogue. Projected catalogue coordinates do not prove that an exposure
detected a faint star.

The 432 compressed spatial cells total **49,837,728 bytes** (47.53 MiB), with
the largest file 526,404 bytes. Frame queries open intersecting sky cells and
cache at most eight numeric cells. The full in-frame stellar inventory is
retained; the independent sparse/balanced/dense stellar annotation setting
controls label selection rather than discarding catalogue records.

## Real-photo end-to-end checks

Each input was analysed in a fresh process using the normal pipeline, the
default magnitude limit of 12, and balanced stellar annotation density.
The test includes original-photo decoding, a fresh plate solve, full catalogue
projection, preview generation, native-size JPEG annotation, and JSON writing.
The original 9504 × 6336 private photographs were not resized before analysis.

| Input | Source and exported pixels | In-frame HYG | Added TYC | Total stars | Deep-sky entries |
| --- | --- | ---: | ---: | ---: | ---: |
| Private 28 mm wide field | 9504 × 6336 | 8,459 | 151,617 | **160,076** | 1,115 |
| Private galaxy-group field | 9504 × 6336 | 679 | 7,652 | **8,331** | 101 |
| Public Orion photograph | 5218 × 3485 | 1,260 | 16,799 | **18,059** | 103 |

The solved fields are respectively 63.84° × 45.10°, 19.62° × 13.15°, and
23.19° × 15.61°. All three runs completed, and each output retained the source
pixel dimensions and JPEG format. Counts are available catalogue positions at
the selected magnitude, not counts of independently detected stars.

| Input | Stellar query | Whole pipeline | Peak working set | Full stored JSON | Full JSON response equivalent |
| --- | ---: | ---: | ---: | ---: | ---: |
| Private 28 mm wide field | 1.311 s | 12.587 s | 1,494.6 MiB | 125.96 MiB | 96.20 MiB |
| Private galaxy-group field | 0.497 s | 5.868 s | 791.2 MiB | 6.65 MiB | 5.09 MiB |
| Public Orion photograph | 0.448 s | 2.509 s | 513.8 MiB | 14.15 MiB | 10.79 MiB |

Peak memory is the Windows process peak working set, including decoding,
solver, catalogue, full-resolution rendering and serialization, not just the
small spatial cache. Times exclude upload/download and browser work, and are
measurements on the validation machine rather than speed guarantees. The
response-equivalent column measures the complete uncompressed dictionary with
Python's ordinary JSON encoding; it is a payload-size benchmark, not a claim
that every UI request needs to transfer the full inventory. The widest field
shows why lightweight result loading and paginated catalogue browsing matter.

The public image is
[Orion wide field by Martinbernardi](https://commons.wikimedia.org/wiki/File:Orion_wide_field.jpg),
CC BY 4.0; see the existing
[photo source record](../tests/network-fixtures/SOURCES_AND_RESULTS.md).
Private photographs, source locations, EXIF and generated private imagery are
not included in this report or published as test material.

## Reproducibility and integrity

- `scripts/download_tycho_catalog.py` rebuilds the spatial data from the
  pinned author files and rejects mismatched SHA-256 hashes.
- `backend/data/athyg_v32/manifest.json` records source hashes, exact counts,
  transformations, passbands and all 432 file hashes.
- All six top-level catalogue artifact hashes match `catalog_manifest.json`.
  Catalogue tests also verified every spatial file, all added identifier
  uniqueness, RA=0 wraparound, both celestial poles, and HYG name preservation.
- The **15 catalogue tests passed**. This report does not substitute for the
  release's full backend, browser and packaged-application checks.
- `scripts/benchmark_stellar_catalog.py --input PHOTO --label GENERIC_LABEL
  --output LOCAL_DIRECTORY` reproduces a cold-process measurement. Its
  `benchmark.json` uses the generic label and excludes original input paths
  and EXIF data; source/result files in the chosen directory remain private.

Licence and transformation details:
[AT-HYG attribution](../backend/data/LICENSES/ATHYG-CC-BY-SA-4.0.md).
