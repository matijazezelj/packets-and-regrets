# Packets & Regrets

Public field notes from a SecOps engineer operating a home lab: architecture,
incident reports, security trade-offs, and verified repairs.

Public URL: <https://blog.zezelj.org>

## Published content

- [The Lab](https://blog.zezelj.org/lab/) — public-safe architecture and operating model
- [What Actually Runs in the Home Lab](https://blog.zezelj.org/posts/what-runs-in-the-home-lab/)
- [Why the Lab Is Boring on Purpose](https://blog.zezelj.org/posts/why-the-lab-is-boring-on-purpose/)
- [The Website Was New. The CSS Was Four Months Old.](https://blog.zezelj.org/posts/the-website-was-new-the-css-was-four-months-old/) — immutable CDN caching and asset-byte verification
- [Prometheus on NFS: Healthy Until It Wasn't](https://blog.zezelj.org/posts/prometheus-on-nfs-healthy-until-it-wasnt/)
- [I Built the Cloud Audit SIEM I Kept Wishing Existed](https://blog.zezelj.org/posts/i-built-the-cloud-audit-siem-i-kept-wishing-existed/) — CAIB architecture, benchmarks, failure testing, and release-candidate boundaries
- [My Inventory Tool Filed a Complaint About Its Own Artwork](https://blog.zezelj.org/posts/my-inventory-tool-filed-a-complaint-about-its-own-artwork/) — source-of-truth inventory, honest "accurate" labels, and no invented data
- [I Gave My Network Gear a Voice. 99% of What It Said Was One Complaint.](https://blog.zezelj.org/posts/i-gave-my-network-gear-a-voice-and-it-would-not-stop-talking/) — UniFi syslog into [SIB](https://github.com/matijazezelj/sib), pipeline reconciliation, and separating proven noise
- [I Put One Docker App on Kubernetes. Download Was Fine. Upload Fell Off a Cliff.](https://blog.zezelj.org/posts/i-put-one-docker-app-on-kubernetes-download-was-fine-upload-fell-off-a-cliff/) — k3s + Cilium + Hubble flows into [SIB](https://github.com/matijazezelj/sib), four apps moved over, and a speed test that caught half a test
- [From 12,669 Findings to a To-Do List: Security Tooling for a Home Lab](https://blog.zezelj.org/posts/one-compose-command-seven-security-tools/)

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

## Deployment

Every push to `main` builds the site with Hugo 0.164.0 and deploys `public/`
as Cloudflare Workers static assets on `blog.zezelj.org`
(`.github/workflows/pages.yml`, configured by `wrangler.jsonc`). Pull requests
only run the validation build (`.github/workflows/validate.yml`).

A manual deployment, after `wrangler login`:

```bash
hugo --gc --minify
npx wrangler deploy
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
