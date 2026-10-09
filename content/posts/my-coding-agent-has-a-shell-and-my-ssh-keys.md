---
title: "My Coding Agent Has a Shell and My SSH Keys. So I Built It a Leash."
description: "I put a leash on my coding agent. Then I had it audited, it found holes in my leash, and I fixed them before telling you."
date: 2026-10-09T16:27:48+02:00
draft: false
categories: ["Build Notes"]
tags: ["AI", "Security", "Claude Code", "Open Source", "Tooling"]
---

Think about what you actually agreed to when you started running a coding agent in your terminal.

It runs as you. It can read your home folder, which has your SSH keys, your cloud credentials and your GitHub token in it. It can run any command you can run. And the thing standing between that and a bad afternoon is a prompt that says "Allow?" and a hand that has pressed `y` four hundred times today.

I like these tools. I use them every day. I also work in security, so I looked at that arrangement for a while and had feelings about it. Mostly the feeling of a man who has been handing his house keys to a very enthusiastic stranger and calling it "productivity".

The result is [**HIB**](https://github.com/matijazezelj/hib), harness in a box. It's the newest of the in-a-box family, and the odd one out: not a Docker Compose stack, but a local program that sits between me and the agent. MIT licensed, about a week old as I write this.

Disclosure up front, because the last few posts taught me to make them early. **I read the code. I did not run HIB for this post**, and I have not run its test suite. Where I tested something, I'll say exactly what. Everything else is source and README.

## What it is

You run `hib` in a project folder and you get a coding agent in your terminal. Run `hib serve` and you get the same folder in a browser, on the loopback interface only. Under the hood it drives the official Claude Code and Codex CLIs, on your own subscriptions, the way you'd run them yourself. There's also a small local router that speaks the OpenAI API, so other tools can point at it.

The README says it doesn't extract your logins or call private endpoints. That's the README's claim and I only checked part of it. What I did confirm is the environment: a child process gets a short allow-list of variables (`PATH`, `HOME`, `TERM` and friends) plus whatever that account needs. Your shell's `AWS_SECRET_ACCESS_KEY` doesn't tag along by accident.

That's the boring part. The interesting part is the leash.

## The leash

**Approvals that mean something.** Every edit shows a diff and waits for Allow, Always or Deny. The detail I like is what "Always" covers. It's keyed to the program *and* the subcommand, so allowing `git status` doesn't quietly allow `git push`, and anything compound (a pipe, a semicolon, a substitution) only ever matches itself. In the code's own words, `cat x; rm -rf y` never rides on "cat".

**Every command runs in the CLI's own OS sandbox.** This is the big one, and it landed after my first read. Writes stay in the folder, the network is closed, the daemon on localhost can't be reached, and a deny list covers `~/.hib`, the CLI logins, `~/.ssh`, `~/.aws`, `~/.gnupg` and the GitHub CLI's config. It applies to every process a command starts, including the script the agent just wrote and ran. On Linux that's bubblewrap; if the sandbox isn't available, auto mode and background tasks simply switch off.

Before that, "auto mode" was a regex deny-list of scary commands. A deny-list is a list of the things you thought of, which is a very short list at 4pm on a Friday. An OS sandbox doesn't care what you thought of.

**Sensitive folders get a stricter regime.** You can pin a folder to a single vendor account. In that folder nothing copies data elsewhere: no failover to another model, no second-opinion advisor, no classifier call. Every file read asks first. Secrets in a prompt are blocked outright, and the repo's own tool settings and hooks are ignored.

The part I want to underline is *where the policy lives*: in HIB's own database, not the repo. An agent in that folder can't edit the rule that restricts it by editing a file, because the rule isn't in the folder. Lifting it takes a command at the terminal, not just the API token. Policy belongs somewhere the thing it governs can't reach. That's not a HIB idea, it's a thing everyone knows and then puts in `.eslintrc` anyway.

## The receipt

A leash tells you what it stopped. A receipt tells you what got through.

HIB keeps an egress log: for each turn, the redacted prompt, the account it went to, and every tool call. The README then says the quiet part itself: the log stores that redacted text locally, so anything the redaction guard missed is sitting in the log too. A receipt can be a liability. Mode `0600`, protect it, and don't pretend it's empty.

## Send the code, not the data

My favorite idea in the project is also the smallest. Say you want an answer from a spreadsheet of user records, and you really shouldn't paste the spreadsheet into a cloud model.

```text
hib analyze logins.csv "impossible travel: consecutive logins per user implying more than 900 km/h"
```

The model never sees the rows. It gets a profile: column names and types, counts, and three invented rows that show the shape. Identity-looking columns are marked and their values are never shown. The model writes a function, you read it and approve it, and it runs on your machine. An offline place-name list lets that code work out distances and speeds without a single real city leaving the building.

For questions that do need rows, `hib ask -f` swaps identifying columns for stable tokens, so grouping by email domain still works, and puts the real values back in the answer. Spotting identifying columns is heuristic and the README says to check the list. Check the list.

## The part where I audited my own leash

Here's the bit I'd skip if I were vain, which is why I'm including it.

I had my assistant go through the code read-only and try to break the claims. It found four things, and I'm telling you what they were because the fixes are public now.

1. **The protected-path check didn't resolve paths.** The rule that keeps "Always allow edits" away from `.git/` and the tool-config folders looked at the first segment of the raw string. So `src/../.git/hooks/pre-commit`, a doubled slash, or a symlink into `.git` all sailed through as "an ordinary edit inside the folder". The whole point of that rule is that an agent can't plant a git hook, and I'd built a door with the lock on the wrong side. I tested this by running verbatim copies of the two functions against a scratch repo; it was real. Fixed by resolving first and comparing case-insensitively (macOS says `.GIT` is the same folder), plus a test with fourteen spellings that must be protected and six that mustn't.
2. **Auto mode approved web fetches and searches.** A prompt-injected page telling the agent to "search for" something with a secret in the query is an exfiltration channel with a friendly name. Web tools now always ask.
3. **"Always" on `python x.py` also covered `python -c …`.** Interpreters and wrappers (`python`, `node`, `bash`, `env`, `xargs`, `find`, `sudo` and friends) now only match the exact command line, because their arguments *are* the code.
4. **The Linux analysis sandbox was a restricted JavaScript context and a good attitude.** With bubblewrap installed it's now a read-only filesystem, an empty home folder and no network. I ran the exact flags with a probe: sandboxed, home hidden, writes blocked, network blocked; unsandboxed, all three open.

Four findings from one read. In my own project. Written by me, a security guy, with opinions about other people's code. I'd like to say I was surprised.

I verified these fixes the way I verified everything else here: by reading the diff and exercising the logic I could extract. I did not run the project's test suite myself, so "fixed" means "the diff does what it says and my probes agree". For what it's worth, the project's CI, on Ubuntu and macOS, passed on the merge.

## What it still does not do

This is the section I'd want if I were deciding whether to trust it.

- **Local processes outside an agent sandbox are trusted.** Anything else running as your user can still read `~/.hib/token`. HIB protects against its agents, not against your own account. The browser now needs a one-time login code instead of handing the cookie to anyone who asks, which is an improvement and not a force field.
- **The CLIs' own file tools aren't sandboxed.** Read and Edit are held to the folder by permission rules and HIB's prompts. If those prompts are wrong, as finding 1 was, nothing else catches it.
- **Your own CLI config still applies.** Broad allow rules in your `settings.json` bypass HIB's prompts, and commands you've listed as sandbox exclusions run outside the sandbox.
- **Codex reads can't be gated.** It runs read-only commands without asking. For a sensitive folder, use a Claude account.
- **Name detection is a model.** The optional local model scored 24 of 24 and 19 of 20 entities on two small hand-labelled sets. Encouraging, small, and it fails closed, which is the correct way to fail.
- **Retention and training are the vendor's business.** A harness can't change what a subscription does with your data.

## If you want to copy the ideas

- **Keep the rules where the agent can't write.** A policy file in the repo is a suggestion. A policy in a database is a rule.
- **Use the OS, not a regex.** If your "safe mode" is a list of bad words, you've built a spell-checker for rm.
- **Resolve a path before you judge it.** String comparison on a path is how you get `src/../.git`.
- **Scope "always".** A command and subcommand, never a bare interpreter, never a compound line.
- **Log what leaves, then protect the log.** The receipt is evidence and also data.
- **Send code, not data,** wherever a question can be answered without the rows.
- **Audit your own stuff.** Preferably before you write a blog post telling people it's secure.

The earlier posts in this family, [From 12,669 Findings to a To-Do List](/posts/one-compose-command-seven-security-tools/) among them, are about the tools that watch a lab. This one is about the tool that's *in* the lab with a shell, and what you hand it.

The code is at [github.com/matijazezelj/hib](https://github.com/matijazezelj/hib). Read it before you trust it. That's the whole point of a box you can open.
