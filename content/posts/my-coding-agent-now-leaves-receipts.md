---
title: "My Coding Agent Has a Leash. Now It Leaves Receipts."
description: "HIB now guards log streams and records security decisions. SIB can collect those receipts and watch agent processes separately."
date: 2026-11-13T16:02:00+01:00
draft: false
categories: ["Build Notes"]
tags: ["AI", "Security", "HIB", "SIB"]
---

A coding agent tries to do something it shouldn't. The harness says no. Lovely. Where does that decision go?

If the answer is "it scrolled past in a terminal", I haven't built an audit trail. I've built a security control with the memory of a goldfish.

The recent Git history of two of my projects is about closing that gap. [**HIB**, harness in a box](https://github.com/matijazezelj/hib), sits around subscription coding CLIs, guards data and handles approvals. [**SIB**, SIEM in a box](https://github.com/matijazezelj/sib), collects security events and uses Falco to watch processes at the kernel boundary.

HIB now has a streaming log filter and a structured security event log. SIB can collect that log, alert on its decisions, and separately watch what coding-agent processes do.

One side says what it allowed. The other can see what happened. That's a better conversation than asking the agent whether the agent behaved itself.

**Scope, before the sales pitch gets ahead of the evidence:** I read both repositories at the source revisions linked below, ran 74 targeted HIB tests and 38 SIB generator tests, and exercised HIB's filter with synthetic input. I did not deploy the new HIB-to-SIB collection path or run the privileged Falco runtime test for this article. Those are different acceptance gates, not inconvenient footnotes.

## 1. HIB can guard a stream, not just a conversation

The first useful addition is [`hib pipe`](https://github.com/matijazezelj/hib/commit/1a2379f).

Previously, the obvious entry point was a conversation: redact identifying values before a prompt leaves, then restore them in the answer. The new filter can sit in a shell pipeline without choosing a model or making a model request itself.

It reads JSON events or text lines from standard input and writes guarded output. That makes it useful before a log shipper, an analysis script, or another tool that really doesn't need everyone's identity to explain a failed login.

I tested it using an invented event:

```json
{"user":{"name":"sample-user"},"message":"login failed for sample-user","process":{"name":"sshd"}}
```

Running it through `hib pipe --vault blog-fixture --format ndjson` produced:

```json
{"user.name":"[HIB09d3-USER-NAME-1]","message":"login failed for [HIB09d3-USER-NAME-1]","process.name":"sshd"}
```

That's actual output from the synthetic fixture, not an illustration of what I hoped the code would do.

The identifying field became a placeholder. Its occurrence in the message became the same placeholder. The process name stayed useful. Nested objects became dotted fields, which is a schema change consumers need to expect.

I then started a second filter process against the same named vault. It produced identical output. Finally, I ran `hib pipe restore --vault blog-fixture`: the username and message came back, while the flattened keys stayed flattened.

**This is pseudonymisation, not magic anonymity.** It preserves relationships deliberately. The mapping remains local in a persistent sealed vault, and anyone with the ability to restore it can recover the values. That's a feature when you're investigating something, and a reason to protect the mapping.

It's also not the entire HIB guard squeezed into a pipe. HIB's optional local name detector is an important part of its other workflows, which I covered in [the original leash post](/posts/my-coding-agent-has-a-shell-and-my-ssh-keys/). **The streaming filter does not currently run that detector.** It uses field classification, patterns, configured terms and remembered values. Same repository does not mean identical coverage.

## 2. A broken filter must not quietly become `cat`

The filter has three error policies: replace a failed line, drop it, or stop with an error. None is supposed to pass the failed original through.

With strict JSON-lines input and an intentionally malformed fixture, the default policy returned:

```json
{"hib_redacted":true}
```

The targeted tests also exercise all three error policies, restoration across chunk boundaries, and a guard that throws.

I like that the progress statistics go to standard error. The guarded stream stays on standard output. If I'm putting a filter in front of a log collector, I don't want a cheerful progress message turning into tomorrow's mysterious parser failure.

There are still limits. The vault is checkpointed periodically and at normal completion; abrupt termination can lose mappings created since the last save. That matters if restoring those particular placeholders is part of your workflow. And per-field replacement is not a proof that the remaining context cannot identify someone.

A filter should explain its contract. "Privacy" on a README badge is not a wire format.

## 3. The harness now records its own decisions

The next addition is a different stream entirely: [HIB's security event log](https://github.com/matijazezelj/hib/commit/9606068).

Don't confuse these two features:

- **`hib pipe`** guards logs you feed into it.
- **HIB's event log** records what HIB itself is doing.

The event log includes approval requests, tool permissions, blocked data reads, authentication failures, unavailable sandboxes, session lifecycle and reverted changes to protected configuration.

The schema includes timestamps, severity and relevant session context. It is designed to record decisions rather than prompts, model answers or file contents. User-controlled command, URL and reason text goes through redaction before logging.

The collector gets a dedicated event directory, not the harness's entire state directory. The implementation creates that directory with owner-only access and new files with owner-only read/write permissions. The event tests check those modes and rotation behaviour.

A small [follow-up commit](https://github.com/matijazezelj/hib/commit/d087569) is particularly good: pending authentication-failure counts are written before a clean daemon stop. Repeated failures are aggregated, so an alert should sum the recorded counts rather than count JSON lines and call that the number of attempts. The shutdown test checks that counted failures aren't lost at that boundary.

That's the kind of change that doesn't make a gorgeous screenshot. It does make the screenshot's number less likely to be nonsense.

**Metadata still deserves protection.** Workspace paths, account names, timing and tool usage can reveal a project or a customer without containing a prompt. This stream belongs behind the same access and retention controls as other security telemetry. "No transcript" does not mean "nothing sensitive".

## 4. SIB gets both the receipt and another viewpoint

[SIB's HIB integration](https://github.com/matijazezelj/sib/blob/main/docs/hib-integration.md) has two opt-in parts.

First, its collectors can ship HIB's JSON events into VictoriaLogs or Loki. The associated alert group covers critical security events, authentication-failure counts, bursts of denials, an unavailable sandbox and missing daemon heartbeats.

Second, an optional Falco rule pack watches coding-agent processes and their descendants. Its targets include credential-store reads, writes that could establish persistence, and changes to repository hooks or agent configuration.

These are different kinds of evidence. HIB can report "I denied that tool call". Falco can report that a matching process opened a watched file. Neither statement, alone, tells the whole story.

Nor is Falco another sandbox. It detects selected behaviour; it doesn't undo the action. Process ancestry and exceptions need testing too. The rule pack deliberately distinguishes legitimate CLI activity from suspicious child-process activity, rather than declaring every credential access a breach.

The repository contains a privileged runtime test using stand-in agent processes and fake files. It defines seven positive and six negative cases, including Git's inert sample hooks. **I read that script; I did not run those thirteen cases.** The documentation reports them passing on the stated Falco version. My article's local test results are the application and generator tests, not a kernel-level validation.

Also worth separating: SIB **0.7.0** contains the recent alerting and delivery improvements. The HIB integration and coding-agent rules are under **Unreleased** in the main-branch changelog I reviewed. Don't install the release tag and assume every feature in this paragraph is included.

## 5. SIB also learned to share a Grafana

The less glamorous half of the Git log is about fitting into an existing installation.

SIB's [shared-Grafana support](https://github.com/matijazezelj/sib/commit/37dbc3367db425fac18ae31c16a45d6c4a04aca8) lets it provision rules and contact points without owning the organisation-wide notification policy. Datasource identifiers are configurable too.

That matters. Adding one tool should not mean handing it the office keys and discovering it has rearranged every other team's alerts.

The setting is explicit:

```dotenv
GRAFANA_MANAGE_NOTIFICATION_POLICY=false
```

In that mode, SIB leaves policy routing to the operator. Generating a Slack or Telegram contact point is not the same as adding the route that will use it.

The newer commits add Telegram delivery and reject incomplete configuration. They also generate an authenticated HTTPS scrape when Falcosidekick's listener requires mutual TLS, rather than letting a plain HTTP metrics request fail forever against a working encrypted service.

That is not glamorous security engineering. It's better: fewer ways to install something that looks configured and isn't.

## What I actually checked

At the snapshots linked below:

- **74 targeted HIB tests passed**, covering records, encoded payloads, persistent vaults, streaming and security events.
- **38 SIB generator tests passed**, covering alert provisioning and Sidekick configuration.
- The separate-process filter fixture preserved its placeholder mapping, restored its values and replaced malformed strict-JSON input.
- GitHub reported successful CI for both reviewed main revisions.

I did **not** run a cloud model, benchmark name detection, connect a production collector to HIB, exercise Telegram delivery, or start the privileged Falco test. Passing this subset is useful evidence, not a security certification with a nicer font.

For anyone copying the design, my checklist is short: keep the two streams distinct, protect the reversible mapping, collect only the event directory, verify the alert route, and test the runtime detector separately from its YAML generator.

The important change isn't that my tools produce more logs. Plenty of software can do that. Most of it appears to do little else.

It's that the guard can now leave a receipt, and the monitoring stack can ask a second witness.

---

**Reviewed source snapshots:** [HIB `24337c9`](https://github.com/matijazezelj/hib/tree/24337c9dcd55bdac18f3aab96696f6bab0a44a5d) and [SIB `8e79b64`](https://github.com/matijazezelj/sib/tree/8e79b64c15595f7eef56b110a5eb2e4cfeaa34ab). These are source-review and isolated-test results, not a claim that every new feature is deployed in my lab.
