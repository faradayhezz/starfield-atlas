# Wide phone photograph verification — 1.3.0

Verified on 2026-09-09 using the user's actual, unannotated **4032 × 3024 JPEG**.
The image contains a strong sky-brightness gradient, sparse visible stars and
buildings along the lower edge. The transferred file has no camera, focal-length
or capture-time EXIF. Camera details shown in a separate reference screenshot
were not inserted into the file or used as solver hints. Neither the image nor
private source paths are distributed in the repository.

## Cause and change

The previous no-EXIF search tried the whole image and central crops at 42% and
68% of the width. In a roughly 70° rectilinear field these crops are too wide
for the existing 10°–30° Hipparcos pattern index. The actual photograph failed
the old search in 12.45 seconds.

The new search adds a **32% central crop**, corresponding to about 25° for a
70° camera. It tries the first extraction profile at each scale before spending
the remaining time budget on other profiles. Crops retain the exact full-frame
centre, including odd-sized inputs. This is a general field-scale strategy;
no target coordinates, camera model or reference-image features enter solving.

The new small-crop wide-field path then validates the full projection with
additional bright stars from the existing ESA/Hipparcos database. Refinement
keeps the principal point at the full image centre and adjusts rotation, focal
scale and radial distortion. The radial coefficient is converted correctly
from crop-width to full-image-width normalization before refinement. It does
not treat an off-axis crop as the centre of the original photograph.

One quarter of candidate catalogue stars are held out of the calibration fit.
Acceptance requires at least eight held-out matches, at least eight held-out
matches outside the original crop, sufficiently broad spatial coverage, and
the unchanged 180 arcsecond residual ceiling. Mutual nearest-neighbour matches
avoid counting one image point twice. No new catalogue download or weaker
false-positive threshold was needed.

## Actual result

| Measurement | Result |
| --- | ---: |
| Initial blind pattern matches | 22 |
| Pattern false-positive score | 9.59 × 10⁻²⁷ |
| Full-field validation anchors | 106 |
| Held-out anchors / outside the original crop | 26 / 16 |
| Anchor span across image width / height | 85.1% / 83.8% |
| Global residual | 168.50 arcsec / 2.60 original pixels RMS |
| Held-out residual | 167.25 arcsec / 2.57 original pixels RMS |
| Centre RA / Dec | 290.37166° / 29.30741° |
| Roll | 290.33605° |
| Calibrated field width / height | 69.97110° / 55.60363° |
| Plate solving, including full-field validation | 1.310 s |
| Complete source pipeline | 9.096 s |
| Output | JPEG, 4032 × 3024 |

Coordinates and field dimensions come from the photograph's stellar geometry.
The separate screenshot provides only a coarse post-solve comparison, not a
high-precision reference calibration. The reported vertical field is computed
from the calibrated perspective and radial model, not by multiplying horizontal
degrees by the image aspect ratio.

A separate check measured the brightest source inside a small region around
three known stars directly in the original JPEG. Residuals below are source
centroid minus the projected HYG position, in original pixels; the reference
annotation image was not used to move any coordinates.

| Star | Predicted x, y | Source centroid x, y | dx, dy | Distance |
| --- | --- | --- | --- | ---: |
| Vega, HIP 91262 | 2641.73, 1750.84 | 2640.47, 1749.89 | −1.26, −0.95 | 1.58 px |
| Altair, HIP 97649 | 885.74, 1517.78 | 880.96, 1517.91 | −4.78, +0.12 | 4.79 px |
| Deneb, HIP 102098 | 2616.09, 495.80 | 2618.49, 492.06 | +2.39, −3.74 | 4.44 px |

Vega was held out of calibration and accepted as a final validation inlier.
Altair and Deneb were training candidates but fell outside the final strict
inlier threshold. Their slight additional differences from the fit-stage
residual arise from measuring full-resolution source centroids here instead
of the smaller solving proxy and from HYG versus solver catalogue epochs.
The reported 2.60 px RMS describes the 106 accepted anchors; it is not a
maximum-error guarantee for every star. This photograph still has roughly
4–5 px residuals on these two bright stars, about 2 px at a 1920 px preview.

The full catalogue query at magnitude 12 returned **266,351 stellar positions**
(10,833 HYG + 255,518 additional TYC) and 1,096 deep-sky records. These are
catalogue positions, not 266,351 stars detected in this short phone exposure.
The complete uncompressed response equivalent was about 168.17 MB and process
peak working set about 2.13 GB; full wide-field inventories remain memory-heavy.
The normal server supports gzip responses and the table renders paginated rows.

## Regression checks and limits

- Both public ESA 16-bit camera fixtures still solve to their reference fields.
- The existing 63.84° DSLR original retains its previous centre, rotation and
  field size within floating-point rounding, with 15 matches and a 4.39 × 10⁻¹²
  false-positive score. Its established hinted-crop path is unchanged.
- Existing cancellation and orientation controls pass.
- Crop-geometry tests cover the metadata-free wide case and odd image sizes;
  a blank negative control cannot produce full-frame validation evidence.
- The private positive regression is opt-in with `STARFIELD_PHONE_FIXTURE`;
  it reads a local file and uses the reference coordinates only as assertions
  after a blind solve. The fixture is not included in the repository.

The optional `wcs.verification` result records anchor counts, held-out counts,
coverage and residuals. It is present for the new validated wide-crop route;
the original pattern-match confidence remains separately recorded. Weak phone
photographs can have a few-pixel astrometric uncertainty, and this case does
not establish universal support for all smartphones, night modes or fisheye
projections. A frame with insufficient real star geometry still fails clearly.
