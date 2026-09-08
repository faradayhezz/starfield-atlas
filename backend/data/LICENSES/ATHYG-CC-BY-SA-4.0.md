# AT-HYG v3.2 stellar catalogue attribution

Creator: David Nash / Astronexus and the authors of its cited astronomical catalogues.

The AT-HYG v3.2 data is licensed under the Creative Commons
Attribution-ShareAlike 4.0 International licence:
<https://creativecommons.org/licenses/by-sa/4.0/>.

Pinned author snapshot:
<https://github.com/astronexus/ATHYG-Database/tree/650346e2bc57f664eb411bc5f44ffd94b8006af2>

Upstream licence declaration:
<https://github.com/astronexus/ATHYG-Database/blob/650346e2bc57f664eb411bc5f44ffd94b8006af2/LICENSE>

The upstream project has since moved to <https://codeberg.org/astronexus/athyg>.
This application intentionally distributes the independently reproducible v3.2
snapshot, not a claim about the latest upstream version.

This application's modified data includes 2,433,199 additional Tycho stars.
The Sun and records already explicitly linked by the author to the bundled
HYG v4.1 identifiers are excluded. Distinct Tycho components are not merged
by coordinate proximity. The original HYG catalogue and its display names are
retained separately. The resulting combined stellar inventory has 2,552,824
entries.

Transformations: keep source IDs, J2000.0 right ascension/declination,
apparent magnitude and passband, HIP/HD cross-references where present, and
proper motions; convert RA hours to degrees; quantize coordinates to 1e-7
degree (0.00036 arcsecond); encode the source's millimagnitude precision as an
integer; divide the sky into 432 spatial cells; compress numeric NumPy columns.
The modified data remains CC BY-SA 4.0. No endorsement by the source authors
or astronomical institutions is implied.

Rebuild instructions and cryptographic source hashes are in
`scripts/download_tycho_catalog.py`. Per-cell hashes, counts, source metadata,
and transformation details are in `backend/data/athyg_v32/manifest.json`.

All additional records have Tycho-derived positions at J2000.0 and Tycho VT
magnitudes. VT is not the same photometric band as Johnson V. The mixed
inventory retains the individual band's name on every result. Proper motion
values in AT-HYG may be from its Gaia cross-match; that does not turn the
position/photometry catalogue into the complete Gaia DR3 catalogue.

Tycho-2 catalogue reference: Høg, E. et al. (2000), Astronomy & Astrophysics,
355, L27–L30, “The Tycho-2 Catalogue of the 2.5 Million Brightest Stars.”
<https://heasarc.gsfc.nasa.gov/w3browse/all/tycho2.html>

Tycho-2 is approximately 90% complete at V = 11.5. The faintest stored entry
does not imply complete all-sky coverage at that magnitude. A projected
catalogue position is not evidence that the user's exposure detected it.
