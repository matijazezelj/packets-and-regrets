---
title: "Why the Lab Is Boring on Purpose"
description: "The design choices behind a two-host Docker home lab: leaving Kubernetes, centralizing ingress, separating state, treating sockets as root, and applying before committing."
date: 2026-07-19T20:10:00+02:00
categories: ["Architecture"]
tags: ["Docker", "Design", "GitOps", "HAProxy", "PostgreSQL", "Security"]
---

The current lab is mostly Docker Compose, HAProxy, PostgreSQL, ZFS, and shell scripts.

That sentence would have embarrassed an earlier version of me. The previous version ran Talos Kubernetes with Flux because Kubernetes was interesting, GitOps was fashionable, and apparently a family photo library needed a control plane.

The cluster worked. It also turned every small operational question into a distributed-systems question. Eventually the useful lesson became obvious: a home lab should optimize for the operator's time, not for the number of CNCF logos in its diagram.

## Why Kubernetes left

Kubernetes gave me declarative resources, reconciliation, rolling deployment primitives, and a clean separation between workload intent and nodes. Those are real strengths.

The lab did not need most of them badly enough to pay their permanent cost:

- only one operator;
- mostly stateful, single-instance applications;
- no independent development teams sharing a platform;
- no burst scheduling requirement;
- storage and device passthrough tied to specific machines;
- failure recovery measured in minutes, not seconds.

Talos, Flux, ingress, persistent-volume machinery, and cluster debugging made ordinary service maintenance less legible. When the platform broke, I had to debug both the application and the abstraction intended to run it.

The migration back to Compose happened one service at a time. The old manifests remain archived as historical evidence, not as a resurrection kit.

## One Compose fragment per service

The current source tree uses one `compose.<service>.yml` file per service or tightly coupled stack, with an aggregate Compose file that includes them.

That structure provides most of the legibility I wanted from Kubernetes:

- a clear ownership boundary;
- small diffs;
- targeted deployment;
- straightforward bind mounts;
- service-specific health checks;
- no 2,000-line monolithic Compose file.

The unit of change is usually one service:

```text
./bin/deploy.sh prometheus
```

The wrapper matters more than the Compose command. It handles the SOPS dotenv round trip, pulls images, applies the selected services, removes orphans where appropriate, and shreds plaintext environment material afterward.

Running `sudo docker compose` is explicitly forbidden. `sudo` drops the invoking user's environment and can recreate containers with empty credentials. That failure mode is impressive because everything looks syntactically successful while authentication quietly burns down.

## Git-backed, not GitOps theatre

The Git repository is the source of truth, but production is not continuously reconciled by a privileged controller.

Each host keeps a clone, synchronizes its host-specific tree into a live directory, and deploys through the wrapper. The live directory is deliberately not a symlink because it also contains host-only runtime state and configuration that must not be bulldozed by a checkout.

The operating sequence is:

1. Edit the repository.
2. Validate Compose, config, and documentation.
3. Synchronize the narrow change.
4. Deploy the affected service.
5. Verify the real application path.
6. Commit and push after the running system is known-good.

“Apply before commit” sounds backward if Git is supposed to be the source of truth. In this one-operator environment it prevents a different problem: preserving an elegant commit for a deployment that never worked. Git records the verified state, while the deployment wrapper constrains how that state reaches a host.

There is no production Docker socket in CI. A green pull request is not allowed to become remote root on both hosts merely because somebody called it continuous delivery.

## One ingress, not one certificate problem per app

A dedicated HAProxy LXC terminates TLS and routes local hostnames to services across Docker hosts, VMs, and LXCs.

This centralizes:

- certificate renewal through DNS validation;
- LAN-only access rules;
- HTTP-to-HTTPS redirects;
- forwarded-header behavior;
- backend health checks;
- PostgreSQL leader routing.

Backends usually speak plain HTTP on the trusted server network. That is a conscious boundary, not a claim that internal traffic deserves no protection. The alternative—dozens of applications each implementing certificates, renewal, and proxy semantics differently—created more fragile security, not less.

HAProxy is handled like infrastructure: back up the configuration, validate with `haproxy -c`, and reload rather than restart.

## PostgreSQL: shared, clustered, and slightly absurd

Most PostgreSQL-backed applications use a three-node Patroni cluster. HAProxy sends connections to the current leader after checking Patroni's role API.

Is three-node PostgreSQL excessive at home? Obviously. It has still taught useful lessons about failover, replication lag, backup behavior, extension compatibility, and the difference between “three servers” and “a tested recovery path.”

One application remains on standalone PostgreSQL 14 because its query behavior exposed a compatibility problem on PostgreSQL 17. The exception is isolated and documented instead of forcing every new service onto the old database.

The rule is simple: shared infrastructure earns exceptions; exceptions do not become the new default.

## Local state versus NAS state

The intended storage policy is:

- databases and write-heavy metadata on local ext4 or PostgreSQL;
- media, recordings, document originals, and large libraries on NAS storage;
- explicit backups crossing those boundaries.

The policy exists because we violated it. Prometheus spent months writing its TSDB and WAL to NFS because the NAS was roomy and the VM disk was not. An NFS stall eventually blocked shutdown and corrupted a WAL segment.

A recovery watchdog restored service availability. It did not make the storage design valid. The TSDB migration remains a separate repair.

Rules written before an incident are architecture. Rules written after one are usually invoices.

## Docker sockets are root access

Several dashboards would happily accept `/var/run/docker.sock`. Mounting it read-only does not make Docker's API read-only; the socket still grants enough control to become root on the host.

The current approach is contextual:

- omit the socket when a service does not need Docker data;
- use a restricted socket proxy when read access is justified;
- firewall cross-host proxies to the one management source that needs them;
- disable mutating API verbs;
- verify the live capability mask and mounts instead of trusting Compose intent.

A prettier topology graph does not justify `NET_ADMIN`, host networking, and the Docker socket. Discovery features are allowed to be worse than compromise features.

## Monitoring asks whether work happened

Container health checks still matter, but they are the first check, not the conclusion.

The stronger checks ask application questions:

- Are new recordings appearing?
- Is the latest Prometheus sample fresh?
- Can the file service read through the actual NAS mount?
- Does DNS answer through both independent resolver paths?
- Did the backup complete, and can its contents be parsed or restored?

That distinction came from Frigate remaining container-healthy while recording nothing after a storage outage. Green health and missing data can coexist peacefully until somebody looks at the data.

## Backups follow the state layers

The backup design is intentionally redundant:

- nightly PostgreSQL dumps for fast logical recovery;
- restic snapshots of Docker application state;
- Proxmox Backup Server for VM and LXC recovery;
- a separate compressed stream mirror of the PBS datastore;
- monitoring metrics for backup age;
- restore validation when “the job ran” is not enough evidence.

The NAS is not the primary PBS datastore. Backing up every VM to the same appliance that already holds application bulk data would turn “off-host” into a creative spelling of “same failure.”

## The design rule underneath all of this

Complexity must remove more operational work than it creates.

Patroni sometimes passes that test because it is educational and shared. Kubernetes stopped passing it. A targeted recovery watchdog passes because it turns a known storage-recovery failure into a bounded action. A second permanent topology database probably will not, which is why two candidates are being evaluated side by side before one is removed.

The home lab is not minimal. It is **deliberate**. There is a difference, and every incident gets a vote.
