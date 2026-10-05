---
title: "From 12,669 Findings to a To-Do List: Security Tooling for a Home Lab"
description: "One Docker Compose command gives you vulnerability scanning, threat intel, compliance, identity, PKI and an asset graph. Here is what it found in my own lab, and how to turn a scary number into a short list you can act on."
date: 2026-10-05T12:30:00+02:00
draft: false
categories: ["Field Notes"]
tags: ["Security", "Vulnerability Management", "Supply Chain", "Homelab", "Docker", "SBOM", "Open Source"]
---

Run a vulnerability scanner on a home lab and it hands you a number. Mine was **12,669**.

A number like that has two effects. It scares you, and then it makes you close the tab, because nobody works through twelve thousand of anything. The scanner did its job. The missing half of the job is turning the pile into something you can do on a Saturday morning.

This post is about that second half, using a real lab: two Docker hosts, 70 distinct images (78 across the two hosts), and the repo that describes them. I will show how the tools fit in, what they found, and the steps I use to get from a scary count to a short list.

## The toolbox

I maintain a small family of open-source security tools. Each is a Docker Compose stack that does one job and ships a Grafana dashboard:

- [**VIB**](https://github.com/matijazezelj/vib), vulnerabilities in a box. Trivy scans every running container image.
- [**TIB**](https://github.com/matijazezelj/tib), threat intel in a box. It takes what VIB found and asks the useful question: is anyone actually exploiting this? It uses CISA's known-exploited list and exploit-probability scores.
- [**CIB**](https://github.com/matijazezelj/cib), compliance in a box. Licences, software bills of materials, end-of-life base images.
- [**IIB**](https://github.com/matijazezelj/iib), identity in a box, built around Authentik.
- [**PIB**](https://github.com/matijazezelj/pib), PKI in a box. A small certificate authority and a certificate-expiry monitor.
- [**AIB**](https://github.com/matijazezelj/aib), an asset graph built from your infrastructure code, with blast-radius and single-point-of-failure analysis.
- [**XIB**](https://github.com/matijazezelj/xib), the umbrella that runs all of the above behind one set of dashboards.

You do not need all of them. VIB and TIB together are the part that pays off first.

## Trying it

On a fresh VM with Docker installed:

```bash
git clone --recurse-submodules https://github.com/matijazezelj/xib.git
cd xib
make setup        # generates every password for you
make up-safe      # starts everything
```

The first scan starts by itself, and the dashboards fill in as it works through your images. `make up-safe` matters for a reason covered below: it lets the scanner look at your containers without being handed the keys to the host.

## How it fits in my lab

The lab has two Docker hosts: a main one with roughly forty services, and a second that runs the camera recorder and the download stack. I gave the tools their own small VM instead of running them on either host. Three reasons:

- **If the scanner is ever compromised, it is not sitting on the thing it scans.**
- **It can be rebuilt without touching production.**
- **It gets its own firewall.** Only the reverse proxy and a short list of management hosts can reach it.

The scanner needs to read the list of containers and images on each Docker host. The lazy way is to mount the Docker socket into the scanner, which is root on the host. Instead, each Docker host runs a small read-only proxy that answers "list containers" and "read images" and refuses everything else, and only the tools VM can reach it. I tested both directions: reads succeed, and a request to create a container comes back as 403.

Pointing the scanners at remote hosts is one line in the top-level `xib/.env`: `DOCKER_HOSTS=main=tcp://<proxy-host>:2375,second=tcp://<proxy-host>:2375`, comma-separated `name=url` pairs. Put it there, not in `vib/.env` or `cib/.env`; with `make up-safe` the umbrella value wins and the per-tool one is quietly ignored. The name becomes a `host` label, so every dashboard can filter by host.

Around that:

- The dashboards sit behind the same reverse proxy and wildcard certificate as everything else.
- The uptime monitor checks each one, including a check that the asset graph has *data* in it, not just that the page loads.
- The VM's metrics go to the same Prometheus as the rest of the lab.
- It is in the nightly backup.

None of that is exotic. It is the treatment any other service in the lab gets, which is the point: a security tool should not be the one thing that is not monitored, backed up and firewalled.

## What it found

**12,669 findings across 70 images.** By severity: 186 critical, 3,442 high, 4,831 medium, 3,212 low, 998 unknown.

The other tools filled in the picture:

- **TIB** checked the pile against CISA's known-exploited list and found **four CVEs**: in a web framework, a browser engine, a font library and an HTTP/2 implementation. They sit in three images, and all four were past CISA's own remediation deadline.
- **CIB** found four images built on end-of-life Alpine versions, one from 2023. Nobody chooses to run those. They are what is left when an upstream image stops being rebuilt.
- **AIB** drew the dependency graph from the compose files and the Ansible inventory: 113 nodes and 151 edges. It ranks single points of failure, and a couple of shared networks and one VPN container carry far more than I would have guessed.
- **A look through the compose files** showed that 51 of 70 images use mutable tags like `latest`, and 51 services lack `init: true`. I wrote both of those rules myself. A checklist that nothing enforces is a diary entry.

## From noise to a to-do list

This is the part I wish more tools explained. Here is the funnel I use, with the real numbers.

**Step 1. Start with what is being exploited, across everything.** Before you filter by severity, check the whole pile against CISA's known-exploited list. Most vulnerabilities never see a real exploit; this list is the ones that do. Four CVEs matched, and one of them was only rated *medium*. A severity filter would have thrown it away. That is your "fix this week" list, and it came out of twelve thousand rows without anyone reading twelve thousand rows.

**Step 2. Set aside what you cannot fix.** 5,444 of the 12,669 have no fixed version yet. They are real, but there is nothing to do today, so they go on a watch list. **Left: 7,225.**

**Step 3. Keep what is serious.** Critical and high only. Medium and low matter eventually, but they are not what gets someone into your network this month. **Left: 2,383.**

**Step 4. Group by image, not by CVE.** You do not patch CVEs one at a time. You update an image, and that image's whole backlog goes with it. Ranking images by their fixable critical and high findings, the top five account for **43% of the 2,383**, and the top ten for 58%. Work from the top and each update removes hundreds of rows at once.

**Step 5. Look at exposure.** The same CVE is a different problem in an image on a private network than in one that faces the internet or sits next to your cameras. The asset graph shows what depends on what, which is how I decide between "update tonight" and "update with the next batch".

**Step 6. Take the cheap wins.** Pinning a tag, adding `init: true` and replacing an end-of-life base are each a one-line change. They do not appear in a CVE count, but they are what stops the count from creeping back up.

### One rule for reading scanner output

A scanner reports that a vulnerable *library* is present. It does not know whether your program ever calls the vulnerable *function*. A "critical" in a library your container never exercises is a smaller problem than a "high" in the thing listening on a port. That is why exploitation and exposure come before the severity column.

## My list for this week

1. **Update the three images that carry the known-exploited CVEs.** One of them, the camera recorder, carries three of the four by itself.
2. **Work down the image ranking** and update the top of it.
3. **Replace the four end-of-life images**, or move them to a maintained tag.
4. **Pin the tags** on everything not already pinned.

Then I rescan and see how far the number actually drops. A finding count that never moves is just a scoreboard, so I will report the before and after in the next post.

## Try it on your own lab

Everything above is open source. Start with [XIB](https://github.com/matijazezelj/xib), run it on a VM that has nothing else on it, and use `make up-safe`. Open the vulnerability dashboard first, then the threat-intel one, and try the funnel on your own numbers.

If it finds something silly in your setup, I would like to hear about it. That is how these tools get better.
