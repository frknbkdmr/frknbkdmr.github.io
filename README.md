# furkanbekdemir.com

Quarto website. Content lives in the `.qmd` files; everything else is
configuration you should rarely touch.

## Before you publish

Profile URLs (ORCID, GitHub, OSF) are filled in and consistent across
`_quarto.yml`, `head.html` and the pages. The JSON-LD block in `head.html` is
what lets search engines resolve these profiles as one person, so a wrong URL
there is worse than no URL — delete a line you can't fill rather than guessing.

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

Live. The apex carries GitHub's four A records and `www` is a CNAME to
`frknbkdmr.github.io`. Cloudflare is the nameserver and nothing more.

If you set this up again elsewhere: point the apex at the A records in
GitHub's current Pages documentation and add the `www` CNAME. Read those
addresses from GitHub's docs the day you do it, not from memory or an old blog
post. Enable **Enforce HTTPS** once the certificate is issued.

`CNAME` is in `resources`, which is what makes GitHub adopt the custom domain
on publish. If you ever move the domain, comment that line out first: with a
CNAME file present but no DNS, every address including `frknbkdmr.github.io`
redirects to a name that does not resolve, and the site is reachable nowhere.

### The Cloudflare proxy stays off

Every record is grey-clouded, and it was decided that way rather than left
that way. Turning the proxy on buys custom response headers and Accept-based
markdown negotiation — both of which this site already answers another way,
with `rel=me` links and `llms.txt`. What it risks is worse than what it buys:

- Cloudflare's **AI Scrapers and Crawlers** blocking, and Bot Fight Mode, sit
  in front of `robots.txt` and reject assistants before the file is ever read.
  That would silently undo the whole point of naming them in there.
- GitHub renews the Let's Encrypt certificate against the origin. Behind a
  proxy that renewal is undocumented for this combination, and a failure shows
  up ninety days later as an expired certificate, not as an error today.

If it is ever turned on, check `Security → Bots` **first** — a blocked crawler
is immediate, an unrenewed certificate is not — and verify with:

```bash
curl -A "Mozilla/5.0 (compatible; GPTBot/1.1)" -o /dev/null -w "%{http_code}\n" https://furkanbekdemir.com/
```

## Build internals

`_quarto.yml` runs `site-post-render.py` after every render, so **Python 3 must be
on PATH** — `quarto render` fails without it. The wrapper runs the original
`post-render.py` fixes, then writes the crawler policy that permits search and
user-initiated AI retrieval while blocking model-training crawlers. The original
script adds canonical tags, normalises the sitemap, defers parser-blocking
scripts, publishes the LLM-readable indexes, and removes `search.json` while
search is off. Both scripts use only the standard library.

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
