---
title: "The Website Was New. The CSS Was Four Months Old."
description: "A production site passed its build, origin, route, header, and preview checks—then looked broken on mobile because immutable CDN caching preserved the previous stylesheet."
date: 2026-07-31T22:00:00+02:00
categories: ["Incident Reports"]
tags: ["Cloudflare", "CDN", "Caching", "Jekyll", "Docker", "Debugging"]
---

The rebuilt site passed its Docker build. The origin container was healthy. Every required route returned HTTP 200. Desktop and narrow mobile screenshots from the production-equivalent preview looked correct.

Then I opened the public site on a phone.

It looked awful.

The background belonged to the previous dark theme. Product cards had lost their borders and structure. Labels collided. Sections that were carefully spaced in preview ran into each other in production.

The HTML was new. The CSS was from April.

## What had just been deployed

The site was the public home for [In a Box Tools](https://in-a-box-tools.tech/), a twelve-project family of inspectable, self-hosted infrastructure blueprints.

The source was Jekyll. A multi-stage Docker build generated the static files and copied them into an unprivileged nginx image. Traefik handled the public routing. Cloudflare sat in front of the origin.

Before release, the deployment path had been intentionally conservative:

1. Build the actual production image, not a development server.
2. Run it as an isolated preview bound to loopback.
3. Reach that preview through an SSH tunnel.
4. Crawl the generated routes.
5. Check expected titles and content markers.
6. Render desktop, tablet, and narrow mobile screenshots with Chromium.
7. Preserve the existing production image under a rollback tag.
8. Replace only the intended container.
9. Wait for the container health check.
10. Probe the public URL through DNS, TLS, Traefik, and Cloudflare.

The site redesign itself is covered separately in [Own the Stack. Keep the Answers.](https://in-a-box-tools.tech/launch/portfolio/infrastructure/2026/07/31/own-the-stack-keep-the-answers.html). This report is about the part that still failed.

## Why the first checks passed

The preview was correct because it bypassed Cloudflare and loaded every asset directly from the new container.

The initial production checks also looked reassuring:

- the container was healthy;
- the origin returned the new homepage;
- the public homepage returned HTTP 200;
- all twelve product routes returned HTTP 200;
- the public HTML contained the new title and headline;
- CSP, frame, MIME, and referrer-policy headers survived the proxy path.

Every one of those checks was true.

None proved that the browser received the stylesheet from the new image.

The contradiction between a correct preview and a broken public screenshot was the useful clue. If the generated HTML and origin image were right, the next question was not “which media query is wrong?” It was “which bytes did the public browser actually receive?”

## The headers that explained it

The public stylesheet response said:

```text
HTTP/2 200
cache-control: public, max-age=31536000, immutable
last-modified: Wed, 08 Apr 2026 17:19:25 GMT
age: 237321
cf-cache-status: HIT
```

The URL was still:

```text
/assets/css/main.css
```

The deployment had changed the file contents without changing the file identity.

Nginx told browsers and Cloudflare that this URL could be cached for one year and was immutable. Cloudflare believed it. The cached response was more than two days old and its `Last-Modified` timestamp came from the previous site build months earlier.

This was not Cloudflare being stubborn. It was Cloudflare honoring the cache contract it had been given.

## The hashes made the split undeniable

I downloaded the public stylesheet and compared it with the file inside the running production container:

```text
public Cloudflare CSS:
c30d8962eb37f3f3cca911cc2e779caea145ebf966ca0e7709ef73b5034eda70

production-container CSS:
7451f1ba9aa83d88eb1c8fc2e76f2d0d9130cd20b5576b4b0cfd56cbdbd4174c
```

Different hashes, different files.

The browser received the new semantic HTML and interpreted it using a four-month-old dark stylesheet. Classes introduced by the redesign had no matching rules in the cached CSS. Old global rules filled the vacuum.

That explained why the page was not merely the wrong color. It was structurally broken.

## Why a cache-bypass query did not save the check

The public HTML probe used a release marker similar to:

```text
https://in-a-box-tools.tech/?verify=release
```

That produced a fresh HTML request. The HTML still referenced the unchanged stylesheet URL:

```text
/assets/css/main.css
```

A query marker on the document does not invalidate independently cached subresources. HTML, CSS, JavaScript, images, fonts, API responses, browser storage, and service-worker state are separate nodes in the delivery graph.

The HTML check was fresh. The stylesheet check never happened.

## Fixing the cache contract

The immediate repair was to give every build a distinct static-asset URL.

In the Jekyll layout:

```go-html-template
{% assign asset_version = site.time | date: "%s" %}

<link rel="stylesheet"
      href="{{ '/assets/css/main.css' | relative_url }}?v={{ asset_version }}">
```

The favicon and social image received the same build version.

A deployment now generates an asset URL such as:

```text
/assets/css/main.css?v=1785526792
```

Cloudflare can still cache that response for a year. The next build receives a different URL, so the immutable promise becomes true: a URL identifies one asset version rather than whichever bytes happened to be deployed most recently.

A content fingerprint would be even stronger because it changes only when the asset changes. A deterministic build identifier is sufficient here and considerably better than an unversioned immutable path.

## The corrected verification

The improved release check follows the dependency from the public HTML to the actual public asset:

```bash
html=$(curl -fsS "$PUBLIC_URL?verify=$RELEASE")
asset=$(printf '%s' "$html" |
  grep -o 'assets/css/main.css?v=[0-9]*' |
  head -1)

curl -fsS "$PUBLIC_ORIGIN/$asset" -o /tmp/public.css
sha256sum /tmp/public.css

docker exec "$CONTAINER" \
  sha256sum /usr/share/nginx/html/assets/css/main.css
```

The release passes only when:

1. public HTML contains the intended release content;
2. the asset URL is versioned;
3. the public asset is retrievable;
4. its checksum matches the file inside the running container;
5. a fresh browser render from the **public URL** matches the verified preview.

After the repair, the versioned public CSS and production CSS had the same hash:

```text
7451f1ba9aa83d88eb1c8fc2e76f2d0d9130cd20b5576b4b0cfd56cbdbd4174c
```

The new public response began at `age: 0`. A fresh narrow Chromium screenshot finally matched the production preview.

HTTP 200 had proved that *a* file arrived. Matching hashes proved that the intended file arrived.

## The deployment itself had another useful constraint

The site repository was private, and the production host intentionally had no reusable GitHub credential. A direct fetch failed rather than quietly encouraging somebody to paste a personal token onto a server.

The deployment used a checksummed Git bundle instead:

1. Push and verify the canonical repository from the trusted workstation.
2. Create a bundle containing the verified commit.
3. Transfer it to production.
4. Verify the bundle checksum.
5. Fetch the bundle into a temporary remote-tracking ref.
6. Confirm that host-specific Compose configuration is unaffected.
7. Fast-forward the checkout.
8. Build, replace, and health-check the service.

That detail did not cause the cache incident, but it preserved an important boundary: solving deployment convenience did not require turning a production web host into a second developer workstation.

## What the incident changed

The static-site release checklist now includes:

- build the exact production image;
- crawl generated and public routes;
- inspect expected content, not only status codes;
- visually review desktop and narrow mobile layouts;
- verify the public path after origin health;
- extract static-asset URLs from public HTML;
- compare public asset hashes with the running container;
- preserve rollback material before replacement;
- verify redirects and CDN-injected links separately from site-owned routes.

The reusable deployment runbook was updated too. A warning that says “check CDN freshness” is not specific enough. The procedure now states exactly which URL to extract, which bytes to hash, and which artifact is authoritative.

## The broader lesson

Every component behaved exactly as configured:

- Jekyll generated the new site.
- Docker built the new image.
- Nginx served the current files.
- Traefik routed correctly.
- Cloudflare honored `immutable`.
- The browser reused a URL it had been told would never change.

The system was wrong because the relationship between deployment version and asset URL was missing.

That is why “the container is healthy” and “the homepage returns 200” are necessary checks, not conclusions. Modern delivery paths are graphs of independently cached artifacts. Verification has to follow the edges a browser follows.

The annoying part is that the user’s review found it immediately:

> “Um, page is a bit… ugly?”

Yes. It was.

The useful part is that the evidence made the failure boring to explain and hard to repeat.
