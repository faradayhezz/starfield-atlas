# Stellarium Chinese skyculture attribution

The `common_name_zh` field in `../bright_stars.csv` is derived only from fixed
revisions of the official Stellarium Chinese skyculture.

## Current skyculture source

- Repository: <https://github.com/Stellarium/stellarium-skycultures>
- Commit: `014fbb5e59233d133c22f9811af96b67d05a95c9`
- Files: `chinese/index.json`, `chinese/po/zh_CN.po`, and
  `chinese/description.md`
- Fixed tree URL:
  <https://github.com/Stellarium/stellarium-skycultures/tree/014fbb5e59233d133c22f9811af96b67d05a95c9/chinese>
- SHA-256 (`index.json`):
  `32e02a66f93c254bcd1b86ee0a3448347d57d0b1ff84714695c0bd0506ab9b0e`
- SHA-256 (`zh_CN.po`):
  `52f220ab11e9684573b4b82c1f06200df5b75a37d55ebd0ec960073815d7a990`

## Verbatim Simplified-Chinese label source

- Repository: <https://github.com/Stellarium/stellarium>
- Release tag: `v0.22.2`
- Peeled tag commit: `9275de93251f2e9e6032afdf889332b9c66a248c`
- File: `skycultures/chinese/star_names.zh_CN.fab`
- Fixed file URL:
  <https://github.com/Stellarium/stellarium/blob/9275de93251f2e9e6032afdf889332b9c66a248c/skycultures/chinese/star_names.zh_CN.fab>
- SHA-256:
  `6379331a5e7f7029a11ab2186c8a0b7897c73684aff410270d8544a4bbed9fd5`

The current `index.json` determines whether a HIP identifier remains part of
the Chinese skyculture. For each retained HIP, this project selects the first
verbatim Simplified-Chinese label in the official `star_names.zh_CN.fab` file.
The one later standalone label used here, `南方之星`, is copied verbatim from
the current `zh_CN.po` translation of `Southern Star`. Composite names lacking
a verbatim complete Chinese string are not fabricated and remain blank.

The skyculture credits in the official `description.md` state that it was
initially contributed by Karrie Berglund of Digitalis Education Solutions,
Inc., based on Hong Kong Space Museum star maps. Sun Shuwei contributed more
than 200 Xingguans and more than 3,000 stars, primarily based on Yi Shitong's
_Chinese and Western Contrast Star Chart and Catalogue 1950.0_. Text was
reworked by the Stellarium team.

The `v0.22.2` skyculture metadata specifies
`CC BY-SA 4.0 International Public License`. The current description states
`Text and line: CC BY-SA`. This derived field is therefore distributed under
CC BY-SA 4.0. A copy of the Creative Commons Attribution-ShareAlike 4.0 legal
code is already included in this directory as
`OPENNGC-CC-BY-SA-4.0.txt`; the same legal code applies here.
