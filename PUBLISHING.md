# Publishing checklist

Steps to take this from a local folder to a public HACS integration.

## 1. Fill in the placeholders

In `custom_components/ferroli_connect/manifest.json` replace every `CHANGEME`
with your GitHub account / repo:

```json
"documentation": "https://github.com/<you>/ferroli-connect",
"issue_tracker": "https://github.com/<you>/ferroli-connect/issues",
"codeowners": ["@<you>"],
```

## 2. Add a LICENSE

The README declares **MIT**. Add a `LICENSE` file with the MIT text and your
name/year.

## 3. The Ferroli logo (brand images)

Since **Home Assistant 2026.3.0**, a custom integration ships its own brand
images directly — no PR to the `home-assistant/brands` repo is needed. HA serves
local images with priority over the CDN, with no extra configuration.

The images live in a `brand/` folder next to `manifest.json` (already included
in this repo):

```
custom_components/ferroli_connect/
├── manifest.json
└── brand/
    ├── icon.png      (256×256, transparent)
    ├── icon@2x.png   (512×512)
    ├── logo.png
    └── logo@2x.png
```

Optional dark-mode variants are also supported: `dark_icon.png`,
`dark_logo.png`, `dark_icon@2x.png`, `dark_logo@2x.png`.

The helper `tools/make_brand_assets.py` regenerates them from a source logo
(needs Pillow): `python tools/make_brand_assets.py path/to/ferroli-logo.png`.

> Note: the Ferroli name and logo are trademarks of Ferroli S.p.A. and are used
> here only for identification; this project is not affiliated with or endorsed
> by Ferroli.

## 4. Push to GitHub

```bash
git init
git add .
git commit -m "Initial release: Ferroli Connect integration"
git branch -M main
git remote add origin https://github.com/<you>/ferroli-connect.git
git push -u origin main
```

Tag a release (`v0.4.0`) so HACS can offer it as a version.

## 5. Install via HACS

HACS → ⋮ → *Custom repositories* → add
`https://github.com/<you>/ferroli-connect` as category **Integration** →
install → restart HA.

## 6. (Later) Submit to the HACS default store

Open a PR to **hacs/default** adding the repo so users can find it without
adding it as a custom repository. Requirements: a release/tag, a README, a
`hacs.json`, and the brand images merged in step 3.
