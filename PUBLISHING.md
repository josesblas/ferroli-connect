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

Home Assistant does **not** read the logo from this repo. Every integration's
icon/logo is served from the central **[home-assistant/brands]** repository
(`https://brands.home-assistant.io/<domain>/...`). Until the images are there,
HA shows a generic placeholder — this is normal for a brand-new custom
integration and does **not** affect functionality.

To get the Ferroli logo to show:

1. Prepare two PNGs with a **transparent background**, trimmed (no padding):
   - `icon.png` — square, **256×256** (a `icon@2x.png` 512×512 is recommended too).
   - `logo.png` — the wordmark, max **256** tall (a `logo@2x.png` is recommended).
   The helper `tools/make_brand_assets.py` in this repo produces them from a
   source logo (needs Pillow): `python tools/make_brand_assets.py path/to/ferroli-logo.png`.
2. Fork **home-assistant/brands**, add the files under
   `custom_integrations/ferroli_connect/` and open a PR.
3. Once merged, the Ferroli logo appears in HA automatically (clear browser
   cache if needed).

> Note: the Ferroli name and logo are trademarks of Ferroli S.p.A. The brands
> repo hosts manufacturer logos for identification; this project is not
> affiliated with or endorsed by Ferroli.

[home-assistant/brands]: https://github.com/home-assistant/brands

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
