---
title: "My Watchdog Restarted My NVR 141 Times. It Was Guessing."
description: "141 restarts, a motion-only recorder, and a watchdog that mistook missing recordings for broken storage. The counter had no alert."
date: 2026-10-23T15:55:00+02:00
draft: false
categories: ["Incident Reports"]
tags: ["Watchdog", "Monitoring", "Frigate", "Homelab", "Automation"]
---

Last week I wrote about [three things that died quietly while every dashboard stayed green](/posts/nothing-was-red-and-three-things-were-dead/). Monitoring that fails to notice a death. Fine. Classic.

This week's is the opposite and, honestly, worse: a thing that **kept restarting a recorder without establishing that storage was broken**, for three months, because I taught it what "broken" looks like and I taught it wrong. And it had a counter. The counter went up 141 times. I have a Grafana panel definition for that counter. I can't swear I ever looked at the thing.

## The setup: a good idea with a loaded gun

My NVR (Frigate, running in Docker) writes recordings to a NAS share. Every so often the share wedges. The NAS blips, the mount goes stale, Frigate keeps "recording" into a hole, and nothing recovers until somebody restarts the container. On July 18 I got tired of being that somebody and wrote `nas-recovery-watchdog.py`.

It's not a stupid script. Credit where it's due:

- It runs from a systemd timer about once a minute.
- It reads the recordings database and asks "when did each camera last commit a segment?"
- If a camera is more than 180 seconds stale **three checks in a row**, that's a failure.
- Before restarting anything it reads a sentinel file off the NAS to make sure the storage is actually readable. No point restarting into a dead mount.
- It refuses to restart if the camera *input* is dead (that's not a storage problem).
- One restart per hour, max, plus a latch. No restart storms. I was proud of the restart storms thing.

Here's the part I got wrong in one sentence: **"no new segment in 180 seconds" does not mean "storage is wedged."** It means "nothing was recorded in 180 seconds." Those are the same thing if you record continuously. I don't record continuously.

## Regret 1: I forgot my own retention policy

My Frigate config uses motion-only retention. I checked the running configuration before publishing: `continuous: 0`, `motion: 14` days, globally and for both cameras. It keeps motion segments rather than a continuous archive. A quiet camera for ten minutes can legitimately commit **nothing**. No retained segments, no new recording rows, "stale" by the watchdog's definition, without that establishing a storage failure.

I wrote the watchdog. I also chose the retention policy. Same brain. The two never met.

So the failure mode I built in was this: a quiet camera could go stale, three failed checks could trigger recovery, and a passing storage-sentinel read could allow a restart without proving writes were broken. Then, as far as I can tell, the fresh container could sit there retaining nothing until something moved and the check passed. Repeat tomorrow. That's a mechanism supported by the code and retention settings, not an end-to-end trace of any particular restart.

## The numbers, from the journal on the host

I'm not guessing here. I pulled these from the watchdog's journal and the textfile metric on the box, this week:

- **141** restarts. The Prometheus counter says 141, and counting `RESTARTED` lines in the journal also says 141. I like it when two things agree.
- First restart July 19, last one October 18 at about 10:17 local time. That's 91 days, roughly 1.5 a day.
- **6,679** Frigate failed-check lines in the retained journal: **6,676 before the change, three after**. These are failed checks, not confirmed storage failures; they include more than stale-recording results.
- There's a gap with no restarts from mid-August to the end of August. I don't know why. I have no evidence for any theory, so I'm not offering one.
- The restarts cluster at two times of day. I can see the clustering. I haven't proven what's behind it, and I'm not going to make up a story because it'd read well.

The container's own restart counter says 0, by the way. That's because `docker restart` isn't a crash, it's an *instruction*. Docker was told to do it by a nice, polite Python script. Nothing in Docker's view was ever wrong.

## Regret 2: the counter had no one to tell

Now the part that actually stings. I did build observability. The watchdog exports `nas_recovery_watchdog_restarts_total`. There's a panel for it in my backups-dashboard configuration. So I had a counter and some Grafana JSON. Apparently I thought that counted as watching. There's even a Prometheus alert for the watchdog...

...and that alert is `nas_recovery_watchdog_check_ok == 0 for 10m`. It tells me when the check is *failing*. It does not tell me when the watchdog is *acting*. The script runs a verification step after a restart; if that passes, it can reset the failure condition before those ten minutes are up. That's the failure mode inferred from the code, not proof of the alert history for each incident. I queried the running Prometheus rules before publishing: the watchdog has that failure alert, but no rule references its restart counter.

I built a smoke detector that can't tell the difference between a fire and the fireman showing up.

A restart counter that increments 1.5 times a day is not a recovery metric. It's the most obvious "this thing is lying to you" signal I own, and I put it in a dashboard definition without establishing that it was telling me anything useful. That's not monitoring. That's a decorative tile.

## What I did about it

Commit `ff039e5`, October 18. One new config option, `stale_mode`:

- `any` (the old behaviour): any single camera stale = failure.
- `all`: failure only if **every** watched camera is stale at once.

The reasoning is the thing I should have written in July. A share-wide storage failure is expected to affect all cameras; one quiet camera needn't mean shared storage is broken. That's still an assumption, not a diagnosis: partial failures and two quiet cameras are both possible. Frigate also has its own recording watchdog; piling another trigger on top needs a better reason than one old database timestamp.

A quiet camera is now logged as "recordings current on at least one camera; quiet (no motion kept)" and moves on with its life.

## Did it work? Mostly. Don't clap yet.

Since the fix: **zero restarts** in five days, and the Frigate container's start time still says the October 18 restart. Three failed-check lines total, instead of the usual hundreds.

But look at those three lines, because they're the honest part. They're two episodes where **both** cameras were stale at once. The first stopped at strike 1. The second, a day and a half later, reached strike 2 of 3 before recovering. `all` mode would have restarted on a third strike. It didn't, but it got two thirds of the way there on a night when I can't show anything was wrong.

Before publishing, I paired each retained restart with the most recent distinct failed-check result. **87** followed a single stale camera. **39** followed both cameras being stale. The other **15** followed a connection refusal from Frigate's stats API—not a stale-recording result at all. That tells me the API wasn't reachable at that check. It doesn't hand me a signed confession from the NAS.

`all` mode removes the single-stale-camera trigger behind those 87 cases. It doesn't establish what caused the 39 both-stale cases, and it doesn't eliminate API failures. When I wrote "~141 false restarts" in the commit message I was rounding up my confidence. I can't prove they were all false. I suspect some both-stale cases were two quiet cameras at the same quiet moment, but that's inference and I'm labelling it as inference.

So the real state is: I turned a restart-every-16-hours problem into a rarer one. That's progress. It's not a fix. A proper fix is a check that tests the thing I care about (can I write to the share?) instead of using "did a camera see motion" as a proxy for it.

## If you want to copy this (the useful part)

1. **A proxy metric is a lie with good manners.** "No new segments" stood in for "storage is broken." They correlate until your config changes what a segment *is*. Test the real thing: write and read a file on the share.
2. **Every automated action needs a counter, and the counter needs an alert.** Not on the *failure*. On the *action*. "Restarted more than twice in 24 hours" is an alert worth waking up for, because healthy systems don't need that many interventions.
3. **Write down what your two systems assume about each other.** The watchdog assumed continuous recording. The recorder assumed nobody was checking. Each was reasonable in isolation, which is exactly how you ship a 91-day-long bug.
4. **A rate-limited restart is still a restart.** My cooldown stopped storms. It didn't stop me from kicking the service every sixteen hours or so without establishing a storage failure, forever, politely.
5. **Confirm the fix by looking at the near-misses, not just the zeroes.** Zero restarts is easy to claim. "Counter hit 2 of 3 on a quiet night" is the number that tells you how close you still are.

## What I still don't know

- Whether any of the 141 were real wedges. I don't have one confirmed. I have no evidence of one either, and "I didn't see it" isn't a result.
- How long each restart actually cost me in missed recording. I didn't measure the downtime per restart, so I'm not going to hand you a number that sounds like I did.
- Whether the mid-August gap means anything.
- Whether the watchdog should exist at all. The honest answer might be a real storage health check and no restart logic, at which point I've spent three months and 141 restarts to learn I wrote a worse version of something simple. Ask me in a month.

I wrote a thing to protect my recordings from a failure, and it produced a pile of restarts whose storage-failure justification I can't establish. I never measured the recording gaps. I can't point to a single confirmed NAS wedge in that stretch. What I can point to is a script I wrote, running once a minute, that kept restarting my NVR.

And it had a dashboard. It was great.

*Related: [Why the Lab Is Boring on Purpose](/posts/why-the-lab-is-boring-on-purpose/), which would have predicted this if I'd been listening to myself.*
