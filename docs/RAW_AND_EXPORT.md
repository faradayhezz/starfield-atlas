# Native-resolution image import and export

Camera RAW is decoded with [rawpy / LibRaw](https://letmaik.github.io/rawpy/api/rawpy.Params.html), using full-resolution demosaicing, camera white balance, and 16-bit sRGB output. The original uploaded file is retained without modification. RAW sensor mosaics cannot contain rendered text while remaining an original camera RAW; annotated RAW therefore exports as a full-resolution **16-bit TIFF**. The interface reports this before download.

JPG/JPEG, PNG and single-frame TIFF retain their source pixel dimensions (after applying EXIF orientation once) and container format. PNG retains 8/16-bit samples; TIFF retains supported unsigned/signed integer or floating-point sample types, including 16/32-bit. Color marks turn grayscale into RGB of the same bit depth. Lossless output samples outside the transparent annotation layer remain exact. JPEG must be re-encoded after adding marks. **Preserving file byte size is not possible** when adding annotations or changing compression; preserving pixel dimensions is guaranteed.

The small browser preview is for display only. Download uses the full-resolution source, never a resized canvas. Adjusting styles calls `POST /api/export/{jobId}` with `{"settings": {...}}`, which returns `downloadUrl` and `export` format/dimension/bit-depth information without repeating plate solving.

The **deep-sky catalogue** control changes the available DSO inventory: common entries include known magnitudes ≤ 10 and named recommended favorites, expanded entries use ≤ 15 plus those favorites, and complete includes all intersecting entries, including unnamed dark clouds with unknown magnitudes. It does not treat a dark cloud's area or opacity as a magnitude. Stellar magnitude selection is separate. Result `catalogSelection` reports both total in-field DSO count and included count; changing catalogue parameters requires analysis again, while pure style changes reuse the saved inventory.

Only one native full-frame operation runs at a time. Display conversion and compositing use bounded strips, and cancellation is checked between operations and strips. LibRaw's native demosaic call finishes its current decode before the next cancellation check.

## Reproducible public RAW decode test

- Source: [rawpy's real Nikon NEF test fixture](https://github.com/letmaik/rawpy/blob/main/test/iss030e122639.NEF), file `iss030e122639.NEF` (10,656,312 bytes).
- Direct download: https://raw.githubusercontent.com/letmaik/rawpy/main/test/iss030e122639.NEF
- SHA-256: `5922721d13f11795557d97fdeb0a60b900086c402bc82a848ff280d15b99ffd4`.
- Actual decoded result: Nikon D3S; 4284 × 2844; RGB uint16; 28 mm; f/1.4; 0.625 s; ISO 3200; EXIF capture time 2012-03-04 17:20:59.
- This is an orbital aurora/sky photograph. The test establishes RAW decoding and metadata extraction, not a claimed successful astrometric identification.
- Save the downloaded file under ignored `.runtime/raw-fixtures/iss030e122639.NEF`; run `RUN_RAW_TESTS=1` and `python -m unittest discover -s tests -p test_native_image_io.py -v`. The binary is not redistributed in the repository.

Native TIFF I/O follows [tifffile](https://github.com/cgohlke/tifffile); native PNG and compressed TIFF codecs use [imagecodecs](https://github.com/cgohlke/imagecodecs). RAW metadata is read using [ExifRead](https://github.com/ianare/exif-py).

## Pinned dependency sources and licenses

The Windows rawpy 0.27.1 wheel loads its separate `raw_r.dll`. Runtime verification reports LibRaw **0.22.1**, matching the header version. Upstream rawpy tag `v0.27.1` pins [LibRaw commit b860248](https://github.com/LibRaw/LibRaw/tree/b860248a89d9082b8e0a1e202e516f46af9adb29) and [LibRaw-cmake commit 6e26c9e](https://github.com/LibRaw/LibRaw-cmake/tree/6e26c9e73677dc04f9eb236a97c6a4dc225ba7e8). The source packages and those two archives are available locally in ignored `release/dependency-sources` for packaging alongside release materials.

The portable build copies each Python distribution's license directory, including rawpy's `LICENSE` and `LICENSE.LibRaw`, and imagecodecs' bundled-codec notices. PyInstaller explicitly collects rawpy and imagecodecs native DLLs. The separate LibRaw DLL may be replaced with an ABI-compatible build; no application signature prevents replacement.

Verified PyPI source distributions:

| Package | Source SHA-256 |
| --- | --- |
| rawpy 0.27.1 | `3194d64ff690ac945e1a43237edae8a18f1f493751924de1ae2bcef473c0fb79` |
| tifffile 2026.8.23 | `bd3c816f166f85c93329a54a0c9a1eccc9968a6a78f91d63b65d7b17675915f2` |
| imagecodecs 2026.8.16 | `03a6add9ad9ba61dce1520489fd090b1b5cf2a2701a9666d1ab8e7653278175f` |
| ExifRead 3.5.1 | `9f998f80d3062741c976dfc4fd033424bc40932937994e4d2181eb70c4b6aedd` |
