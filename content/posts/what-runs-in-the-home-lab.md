---
title: "What Actually Runs in the Home Lab"
description: "A curated inventory of the services behind 81 running containers—what each group does, why it exists, and which pieces are temporary."
date: 2026-07-19T20:20:00+02:00
categories: ["Lab Notes"]
tags: ["Docker", "Self-hosting", "Services", "Observability", "Home Lab"]
---

At the publication snapshot, the two Docker hosts were running **76 containers**: 61 on the general application host and 15 on the specialist host.

> **Update, 2 October 2026:** the count is now **81** (60 and 21). The lab changed more than the number did. n8n is gone (see below), the GPU VM that ran Ollama is gone, and the cluster is down to four Proxmox nodes. The rest of this inventory is left as originally written, with corrections marked where they matter.

That is not 76 independent products. Sidecars, exporters, databases, browser workers, VPN helpers, and document processors inflate the container count. This inventory groups them by the job they perform instead of pretending every YAML service deserves its own logo wall.

It also omits exact addresses, internal names, camera topology, credentials, firewall details, and management paths. A service catalogue should explain the system, not pre-write somebody else's reconnaissance report.

## Core network and access

### HAProxy

One dedicated LXC terminates TLS and routes applications by hostname. It also sends PostgreSQL traffic to the current Patroni leader. Keeping ingress outside the Docker hosts means an application-host incident does not automatically erase the front door's diagnostics.

### Pi-hole, twice

Two Pi-hole instances are handed to clients through DHCP. The primary and replica live on different Docker hosts. One-way Nebula Sync copies gravity-related configuration from primary to secondary every 15 minutes.

The synchronization is intentionally not bidirectional. There is no merge algorithm; two writers would merely provide a more sophisticated way to overwrite the correct configuration.

### Unbound, twice

Each Pi-hole has its own Unbound resolver on a private Docker bridge. Both validate DNSSEC and recurse from the root rather than forwarding every query to a public resolver. This gives the two advertised DNS paths independent recursive backends instead of two frontends sharing one hidden dependency.

### UniFi gateway and network

A UniFi gateway provides DHCP, firewalling, and segmentation. Management, home devices, children, IoT, guests, and restricted systems do not all receive the same trust merely because they share a building.

## Productivity and personal data

### Paperless-ngx

Paperless stores documents, extracted text, correspondents, tags, and workflow state. Document originals live on bulk storage; structured application state uses PostgreSQL. Redis, Gotenberg, and Tika provide queueing and document conversion/extraction.

Two AI companions are currently present: the established Paperless-AI integration and a guarded evaluation of Paperless-AI Next. Automatic whole-archive changes are disabled for the evaluation path; only explicitly tagged test documents are eligible.

### Karakeep

Karakeep is the durable inbox for links worth keeping. A headless browser captures pages, Meilisearch indexes them, (AI tagging was originally wired to a local Ollama; that GPU VM has since been retired, so the archive is searchable but no longer machine-summarized).

### Miniflux

Miniflux handles RSS without trying to become a social network, a read-later gamification engine, or a lifestyle brand. It retrieves feeds and gets out of the way.

### Super Productivity and WebDAV

Super Productivity handles task and time tracking. A small WebDAV sidecar provides synchronization. HAProxy performs path-based routing so the application and sync endpoint share one user-facing origin.

### Vaultwarden

Vaultwarden provides the Bitwarden-compatible server used by family clients. Database state sits in PostgreSQL; attachments and other file state are covered separately by restic. It is one of the services where “the container starts” is several checks short of “recovery works.”

### Gitea and MkDocs

Gitea holds the active homelab repository and other personal Git projects. MkDocs renders the private operational wiki from repository-backed Markdown. The wiki remains private; public articles are rewritten and sanitized in this separate blog repository.

### n8n (retired)

*Update, 2 October 2026: removed.* n8n was meant to provide non-critical workflow glue: health snapshots, Telegram summaries, and alert enrichment. It was deliberately not the monitoring source of truth. Gatus and Prometheus decide what happened, and Gatus alerts go straight to the agent that handles them.

Before deleting it I checked its database: **six workflows, zero executions, ever.** It had spent its entire life being healthy-looking and unemployed, and it fell over with a stuck connection pool the first time anyone looked. Rule five below ("someone actually uses it") has veto power, and it used it. I kept a final database dump, dropped the database and role, and removed the containers, routes, checks and dashboard tile.

## Photos, audio, and media

### Immich

Immich handles photo and video backup, browsing, search, and machine-learning features. Uploads and the read-only existing library use NAS storage; relational metadata lives in PostgreSQL. Machine-learning and Valkey sidecars account for additional containers.

### Audiobookshelf and Navidrome

Audiobookshelf serves audiobooks and podcasts. Navidrome provides music streaming through the Subsonic ecosystem. Both keep replaceable media on bulk storage while retaining application metadata separately.

### Frigate

Frigate runs on the specialist Docker host because that VM owns Coral TPU passthrough and camera storage access. A notification companion handles event messaging.

Frigate earned special monitoring after a CIFS interruption left the container healthy, camera FPS normal, and recordings completely stalled. Current checks inspect database recording timestamps and physical media progress rather than trusting `/api/stats` alone.

### Jellyfin

Jellyfin runs outside the Docker hosts in its own LXC. Not every workload benefits from joining the main Compose inventory, especially when an existing isolated service already works.

## Media acquisition

### qBittorrent through Gluetun

qBittorrent shares the specialist host with Gluetun. Its network path is VPN-isolated, with a helper for forwarded-port updates and a Prometheus exporter for operational visibility.

The isolation rule is stronger than “the VPN container is healthy.” qBittorrent's network namespace is tied to Gluetun so losing the tunnel does not silently move traffic to ordinary egress.

### The Arr stack

The automation group includes:

- Sonarr for television;
- Radarr for films;
- Lidarr for music;
- Prowlarr for indexer coordination;
- Bazarr for subtitles;
- Jellyseerr for requests;
- Unpackerr for post-download extraction;
- FlareSolverr for the unpleasant corners of indexer access.

Exporters expose selected application metrics. A standalone PostgreSQL 14 container remains for Sonarr because an observed query compatibility issue on PostgreSQL 17 made “standardize everything” less useful than “keep one documented exception.”

## Monitoring and operations

### Prometheus and Grafana

Prometheus collects infrastructure and application metrics; Grafana visualizes them. Export sources include node-exporter, cAdvisor, UniFi Poller, Pi-hole exporters, Arr exporters, qBittorrent exporter, and speed-test data.

Prometheus currently carries documented storage debt: its TSDB remains on NFS after a WAL-corruption incident. It recovered, but “working now” is not being misrepresented as “fixed.”

### Gatus

Gatus performs direct endpoint checks and sends alerts. It covers HTTP behavior, DNS, infrastructure APIs, and selected external dependencies. Two consecutive failures are required for the Telegram watchdog because one failed sample during a planned Pi-hole synchronization is noise, not an incident.

### Homepage

Homepage is the human launchpad. It provides links and status widgets, but it is not authoritative inventory. Dashboards are excellent at becoming decorative fiction when nobody decides which system owns the truth.

### Dockhand and a restricted socket proxy

Dockhand manages Compose workloads across both Docker hosts. Local access uses the main host's socket; cross-host access goes through a restricted Docker API proxy protected by host firewall rules.

A Docker socket is root access with a friendlier pathname. The remote proxy exposes only the API surface needed for management and accepts traffic only from its expected source.

### Dozzle

Dozzle provides live container logs from agents on both Docker hosts. Loki and its shipping stack were retired because the current need is fast incident inspection, not indefinite centralized log retention.

### Homelable and RackPad

Two infrastructure-visualization tools are temporarily running side by side. This is an evaluation, not a commitment to duplicate inventory forever. RackPad is constrained without a Docker socket, host networking, or packet-level capabilities; Homelable remains available while representative workflows are compared.

One will be removed. A home lab does not need two databases disagreeing about which cable goes where.

### Dependency-Track

Dependency-Track receives CycloneDX SBOMs and tracks component exposure. It exists because vulnerability management is more useful as an inventory-and-impact question than as another stream of unactioned scanner output.

## Utilities

Several smaller tools earn their place by doing one bounded job:

- **ConvertX** for file conversion;
- **IT-Tools** for developer utilities;
- **OpenSpeedTest** for LAN throughput checks;
- **Smokeping** for latency history;
- **Caddy file browser** for read-only access to selected files;
- **Dozzle** for immediate logs;
- **an e-school notification bot** for family logistics.

These are the easiest services to retire when usage disappears. Self-hosting does not improve when every experiment becomes permanent infrastructure.

## Services that are not containers

The wider lab also includes:

- four clustered Proxmox nodes (two more retired along the way, one of them powered off to save electricity);
- a three-node Patroni PostgreSQL cluster;
- Proxmox Backup Server with a five-disk RAIDZ2 datastore;
- a NAS for bulk application data and backup mirrors;
- Home Assistant OS;
- a Jellyfin LXC;
- the HAProxy ingress LXC;
- a restricted remote-access exit point.

Container count therefore measures deployment density, not the size of the system.

## What qualifies a service to stay

A service should satisfy at least one of these:

1. It protects important data or access.
2. It replaces a paid or privacy-hostile dependency.
3. It removes recurring manual work.
4. It teaches something worth its operating cost.
5. Someone in the house actually uses it.

Number five has veto power over many beautifully engineered answers.

The inventory will change. That is why this is a dated snapshot rather than a claim that 81 containers represent a personal achievement. The useful question is not “how many services can run?” It is “how many failures can one person still understand?”
