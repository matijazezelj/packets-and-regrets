---
title: "Nothing Was Red, and Three Things Were Dead"
description: "A power monitor dead for 22 days, a UPS feed missing for 8, a sync failing 1,216 times. The one alert that fired was muted until 2099."
date: 2026-10-16T15:55:00+02:00
draft: false
categories: ["Incident Reports"]
tags: ["Observability", "Systemd", "NUT", "Monitoring", "Homelab"]
---

I run Prometheus. I run Gatus. I have dashboards with so many green tiles that it looks like a golf course. And in the last three weeks, three separate things in my lab were quietly dead. Two of them never turned a single tile red. The third one did go red, for eight straight days, and I had personally made sure nobody would hear about it.

One was the thing that's supposed to shut my servers down cleanly when the power goes out. It was dead for 22 days.

I found all three in the same week, which is the only reason this is a post and not three separate bouts of denial.

## Regret 1: the power monitor that retired without telling anyone

Some background, because it matters. On September 9 my three Proxmox nodes decided the UPS was dying and shut themselves down at 3 AM. There was no power event. It was a known bug in the NUT version Debian ships (`upsmon` sets a "calibrating" flag when the UPS self-tests and never clears it). I wrote about the fix in my own docs: a "verified shutdown" guard that double-checks the UPS before letting a shutdown through. Good. Responsible. I was a little smug about it.

Then, on September 22, a relay blip made all three nodes *try* to shut down again. The guard did its job and blocked all three. Exactly what I designed it to do.

Here's what I didn't design for: `upsmon` exits with code **0** after it runs its shutdown command. Including when the guard blocks the shutdown. The stock systemd unit only restarts a service when it *fails*. Exit 0 isn't a failure. It's a clean, polite retirement.

So `upsmon` quietly clocked out, systemd said "fine, it finished," and all three nodes sat there with **no power protection at all**. My own notes say it plainly: the nodes stayed unmonitored for three weeks. The unit was never "failed." There was nothing to alert on, because from the machine's point of view nothing had gone wrong.

I fixed it on October 14 with a three-line systemd drop-in (`Restart=always`, `RestartSec=60`). Then I killed the unit on one node and watched it come back after a minute, because I've been burned by "fixed" before. The service's start timestamp on that node still says October 14, 22:18.

I'd like to say the guard worked perfectly. It did. It worked so perfectly that it created the second bug. That's the genre: **every safety net has a hole shaped like the net.**

## Regret 2: the UPS that stopped answering, and a relay that stopped asking

The same week, a different piece of the power chain. My UPS exposes its status over NUT. The NUT version in the container image I use for a small metrics relay can't pass credentials to the UPS, so the relay depends on the UPS answering anonymous reads. That works. I verified it with a raw socket probe when I built it.

On October 6 something on the UPS side was set to "credentials required." I don't know who or what flipped it. I'm not going to pretend I do. The docs I wrote after the fact say the setting was on from October 6 and I turned it off on the 14th, and that's all the evidence there is.

What happened next is a chain of polite failures:

1. The UPS answered "access denied" to the relay.
2. The relay's driver exited on start.
3. The relay went unhealthy.
4. The exporter that depends on the relay never started.

So for **8 days** I had no UPS data. No battery charge, no load, no runtime estimate. And the graph panels? They just... showed nothing. A blank panel is not a red panel. It's a panel that has quietly stopped talking to you.

Except this time something *was* red. Gatus has two UPS checks, "on mains power" and "battery above 30%", and both failed for the whole eight days. Gatus did its job. The thing that turns a red Gatus check into a message on my phone is a small watchdog script, and that script has an ignore list. On September 12, in the middle of the earlier NUT mess, both UPS checks went onto it. As a temporary mute. With an expiry date of **2099**.

I found that while fact-checking this post, which is a sentence I'd like to never write again. Think about what it means: "UPS on mains power" was the one check whose entire job is to tell me the power went out, and it had been switched off for a month. A real power cut would have produced a red tile and total silence. The mute is gone now. The expiry is the joke; the month without the one alarm that matters isn't.

Notice the pair. Regret 1 means the nodes weren't *listening* to the UPS. Regret 2 means I wasn't either. For a week I had a UPS, three nodes and a monitoring stack, and they were all politely not talking to each other.

## Regret 3: the sync that failed 1,216 times

The third one is the funniest and the most embarrassing, so it gets the most words.

I have a small script that syncs live state (Proxmox, network gear, compose files, my wiki) into an inventory tool, every 15 minutes, from a systemd user timer. I wrote it at the end of September, I liked it, I moved on.

On October 15 I finally looked at the journal. Here's what it said, counted from the actual log:

- Last successful run: **October 2, 16:51.**
- First failure: **October 2, 17:07.**
- Last failure before the fix: **October 15, 22:50.**
- Failed runs in between: **1,216.**

That's 13 days of a service failing every 15 minutes. It failed 1,216 times. Nobody told me, because nothing was *wired* to tell me. The timer kept firing. The service kept exiting non-zero. systemd kept dutifully marking it "failed" and the failed state kept sitting there in a place I never look.

The cause is a gem. The sync does a `DELETE` when something's been removed from the lab. On October 2 I retired a service (a workflow tool nobody used) and that was the first time the sync ever had to delete anything. I'd always sent every request with `Content-Type: application/json`, including a `DELETE` with no body. The inventory tool's HTTP framework answers a bodiless request that *claims* to be JSON with a **500**.

So the bug had been sitting there since I wrote the script. It was latent. It needed a deletion to wake it up, and my own cleanup supplied one. The fix is four lines: only set the JSON header when there's a body. The commit message calls it "broke every run since 2026-10-02," which is a very tidy way of writing "I didn't notice for two weeks."

And check this out, because it's the same lesson one more time: the script's own **dry-run mode** never caught it. Dry run returns early for anything that isn't a GET, so the request that was going to fail never got sent. I tested the thing by carefully not doing the part that breaks.

## What these three have in common

| What died | What the machine saw | Why nothing alerted |
|---|---|---|
| power monitor | clean exit, code 0 | not "failed", so no failed-unit signal |
| UPS data feed | two Gatus checks red, exporter gone | the alert was muted "temporarily", until 2099 |
| inventory sync | failed unit, every 15 min | failed state in a place nobody watches |

My monitoring was built around one question: **is the thing up?** HTTP 200, port open, container healthy. That's a good question for a web server. It's a bad question for a job. A sync job isn't "up." It runs, or it doesn't. A monitor that exits 0 isn't "down," it's *absent*, and absence has no metric.

I wrote about this exact trap in [Prometheus on NFS: Healthy Until It Wasn't](/posts/prometheus-on-nfs-healthy-until-it-wasnt/): a green health check is not a storage architecture. Turns out a green dashboard is also not a functioning power system. I keep relearning this at different levels of the stack. Ricky Gervais would say I'm a slow learner, and Ricky would be right.

## What I built: a boring watchdog

I did not install another observability platform. I'm still [in favour of boring](/posts/why-the-lab-is-boring-on-purpose/). I wrote one Python script (`unit-watchdog.py`, about 170 lines) and ran it from a cron job on the machine that already runs my agent, every 15 minutes, no LLM involved. It does three things:

- **Must-run list.** Per host, a list of units that have to be *active*: NUT monitors on the Proxmox nodes, the cluster services, Patroni, HAProxy and keepalived on both load balancers, Docker, the backup server, the sync timer. 15 targets in all. If one isn't active, that's an alert, even if it exited cleanly. This is the fix for regret 1: "not failed" is not "running."
- **Any failed unit, anywhere.** `systemctl --failed` on every host, plus the user session on the agent box. This is regret 3.
- **Can't reach the host.** If SSH fails, that's an alert too, because a watchdog that stays quiet when it can't see is just a prettier way to be blind.

Design rules I'm trying to keep it honest with:

- A problem must show up on **two consecutive runs** before it messages me. One blip isn't an incident, and I've had enough 3 AM false alarms this month.
- It **reminds me every 12 hours** while a problem persists, so "I'll look later" can't turn into 13 days.
- It sends **one "recovered" line** when something clears, so silence means good and not "it gave up."
- Empty output means nothing to say. No daily "all good" message to train me to ignore it.

First thing it taught me was humility: I immediately had to add a short ignore list, because five machines carry a failed IPMI unit. Those boxes have no BMC, so there's nothing for the service to talk to. I'd guess it has been failing since they were installed (that's inference, I didn't check the history), and I'd never once looked. That's a fourth silent failure, except this one is permanent and harmless, which is the best kind. I wrote the reason next to each ignore, so I don't mute a real one in six months and forget why.

## If you want to copy it

- **Ask "did it run?", not "is it up?"** For jobs, timers and daemons, the interesting signal is last-success age, not a port check. If your monitor is a timer, export the last-success timestamp and alert on its age.
- **Check what your units do on exit 0.** `Restart=on-failure` restarts nothing that exits cleanly. If a long-running daemon should never exit, use `Restart=always` and let `RestartSec` stop it from spinning.
- **A blank graph is a finding.** If a panel goes empty, that's a failure of the exporter, not a quiet day. Alert on `absent()` for things that must always report.
- **Your dry-run mode is not a test.** Mine skipped every write. Tell yourself which half of the code path it doesn't exercise.
- **Test the recovery, not just the fix.** I killed the unit and watched it come back. That takes a minute and it's the only proof that counts.
- **Write the reason next to every ignore, and give it an expiry you will actually live to see.** Future you is a stranger with a mute button. Past me apparently thought 2099 counted as temporary.

## What I don't know yet

- **I haven't proven the watchdog against a live incident.** It's registered, it runs every 15 minutes, and its state file is currently empty. That means it's seen nothing it considers a problem. It does not mean I've watched it catch something real. I'd rather say that than call it "battle-tested."
- **Who watches the watchdog?** It runs from my agent's scheduler. If that dies, I'm back to silence, just one layer up. A dead-man's switch is the honest answer and I haven't built it. This is inference about a gap, not a failure I've seen.
- **I don't know why the UPS setting flipped.** It might be a firmware update, a controller change, or me. The evidence only shows that it was on and then it wasn't.
- **The 22 days and 8 days come from my own notes and commit history**, not from a graph I can pull up now. The 1,216 failed runs come straight from the journal, counted this week.

The uncomfortable bit isn't any single bug. It's that all three of them were boring, ordinary failures that a decently built system should have *shouted* about. Two times the thing that was supposed to shout was waiting for a crash. The third time it was shouting, and I'd put a pillow over it. Something that quietly stops is not a crash. It's a resignation, and I hadn't given my lab a way to notice people leaving.
