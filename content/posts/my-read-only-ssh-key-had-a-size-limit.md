---
title: "My Read-Only SSH Key Had a Size Limit. Stderr Didn't Get the Memo."
description: "A forced-command SSH key that can only look. Its 4 MiB cap ignored stderr, read-only wasn't harmless, and an unauthorized key ran a command anyway."
date: 2026-11-20T15:53:17+01:00
draft: true
categories: ["Build Notes"]
tags: ["Security", "SSH", "Docker", "AI Agents", "Homelab"]
---

Last Sunday I wanted a terminal dashboard on my laptop. Nothing fancy. Containers, health, restarts, a log tail, problems first. The kind of thing you build at nine in the evening because you're tired of typing `docker ps` with the enthusiasm of a man filling in a tax form.

The dashboard needs to *see* the Docker hosts. Seeing the Docker hosts means SSH. SSH into the account I normally use means a key that can do anything I can do, and on those hosts I'm in the `docker` group, which is root with extra steps. I am not leaving a key like that on a laptop for a pretty TUI. I've written [two posts about putting a coding agent on a leash](/posts/my-coding-agent-has-a-shell-and-my-ssh-keys/). I'm not handing my own dashboard the keys to the building.

So I built a leash for the dashboard. It's a good leash. It had three holes in it anyway, and one of them wasn't in the leash at all.

## The design, which I still like

OpenSSH lets you bind a key to a single program in `authorized_keys`:

```text
restrict,command="/usr/local/bin/lab-ro" ssh-ed25519 AAAA... lab-tui
```

With that line, sshd ignores whatever the client asked to run and runs the script instead. What the client asked for arrives in an environment variable, and the script decides what to do with it. `restrict` turns off the pty, port/agent/X11 forwarding and `~/.ssh/rc` for that key.

The script, `lab-ro`, is about 130 lines of Bash. I wrote it with Claude Code on the laptop. It accepts exactly six requests: `version`, `ps`, `inspect NAME`, `logs NAME [LINES]`, `stats` and `host`. Everything else exits with status 2. No restart, no stop, no exec, no compose, no shell. Other details:

- The request may only contain letters, digits, spaces, `_`, `.` and `-`, and at most 256 characters. It gets split into words and matched against a fixed table. Nothing is evaluated by a shell.
- A container name has to exist in `docker ps -a` at that moment, so you can't sneak in an option, an ID prefix or a path.
- `ps` and `inspect` use fixed output templates. The full `docker inspect` includes the environment, and the environment is where the secrets live. The template returns state, health, restart count and exit code, and that's it.
- Every Docker call has a 20-second timeout and a 4 MiB output cap.
- The script is root-owned, so the account the key logs into can't rewrite what the key runs. Every request goes to syslog.

I was proud of it. Then I handed it to my other agent, the one that runs the lab, and told it to deploy it. That's the arrangement I described in [the post about managing an agent instead of being a sysadmin](/posts/i-stopped-being-my-homelabs-sysadmin-now-i-manage-one/): it doesn't get to deploy something it hasn't read.

It read it. The original commit landed at 21:35. The fix commit landed at 21:47. Twelve minutes. Long enough to find out I'd been an idiot in a very specific way.

## Regret 1: the size limit only watched one door

Here's the line that enforced the cap, from the original commit:

```bash
timeout --kill-after=5 "$DOCKER_TIMEOUT" docker "$@" | head -c "$MAX_BYTES"
```

Looks fine. Pipe Docker into `head -c`, stop at 4 MiB. Done.

Except a pipe only carries stdout. `docker logs` replays a container's stdout **and** stderr, on the matching streams. Plenty of applications log everything to stderr. So for any of those containers, the 4 MiB cap was a bouncer standing at the front door while everybody walked in through the kitchen.

The agent didn't argue about it in the abstract. It pulled the script out of the original commit, put a fake `docker` on the `PATH` that writes 5 MiB to stderr, and ran it:

- bytes out: **5,242,880**
- cap: **4,194,304**
- exit status: **0**

Zero. Successful. The script happily blew through its own limit and reported a clean exit. The fix is four characters, `2>&1`, before the pipe. Then it wrote a regression test for each stream, with a comment pointing at the commit that got it wrong. I re-ran that suite for this post. Six tests pass, including the stderr one and a refusal test that throws 14 bad requests at the parser (`restart`, `exec`, `ps; id`, `$(id)`, `inspect --help`, a negative line count, an empty string, 257 characters of `a`) and checks that none of them reach Docker.

How bad was the original bug? Honestly, not very. It's a resource limit, not an authorization hole. The worst case is a big log dump to someone who already holds the key. But the README said "4 MiB output cap", and for a whole class of containers that sentence was fiction. If a control is written down, it should be true. Otherwise it's not a control, it's a vibe.

## Regret 2: "it can only read" was doing too much work

The original setup instructions generated the key with no passphrase, because the dashboard runs unattended. The justification, in my own README: *acceptable only because the key can do nothing but read.*

Read what, though? **Logs.** Application logs are where credentials go to die. A connection string printed at startup. A token in a debug line. Somebody's email address in a stack trace. My fixed templates carefully keep the environment out of `inspect`, and then the `logs` endpoint hands over whatever the application decided to print. The script doesn't redact, and it can't, because it has no idea what a secret looks like in dozens of different apps.

So the review rewrote that paragraph. The README now says read-only is not secret-free, recommends a passphrase-protected key in `ssh-agent`, and treats this key as "sensitive read access, not a harmless status token". Which is what it always was. I just wrote a nicer sentence about it the first time.

Same family of lie: the account the key logs into is in the `docker` group. If the forced command ever leaks a shell, the key is root. The whole thing rests on one Bash script and one line in `authorized_keys` staying exactly as they are. That's fine. It's also something I should say out loud instead of letting "read-only" imply more than it delivers.

## Regret 3: the test that proves nothing

This is the one I'd have walked straight past.

The obvious way to test a forced command is to SSH in with the key and try something rude: `ssh -i lab_ro host restart gatus`, expect a refusal, feel smug. The review added a warning to the instructions: **turn off connection multiplexing first** (`-o ControlPath=none -o IdentitiesOnly=yes`), because an existing master connection authenticated with a different key doesn't exercise this key at all.

I wanted to see that with my own eyes, so for this post I did it on a machine I'm allowed to break. The agent's own SSH config multiplexes connections to its jump host: one persistent master, everything else rides it. I generated a brand-new throwaway key that's authorized nowhere and asked it to run `echo` on the jump host:

- through the normal, multiplexed config: **the command ran.** Exit 0.
- same throwaway key with `ControlPath=none`: **`Permission denied (publickey)`**, exit 255.

A key nobody has ever authorized "worked", because `-i` doesn't matter when the client reuses a session that already logged in with a real key. Now imagine running the rude test against a forced-command host through a master opened with your normal key. `restart` succeeds. You'd either conclude the leash is broken (and waste an evening) or, worse, run a "must be refused" test that actually restarts something. Either way you've tested the wrong key, and nothing about the output tells you.

The dashboard client got the same treatment. Its SSH call is a fixed argument list with `IdentitiesOnly`, `BatchMode`, no forwarding, and `RemoteCommand=none`, and it multiplexes over its *own* control socket in a private runtime directory. The code comment says why: so it never rides a session authenticated with another key. The Go tests pass. I read that part of the code; I didn't attack it.

## Regret 4: what the receipts say

Every request goes to syslog, so I can audit my own leash. I pulled the journal from both Docker hosts today and counted.

- The installed script matches the repo byte for byte on both hosts (same SHA-256), root-owned, mode 755. Each host has exactly one key line bound to it.
- First, a burst of 14 requests per host at deploy time, including two `restart` attempts. That's the agent running the script directly on the hosts as a protocol test. By its own instructions, that test doesn't prove the *laptop* key path works, and I'm not going to pretend it does. That's inference from the request pattern and source, and it lines up exactly: seven loggable requests per run, two runs.
- Then the laptop shows up. Its first two requests are `version`, then `id`, which isn't in the allow-list. That's me poking the fence. In total the laptop sent 100 requests to one host and 64 to the other, between 21:50 and 22:29, the same evening the dashboard's host view was written.
- Since then: **zero**. Five days. Both journals go back months and have entries from today, so it isn't rotation. The receipts are telling me I built the dashboard and haven't opened it since.

So the score for the week: a carefully hardened, audited, regression-tested, read-only SSH channel, used for about 40 minutes on a Sunday. I built a bank vault door for a room I've visited once. The receipts don't care about my feelings, which is exactly why I wanted receipts.

## What I don't know yet

- Whether the laptop actually authenticated with the restricted key. The requests came from the laptop's network and the dashboard's host view is built to use that key, so probably. I didn't watch an auth log line with the key fingerprint to prove it.
- Whether a `restart` sent from the laptop *through the key* is refused. The code says yes and the server-side tests say yes. The laptop only ever tried `id`.
- How much of what the log endpoint can return is actually sensitive in my containers. I haven't grepped 80-odd containers' logs for secrets, and "the README warns you" is not the same as "it's clean".
- Whether I'll use the dashboard enough to justify any of this. Jury's out. The journal is the jury.

## If you want to copy it

1. **Bind the key with `restrict,command=...`** and parse the request against a fixed table. No shell, no `eval`, no "just pass the arguments through".
2. **Validate names against live state**, not just a regex. A name that has to exist right now can't be an option or a path.
3. **Use fixed output templates.** Full `inspect` output is a secrets dump with JSON formatting.
4. **Cap stdout *and* stderr.** `2>&1` before the `head -c`. Then test both streams, because I didn't.
5. **Don't call log access harmless.** Passphrase the key, keep it on one machine, pin the source address with `from=` if you can.
6. **Test with `-o ControlPath=none -o IdentitiesOnly=yes`.** Otherwise you may be testing your other key, and the output won't tell you.
7. **Log every request and actually read the log.** Mine found the boring truth, which is the most useful kind.

The script was fine. The design was fine. It's the stuff *around* it, the stream I forgot, the adjective I leaned on, the test that tests something else, that would have bitten me. That's usually where it is.
