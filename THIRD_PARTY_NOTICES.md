# Third-party notices

Starfield Atlas / 星图寻迹 combines original application code with third-party
software, astronomical catalogues, survey imagery, and public test photographs.
Those third-party materials remain under their own terms and are **not**
relicensed by any project-level licence.

Original Starfield Atlas application code is released under GPL-3.0-only; see
the root [`LICENSE`](LICENSE). This document records provenance and attribution
for separately licensed material and does not replace any referenced licence
text or usage policy.

## Application software

### Aladin Lite 3.8.1

- Copyright: Centre de Données astronomiques de Strasbourg (CDS) and contributors
- Project: <https://github.com/cds-astro/aladin-lite>
- Version: `3.8.1`
- Licence: GNU General Public License version 3, as declared by the package
  metadata and upstream README
- Source archive: <https://github.com/cds-astro/aladin-lite/tree/v3.8.1>

Aladin Lite is bundled into the frontend and powers the HiPS celestial-sphere
viewer. The application keeps the Aladin/CDS credit and source link visible.
Copies of the upstream `COPYING`, `COPYING.LESSER`, and `LICENSE` files must
accompany distributable builds.

### Other direct frontend dependencies

| Component | Bundled version | Licence | Upstream |
| --- | ---: | --- | --- |
| React | 19.2.8 | MIT | <https://github.com/facebook/react> |
| React DOM | 19.2.8 | MIT | <https://github.com/facebook/react> |
| Leaflet | 1.9.4 | BSD-2-Clause | <https://github.com/Leaflet/Leaflet> |
| Vite | 8.2.2 | MIT | <https://github.com/vitejs/vite> |
| `@vitejs/plugin-react` | 6.1.1 | MIT | <https://github.com/vitejs/vite-plugin-react> |
| TypeScript | 7.0.2 | Apache-2.0 | <https://github.com/microsoft/TypeScript> |

### Direct Python/runtime dependencies

| Component | Pinned/range used by the project | Licence | Upstream |
| --- | --- | --- | --- |
| ESA `tetra3` | commit `f9fa2eb9a32a5efc529e2d86f0b59f35b1e9028d` | Apache-2.0 | <https://github.com/esa/tetra3> |
| Pillow | 12.3.0 | MIT-CMU | <https://github.com/python-pillow/Pillow> |
| NumPy | 2.5.2 | BSD-3-Clause and bundled third-party terms | <https://github.com/numpy/numpy> |
| SciPy | 1.18.1 | BSD-3-Clause and bundled third-party terms | <https://github.com/scipy/scipy> |
| rawpy | 0.27.1 | MIT; bundled LibRaw LGPL-2.1/CDDL terms | <https://github.com/letmaik/rawpy> |
| tifffile | 2026.8.23 | BSD-3-Clause | <https://github.com/cgohlke/tifffile> |
| imagecodecs | 2026.8.16 | BSD-3-Clause and bundled codec licences | <https://github.com/cgohlke/imagecodecs> |
| ExifRead | 3.5.1 | BSD-3-Clause | <https://github.com/ianare/exif-py> |
| pywebview | 6.2.1 | BSD-3-Clause | <https://github.com/r0x0r/pywebview> |
| pythonnet | runtime dependency | MIT | <https://github.com/pythonnet/pythonnet> |
| PyInstaller | 6.22.2 | GPL-2.0-or-later with the PyInstaller bootloader exception | <https://github.com/pyinstaller/pyinstaller> |

Additional transitive packages retain the notices shipped in their package
metadata. A release build must carry those installed-package licence files
alongside this notice.

## Astronomical catalogues and sky culture data

| Data | Terms | Project record |
| --- | --- | --- |
| OpenNGC v20260501 | CC BY-SA 4.0 | [`backend/data/LICENSES/OPENNGC-CC-BY-SA-4.0.txt`](backend/data/LICENSES/OPENNGC-CC-BY-SA-4.0.txt) |
| HYG Database v4.1 full stellar catalogue and enrichment | CC BY-SA 4.0 | [`backend/data/LICENSES/HYG-CC-BY-SA-4.0.md`](backend/data/LICENSES/HYG-CC-BY-SA-4.0.md) |
| AT-HYG v3.2 / Tycho-2 indexed stellar extension | CC BY-SA 4.0 | [`backend/data/LICENSES/ATHYG-CC-BY-SA-4.0.md`](backend/data/LICENSES/ATHYG-CC-BY-SA-4.0.md) |
| Lynds dark nebulae, CDS VII/7A | Scientific catalogue attribution and source terms | [`backend/data/LICENSES/LYNDS-DARK-NEBULAE-NOTICE.md`](backend/data/LICENSES/LYNDS-DARK-NEBULAE-NOTICE.md) |
| Hipparcos-derived bright-star data | ESA Hipparcos catalogue notice | [`backend/data/LICENSES/HIPPARCOS-NOTICE.txt`](backend/data/LICENSES/HIPPARCOS-NOTICE.txt) |
| Stellarium Chinese sky-culture names | CC BY-SA 4.0 | [`backend/data/LICENSES/STELLARIUM-CHINESE-SKYCULTURE-NOTICE.md`](backend/data/LICENSES/STELLARIUM-CHINESE-SKYCULTURE-NOTICE.md) |
| Celestial Data / d3-celestial constellation geometry | BSD-3-Clause | [`backend/data/LICENSES/CELESTIAL-DATA-BSD-3-CLAUSE.txt`](backend/data/LICENSES/CELESTIAL-DATA-BSD-3-CLAUSE.txt) |
| ESA `tetra3` data/code notice | Apache-2.0 | [`backend/data/LICENSES/TETRA3-APACHE-2.0.txt`](backend/data/LICENSES/TETRA3-APACHE-2.0.txt) |

Version, integrity, transformation, and source details are recorded in
[`backend/data/catalog_manifest.json`](backend/data/catalog_manifest.json) and
[`backend/catalog_notes.md`](backend/catalog_notes.md).

## Survey imagery and HiPS layers

- **DSS2 colour optical:** Digitized Sky Survey / STScI / Caltech / AAO; served
  as HiPS by CDS. Credits and terms are displayed in the sky viewer.
- **DESI Legacy Surveys:** Legacy Surveys / D. Lang (Perimeter Institute),
  CC BY 4.0. See
  [`backend/data/legacy-survey-dr11/SOURCES.md`](backend/data/legacy-survey-dr11/SOURCES.md).
- **2MASS colour J/H/Ks:** University of Massachusetts and IPAC/Caltech,
  funded by NASA and NSF; colour HiPS by CDS. The packaged transformed overview
  is recorded as ODbL 1.0. See
  [`backend/data/2mass-allsky/SOURCES.md`](backend/data/2mass-allsky/SOURCES.md).

The viewer fetches higher-order tiles only for the user's current view and
retains the provider credits. Blank Legacy areas indicate survey coverage, not
an absence of celestial objects.

## NASA offline object guide

NASA observation images and facts are obtained from official source pages.
Every packaged record stores its own credit, source URL, dimensions, and
SHA-256. NASA content is used factually under the
[NASA Images and Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/).
NASA has not reviewed or endorsed Starfield Atlas. Some NASA pages contain
additional institutional or photographer credits, which remain attached to the
individual records.

See [`backend/data/nasa-deep-sky/SOURCES.md`](backend/data/nasa-deep-sky/SOURCES.md).

### NASA SkyView / DSS2 target cutouts

In addition to the curated NASA images, 68 small DSS2 Red survey cutouts are
bundled, and other catalogue targets can request their own field on demand.
NASA GSFC SkyView provides the cutout service; the underlying Digitized Sky
Survey data retain their original STScI, Palomar/Caltech, ROE and AAO credits and
terms. These survey cutouts are explicitly distinguished from Hubble or other
curated NASA target photographs. They are not relicensed by this application's
GPL, and NASA delivery does not imply that every underlying survey image is
public domain.

The coordinates, reproducible NASA queries, image hashes, dimensions and credits
are recorded in [`backend/data/nasa-survey-cutouts/SOURCES.md`](backend/data/nasa-survey-cutouts/SOURCES.md)
and its manifest. See [SkyView documentation](https://skyview.gsfc.nasa.gov/current/docs/batchpage.html)
and the [SkyView data-use FAQ](https://skyview.gsfc.nasa.gov/current/help/faq.html).

## Public real-sky photographs and README images

### Hubble and Webb telescope test inputs

- `tests/network-fixtures/nasa_hubble_westerlund2.jpg`: Hubble Westerlund 2
  and Gum 29, credit NASA, ESA, A. Nota (ESA/STScI), and the Westerlund 2
  Science Team. [Official source](https://science.nasa.gov/asset/hubble/westerlund-2-2/).
- `tests/network-fixtures/nasa_webb_cosmic_cliffs.png`: Webb NIRCam Cosmic
  Cliffs in NGC 3324, credit NASA, ESA, CSA, STScI.
  [Official source](https://science.nasa.gov/asset/webb/cosmic-cliffs-in-the-carina-nebula-nircam-image/).

These files are unchanged official display renditions, used as factual testing
and educational documentation under the
[NASA Images and Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/).
They retain the individual source credits and are not relicensed under GPL.
No NASA, ESA, CSA, STScI or science-team endorsement is implied. Source URLs,
download variants and SHA-256 hashes are in
[`TELESCOPE_SOURCES.json`](tests/network-fixtures/TELESCOPE_SOURCES.json);
[test results](docs/HUBBLE_WEBB_TESTS.md) distinguish import success from
failed blind solving. Neither image has application annotations added.

### Wide-field photographs

The repository deliberately excludes private user photographs and a local test
image whose redistribution permission was not confirmed.

- **Orion wide field** — photograph by Martinbernardi,
  [Wikimedia Commons source](https://commons.wikimedia.org/wiki/File:Orion_wide_field.jpg),
  licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  The copies in `docs/images/` are resized and, where stated, modified by adding
  Starfield Atlas annotations or application UI.
- **Wide Field in Cygnus** — Giuseppe Donatiello / Giovanni Vincenzo
  Donatiello,
  [Wikimedia Commons source](https://commons.wikimedia.org/wiki/File:Wide_Field_in_Cygnus_(Giuseppe_Donatiello).jpg),
  dedicated under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
  The published preview is resized and modified by adding annotations.
- **ISS006-E-28028 Southern Cross / Carina** — Don Pettit, ISS Expedition 6,
  NASA,
  [official NASA record](https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?frame=28028&mission=ISS006&roll=E).
  The published preview is resized and modified by adding annotations; the
  NASA photo identifier and source credit are retained.

Full source pages, hashes, camera metadata, measured solutions, and usage notes
are documented in
[`tests/network-fixtures/SOURCES_AND_RESULTS.md`](tests/network-fixtures/SOURCES_AND_RESULTS.md)
and [`tests/network-fixtures/SOURCES.md`](tests/network-fixtures/SOURCES.md).
