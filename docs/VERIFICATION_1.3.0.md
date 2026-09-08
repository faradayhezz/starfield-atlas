# Version 1.3.0 verification

The final backend suite passed **122 / 122** tests, including the genuine RAW
fixture, native-size exports, MPO input, ring intersections, star selection,
NASA source matching, catalogue integrity and large JSON compression.
The frontend suite passed **25 / 25** tests; TypeScript and Vite build passed.

The in-app browser exercised real photos through the normal upload workflow.
The public Orion photo returned 18,059 stars and 103 deep-sky catalogue entries.
Its initial photo layer drew 60 stars and eight deep-sky markers. None of the
stellar/deep-sky marker groups had a destructive core mask or filled centre.
M42's actual NASA reference photo displayed above a table of target thumbnails.
Coordinates and descriptive text were collapsed to retain usable table space;
switching to the stellar category hid the unrelated deep-sky detail.

The original 60 MP wide-field photograph completed in the browser with all
160,076 stellar records present. Searching TYC returned 151,617 records;
pagination moved from page 1 to page 2, with only 60 DOM table rows rendered.
No browser console errors appeared. The full response was compressed to about
13.55 MB without dropping catalogue entries.

The exact NGC6269-group photo was also re-rendered privately. Overlapping rings
retained complete thin outlines, labels avoided marker extents, and displaced
labels used leader lines that also avoid previously placed text. The user photos and their cropped comparisons are
not distributed with the repository.

The user's metadata-free 4032 × 3024 wide phone photo was also blind-solved,
using a general 32% central probe and full-frame validation. The solved TAN
field was about 69.97° × 55.60°. The 106 accepted full-frame anchors include
26 held out of calibration; accepted-anchor RMS was about 2.60 original
pixels, not a bound for every star. Separate checks of Vega, Altair and Deneb
found about 1.6–4.8 pixel offsets. The whole source pipeline took about nine
seconds and retained the original JPEG dimensions. See the
[phone validation record](PHONE_WIDE_FIELD_1.3.0.md) for limitations and memory use.

The portable executable was built as version 1.3.0, including the 432 stellar
index shards and the NASA reference-image packs. Its loopback health endpoint
returned OK. Source benchmark details and magnitude limits are recorded in
[the stellar-catalogue report](STELLAR_CATALOG_1.3.0.md).

![Real Orion with NASA reference imagery](images/workbench-1.3.0-nasa.jpg)

![Stellar inventory](images/workbench-1.3.0-stars.jpg)
