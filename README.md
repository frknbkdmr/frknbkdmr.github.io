# furkanbekdemir.com

Quarto website. Content lives in the `.qmd` files; everything else is
configuration you should rarely touch.

## Before you publish — fill these in

Search the repo for `CHANGE-ME` and `0000-0000-0000-0000`. They appear in:

- `_quarto.yml` — footer links
- `head.html` — the JSON-LD `sameAs` list **and** the ORCID URL
- `index.qmd`, `cv.qmd` — ORCID, GitHub, OSF links

The JSON-LD block is the part that matters for being resolved as one person
across profiles. A wrong or placeholder URL there is worse than no URL, so
delete any line you can't fill yet and add it back when the profile is live.

## Run it locally

```bash
quarto preview
```

## Publish to GitHub Pages

```bash
git init && git add -A && git commit -m "initial site"
gh repo create furkanbekdemir.com --public --source=. --push   # or create it in the web UI
quarto publish gh-pages
```

Then in the repo's **Settings → Pages**, set the custom domain to
`furkanbekdemir.com`. The `CNAME` file in this repo is already set, but
GitHub sometimes needs it confirmed in the UI as well.

## DNS

At your registrar, point the apex domain at GitHub Pages using the A records
listed in GitHub's current Pages documentation, and add a `www` CNAME to
`<username>.github.io`. Don't copy IP addresses from memory or from an old
blog post — read them from GitHub's docs the day you set it up. Enable
**Enforce HTTPS** once the certificate is issued (can take an hour or so).

## Adding a page

Create `newpage.qmd` with a YAML header, then add it to the `navbar` in
`_quarto.yml`. That's the whole workflow.

## Notes on the design

- Type: IBM Plex Serif (headings) / Sans (body) / Mono (labels and metadata).
  Full Turkish diacritic coverage, which most display faces lack.
- The hero graphic is a real trace, not decoration: a simulated agent tracking
  a reversing contingency, with the uncertainty band widening after each
  reversal. Regenerate it if you want different data, but keep it honest.
- Structural labels are set as axis ticks rather than numbered sections,
  because the content isn't a sequence.

## Scope discipline

This is meant to be finished in a weekend and then left alone. The failure
mode is not an unbuilt site; it is a site that keeps getting rebuilt. If you
find yourself writing a custom theme, stop and go write the preregistration.
