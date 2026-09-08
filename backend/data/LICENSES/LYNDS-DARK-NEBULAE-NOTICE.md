# Lynds dark-nebula catalogue attribution

The numeric dark-cloud catalogue in `lynds_dark_nebulae.csv` is derived from:

Beverly T. Lynds (1962), *Catalogue of Dark Nebulae*, Astrophysical Journal
Supplement Series **7**, 1, bibcode `1962ApJS....7....1L`; updated machine-readable
catalogue CDS **VII/7A**, 22 February 1996.

- [Catalogue and byte descriptions](https://cdsarc.cds.unistra.fr/viz-bin/ReadMe/VII/7A?format=html&tex=true)
- [CDS catalogue landing page](https://cdsarc.cds.unistra.fr/viz-bin/cat/VII/7A)
- [NASA HEASARC dataset entry](https://data.nasa.gov/dataset/lynds-catalog-of-dark-nebulae)
- [VizieR data-use and citation terms](https://cds.unistra.fr/vizier-org/licences_vizier.html)

VizieR provides catalogue data for scientific use with attribution to the original
authors and publication. The NASA dataset entry identifies its catalogue as the
HEASARC version of CDS VII/7A and links its licence field to United States
government-works guidance. These records are third-party scientific data, not
application source code; this project does not assert that the original catalogue
is licensed under the application's GPL or the HYG/OpenNGC CC BY-SA licence.

This application has made use of the VizieR catalogue access tool, CDS, Strasbourg,
France. Catalogue citation: Lynds (1962), CDS VII/7A. No original photographic
plates, journal pages or CDS web-interface assets are included.

The downloaded numeric fields are LDN number, running sequence number, cloud area,
opacity class, Barnard associations, and J2000 FK5 coordinates computed by VizieR
from the original FK4 B1950 coordinates. All 1,791 rows are retained. The four
clouds without a published LDN number use explicit `LDN-SEQ-...` identifiers.
Area is square degrees and opacity class is 1–6; neither is a magnitude.

The runtime derives an equivalent-area circle for a rough angular size. It is
not the measured outline of a nebula. The catalogue centres have arcminute-scale
source precision; extra decimal places in converted coordinates do not increase
that precision. Barnard associations can describe contained subclouds, so they
are related identifiers rather than aliases used for deduplication.

Source URL, hashes and transformation details are recorded in
`catalog_manifest.json`. Rebuild with `scripts/download_faint_catalogs.py`.
