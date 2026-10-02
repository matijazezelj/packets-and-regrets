# Packets & Regrets

Public field notes from a SecOps engineer operating a home lab: architecture,
incident reports, security trade-offs, and verified repairs.

Current public URL: <https://matijazezelj.github.io/packets-and-regrets/>

Planned canonical URL: <https://blog.zezelj.org> (Cloudflare Pages)

## Published content

- [The Lab](https://matijazezelj.github.io/packets-and-regrets/lab/) — public-safe architecture and operating model
- [What Actually Runs in the Home Lab](https://matijazezelj.github.io/packets-and-regrets/posts/what-runs-in-the-home-lab/)
- [Why the Lab Is Boring on Purpose](https://matijazezelj.github.io/packets-and-regrets/posts/why-the-lab-is-boring-on-purpose/)
- [The Website Was New. The CSS Was Four Months Old.](https://matijazezelj.github.io/packets-and-regrets/posts/the-website-was-new-the-css-was-four-months-old/) — immutable CDN caching and asset-byte verification
- [Prometheus on NFS: Healthy Until It Wasn't](https://matijazezelj.github.io/packets-and-regrets/posts/prometheus-on-nfs-healthy-until-it-wasnt/)
- [I Built the Cloud Audit SIEM I Kept Wishing Existed](https://matijazezelj.github.io/packets-and-regrets/posts/i-built-the-cloud-audit-siem-i-kept-wishing-existed/) — CAIB architecture, benchmarks, failure testing, and release-candidate boundaries
- [My Inventory Tool Filed a Complaint About Its Own Artwork](https://matijazezelj.github.io/packets-and-regrets/posts/my-inventory-tool-filed-a-complaint-about-its-own-artwork/) — source-of-truth inventory, honest "accurate" labels, and no invented data
- [I Gave My Network Gear a Voice. 99% of What It Said Was One Complaint.](https://matijazezelj.github.io/packets-and-regrets/posts/i-gave-my-network-gear-a-voice-and-it-would-not-stop-talking/) — UniFi syslog into [SIB](https://github.com/matijazezelj/sib), pipeline reconciliation, and separating proven noise
- [I Put One Docker App on Kubernetes. Download Was Fine. Upload Fell Off a Cliff.](https://matijazezelj.github.io/packets-and-regrets/posts/i-put-one-docker-app-on-kubernetes-download-was-fine-upload-fell-off-a-cliff/) — k3s + Cilium + Hubble flows into [SIB](https://github.com/matijazezelj/sib), four apps moved over, and a speed test that caught half a test

## Local development

Requires Hugo Extended 0.164.0 or newer.

```bash
hugo server --buildDrafts --disableFastRender
```

Open <http://127.0.0.1:1313>.

## Production build

```bash
hugo --gc --minify --printPathWarnings --printUnusedTemplates
```

The generated site is written to `public/`. Build output is intentionally not
committed.

## Cloudflare Pages

Preferred configuration:

| Setting | Value |
|---|---|
| Production branch | `main` |
| Build command | `hugo --gc --minify` |
| Build directory | `public` |
| Environment variable | `HUGO_VERSION=0.164.0` |
| Custom domain | `blog.zezelj.org` |

A direct deployment can also be performed after `wrangler login`:

```bash
hugo --gc --minify
npx wrangler pages deploy public --project-name packets-and-regrets
```

## Publication boundary

Before publishing, review every post for:

- credentials, tokens, cookies, hashes, and private keys;
- public IP addresses and externally reachable management endpoints;
- camera names, locations, or stream details;
- directly reusable internal network maps;
- active vulnerabilities that have not been remediated;
- employer/customer/internal-company details;
- claims not supported by captured evidence.

RFC1918 addresses are omitted by default even though they are not secrets. The
private operational wiki is never used as the public site source tree.

## Licensing

- Article and documentation content: CC BY 4.0
- Templates, CSS, and supporting code: MIT

See `LICENSE.md`.
