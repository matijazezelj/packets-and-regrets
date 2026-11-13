---
title: "My Sensor Heartbeat Counted to Ten and Never Said Who"
description: "After ten sensors went dark for 13 days, I added a heartbeat that counts to ten. Then I rebuilt it to name names. The alert still has nobody to tell."
date: 2026-11-13T15:52:55+01:00
draft: true
categories: ["Lab Notes"]
tags: ["Security", "Falco", "Monitoring", "Homelab", "Alerting"]
---

In October, every remote Falco sensor in my lab went quiet for about two weeks and I didn't notice. The documented window in my own notes is October 8 to 21. The cause was the kind of dumb you only get from infrastructure: the collector got recreated without its environment file, fell back to listening on loopback only, and ten sensors kept shouting at a door nobody was behind.

So I fixed it, and then I did the thing you do after you get burned. I added a heartbeat. This is the story of that heartbeat being *almost* right, and what I rebuilt this week. It's a sequel to [the post about monitoring that stayed green while things were dead](/posts/nothing-was-red-and-three-things-were-dead/), because apparently I'm a series now.

## Regret 1: the heartbeat counted to ten

Each sensor emits an hourly "metrics snapshot" event. The fix after the outage was an uptime check that asks the log store every 15 minutes how many *distinct hosts* sent one in the last three hours, and fails if the answer is under ten. Here's the shape of it, straight from the config:

- window: 3 hours
- check interval: 15 minutes
- condition: `hosts >= 10`
- alert after: 5 consecutive failures (the config comment says "75 min: heartbeat is hourly")

I was pleased with that. Then I looked at it like a stranger would.

**It counts. It doesn't name.** The number ten is hard-coded. If I add an eleventh sensor, one dead sensor hides behind it. If I retire one and forget the check, it screams forever. And when it does fail, the message is "fewer than ten" and I get to go play detective on which one.

**It's slow, by arithmetic.** Inference from the config, not a measurement: a sensor that dies right after its snapshot still counts for up to three hours, and then five failing checks at 15 minutes each add more. That's a worst case somewhere around four hours before I'm told. I did not kill a sensor to time it. For a thing that was dark for 13 days it's a big improvement. For a security sensor it's a long time to be blind.

**It measures whether a quiet host felt like talking.** A heartbeat built out of log events only proves the *event pipeline* delivered something. If the host is alive but the pipeline is broken, I get the same silence as a dead host. Two different problems, one symptom.

## Regret 2: so I built the one that names names

This week's commit adds a small script and a timer. Every minute it asks each of the ten sensors, over SSH I already use, whether its local metrics endpoint answers and actually contains Falco metrics. The result is one sample per host: `up=1` or `up=0`, stamped with the host name, imported into the security stack's metrics store.

Design decisions I'd defend in a pub:

- **A failed probe writes a zero, not nothing.** Transport error, timeout, non-zero exit: all become `up=0`. The test suite has a case for each. A silent probe that drops failures is a heartbeat that lies by omission.
- **The alert doesn't ask who reported in. It asks who's missing.** The ten expected host names are embedded in the alert expression itself, and the alert is "expected names unless a healthy sample exists in the last five minutes". It doesn't read the log history, so a host that's been dead for a month doesn't age out of existence when retention rolls over. The metric an absent host *doesn't* produce is exactly what I'm now alerting on.
- **"No data" is a pass, on purpose.** That sounds backwards. It's not: the expression always returns the ten constants minus the healthy ones, so it always has data. If the collector itself dies, all ten fire. I read that off the generated rule and the 11 rules in the file; the one test that touches it checks that every host name appears in the expression and that the no-data state is OK.
- **Retiring a host is a deliberate edit.** You remove it from the script and regenerate the rules. Otherwise it pages. I'd rather be annoyed by a retired host than quietly stop watching a live one.

There's a smaller regret in the middle. The probe for the collector's own endpoint uses mutual TLS against my private CA, and that CA predates Python 3.13's stricter CA-extension checks. The code relaxes exactly that one strictness flag. The comment in the script says chain, hostname, validity and client certificate checks stay on. I read the code. I did not independently prove what the relaxed flag allows. Writing the comment felt better than not writing it, which is a low bar, but it's mine.

## What I actually checked, and what I didn't

Stuff I did for this post, today:

- **Ran the unit tests.** Seven pass. They cover: ten unique hosts in the inventory, down is exported rather than dropped, an unknown host is rejected, a transport error counts as down, a timeout counts as down, a good probe counts as up, and the generated rules contain no notification policy or contact points. These are mocks. They prove the logic, not the wire.
- **Read the timer's journal.** Between 22:56 on Nov 12 and 16:01 on Nov 13, the collector ran **992 times**. Every logged run reported **10 of 10 healthy**. There was no gap longer than 75 seconds. For about seventeen hours of boring, that's the most boring graph I own, and I mean that as a compliment.

What I did **not** do:

- I did not re-run the query that proves an absent host shows up as missing. My notes from the rollout say a query against a nonexistent scrape job returned all ten names and the real one returned none. I read that note. When I tried to reach the metrics store from this machine to repeat it, the request timed out, so I'm quoting my own notes rather than a fresh result.
- I have no record of killing a real sensor and watching this alert fire.
- Sensor *liveness* is not *detection*. The probe asks whether the metrics endpoint answers. It says nothing about whether a rule would fire on a real attack. My own doc says an endpoint check doesn't replace an end-to-end detection test, and that's still a to-do.

## Regret 3: the alert has nobody to tell

Here's the part where I'd like a different hobby. The doc I wrote the same night says it plainly: **Slack or webhook delivery and the external heartbeat are not configured or tested.**

So I now have a precise, name-aware, five-minute fleet-liveness alert that evaluates beautifully into a dashboard I have to open. The new alert currently has the notification wiring of a smoke detector on a shelf: great at knowing, useless at telling. I don't know how well the older uptime check delivers either; I didn't test that this week.

The documented plan is a single child route that sends only security alerts somewhere I'll see them, leaving the existing organisation routing untouched, because the alerting setup is shared with other things. It isn't done. That's the next job, and it's embarrassing that it comes after the clever part.

## If you want to copy it

- **Alert on who's missing, not on how many reported.** Put the expected list somewhere the logs can't erase.
- **Write failures as data.** `up=0` beats a dropped sample every time.
- **Keep liveness and detection as two separate claims.** "The sensor is up" and "the sensor would catch something" are different tests. Don't merge them in a headline.
- **Check the delivery path before the rule.** The best alert in the world is a log line if nothing routes it.
- **Do the worst-case latency arithmetic** on whatever check you're proud of. Window plus interval plus threshold. Mine was around four hours and I'd never added it up.

## What I still don't know

Whether the alert fires end to end. How long a dead sensor really takes to turn into a page, as opposed to arithmetic. And whether the next thing to fail will be one of the ten, or the one box doing the probing. (That's what "who watches the watchers" is for, and I'm not pretending I'm done.)

I'll be back when I've killed a sensor on purpose and watched what happens. It's a better hobby than waiting for October to do it for me.
