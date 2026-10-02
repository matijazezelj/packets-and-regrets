---
title: "I Put One Docker App on Kubernetes. Download Was Fine. Upload Fell Off a Cliff."
description: "A throwaway k3s + Cilium + Hubble cluster, its flow logs shipped into SIB, four apps moved over, and a speed test that caught me grading my own homework with half the questions missing."
date: 2026-10-02T17:14:00+02:00
draft: false
categories: ["Build Notes"]
tags: ["Kubernetes", "k3s", "Cilium", "Hubble", "SIB", "VictoriaLogs", "Observability", "Homelab"]
---

I run my lab on Docker Compose and I'm happy there. It's a text file. It does the thing. Nobody has ever needed a certification to read a compose file.

Then a new k3s release dropped and the itch started: what would one of my perfectly boring apps feel like on Kubernetes? You know this itch. It's the same one that makes grown men buy a second smoker.

So I built a sandbox. One VM, two cores, 8 GB of RAM, **deliberately not in the backup scope**. If it dies, I rebuild it from git. Best design decision of the whole project, and I made it before I'd screwed anything up, which is not my usual order of operations.

The stack: k3s with flannel, kube-proxy and the built-in network policy turned off, and [Cilium](https://cilium.io/) doing all three jobs instead. I didn't pick Cilium for the apps. I picked it for [Hubble](https://github.com/cilium/hubble), because I wanted to see what flow-level network telemetry looks like when it lands in the same SIEM as everything else. The apps were the excuse. The packets were the point.

## Hubble at idle is a firehose of nothing

Turned on flow export, went to get coffee. Came back to an *idle* cluster, a couple of test pods doing absolutely nothing, producing about **21 flows per second**.

Twenty-one a second. For nothing. That's not telemetry, that's a toddler narrating the drive to the grocery store.

I sampled 2,246 of them before touching anything. Nearly all were per-packet trace events: every ACK, every PSH, every FIN. Zero application-layer data. I was one default setting away from paying to store TCP's inner monologue.

The fix goes at the source, not downstream. Filter in the shipper and you've already written everything to disk first, which is like fixing a flooded basement by buying a better mop. So the filter lives in the Cilium exporter:

- **Keep:** anything that isn't a plain "forwarded" verdict (drops, errors, audits), policy verdicts, L7 events, and new TCP connections (a SYN with no ACK, request side only).
- **Drop:** per-packet trace, kubelet and host probes, and two kinds of noise I named by looking at them, not by guessing.

Noise one was `VLAN_FILTERED`: device-discovery broadcast from other VLANs reaching the node. That's the network being chatty, not the cluster misbehaving. Noise two was `UNSUPPORTED_L2/L3_PROTOCOL`: IPv6 neighbour discovery from pod interfaces on a cluster that is IPv4-only. The cluster whispering to a protocol that isn't there.

Same rule I use for Falco tuning: an exclusion has to point at a pattern I can *name*. "This looks annoying" is not evidence, it's a mood.

## Into SIB

The shipper is a small [Vector](https://vector.dev/) DaemonSet. It tails the exported file, flattens each flow into fields a human can read (`src` and `dst` as `namespace/workload`, verdict, drop reason, protocol, port), and posts JSON lines to VictoriaLogs tagged `source=hubble`. There's a disk buffer so a log-side outage doesn't eat flows.

To prove it works I needed something worth catching, so I did what any responsible adult does: built a victim and an attacker. A default-deny policy on one namespace, a pod that keeps knocking on its door. The dashboard now shows this, with names instead of IPs:

```text
DROPPED demo/attacker -> locked/db tcp/80 [SYN] (POLICY_DENIED)
```

*That's* the product. Not "Kubernetes metrics." Who tried to talk to what, and who got told no. It's a bouncer's clipboard, and I wanted one.

## The regrets

Every one of these was my own doing. I looked for someone else to blame. There's nobody else in the room.

1. **A semicolon ate the VM.** `--tags automation;lab`. To bash that's two commands. The first created an empty stub VM; the second died with `lab: command not found`. Quote your tags, you animal.
2. **`helm upgrade` does not restart Cilium.** I changed the export filters, admired the lovely quiet config, and the old loud filters just kept running. A ConfigMap change doesn't roll the agent. I was very impressed with my work, which wasn't running.
3. **I deleted a file while a process was writing to it.** `rm` on the flow log with the agent holding it open. The agent happily wrote to an unlinked inode and the shipper read an empty file. You didn't delete it. You *hid it from yourself*. Not my first time, either.
4. **I broke my own dashboard link with a Helm upgrade.** I'd exposed the Hubble UI by hand-patching a Service, then ran `helm upgrade` for something unrelated. Helm put the Service back to whatever the values file said. If it's not in the values file, it doesn't exist. It's *on loan*.
5. **The firewall was doing its job, at me.** Requests to the log store just hung. The log host deliberately blocks that port from the LAN, which is the entire point of that rule. I got defeated by my own security. The fix was one rule: one source, one port, backup first. Not "just open it," because I'd never hear the end of it from myself.
6. **A container wouldn't start with every Linux capability dropped.** `exec: operation not permitted`. The binary carries a file capability, and exec fails if it's missing from the bounding set, even though the port it listens on needs no privileges whatsoever. Added back exactly one capability. The least-privilege crowd can wait outside.
7. **The cloud image had no NFS client.** Port open. Allow-list done. Mount still failed. A plain `mount -t nfs` test *before* involving Kubernetes would have saved me an hour and a little dignity.

## Moving four apps

I moved four small apps: a static tools page, an RSS reader, a speed test and a read-only file browser. Each one lived in a compose file of about a dozen lines. Each became a Deployment, a Service and an Ingress. The YAML-to-benefit ratio is... let's call it "character building."

For the static page I ran two replicas and then did the only test I actually trust: **kill both pods under steady load and count what breaks.** At ten requests a second through the real path, **5 of 210** requests failed. A rolling update lost **1 of 208**. It's one node, so both replicas die together. Two replicas on one machine protect you from a bad deploy, not a dead node. It's two seatbelts in a car with no wheels.

The RSS reader was the interesting one, since its state lives in an external Postgres cluster. It connected through the same load balancer the Docker copy uses with zero ceremony, and Hubble showed me the whole thing: the pod, the database port, a count. I ran it with its feed scheduler disabled so two copies never fight over polling or schema migrations. The Docker copy stays the grown-up in the house.

The file browser was the first one with storage: a read-only NFS volume from the NAS, declared as a PersistentVolume. Listings matched the Docker copy exactly, and a write from inside the pod gets `Read-only file system`, which is the right answer and the only time all day a computer told me no and I was happy about it.

## The part where my own test lied to me

I measured the speed test with `curl`, got about 2 Gbit/s down, noted it matched the Docker copy, and wrote "same" in my notes. Moved on. Pleased with myself.

Then I opened it in an actual browser, which is, and I cannot stress this enough, *what a speed test is for*:

| | Download | Upload |
|---|---|---|
| Docker copy | 942.8 Mbit/s | 687.5 Mbit/s |
| Kubernetes copy | 936.5 Mbit/s | **6.3 Mbit/s** |

Download: fine. Upload: fell off a cliff. The curve looks like a transfer that starts out confident and then quietly gives up on life.

I tested one direction and declared them identical. That's not a result. That's a gap in the test wearing a result's jacket. My claim had exactly as much evidence as I'd collected, which was **half**. You can't grade your own homework with half the questions missing and then act surprised when someone else checks the back of the book.

So I went hop by hop, and this time I sent bytes in the direction that was actually broken.

First, rule out the usual suspect. MTU was 1500 end to end and don't-fragment pings were clean. Not it. Then real POST bodies at three sizes through each layer. 1 MB and 8 MB: perfect everywhere. 30 MB: the upload through the load balancer reached the app about 17 MB in and then just *stopped*. The Docker copy took all 30 without blinking.

Two things I'd like to have known an hour earlier. A 50 MB upload returned `413` on **both** copies, which is just the speed test's own body limit, and a red herring that cost me ten minutes of feeling clever. And from a different machine, the same 30 MB went through the ingress in full. A failure that depends on who's asking is a race, which is exactly why one curl from one box fooled me the first time.

Here's what I think is happening, and I'm labelling it inference because I did not attach a debugger to a reverse proxy to prove it. The speed test's nginx answers every upload with an instant, cheerful 200 without reading the body. Talking to it directly, that's fine. Put a Go reverse proxy in front and the proxy sees a response arrive while the upload is still in flight, decides the conversation is over, and hangs up with the body unread. The client sees an upload that quietly stops mid-sentence. The Docker copy has no such proxy in front, so nothing ever hung up on anyone.

The fix is one object: a buffering middleware on the ingress, so the proxy reads the whole body before forwarding it. The evidence it's the right one is boring and solid: the truncation reproduced on demand before, and doesn't now. Full 30 MB, every run. Then, because curl already lied to me once, the actual browser, back to back in the same session:

| | Download | Upload |
|---|---|---|
| Docker copy | 2432.4 Mbit/s | 2184.5 Mbit/s |
| Kubernetes copy, after the fix | 901.3 Mbit/s | **1927.2 Mbit/s** |

Upload went from 6.3 to 1927, and the curve is flat instead of dying. The cliff is gone.

It ends with a smaller mystery, which is the good kind. The Kubernetes download is less than half the Docker one, with a ragged curve. I haven't measured why. My bet is a two-core VM doing a lot of work for two extra hops, but that's a bet, not a result, and I've been burned by those today.

## What I'd tell someone considering it

- **The apps are the easy part.** A dozen lines of compose turned into about fifty of YAML, and none of it was hard. Just *more*.
- **Secrets are the missing piece.** My Docker side has a proper encrypted-secrets workflow. The cluster had a Secret I made by hand. Anything that matters needs a real answer there first, and "I made it by hand" isn't one.
- **Routing is a new place to break.** Every app needs a hostname rule at the load balancer. The old `*-k8s` catch-all from a previous cluster pointed at a machine that no longer exists, and nothing complained. A lighthouse in the desert, still faithfully pointing at the sea.
- **A proxy in front changes how apps behave.** An app that never reads its request body works fine until something in the middle takes that personally. Test every direction, not just the easy one.
- **The payoff is visibility, not features.** Rolling updates, declared state in git and flow-level telemetry are real. Everything else compose already did, with fewer moving parts and fewer meetings.

I kept the Docker copies as production. The cluster stays as a sandbox, which is the correct job for something that taught me seven ways to be wrong in a single afternoon.

If you want the SIEM side, [SIB](https://github.com/matijazezelj/sib) is open source. It's the same stack from [What Actually Runs in the Home Lab](/posts/what-runs-in-the-home-lab/), and it exists because [I like my lab boring](/posts/why-the-lab-is-boring-on-purpose/). Boring includes knowing which half of your test you skipped.
