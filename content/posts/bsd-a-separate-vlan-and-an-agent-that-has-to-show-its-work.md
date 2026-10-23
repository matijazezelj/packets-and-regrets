---
title: "BSD, a Separate VLAN, and an Agent That Has to Show Its Work"
description: "I moved small services to BSD, gave the agent its own network segment, and replaced vague approval with evidence and numbered plans."
date: 2026-10-23T16:40:00+02:00
draft: true
categories: ["Build Notes"]
tags: ["BSD", "Networking", "AI Agents", "Change Control", "Homelab"]
---

The usual homelab upgrade is a new service. Mine this week was a paperwork requirement.

Some services moved to BSD. The agent moved to its own network segment. And I stopped accepting a chat history as a reliable change-management system, because apparently my architecture had become “a helpful machine, a pile of credentials, and me remembering what I meant by yes.”

Excellent. Very enterprise. We just needed a spreadsheet called FINAL-final-v3.

These look like three unrelated changes. They're really the same argument: **give a component a specific job, make its boundaries explicit, and don't call the job finished because something turned green.**

## 1. BSD came back because some jobs are pleasantly small

I haven't replaced Linux. I haven't discovered that containers were a mistake. The machines doing hardware-specific work and the applications whose upstreams are built around containers still have perfectly good reasons to stay where they are.

What I wanted was somewhere sensible to put the quieter jobs: serving documentation, a small status frontend, static browser tools, a feed reader, music, and another watcher.

OpenBSD got the small web-serving roles. Its base `httpd` is useful precisely because it doesn't arrive with an ambition to become my entire application platform. But it also doesn't do every job I need. Some frontend and proxy behaviour needed packaged nginx.

That's an important distinction. “I used OpenBSD” does not mean “everything is in base,” and “small web service” does not mean “every HTTP server is interchangeable.” I kept the software that actually supports the application instead of turning an operating-system preference into unpaid porting work.

FreeBSD got applications in jails, with separate ZFS datasets: a host, named compartments, ordinary service management, and application data with a known home.

Jails share their host kernel. They are not little virtual machines wearing better shoes. ZFS datasets are not, by themselves, a backup strategy. I'm using those tools for the boundaries they provide, not the ones I'd like a diagram to imply.

The selection rule is deliberately unromantic: **use BSD where the service fits; use Linux where Linux is the better fit.**

Nobody gets a prize for moving a working hardware-dependent application just to make the operating-system chart symmetrical.

## 2. A migration needs an exit door

The old container instances weren't immediately deleted. The reverse proxy gained BSD primaries while retaining the previous backends as backups.

That is a much better migration shape than “change the destination, remove the old thing, and become religious about backups.”

It also needs two different checks:

- Does the user-facing route work?
- Is the intended new backend actually healthy?

If you only ask the first question, a proxy can quietly fall back to the old backend while you congratulate yourself on a successful migration. The old service is doing all the work. The new service is technically participating as a decorative outage.

So the new backends also have direct checks. A successful public-facing request should not erase evidence that the thing I meant to migrate to is unavailable.

There is a nastier qualification for stateful services: **a retained backend is not necessarily a current copy of the data.**

One migrated application's database was copied at cutover. Changes after that point can diverge from the old instance. Sending traffic back is easy; deciding which state is authoritative is not. Other applications share a database, which has its own concurrency considerations rather than magically removing them.

“Rollback available” therefore means something service-specific. For static content it can be a routing decision. For mutable application data it needs an explicit data-recovery story. The backup flag in a proxy configuration doesn't write that story for me.

## 3. I moved the agent, not the meaning of “isolated”

The agent now has its own network segment rather than living among the ordinary workloads. An OpenBSD bastion provides a designated SSH jump path, with a separate forwarding role and connection auditing.

This is where a nice diagram can get ahead of reality.

A VLAN is a place to enforce policy. It isn't the policy. A bastion is a path I can constrain and inspect. It isn't proof that every other path is denied. An approval workflow is an authorization mechanism. It isn't a kernel-enforced sandbox.

Those statements sound pedantic until the component you're discussing can run commands. Then pedantry becomes considerably cheaper than optimism.

The honest description of this stage is **moved to a dedicated segment, with the isolation acceptance work tracked separately**. I'm not presenting the move itself as a completed containment test.

Isolation needs allow/deny evidence across SSH, APIs and other traffic, plus independent human recovery before restrictions can lock out administration. A VLAN label isn't that evidence.

The agent mustn't become the only thing capable of fixing the fence around the agent. That's not a recovery plan. That's a hostage arrangement with excellent autocomplete.

## 4. The move exposed a connection-management problem

There was also a practical snag: bursts of new SSH connections after the move were associated with temporary connection blocking. The operational notes attribute it to the router's threat handling, but I don't have a complete controller-side event reconstruction proving that cause. I'm not upgrading a plausible explanation into a fact because it gives the story a villain.

The operational change was SSH connection multiplexing: a persistent master carries the jumps instead of creating a fresh connection for every small command. It runs under service supervision rather than being a lucky child process of an interactive session.

That master has a health check too. Otherwise I've just made administration depend on another background process whose failure mode is “everything looks inexplicably broken.” I have written that episode already. I don't need a franchise.

The lesson isn't “disable the router's protections.” It's that moving a workload across a routing boundary changes the connection pattern seen by the infrastructure. Check that pattern before treating every refusal as a broken target host.

## 5. The tracker is the important part

The most useful change wasn't an operating system. It was giving the work somewhere better to live than the middle of a conversation.

The private issue tracker now separates a finding, a proposed change, the investigation, approval, execution, and acceptance. Those are different objects even when a human is tempted to compress all of them into “yeah, fix it.”

Every finding needs four things:

1. **Observed evidence.** Actual configuration, command output or an API response, with secrets removed and missing evidence called out.
2. **Attack path.** What an attacker would need to control and what that could achieve. A reachable page is not automatically an authentication bypass.
3. **Smallest reasonable remediation.** Not a general invitation to redesign the network.
4. **Acceptance test.** Evidence that the unwanted path is closed and the intended workload still works.

Without that distinction, an automated audit can produce an impressive mountain of statements that look like findings but don't establish anything actionable.

I don't need an AI to tell me software has versions and networks have ports. I need it to explain what it actually observed, what that observation doesn't prove, and which bounded change would improve the situation.

Dependencies matter too. Investigating an issue early can be useful; applying its remediation before its prerequisites are proven is a different decision. Closing a report doesn't implement the control described in it.

## 6. “Pickup” is not “go ahead”

A fresh owner `/pickup` comment requests investigation. It doesn't authorize a deployment.

Each picked-up issue now gets stable option IDs. If there are genuinely different approaches, they're listed separately, with their scope, gate, acceptance and rollback or stop conditions. Independent workstreams aren't disguised as mutually exclusive alternatives.

The discussion IDs are deliberately distinct from executable approval IDs. Choosing an idea asks the agent to refine that scope. It does not turn a paragraph into a command.

For a supported routine action, the next step is a separate exact execution plan. That plan identifies the service and operation, relevant current state, verification, rollback, prerequisites and expiry. A fresh owner `/approve` comment must name that plan.

I don't want “approved” to mean whatever the model thinks I probably intended based on three other conversations and a sentence beginning with “while you're there.”

There is no “while you're there.” There is another plan.

## 7. The model investigates; a narrower program handles execution

The investigator can read infrastructure within its permitted scope and write evidence or proposals to the tracker. Supported routine mutations go through a separate deterministic handler with a fixed operation catalog. Issue text isn't evaluated as shell.

Approval binds authenticated owner, issue and immutable plan. Changed state invalidates it; holds and prerequisites still apply. Duplicate delivery mustn't become duplicate production work.

The initial catalog is intentionally small: specified single-service restarts and particular digest-pinned stateless image updates. Network policy, credentials, permissions, reboots, restores, destructive actions and unsupported changes still require separately scoped supervision.

That's not the AI being less useful. It's the AI being useful without turning a typo into an infrastructure-wide referendum.

After execution and verification, `/accept` records acceptance of the result. It doesn't retrospectively authorize another operation. Partial remediation leaves the broader finding open.

A real owner acceptance has already gone through this path. At drafting time the queue and handler suite passed **84 tests**; rollback and failure cases include isolated command stubs, not surprise production outages. I also exercised live read-only service checks and a bot-authored approval that was rejected.

That is evidence for those checks. It is not a claim that every unattended rollout has been tested in production. Separating two programs is also not equivalent to enforcing an operating-system security boundary. Different claims, different acceptance tests.

## What I checked, and what I didn't

While drafting, I checked the BSD systems, the running FreeBSD jails, and six direct service endpoints from a separate LAN host. Those endpoints returned successful responses. I checked the supervised SSH master and the approval timer, and reran the tracker tests.

I did **not** repeat a failover exercise, perform a restore, revoke identities, test every network-denial path, or run a production image update for the sake of an article. The migration records explain the retained-backend arrangement and its state caveats; today's endpoint checks are not substitutes for those other tests.

The different operating systems also still depend on physical infrastructure. A watcher in another guest can catch some application-host failures without being an independent power supply. I'm not claiming fault-domain diversity just because `uname` prints something different.

## If you want to copy the useful bits

- **Pick an operating system for the workload, not the screenshot.** Small and conventional beats an elaborate demonstration of loyalty.
- **Monitor the intended backend, not just the route.** Fallback can hide a failed migration.
- **Treat state separately from traffic.** Keeping the old process doesn't keep its database current.
- **Separate placement from enforcement.** A network segment is the start of an isolation design, not its acceptance report.
- **Give each decision an identity.** An idea, an execution plan and an accepted result shouldn't share one ambiguous yes.
- **Make the agent show its work.** Evidence first, bounded proposal next, authorization for that proposal, then verification.

The point wasn't to make the lab more exotic. It was to make the responsibilities less vague.

BSD got a few jobs it fits. The agent got a designated place to live and a more explicit way to ask for changes. I got fewer decisions hidden in a scrollback buffer.

If it wants to be helpful, it can bring a plan number. I'm trying a radical new management technique: remembering what I approved.

*Related: [My Coding Agent Has a Shell and My SSH Keys. So I Built It a Leash.](/posts/my-coding-agent-has-a-shell-and-my-ssh-keys/) and [My Watchdog Restarted My NVR 141 Times. It Was Guessing.](/posts/my-watchdog-restarted-my-nvr-141-times/).*
