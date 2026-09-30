---
title: "I Gave My Network Gear a Voice. 99% of What It Said Was One Complaint."
description: "Shipping UniFi syslog into SIB (VictoriaLogs + Grafana), proving nothing was dropped, and finding out that almost every error was the same access-point chore."
date: 2026-09-30T18:00:00+02:00
draft: false
categories: ["Build Notes"]
tags: ["SIB", "UniFi", "Syslog", "VictoriaLogs", "Grafana", "Observability", "Detection Engineering"]
---

My security monitoring watched containers and hosts closely. It knew when a process opened something it should not have.

It knew nothing about the network gear those hosts sit behind. The gateway, the switches and the access points were a black box that occasionally reported "I dropped your internet for five minutes" through my family, in person.

That is a poor place to have a blind spot. So I pointed the appliances' syslog at [SIB](https://github.com/matijazezelj/sib), my SIEM-in-a-box, and read what they had been saying all along.

## The plumbing

The path is deliberately short:

```text
UniFi devices --UDP syslog--> VictoriaLogs (source=unifi_syslog) --> Grafana
```

There is no parser farm and no extra collector. VictoriaLogs accepts syslog natively, so the change in SIB was small: open one UDP listener, tag everything that arrives on it, and keep it for seven days. The commit is [a982d41](https://github.com/matijazezelj/sib/commit/a982d41070e289591e1d68eecbf0b6c345ff8596), and the dashboard followed in [430f00e](https://github.com/matijazezelj/sib/commit/430f00e).

Two decisions worth stealing:

- **One tag for the whole feed.** Everything from the controller gets `source=unifi_syslog`. Any query starts with that, and appliance noise never mixes with Falco events by accident.
- **Short retention on purpose.** Seven days is enough to answer "what happened last night" and small enough that I do not have to think about disk.

I asked the controller to enable syslog through its API first. It refused with a 403. The setting is one toggle in the UI, so I stopped arguing with a permission boundary and clicked it. Not every problem needs a clever workaround.

## First, prove it is not lying

A log pipeline that silently drops events is worse than no pipeline, because you trust it. Before reading a single message I checked the two ends against each other:

- **3,166** syslog datagrams received on the listener
- **3,166** rows in VictoriaLogs
- **0** errors, **0** drops

Boring is the desired result. Only now does the content mean anything.

## Then the content, which was mostly one thing

The first dashboard looked alarming: hundreds of errors. I did the thing I always tell people to do and grouped them before reacting.

Of **637** error records, **631** were the same message: an access point's `uplink-monitor` failing to resolve its own uplink, over and over. That is **99.1%** of all errors from a single, repetitive chore.

Was it a real fault? I checked, because "known noise" is only a safe label once you have proven it. The access points sat on healthy switch ports with healthy negotiated speeds. The device was clumsily asking a question it already knew the answer to.

So the dashboard now does two things:

- **It counts that message separately**, so it is visible and never deleted.
- **It excludes it from the "actionable errors" and "disruption" panels**, so a real error does not have to outshout it.

The rule I hold myself to is the same one I use for Falco tuning: an exclusion has to point at a proven pattern. "This looks annoying" is not a reason to hide a log line.

That left six error records that were not the chore. Those are the ones worth reading, and now I can find them in seconds instead of scrolling past hundreds of copies of nothing.

## The bug in my own dashboard

One panel was supposed to show how many distinct devices were talking. It said far more than I own. I had counted unique *messages*, not unique *senders*. Fixing it meant grouping by the remote IP of the sender ([77f5126](https://github.com/matijazezelj/sib/commit/77f5126)).

I am mentioning this because a dashboard that confidently shows the wrong number is how "monitoring" turns into decoration.

## What it is for

The immediate payoff is boring and useful: when the connection blips, there is now a timeline instead of an argument. Gateway events, DHCP renewals and access-point chatter line up on one screen with timestamps.

The larger point is coverage. A homelab that monitors its workloads but not its network is watching the house while leaving the front door unattended. Appliance logs are noisy, badly formatted and easy to ignore, which is exactly why nobody reads them until something is already wrong.

## If you want to copy it

- Enable remote syslog on the controller and point it at one UDP port.
- Tag the source at ingestion, not in the query.
- **Reconcile sent vs stored** before trusting the pipeline.
- **Group errors before reacting.** One noisy message can be nearly all of your volume.
- Separate known noise instead of deleting it, and require evidence for every exclusion.
- Count senders, not messages, when you claim coverage.

SIB is [open source](https://github.com/matijazezelj/sib) if you want the listener config and the dashboard JSON. It is the same stack described in [What Actually Runs in the Home Lab](/posts/what-runs-in-the-home-lab/), and it exists because [I like my lab boring](/posts/why-the-lab-is-boring-on-purpose/). Boring includes knowing what your switches are saying.
