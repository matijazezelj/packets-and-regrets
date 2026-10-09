---
title: "I Wrote Four Rules Against Things That Don't Hold Still"
description: "A firewall that pinned a container IP, an alert that ignored time, a backup that tripped on a temp file, and a comment that lied. One bug, four costumes."
date: 2026-10-09T09:10:00+02:00
draft: true
categories: ["Lab Notes"]
tags: ["Firewall", "Docker", "Prometheus", "Restic", "Observability", "Homelab"]
---

Four small fixes landed in my lab repo this week. None of them is worth an article on its own. A one-line firewall change. A two-line alert tweak. An exclude flag. A corrected code comment.

Lined up in the git log, though, they're the same bug four times. And I'm the guy who wrote it four times.

The bug: **I wrote a rule against something I treated as a fixed point, and it was a moving part.**

Let's go through the crime scene.

## Regret 1: the firewall that knew the container's address by heart

Earlier this month I gave my video recorder container its own network path to a locked-down device network (no names, no addresses, sorry). New NIC on the Docker host, a dedicated nftables table, default drop, and one allow rule: this one source address may open one TCP stream to those two devices. Everything else in or out of that interface gets dropped, with counters so I can see who knocked.

I was proud of it. Tight rule, no `flush ruleset` (which would have nuked Docker's own rules, a mistake I have read about and not made, thank you), separate table, a systemd unit, a README.

The allow rule looked like this, trimmed:

```text
oifname "<nic>" ip saddr <the container's IP> ip daddr @devices tcp dport <stream port> accept
oifname "<nic>" counter drop
```

See it? "This one source address." I hard-coded the container's IP on the Docker bridge.

Docker hands out those addresses. It doesn't promise them. I recreated the container (which is a normal thing, it's the thing `deploy.sh` does every time a digest changes), it got a new address, my allow rule matched nothing, and the very next line, the default drop, did exactly what I told it to. Both video feeds went dark.

The git log says it plainly. The firewall was committed on the morning of the 5th. The fix, on the 8th at 15:27, reads: *"match the compose subnet, not the container IP (a recreate changed the IP and dropped both feeds)."*

Three days. The thing I built to be strict was strict about the wrong noun.

What's funny, in the Bill Burr sense where it hurts, is that the README I wrote on day one *said so*. It had a line: "If the container IP changes, update the rule or the recorder loses its feeds." I documented the landmine and then stood on it. A runbook entry that says "this will break by itself, fix it by hand" is not documentation. It's a confession.

The fix matches the whole compose network's subnet now. That's a wider rule: any container on that network could use the path, where before it was one. I made that trade on purpose and I'd rather say so than pretend it's free. Only containers I deploy live there, and the destination and port are still pinned, but it's a loosening and I know it. The README now says "matches the subnet on purpose" and names the one thing that would break it (the subnet itself changing), which, unlike a container IP, doesn't change when I breathe on `docker compose`.

## Regret 2: the alert that couldn't read a clock

Backups: Proxmox Backup Server verifies every snapshot after the nightly job. My exporter publishes `last_verify` per snapshot, and I have a critical alert, `PBSVerifyFailed`, that fires when it equals zero for 30 minutes.

Here's the thing about a brand-new snapshot: until its verify finishes, `last_verify` is zero. Zero means "not verified yet" and zero also means "verify failed". The metric has one number for two different situations.

One VM's nightly verify takes up to 39 minutes (that figure is straight from my commit message; I didn't re-time it for this post). The alert waits 30. You can do that math in your head. This morning it fired a critical for a verify that was merely still running (the commit message calls it a false critical).

The fix, commit `1dc1613` at 07:04 this morning:

```yaml
expr: |
  pbs_snapshot_vm_last_verify{vm_id!~"..."} == 0
    and on(vm_id) (time() - pbs_snapshot_vm_last_timestamp > 2*3600)
for: 30m
```

Only count snapshots older than two hours. A real failure stays at zero forever. A pending verify is gone long before then. Same alert, now it understands that "zero" depends on how old the thing is.

The lesson I keep relearning: **a `for:` duration is a guess about how long something takes, and guesses rot.** The backup got a bit bigger, the verify got a bit longer, and my 30 minutes quietly became wrong without anybody touching the alert. I don't know when it crossed the line; I only know it did.

## Regret 3: the backup that quit over a file that wasn't there

The other host's restic backup walks its state directory nightly. One of the things in that directory is Pi-hole's data. Pi-hole rebuilds its gravity blocklist database in a temporary database next to the real one, then swaps it in.

That means for a few seconds, there's a file that restic lists... and then it's gone by the time restic goes to read it. Restic is a polite tool. It notes that a file vanished, finishes the backup, and exits with code **3**: "snapshot created, but some files couldn't be read."

My cron wrapper, sensibly or not, treated non-zero as failure and **skipped writing the success metric**. So the backup *worked*, and the dashboard and the stale-backup alert said it hadn't. Restic did its job. My glue code held a grudge over a temp file.

The fix (commit `7994789`, October 6) is one more `--exclude` for `gravity.db_temp*`. The comment I left in the compose file explains the dance, so the next person (me, in six months, no memory) doesn't "clean up" the exclude.

Two honest caveats. First, exit 3 isn't a clean bill of health in general. It can mean a real file was unreadable, and I've now made *this specific* file invisible rather than teaching the wrapper to tell the difference. Second, I haven't built that distinction. If something else vanishes mid-backup, I'll see the stale alert again and will, I assume, learn this lesson a second time.

## Regret 4: a comment that claimed a fix that wasn't there

This is the one that stings, because it's a lie in my own handwriting.

The same day I pinned all 68 remaining container image references by digest (commit `52d1ef9`, with the stated goal that a restart can't move the image under me), I also pinned a couple of images that had open security findings. On one of them I wrote a comment saying the version I pinned shipped the upstream fix for a known-exploited dependency flaw.

I wrote that at 12:50.

At 12:56, six minutes later, I committed a correction. The version I'd pinned does *not* ship the fix. The dependency inside the image was still the old, vulnerable one, and forcing a newer dependency under that framework would break things. I rewrote the comment to say "NOT fixed upstream," wrote down the mitigation (the container publishes no port and only its sibling container can reach it), and added "re-check on each release."

In the same commit I annotated two scanner findings on another image as false positives, after checking the distro tracker: the image claims one Debian release but ships packages from an older one, and those exact package versions were already the fixed ones.

Six minutes. Which is lucky. A comment saying "this is fixed" in a compose file is a security control for the *next* reader: nobody re-checks a thing the file says is handled. If I'd gone to lunch instead, that line would have sat there, authoritative and wrong, until a scanner stopped being quiet.

## What these have in common

| What I pinned | What it actually does | How it broke |
|---|---|---|
| a container's address | changes on recreate | default-drop ate the traffic |
| a 30 minute `for:` | verify takes up to 39 | false critical |
| "non-zero exit = failed" | exit 3 means "mostly fine" | good backup, bad dashboard |
| "this version has the fix" | I read the wrong line | false assurance |

Every one of these was a *correct rule written at the wrong level of abstraction*. Pin the network, not the host on it. Pin the age of the snapshot, not just its state. Pin the meaning of the exit code, not "zero or not". Pin the fact by checking it, not by remembering the release notes.

## If you want to copy my cleanup

- **Firewall rules for containers: match the network, not the container.** If you must be tighter, pin on something stable (a labelled network, a fixed `ipv4_address` in compose) and test with a recreate before you call it done. I did not test a recreate. That is the entire bug.
- **Do the "recreate it" test for anything that depends on an address.** It takes thirty seconds and you'll feel stupid for not doing it earlier. I did.
- **Compare your `for:` to a measured duration.** If a job takes 39 minutes, a 30 minute window is a coin flip with extra steps. Put the measured number in the alert's comment so it can be re-checked.
- **Make your wrapper script say what happened, not just pass/fail.** "Backup finished with warnings" and "backup failed" are different sentences.
- **Treat "fixed in version X" in a comment as a claim that needs a check, not a note.** Date it. I now write "re-check on each release" next to anything I haven't proven.

## What I don't know yet

I haven't audited the rest of the repo for the same pattern. I'd bet there are more hard-coded addresses and more `for:` values older than the jobs they watch. That's inference, not a count. The honest next step is a grep, and I'd rather run it than guess.

For earlier episodes of me learning how the thing I built works by watching it fail, see [Why the Lab Is Boring on Purpose](/posts/why-the-lab-is-boring-on-purpose/) and [Prometheus on NFS: Healthy Until It Wasn't](/posts/prometheus-on-nfs-healthy-until-it-wasnt/). Boring is the goal. Pinning things that move is how I keep missing it.
