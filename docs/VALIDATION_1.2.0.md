# Version 1.2.0 validation

## Expanded catalogues and real-photo regression

Validated on 2026-09-08 on the development Windows machine, using the actual
`backend.pipeline.analyze_image` path: original-file decoding, blind plate solve,
catalogue projection, preview and full-resolution annotated export. No RA/Dec was
supplied manually. Star inventory magnitude limit: V=12; full in-field DSO
inventory (the final `deep` setting); DSO display threshold: 75; sparse labels.
These runs preceded the final appearance-only adjustment to 85% opacity,
18 px text and 1.25 px lines per 1920 px image width; final appearance is
inspected separately. Timings are individual local test runs,
not a cross-machine performance guarantee.

| Real input | Input and output pixels | Full pipeline | Stars in field | Stars fainter than V=7 | DSO-catalogue entries | Added LDN clouds | Peak process working set |
|---|---|---:|---:|---:|---:|---:|---:|
| User's original 28 mm wide field | 9504 × 6336 | 9.186 s | 8,459 | 7,281 | 1,115 | 251 | 789.6 MiB |
| User's original 70 mm wide field | 9504 × 6336 | 4.479 s | 1,603 | 1,385 | 212 | 4 | 779.5 MiB |
| Public Orion wide field | 5218 × 3485 | 2.246 s | 1,260 | 1,035 | 103 | 40 | 485.7 MiB |
| Public Cygnus wide field | 4428 × 3452 | 2.146 s | 1,380 | 1,149 | 218 | 175 | 468.6 MiB |

All four inputs and full-resolution outputs were JPEG; all dimensions matched
exactly, with 8-bit RGB outputs. Annotations require JPEG re-encoding, so output
file byte counts differ from the original. These four runs do not by themselves
validate RAW or high-bit-depth TIFF; those formats require their own decoding and
export checks.

The user's temporary clipboard originals were no longer present at their old
Temp paths. The tests used the original uploaded files preserved in local jobs,
whose stored filenames match the original attachments, rather than resized
previews or already annotated images. Their SHA-256 values are:

- 28 mm: `bc774317c9fc2474e4cd36dc820ff77c843ff84461b0045a3356c4ac5d86bd65`
- 70 mm: `b3c57e2152bb0b94ec8b82c670ef0476c0842b816f4fd6b85df4d2ca6b7d8f28`

The public inputs, credits and licences remain documented in
[the original source record](../tests/network-fixtures/SOURCES_AND_RESULTS.md):
[Orion / Martinbernardi, CC BY 4.0](https://commons.wikimedia.org/wiki/File:Orion_wide_field.jpg)
and [Cygnus / Giuseppe Donatiello, CC0](https://commons.wikimedia.org/wiki/File:Wide_Field_in_Cygnus_(Giuseppe_Donatiello).jpg).

### Astrometric and annotation checks

| Input | Centre RA | Centre Dec | Matched reference stars | Solve RMSE |
|---|---:|---:|---:|---:|
| Original 28 mm | 13.500101° | +40.687531° | 15 | 90.931″ |
| Original 70 mm | 15.818793° | +44.175951° | 20 | 82.896″ |
| Public Orion | 84.416267° | −1.132724° | 22 | 32.335″ |
| Public Cygnus | 310.163882° | +44.989014° | 16 | 68.721″ |

Both original-photo solutions reproduce the stored previous RA, Dec and
horizontal field of view exactly. The public-photo solutions differ by less
than 0.0000005 degrees from the rounded historical reference values. Catalogue
expansion does not change the established plate solution.

Every returned star and DSO entry retained `evidence: catalog_position` and
`pixelDetected: false`. The counts above are catalogue positions projected into
the photo, not claims that thousands of faint stars or dark clouds were measured
from those pixels. Dark-cloud examples in the 70 mm field include LDN 1310,
1296, 1295 and 1299; Orion includes LDN 1617, 1641 and 1630. Cloud centres and
approximate extents come from the actual catalogue.

The full inventories remain available while the initial display recommends only
10 stellar anchors per sample. DSO display recommendations are respectively
25, 7, 8 and 7; label collision handling can reduce the number actually drawn.
New unnamed large LDN clouds do not automatically become initial labels just
because of their angular size. Deep catalogue settings or explicit selection
can expose them. A regression test checks this default separately.

### Data integrity and scientific limits

- Full [HYG v4.1](https://github.com/astronexus/HYG-Database/blob/c7f7f883fe678cc7680169a50ccd7dcc49b060ce/hyg/README.md):
  119,625 unique stars after excluding the Sun, including 104,027 fainter than
  V=7. All 2,253 existing Chinese labels survive their exact HIP identifier join.
  The sparse catalogue tail reaches V=21; this is not completeness to V=21 and
  is not an image detection limit. HYG data is CC BY-SA 4.0.
- [Lynds (1962), CDS VII/7A](https://cdsarc.cds.unistra.fr/viz-bin/ReadMe/VII/7A?format=html&tex=true):
  all 1,791 updated dark-cloud records, with 1,787 published LDN numbers and
  four explicit sequence-based identifiers. Original B1950 coordinates are
  converted to J2000 by VizieR. Opacity class and square-degree area are retained
  as such, never converted into invented magnitudes.
- Combined runtime DSO-catalogue inventory: 15,162 unique entries after excluding
  OpenNGC `NonEx` and `Dup` rows, with 1,793 dark nebulae. This includes 790
  historical NGC/IC entries classified as individual or double stars, so the
  catalogue-entry count is not a count of 15,162 distinct nebulae and galaxies.
- Star API IDs remain stable for HIP entries; non-HIP HYG IDs have their own
  namespace. All 119,625 output IDs are unique. Different extended clouds are
  not merged by angular proximity; Barnard associations can be nested clouds
  rather than equivalent objects.
- HYG coordinates retain epoch/equinox J2000.0. Proper-motion metadata is kept,
  but positions are not propagated to an assumed observation date. High
  proper-motion stars can be displaced in recent photographs; reliable
  date-aware propagation remains a limitation of this catalogue overlay.
- An area-derived circle for an LDN cloud is a size guide, not a measured cloud
  outline. Original cloud-centre accuracy is arcminute-scale; decimal places in
  the coordinate conversion do not add observational precision.

The catalogue-specific suite passes **11 tests**, including real target
coordinates, RA=0 seam handling, faint magnitude filtering, complete inventory
versus default-label separation, primary-ID uniqueness, named-star retention,
the source-preserving IC 434 / NGC 2024 display correction,
dark-cloud units and distributed-artifact checksums. The existing sky-dome data
suite also passes **9 tests**. A cached vector query over the full stellar
catalogue returned 5,245 stars in a 60° test field in about 0.022 s after loading;
this is an isolated catalogue-query measurement, not a full-analysis time.

The reproducible catalogue downloader and provenance are
[`download_faint_catalogs.py`](../scripts/download_faint_catalogs.py) and
[`catalog_manifest.json`](../backend/data/catalog_manifest.json). Local
full-photo QA script, detailed stage timings, JSON results and images are kept
under ignored `.runtime/validation-v1.2.0/`; private uploaded photos are not
included in repository documentation assets.
