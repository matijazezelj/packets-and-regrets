---
title: "My Coding Agent Has a Shell and My SSH Keys. So I Built It a Leash."
description: "A local harness over Claude Code and Codex: per-folder policy, an egress log, a redaction guard, and an honest list of what it can't stop."
date: 2026-10-09T16:27:48+02:00
draft: true
categories: ["Build Notes"]
tags: ["AI", "Security", "Claude Code", "Open Source", "Tooling"]
---

Think about what you actually agreed to when you started running a coding agent in your terminal.

It runs as you. It can read your home folder, which has your SSH keys, your cloud credentials and your GitHub token in it. It can run any command you can run. And the thing standing between that and a bad afternoon is a prompt that says "Allow?" and a hand that has pressed `y` four hundred times today.

I like these tools. I use them every day. I also work in security, so I spent a while looking at that arrangement and having feelings about it.

The result is [**HIB**](https://github.com/matijazezelj/hib), harness in a box. It's the newest of the in-a-box family, and it's the odd one out: not a Docker Compose stack, but a local program that sits between me and the agent. It's MIT licensed, it's two days old as I write this, and this post is about what it does and, more usefully, what it *doesn't*.

One disclosure up front, because the last few posts taught me to make them early. **I read the code. I did not run it for this post.** Everything below is from the source and the README, not from a benchmark. Where I'm repeating a claim I haven't checked, I'll say so.

## What it is

You run `hib` in a project folder and you get a coding agent in your terminal. Run `hib serve` and you get the same folder in a browser, on the loopback interface only. Under the hood it drives the official Claude Code and Codex CLIs, on your own subscriptions, the way you'd run them yourself. There is also a small local router that speaks the OpenAI API, so other tools can point at it.

The README's position on credentials is blunt: it doesn't extract your logins and doesn't call private endpoints. That's the README's claim, and I only checked part of it. What I did confirm is the environment: when HIB starts a CLI, the child process gets a short allow-list of variables (`PATH`, `HOME`, `TERM` and friends) plus whatever that specific account needs. Your shell's `AWS_SECRET_ACCESS_KEY` doesn't ride along by accident.

That's the boring part. The interesting part is the leash.

## The leash

**Approvals that mean something.** Every edit shows a diff and waits for Allow, Always or Deny. The detail I like is what "Always" covers. It's keyed to the program *and* the subcommand, so allowing `git status` doesn't quietly allow `git push`. And anything compound, a pipe, a semicolon, a substitution, a redirect, only ever matches itself. In the code's own words, `cat x; rm -rf y` never rides on "cat".

If you've ever clicked "always allow" on a command and then watched the agent use that permission for something you didn't picture, you know why this matters.

**Edits to the agent's own cage are meant to need a human, every time.** The design keeps the tool-config folders and `.git/` out of "always allow edits", and the reasoning is sound: if an agent can edit its own permission file or plant a git hook, the approval prompt is decoration. How well that holds in practice is something I haven't finished testing, so I'm not going to vouch for it here.

**Credentials are off-limits.** The Claude driver carries a deny list for reads of `~/.ssh`, `~/.aws`, `~/.gnupg`, the GitHub CLI's config, and the agent CLIs' and HIB's own folders. Sensible, and one line of config you could write yourself. The value is that somebody wrote it down in one place.

**Sensitive folders get a stricter regime.** You can pin a folder to a single vendor account. In that folder, nothing copies data elsewhere: no failover to another model, no second-opinion advisor, no classifier call. Every file read asks first, so you see each file before its contents go out. Secrets in a prompt are blocked outright, and the repo's own tool settings and hooks are ignored.

The part I want to underline is *where the policy lives*. It's stored in HIB's own database, not in the repo. An agent working in that folder can't edit the rule that restricts it by editing a file in the folder, because the rule isn't in the folder. (Anything running as you can still reach HIB's own directory. The project lists local processes as trusted, and in a sensitive folder every shell command asks first.) Lifting the policy takes a command at the terminal, not just the API token, so a stolen token can tighten things but can't loosen them.

That's the right shape. Policy belongs somewhere the thing it governs can't reach.

## The receipt

A leash tells you what it stopped. A receipt tells you what got through.

HIB keeps an egress log: for each turn, the redacted prompt, the account it went to, and every tool call. `hib workspace egress` shows what left the machine in the latest session. For the router, `hib egress last` prints the exact text that was sent.

The README says the next sentence itself, and I respect it: the log stores that redacted text locally, so anything the redaction guard missed is sitting in the log too. A receipt can be a liability. Write it down, protect the file (it's mode `0600`), and don't pretend it's empty.

## Send the code, not the data

My favorite idea in the project is also the smallest. Say you want an answer from a spreadsheet of user records, and you really shouldn't paste the spreadsheet into a cloud model.

```text
hib analyze logins.csv "impossible travel: consecutive logins per user implying more than 900 km/h"
```

The model never sees the rows. It gets a profile: column names and types, counts, and three invented rows that show the shape. Columns that look like identities are marked, and their values are never shown. The model writes a function. You read it and approve it. It runs on your machine, and the answer stays there.

There's an offline place-name list for geography questions, so the code can work out distances and speeds without a single real city name leaving the building.

For questions that do need rows, `hib ask -f` swaps identifying columns for stable tokens, so grouping by email domain still works without revealing the domain, and puts the real values back in the answer.

It's a better default than "be careful what you paste". It isn't perfect, and the README is upfront that spotting identifying columns is heuristic and you should check the list.

## What it does not do

This is the section I'd want if I were deciding whether to trust it.

- **Auto mode is a speed bump, not a sandbox.** It approves edits and commands inside the folder and still asks for network tools, pushes, publishing, `sudo`, recursive deletes and anything touching HIB's own folders. The project says so itself: a script the agent writes and runs can do anything you can. A deny-list of risky commands is a list, and lists have gaps.
- **The analysis sandbox is a macOS feature.** There, model-written code runs with no network, no writes and no reads under your home folder. On Linux it runs in a separate process with a restricted JavaScript context. That's a weaker promise, so know which of the two you're on.
- **Codex reads can't be gated.** It runs read-only commands without asking. For a sensitive folder, use a Claude account.
- **Name detection is a model.** The optional local model scored 24 of 24 and 19 of 20 entities on two small hand-labelled sets. That's encouraging and small. It fails closed (if the model is missing, the request waits for you), which is the correct way to fail.
- **Local processes are trusted.** Anything already running as you can read `~/.hib`. HIB raises the bar for a browser, a website or a cloned repo. It does not sandbox your own account.
- **Retention and training are the vendor's business.** The harness can't change what a subscription does with your data.

None of this is a flaw in the pitch. It's the pitch, stated plainly.

## What I checked, and what I didn't

I read the server's request handling, the permission and "always" logic, the credential deny list, the child-process environment, how it starts git and the CLIs, the analysis runner and sandbox profile, and the guard's configuration. Loopback only, a Host check against DNS rebinding, an Origin check, a strict same-site cookie, argument arrays instead of shell strings, and `--` before paths. A scan of the repo for committed secrets matched only test files.

I did not run the test suite (CI runs it on Ubuntu and macOS, and there are over 150 tests), I did not try to attack a running instance, and I did not read every one of the 86 files. A review that says "looks good" about code it only skimmed is how things get a reputation they didn't earn.

I also had my assistant go through the code read-only, and it came back with notes I'm still working through. If any of them turn out to matter, they get fixed first and written up afterwards, in that order.

## If you want to copy the ideas

- **Keep the rules where the agent can't write.** A policy file in the repo is a suggestion. A policy in a database or a different account is a rule.
- **Scope "always".** Allow a command and a subcommand, never a bare program, and never a compound line.
- **Log what leaves, then protect the log.** The receipt is evidence and also data.
- **Send code, not data,** wherever a question can be answered without the rows.
- **Write down what it can't stop.** If your tool's README has no "does not" section, it hasn't been looked at hard enough.

The earlier posts in this family, [From 12,669 Findings to a To-Do List](/posts/one-compose-command-seven-security-tools/) among them, are about the tools that watch a lab. This one is about the other half: the tool that's *in* the lab with a shell, and what you hand it.

The code is at [github.com/matijazezelj/hib](https://github.com/matijazezelj/hib). Read it before you trust it. That's the whole point of a box you can open.
