---
title: "My Watchdog Restarted My NVR 141 Times. The NVR Was Fine."
description: "I wrote a watchdog for a wedged NAS mount. In 91 days it restarted a healthy-looking recorder 141 times. Nobody noticed, me included."
date: 2026-10-23T15:55:00+02:00
draft: true
categories: ["Incident Reports"]
tags: ["Watchdog", "Monitoring", "Frigate", "Homelab", "Automation"]
---

Last week I wrote about [three things that died quietly while every dashboard stayed green](/posts/nothing-was-red-and-three-things-were-dead/). Monitoring that fails to notice a death. Fine. Classic.

This week's is the opposite and, honestly, worse: a thing that **killed a healthy service on a schedule**, for three months, because I taught it what "broken" looks like and I taught it wrong. And it had a counter. The counter went up 141 times. I have a Grafana panel for that counter. I can't swear I ever opened it.

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

My Frigate config uses motion-only retention. My own wiki says it: `continuous: 0`, `motion: 14` days. It only keeps segments when something moves. A camera pointed at an empty room for ten minutes legitimately commits **nothing**. No segments, no database rows, "stale" by the watchdog's definition, and perfectly healthy.

I wrote the watchdog and the retention policy. In the same month. Same brain. The two never met.

So the watchdog did what I told it to: a quiet camera went stale, three checks later it declared a failure, the storage sentinel read fine (because the storage *was* fine), and it restarted the container. Then, as far as I can tell, the fresh container sat there recording nothing until something moved, the check passed, and everybody was happy. Repeat tomorrow. (Inference: I did not trace a single cycle end to end.)

## The numbers, from the journal on the host

I'm not guessing here. I pulled these from the watchdog's journal and the textfile metric on the box, this week:

- **141** restarts. The Prometheus counter says 141, and counting `RESTARTED` lines in the journal also says 141. I like it when two things agree.
- First restart July 19, last one October 18 at about 10:17 local time. That's 91 days, roughly 1.5 a day.
- **6,681** failed-check lines in the journal over the same stretch. The restarts are just the ones that survived three strikes.
- There's a gap with no restarts from mid-August to the end of August. I don't know why. I have no evidence for any theory, so I'm not offering one.
- The restarts cluster at two times of day. I can see the clustering. I haven't proven what's behind it, and I'm not going to make up a story because it'd read well.

The container's own restart counter says 0, by the way. That's because `docker restart` isn't a crash, it's an *instruction*. Docker was told to do it by a nice, polite Python script. Nothing in Docker's view was ever wrong.

## Regret 2: the counter had no one to tell

Now the part that actually stings. I did build observability. The watchdog exports `nas_recovery_watchdog_restarts_total`. There's a Grafana panel for it on the backups dashboard. There's even a Prometheus alert for the watchdog...

...and that alert is `nas_recovery_watchdog_check_ok == 0 for 10m`. It tells me when the check is *failing*. It does not tell me when the watchdog is *acting*. As far as I can tell from reading the script, a restart is followed by a verify step and the check goes green, so the alert resets before 10 minutes are up and never fires. I grepped the Prometheus rules while writing this: nothing anywhere alerts on the restart counter going up.

I built a smoke detector that can't tell the difference between a fire and the fireman showing up.

A restart counter that increments 1.5 times a day is not a recovery metric. It's the most obvious "this thing is lying to you" signal I own, and I put it on a panel I never open. That's not monitoring. That's a decorative tile.

## What I did about it

Commit `ff039e5`, October 18. One new config option, `stale_mode`:

- `any` (the old behaviour): any single camera stale = failure.
- `all`: failure only if **every** watched camera is stale at once.

The reasoning is the thing I should have written in July. A wedged NAS share stops *all* cameras simultaneously. A quiet camera is one camera. If a single camera's recorder process genuinely breaks, Frigate has its own internal watchdog for that, and I don't need a second, dumber one doing a worse job on top.

A quiet camera is now logged as "recordings current on at least one camera; quiet (no motion kept)" and moves on with its life.

## Did it work? Mostly. Don't clap yet.

Since the fix: **zero restarts** in five days, and the Frigate container's start time still says the October 18 restart. Three failed-check lines total, instead of the usual hundreds.

But look at those three lines, because they're the honest part. They're two episodes where **both** cameras were stale at once. The first stopped at strike 1. The second, a day and a half later, reached strike 2 of 3 before recovering. `all` mode would have restarted on a third strike. It didn't, but it got two thirds of the way there on a night when I can't show anything was wrong.

And I looked back at the journal line right before each restart (I could pair up 139 of the 141). In **100** of them only one camera was stale. In **39**, both were. The `all` fix handles the 100. It does *not* handle the 39. When I wrote "~141 false restarts" in the commit message I was rounding up my confidence. I can't prove the 39 were false. I can't prove they weren't either. I suspect most were two quiet cameras at the same quiet moment, but that's inference and I'm labelling it as inference.

So the real state is: I turned a restart-every-16-hours problem into a rarer one. That's progress. It's not a fix. A proper fix is a check that tests the thing I care about (can I write to the share?) instead of using "did a camera see motion" as a proxy for it.

## If you want to copy this (the useful part)

1. **A proxy metric is a lie with good manners.** "No new segments" stood in for "storage is broken." They correlate until your config changes what a segment *is*. Test the real thing: write and read a file on the share.
2. **Every automated action needs a counter, and the counter needs an alert.** Not on the *failure*. On the *action*. "Restarted more than twice in 24 hours" is an alert worth waking up for, because healthy systems don't need that many interventions.
3. **Write down what your two systems assume about each other.** The watchdog assumed continuous recording. The recorder assumed nobody was checking. Each was reasonable in isolation, which is exactly how you ship a 91-day-long bug.
4. **A rate-limited restart is still a restart.** My cooldown stopped storms. It didn't stop me from kicking a healthy service every sixteen hours or so, forever, politely.
5. **Confirm the fix by looking at the near-misses, not just the zeroes.** Zero restarts is easy to claim. "Counter hit 2 of 3 on a quiet night" is the number that tells you how close you still are.

## What I still don't know

- Whether any of the 141 were real wedges. I don't have one confirmed. I have no evidence of one either, and "I didn't see it" isn't a result.
- How long each restart actually cost me in missed recording. I didn't measure the downtime per restart, so I'm not going to hand you a number that sounds like I did.
- Whether the mid-August gap means anything.
- Whether the watchdog should exist at all. The honest answer might be a real storage health check and no restart logic, at which point I've spent three months and 141 restarts to learn I wrote a worse version of something simple. Ask me in a month.

I wrote a thing to protect my recordings from a failure, and the failure it caused was, at minimum, a pile of needless restarts (I never measured the recording gaps). I can't point to a single real NAS wedge in that stretch. What I can point to is a script I wrote, running once a minute, that kept restarting my NVR.

And it had a dashboard. It was great.

*Related: [Why the Lab Is Boring on Purpose](/posts/why-the-lab-is-boring-on-purpose/), which would have predicted this if I'd been listening to myself.*
