# furkanbekdemir.com

Quarto website. Content lives in the `.qmd` files; everything else is
configuration you should rarely touch.

## Before you publish

Profile URLs (ORCID, GitHub, OSF) are filled in and consistent across
`_quarto.yml`, `head.html` and the pages. The JSON-LD block in `head.html` is
what lets search engines resolve these profiles as one person, so a wrong URL
there is worse than no URL — delete a line you can't fill rather than guessing.

**The domain is the open item.** `furkanbekdemir.com` does not resolve yet, and
every canonical URL, the sitemap and the JSON-LD point at it. See DNS below.

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

## Build internals

`_quarto.yml` runs `post-render.py` after every render, so **Python 3 must be on
PATH** — `quarto render` fails without it. The script uses only the standard
library. It adds the `<link rel="canonical">` tags Quarto does not emit, points
the sitemap at the bare origin and drops the duplicate that creates, defers the
parser-blocking scripts in `<head>`, and deletes `search.json` while search is
off. It reads the site URL from `_quarto.yml` rather than keeping its own copy,
and it is safe to run again on an already-processed `_site`.

If you ever move the build to CI, note that many Linux runners ship `python3`
but no `python`, which is the name `_quarto.yml` calls.

Fonts are self-hosted in `fonts/` so no visitor IP reaches a third party.
Regenerate them with `python fetch_fonts.py` if a weight is added, and keep
`$web-font-path: false` in `custom.scss` — it stops the Cosmo theme from pulling
a Google font the site never uses.

The body measure is set in two places that must agree: `grid: body-width` in
`_quarto.yml` (the text column) and `$measure` in `custom.scss` (which aligns
the navbar and footer to it). Change one, change the other.

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
