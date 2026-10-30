---
title: "My Security Sensor Complained 12,620 Times. Nobody Was Listening."
description: "A Falco sensor logged 12,620 'can't connect' errors over 16 days while my security stack looked fine. Safe defaults plus no receiver-side check."
date: 2026-10-30T15:50:00+01:00
draft: true
categories: ["Incident Reports"]
tags: ["Falco", "SIB", "Observability", "Security", "Homelab"]
---

I run a runtime security stack. Falco sensors on my hosts watch syscalls, a collector in the middle receives the alerts, a log store keeps them, dashboards draw them. It's the part of the lab I'm most smug about. It's literally the thing that's supposed to tell me when something is wrong.

For about two weeks in October, most of it couldn't tell me anything, because the collector had quietly stopped listening to the network. And the sensors? The sensors *knew*. They said so. Over and over. In a log file. That I did not read.

I pulled the count this week from the journal on one of those sensors: **12,620 lines** of `libcurl failed to perform call: Couldn't connect to server`. First one on October 5 at 14:45. Last one on October 21 at 21:51. That's sixteen days and change of a security sensor politely, persistently, **screaming into a drawer**.

This is the third post in a row about monitoring that missed something. I'm aware. I'd like to say I've learned the lesson, but you're reading the post.

## What I actually know (and what I don't)

Before the story, the evidence ledger, because I've been burned by narrating a clean story over thin facts (see [the NVR watchdog post](/posts/my-watchdog-restarted-my-nvr-141-times/), where I had to correct myself before publishing):

- **Checked this run:** the journal of the Falco sensor on my agent box. 12,620 connection-failure lines, first/last timestamps above, a daily count that never dropped to zero for sixteen days.
- **From my own commit message and wiki, not re-verified:** that *every* remote sensor went dark between October 8 and October 21, and that the cause was the collector binding to loopback only. I wrote that on October 21. I could not re-check it from the collector side this week, because the log store only keeps seven days of events and the window is long gone.
- **Unexplained:** my own sensor's failures start on October 5, *three days before* the window in my notes. I don't know why. There are at least two candidates (the collector was recreated earlier than I wrote down, or my agent box's address changed and the collector's source allowlist didn't know the new one; I did have to add it in the same fix commit). I haven't proven either. If you take one thing from this section: my incident write-up and my own journal disagree by three days, and the journal wins.
- **Unknown:** what the sensors saw during those sixteen days that never arrived. I can't count alerts I never received. That's sort of the whole problem.

## The setup

The pipeline is the open-source [SIB stack](https://github.com/matijazezelj/sib) I maintain: Falco on each host, Falcosidekick fanning events out, VictoriaLogs storing them. Remote sensors push over mutual TLS to a collector on my second Docker host. The collector is firewalled to the sensor addresses I approve. Belt, braces, and a second belt.

And the collector's compose file ships with a **safe default**: it binds to loopback unless you explicitly tell it otherwise with an environment variable. The repo's README says so, in a little padlock callout. It's the right default. I'd defend it in a code review. A security tool that listens on every interface out of the box is a security tool that makes the news.

My deployment overrides that default through a root-level `.env` file.

You can see where this goes.

## Regret 1: a safe default that fails silently is still a failure

Compose only reads that root `.env` if you point it there. Run a plain `docker compose up -d` from the subdirectory and compose happily reads nothing, uses the default, and starts a perfectly healthy container bound to loopback. No error. No warning. The container is up. My inference (I didn't capture the outage-time health state): anything that checks the collector from inside the container sees loopback and says "fine".

From the outside, the port is just closed.

This is the exact same trap my own notes already list for the main stack ("never `sudo docker compose`, it strips env"), except this time it was a separate project with its own compose file, and I deployed it the way my fingers deploy things. Muscle memory is a wonderful thing right up until it's a different project.

Safe defaults protect you from the thing you forgot to configure. They don't tell you that you forgot. Those are two separate jobs and I'd only built the first one.

## Regret 2: the sensors were honest, and I wasn't listening

Here's what bugs me. The system was *not* silent. The sensor was complaining at a rate of roughly one error every couple of minutes, 12,620 times, for sixteen days. The daily counts, from the journal:

- Between 200 and 970 lines a day for most of it.
- A spike to 2,540 on October 21, the day of the fix. (Probably me restarting and poking at the sensor. Inference.)
- Not one zero-day between October 5 and October 21.

There were also three lines of `"http" output timeout, all output channels are blocked`, two of them on the 21st and one on the 29th. That's Falco telling you its output queue is full and it's dropping its own alerts. Three lines. In a pile of twelve thousand. If you had grepped for "error" you'd have drowned. If you had grepped for "blocked" you'd have found three lines and a very expensive realization.

Detection tooling has a built-in humility problem: **the failure of the transport looks like the absence of events.** A quiet security log is exactly what a healthy, boring lab looks like. The dashboards were serene and I can't tell you what I thought of them; I can't tell you what I thought of the dashboards during those weeks, but nothing in my setup would have told me they were wrong.

I built a smoke detector, wired it to a speaker in the next building, and then admired how quiet the house was.

## Regret 3: I was watching the sender's health, not the receiver's

The sensor process was up. As far as I can tell nothing on the sensor's side was failing except the one thing that mattered: delivery. The thing that was broken was the path between the sensor and anyone who cared.

What was missing was a check from the receiver's side. And no alert told me: my notes say nothing noticed, and I added the checks afterwards. I'm not going to invent a dramatic discovery scene. Nobody was watching.

## What I changed

Two Gatus checks, written the same evening (commit `68c464b` in my private repo, so I'm quoting my own notes here and not something you can click):

1. **Can anything connect to the collector's ingest port?** A plain TCP check, every two minutes. This is the one that would have caught the loopback bind within two minutes. It's dumb, and dumb is good.
2. **Is every sensor actually reporting?** Each Falco sensor emits an hourly internal metrics snapshot. A query against the log store counts the *distinct hosts* that reported in the last three hours, and the check fails if it's below the expected number, five failures in a row at fifteen-minute intervals, about 75 minutes before it alerts. That tolerates one missed hourly heartbeat and not much more.

The second check is the better one. It doesn't ask "is the pipe open?" It asks "did the thing I care about arrive?" End to end, measured at the end.

Since then I enrolled the rest of my hypervisor nodes as sensors, and the expected host count in that check went up to ten. That's a **hard-coded number**. Which means it'll alert if one goes missing, but it also means the next time I add a sensor and forget to bump it, the check will either scream or, worse, quietly pass with a sensor missing. I haven't solved that. A counted threshold is a proxy; the thing I want is a named list. Putting it on the to-do list is how I got here.

The doc page for the collector now carries a big warning box: start it with the root env file, then check the published port. I wrote it in the voice of a man who has done the thing.

## One thing from this week that rhymes

On October 30 I upgraded one of the sensors to Falco 0.45.1 (the one on my main Docker host, with a rollback copy taken first). The write-up in my wiki has a line I'm going to steal for the takeaways: *a green health endpoint does not prove an intermittent fault is gone; keep watching the restart and error counters.* I wrote that last week's lessons into this week's runbook. It's slightly embarrassing how much of my operational maturity is just quoting my previous incident reports back to myself.

## If you want to copy it

- **Monitor from the receiving end.** "Did the event arrive?" beats "is the sender up?". A heartbeat is just an event you control, so you know what the count should be.
- **A safe default needs a failure signal.** If your tool silently falls back to loopback, wire a check on the *actual* published port, not the container's self-reported health.
- **Grep your sensors' own logs for transport failures.** I could have found this on day one with one `journalctl | grep -c`. The sixteen days of evidence were right there on the box the whole time.
- **A quiet dashboard is a claim, not a result.** If an empty security log would look identical to a broken pipeline, you don't have a quiet dashboard, you have a coin you haven't flipped.
- **Keep the count in the alert, not in your head.** Mine is a number I have to remember to update. A named list would be better. I'll let you know when I stop being lazy.
- **Write down the date window while you can.** My log store keeps seven days. The one thing that could have settled my three-day discrepancy expired before I looked.

A monitor has to be able to fail for the right reason. My sensors were never lying. They were telling the truth, loudly, to nobody. The truth is cheap if nobody's reading it.

If I get the heartbeat-by-name check built, you'll hear about it. Until then I'm reading the journal like it owes me money.
