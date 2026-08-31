# Network real-sky test images: provenance and results

Collected and tested on 2026-08-30. The input is an authentic photograph of the night sky. It is not a generated star field, a screenshot of planetarium software, or an AI-generated image. The downloaded input bytes were not resized, cropped, tone-mapped, or transcoded locally.

## Inventory

| Local file | Upstream role | Format and dimensions | Bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| `nasa_iss006-e-28028_southern-cross.jpg` | NASA astronaut photograph ISS006-E-28028, Southern Cross/Carina region | JPEG, 2000 x 1368, RGB | 1,268,246 | `ef387d4e412037126f82be9390a85ee5178227000d6ff9cd3da535a80cebfab8` |

## NASA ISS006-E-28028 Southern Cross photograph

### Source and authenticity

- Institution: NASA Johnson Space Center, Gateway to Astronaut Photography of Earth.
- Official record: [Astronaut Photo ISS006-E-28028](https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?frame=28028&mission=ISS006&roll=E).
- Exact downloaded image: [`ISS006-E-28028.JPG`](https://eol.jsc.nasa.gov/DatabaseImages/ESC/large/ISS006/ISS006-E-28028.JPG).
- Photographer/credit: Don Pettit, ISS Expedition 6, NASA.
- The official record gives Nikon D1 Electronic Still Camera, 58 mm focal length, capture time `2003-02-21 10:32:19 GMT`, and identifies **Southern Cross** and **Keyhole Nebula** as image features.
- NASA's [Astronomy Picture of the Day description](https://apod.nasa.gov/apod/ap030507.html) additionally identifies the Coalsack and Carina Nebula in this same photograph.
- The file itself has no EXIF; the application therefore correctly treated time, camera and focal length as absent rather than inventing metadata.

The direct JPEG is 2000 x 1368. Its top 2000 x 1312 pixels are the photographed field and the remaining 56 pixels are NASA's white image-ID strip. The exact upstream file, including that strip, was tested without local cropping.

### Usage permission

NASA's [Images and Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) state that NASA content generally is not subject to copyright in the United States and may be used factually for educational or informational purposes without separate permission, with NASA acknowledged as the source and without implying endorsement. No third-party copyright notice appears on this image's official record. This test use retains the NASA photo ID and credit.

### Independent known-content check and local verification

The blind solution agrees with the objects named by NASA: the overlay places the Southern Cross at left and NGC 3372 (the Carina/Keyhole complex) at upper right. It also identifies the Coalsack (C99), Jewel Box cluster (NGC 4755), IC 2602, and constellation geometry for Crux, Centaurus, Carina and Musca.

| Result | Value |
| --- | ---: |
| Centre RA / Dec (J2000) | `177.387795 deg`, `-62.240602 deg` |
| Horizontal / vertical FOV | `23.011495 deg` / `15.852991 deg` |
| Roll | `24.028997 deg` |
| Solve method | `tetra3-central-crop` |
| Solved crop FOV | `9.773108 deg` |
| Matched stars | `14` |
| RMS residual | `45.039 arcsec` |
| False-positive probability | `3.2349e-10` |
| Solver time / complete pipeline wall time | `13.668 s` / `13.929 s` |
| OpenNGC entries in frame / expected visible | `59` / `8` |

Generated full-resolution outputs stay in the local ignored `results/` tree. A compressed, attribution-safe representative preview is published at [`docs/images/nasa-southern-cross-annotated-public.jpg`](../../docs/images/nasa-southern-cross-annotated-public.jpg).

## Interpretation

This is a successful end-to-end application test, not merely a call to the plate solver: the run read file metadata, blind-solved the star geometry, projected the local OpenNGC/bright-star/constellation catalogues, generated preview and full-resolution annotated JPEGs, and wrote the full JSON inventory. It is a strong independent validation because NASA's official source names celestial features before our solver is run.
