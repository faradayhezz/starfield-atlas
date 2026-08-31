# Real-sky image fixtures: provenance and licences

Collected on 2026-08-30. These fixtures are authentic camera/astronomical images, not AI-generated or synthetic star fields. The three image files are exact byte copies of their upstream originals; only the local filenames were changed. No resizing, cropping, tone mapping, or transcoding was performed.

The images total 7,936,991 bytes (about 7.57 MiB), comfortably below the 30 MiB fixture budget.

## Inventory

| Local file | Test role | Format and dimensions | Bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| `esa_tetra3_alt40_az-135_20190729.tiff` | Wide-field, low-SNR, raw 16-bit camera frame | TIFF, 1024 x 768, 16-bit grayscale | 1,573,184 | `f5d6c27ac7e8e2114fbeb45196380703e138031819714db7e39f3e101b32b557` |
| `esa_tetra3_alt60_az-135_20190729.tiff` | Wide-field, low-SNR, raw 16-bit camera frame | TIFF, 1024 x 768, 16-bit grayscale | 1,573,184 | `f288f6e1fb3a1299626956e3d44740c0260348c65dd9296ac8e07bb27524a5e9` |
| `wikimedia_m31_cc0_20190830.png` | Narrower deep-sky target with dense stellar background and companion galaxies | PNG, 4144 x 2822, RGBA | 4,790,623 | `9edbcaab9576e9ee9e7226c97118617c2d74e793b3281d5e56eac68319a05494` |

## ESA tetra3 real-world camera frames

Applies to:

- `esa_tetra3_alt40_az-135_20190729.tiff`
- `esa_tetra3_alt60_az-135_20190729.tiff`

### Source and authenticity

- Institution/project: European Space Agency (ESA), [`esa/tetra3`](https://github.com/esa/tetra3), with project contributors.
- Repository revision pinned for reproducibility: [`f9fa2eb9a32a5efc529e2d86f0b59f35b1e9028d`](https://github.com/esa/tetra3/tree/f9fa2eb9a32a5efc529e2d86f0b59f35b1e9028d).
- Upstream originals:
  - [`2019-07-29T204726_Alt40_Azi-135_Try1.tiff`](https://raw.githubusercontent.com/esa/tetra3/f9fa2eb9a32a5efc529e2d86f0b59f35b1e9028d/examples/data/2019-07-29T204726_Alt40_Azi-135_Try1.tiff)
  - [`2019-07-29T204726_Alt60_Azi-135_Try1.tiff`](https://raw.githubusercontent.com/esa/tetra3/f9fa2eb9a32a5efc529e2d86f0b59f35b1e9028d/examples/data/2019-07-29T204726_Alt60_Azi-135_Try1.tiff)
- The [official README at that revision](https://github.com/esa/tetra3/blob/f9fa2eb9a32a5efc529e2d86f0b59f35b1e9028d/README.rst) explicitly describes these example data as a **real-world** image set acquired with a FLIR Blackfly S BFS-U3-31S4M-C camera (Sony IMX265 sensor, 2x2 binning) and a Fujifilm HF35XA-5M 35 mm f/1.9 lens, with an approximately 11.4 degree field of view.
- The original filenames encode `2019-07-29T20:47:26`, azimuth `-135` degrees, and altitude `+40` or `+60` degrees. The upstream project does not state a timezone, so the timestamp must not be interpreted as UTC without additional evidence.

### Licence

- Repository-level licence: [Apache License 2.0](https://github.com/esa/tetra3/blob/f9fa2eb9a32a5efc529e2d86f0b59f35b1e9028d/LICENSE.txt). No per-image exception is present in the source tree.
- A verbatim copy is included as `LICENSE-ESA-TETRA3-APACHE-2.0.txt` (SHA-256 `d6cbf26a85a5855d30156b89e24adfaaad6a4cd5c6944b08850c1e36f92352dd`).
- The image bytes were not modified.

### Plate-solve verification values

These values are derived verification aids, not embedded EXIF. Each original image was blind-solved with tetra3's bundled default database and `distortion=[-0.2, 0.1]`. The solver reports J2000 equinox coordinates; horizontal FOV and residuals are in degrees and arcseconds respectively.

| Local file | Centre RA | Centre Dec | Horizontal FOV | Roll | Matches | RMS residual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `esa_tetra3_alt40_az-135_20190729.tiff` | 230.667360 deg | +11.034223 deg | 11.426214 deg | 332.279807 deg | 11 | 6.461 arcsec |
| `esa_tetra3_alt60_az-135_20190729.tiff` | 240.464077 deg | +28.940573 deg | 11.421557 deg | 329.049101 deg | 16 | 5.024 arcsec |

The TIFF tags contain image geometry, 16-bit sample depth, uncompressed storage, and a `tifffile.py` software tag. They do **not** contain camera make/model, focal length, GPS, an absolute timezone, or celestial WCS.

## Wikimedia Commons M31 photograph

Applies to `wikimedia_m31_cc0_20190830.png`.

### Source and authenticity

- Author: Stephen Rahn (`StephenGA` / `srahn` on Flickr), Macon, Georgia, USA.
- Capture/publication date stated by the source: 2019-08-30 00:17; timezone unspecified.
- Stable Wikimedia Commons description page: [`File:Messier 31 (48645809527).png`](https://commons.wikimedia.org/w/index.php?title=File:Messier_31_%2848645809527%29.png&oldid=938537143).
- Upstream original: [`Messier_31_(48645809527).png`](https://upload.wikimedia.org/wikipedia/commons/1/12/Messier_31_%2848645809527%29.png).
- The Commons page records that the image came from the author's [Flickr photograph 48645809527](https://www.flickr.com/photos/97839409@N00/48645809527) and that Wikimedia's FlickreviewR 2 verified its licence on 2020-11-11.

### Licence

- [CC0 1.0 Universal Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/).
- Attribution is not legally required by CC0, but the author and source are retained here for scientific provenance.
- The image bytes were not modified.

### Known sky content

- Primary object: M31 / NGC 224, the Andromeda Galaxy. Its compact companion M32 and diffuse companion M110 are also visible in the frame.
- Reference position from [CDS SIMBAD](https://simbad.u-strasbg.fr/simbad/sim-id?Ident=Messier+31): ICRS J2000 RA `00h 42m 44.330s`, Dec `+41d 16m 07.50s` (decimal RA `10.6847083 deg`, Dec `+41.2687500 deg`). SIMBAD gives an optical angular size of about `199.53 x 70.79 arcmin`, position angle `35 deg`.
- This is the narrower/deep-sky fixture relative to the 11.4-degree ESA frames. The PNG contains no EXIF or WCS, so the M31 coordinate is a catalogue reference for the depicted target, not a claim that the exact image centre or plate scale is embedded in the file.

## Integrity/metadata check

The format, dimensions, bit depth/mode, byte lengths, and hashes above were read after download with Pillow and SHA-256. All files opened successfully as single-frame images. Hashes should be checked before using a fixture as a golden test input.
