---
title: "Prometheus on NFS: Healthy Until It Wasn't"
description: "A network filesystem stall blocked shutdown, corrupted the Prometheus WAL, and demonstrated why a green health check is not a storage architecture."
date: 2026-07-19T19:30:00+02:00
categories: ["Incident Reports"]
tags: ["Prometheus", "NFS", "Docker", "Observability", "Storage"]
---

The monitoring page was green. The container was healthy. Queries worked.

The storage design was still wrong.

I had put the Prometheus time-series database on an NFS share. It was roomy, already mounted, and moved roughly 30 GiB away from a Docker VM whose local disk was tight. This seemed like a reasonable home-lab compromise right up to the moment the NAS stopped answering.

Then Prometheus became the incident it was supposed to help explain.

## The decision that aged badly

The setup was simple:

```yaml
services:
  prometheus:
    volumes:
      - /mnt/shared/containers/prometheus:/prometheus
    command:
      - --storage.tsdb.path=/prometheus
      - --storage.tsdb.retention.time=30d
```

The reasoning was not completely stupid:

- The local VM disk was only 100 GiB.
- Prometheus retained 30 days and used about 30 GiB.
- The NAS had terabytes free.
- Query load was modest.
- NFS was already used successfully for media and bulk files.

The mistake was treating **low query volume** as **low storage sensitivity**. Prometheus still relies on memory-mapped files, a write-ahead log, atomic filesystem operations, and predictable `fsync` behavior. Those requirements do not disappear because only one person reads the graphs.

Prometheus documents that its local storage is not supported on NFS. I had read the warning and mentally translated it into “probably slower.” That translation was convenient and wrong.

## The incident

The NAS began stalling shortly after 22:00. The Docker host recorded repeated transitions like these:

```text
22:06:42 nfs: server not responding, still trying
22:07:21 nfs: server OK
22:11:13 nfs: server not responding, still trying
22:20:12 nfs: server OK
```

The mount was a hard NFS mount. That protects applications from silently receiving partial I/O failures, but it also means a process can wait indefinitely for the server to return.

Prometheus stopped producing fresh samples. A recovery watchdog correctly waited until the NAS was reachable again, checked a sentinel through the actual mount, repeated the application-level check, and attempted to restart only Prometheus.

Docker could not stop it:

```text
Container failed to exit within 10s of kill - trying direct SIGKILL
error killing container: context deadline exceeded
Cannot restart container prometheus: tried to kill container,
but did not receive an exit event
```

The pattern was consistent with Prometheus being blocked in network-filesystem I/O. A container boundary does not make blocked kernel I/O disappear. `SIGKILL` is not a magic crowbar for a process waiting inside a hard NFS operation.

When storage finally recovered, the restart completed. Prometheus then found what the interruption had done to its write-ahead log:

```text
Encountered WAL read error, attempting repair
corruption in segment /prometheus/wal/00000902 at 45023232:
unexpected checksum
Starting corruption repair
Deleting all segments newer than corrupted segment
Rewrite corrupted segment
Successfully repaired WAL
```

And, in case the point remained unclear, it printed this immediately afterward:

```text
This filesystem is not supported and may lead to data corruption
and data loss. fs_type=NFS_SUPER_MAGIC
```

Subtle.

## What survived

Prometheus repaired the WAL and returned to service. After recovery:

| Check | Result |
|---|---|
| Container health | Healthy |
| Configuration reload | Successful |
| Retention | 30 days |
| Active series | About 42,000 |
| TSDB blocks inspected at startup | Healthy |
| Recorded corruption count | 1 |

Historical blocks remained readable. The repair may have discarded recent samples from the damaged WAL tail; I cannot prove an exact loss window, so I will not manufacture one.

The monitoring system was functional again. The architecture was not fixed.

## The watchdog did its job—and exposed its limit

The recovery watchdog was designed after an earlier NAS outage left applications “healthy” while they had stopped doing useful work. It deliberately avoids blanket restarts:

1. Require repeated application-level failures.
2. Do nothing while shared storage is unavailable.
3. Read a sentinel through the real mount after storage returns.
4. Repeat the application check.
5. Restart only the application that remains wedged.
6. Apply a cooldown and latch to avoid restart storms.

That logic was correct. It detected stale Prometheus samples and eventually recovered the service without restarting unrelated containers.

But a watchdog is mitigation. It cannot make an unsupported filesystem supported, and it cannot reliably terminate a process blocked in hard-mount I/O. Automation does not repeal filesystem semantics.

## The adjacent capacity problem

Moving the TSDB back to local storage required more room in the Docker VM. The hypervisor's ZFS root pool appeared nearly full, which initially made expansion unattractive.

The actual space consumer was not live VM data. Recursive automatic ZFS snapshots on the dataset containing sparse qcow2 VM images were retaining old blocks:

| Before cleanup | Value |
|---|---|
| Pool allocation | 88% |
| VM-image snapshots | 25 |
| Snapshot space pinned | About 125 GiB |
| Latest VM backup | Successful on PBS |

Those snapshots duplicated a job already handled better by nightly Proxmox Backup Server backups. After verifying the latest backup and checking for snapshot holds, I disabled automatic snapshots only on the VM-image dataset and removed its 25 existing snapshots.

The pool fell from 88% to 34% allocation and gained roughly 125 GiB. Root-filesystem snapshots stayed enabled, and the running VM disk was unchanged.

This is another layered-storage trap: qcow2 copy-on-write inside ZFS copy-on-write, with recursive snapshots on top, is very good at retaining blocks you thought you had deleted.

## The real repair

Prometheus still needs a controlled migration. The plan is:

1. Expand the Docker VM disk.
2. Grow the ext4 filesystem online.
3. Copy the TSDB to `/opt/docker-data/prometheus` while Prometheus runs.
4. Stop only Prometheus.
5. Perform a short second synchronization.
6. Switch the Compose bind mount to local storage.
7. Start Prometheus and verify readiness, WAL replay, queries, targets, and dashboards.
8. Keep the old NFS copy temporarily as rollback material.
9. Delete it only after a separate retention decision.

The destination is also covered by encrypted block-level backups, but Prometheus remains a disposable monitoring database: backups are useful; the ability to rebuild it is more important.

## Lessons worth keeping

### “Healthy” describes now, not the design

A health endpoint can prove that an application answered one request. It cannot prove that its storage is supported, durable, or likely to survive the next network interruption.

### Databases do not belong on a filesystem merely because it is mounted

Media files, backup archives, and database write-ahead logs have different correctness requirements. “NFS works elsewhere” is not evidence that NFS is appropriate here.

### Recovery automation should wait for dependencies

Restarting applications while storage is still unavailable creates noise and can make recovery worse. Confirm dependency recovery first, then act narrowly.

### Snapshot policy must understand the data below it

Recursive snapshots across frequently changing VM-image datasets can consume extraordinary space. PBS backups made those snapshots expensive redundancy, not useful protection.

### Warnings are not decorative prose

Prometheus said NFS was unsupported. The incident did not reveal an undocumented edge case. It collected the debt on an explicitly documented shortcut.

That is the annoying thing about good warnings: when you ignore them, they tend to remain correct.
