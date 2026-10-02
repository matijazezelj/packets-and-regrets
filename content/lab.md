---
title: "The Lab"
description: "A public-safe map of the architecture, operating model, and design boundaries behind Packets & Regrets."
---

This is the stable overview behind the incident reports: enough architecture to explain the engineering, without publishing a reconnaissance pack disguised as documentation.

{{< diagram src="images/homelab-architecture.svg" alt="Logical home-lab architecture showing segmented clients, redundant DNS, HAProxy, two Docker hosts, PostgreSQL, NAS, security telemetry, Proxmox, and backup layers" caption="Logical roles and trust boundaries. Addresses, camera topology, firewall rules, and management endpoints are deliberately omitted." >}}

## At a glance

| Layer | Current shape |
|---|---|
| Compute | Four clustered Proxmox nodes running purpose-specific VMs and LXCs |
| Application runtime | Two Docker VMs, 81 running containers (October 2026 snapshot), plus a throwaway single-node k3s sandbox |
| Ingress | One HAProxy LXC for TLS and host-based routing |
| Databases | Three-node PostgreSQL/Patroni cluster, plus one compatibility PG14 instance |
| DNS | Two Pi-hole instances, each with its own recursive Unbound resolver |
| Storage | Local disks for databases and mutable app state; NAS for media and bulk documents |
| Backups | Nightly database dumps, restic, Proxmox Backup Server on RAIDZ2, and an off-host stream mirror |
| Security telemetry | [SIB](https://github.com/matijazezelj/sib): Falco on every host, UniFi syslog, and sandbox network flows, all in VictoriaLogs with Grafana on top |

## The request path

Clients receive two DNS servers through DHCP. Both can answer local service names and both recurse independently through their own Unbound instance. One-way configuration synchronization keeps the secondary useful without pretending two mutable Pi-hole databases can magically merge.

Most web requests terminate TLS at HAProxy. It routes by hostname to a Docker service, VM, or LXC. Application containers therefore do not each need to become miniature certificate-management projects.

PostgreSQL clients also enter through HAProxy. Health checks identify the current writable Patroni leader, so applications do not need to know which database node currently owns that role.

## The state path

The important boundary is not “container versus VM.” It is **latency-sensitive state versus bulk data**.

Databases and mutable application metadata belong on local filesystems or the PostgreSQL cluster. Media libraries, document originals, recordings, and backup repositories use the NAS. A legacy Prometheus TSDB-on-NFS decision violated that boundary and eventually corrupted its WAL; that incident has its own field note because architectural rules are more convincing after they invoice you.

## The operational path

Compose configuration lives in Git, split into one fragment per service. Each Docker host keeps a repository clone and synchronizes its host-specific tree into a separate live directory. A SOPS-aware deployment wrapper decrypts secrets into a real temporary dotenv file, deploys, verifies, and removes plaintext afterward.

Changes are applied and verified against the running system before being committed. That is not pure reconciliation-driven GitOps. It is intentionally boring Git-backed operations with a small blast radius and an audit trail.

## The failure boundaries

- The two DNS paths fail independently.
- The reverse proxy is separate from application hosts.
- One Docker host carries general applications; the other isolates NVR hardware, VPN-routed downloads, primary DNS, and one compatibility database.
- Shared PostgreSQL is clustered across three LXCs.
- Proxmox guests are backed up to storage that is not the NAS.
- The NAS mirror is a backup-of-backups, not the primary PBS datastore.
- Monitoring checks application behavior, not merely whether a container PID exists.

None of this makes a home lab “highly available.” Power, switching, storage, and the person operating it still create shared failure domains. The point is graceful degradation and diagnosable failures, not enterprise cosplay.

## Read next

- [How the architecture evolved]({{< relref "posts/why-the-lab-is-boring-on-purpose.md" >}})
- [What actually runs here]({{< relref "posts/what-runs-in-the-home-lab.md" >}})
- [Prometheus on NFS: Healthy Until It Wasn't]({{< relref "posts/prometheus-on-nfs-healthy-until-it-wasnt.md" >}})
