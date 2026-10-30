---
title: "I Stopped Being My Homelab's Sysadmin. Now I Manage One."
description: "Twenty-five years of experience, an agent that can execute, and the inconvenient discovery that delegation still needs a grown-up."
date: 2026-10-30T16:00:00+01:00
draft: true
categories: ["Build Notes"]
tags: ["AI Agents", "Operations", "Change Control", "Homelab"]
---

I used to operate my homelab by opening a terminal and doing the work.

Now I also spend time telling an agent what the work actually is, rejecting the thing it decided would be more interesting, and asking whether “verified” means it checked the running service or simply admired the file it wrote.

Apparently I have promoted myself into management. Nobody mentioned the benefits package was more reading.

The title is a provocation, not a resignation letter. **I'm still the sysadmin. I've delegated more of the execution, not the responsibility.**

But something has changed. After twenty-five years working with infrastructure, the useful question isn't whether a model can remember a command. It's whether experience, a capable agent and real boundaries can produce something resembling the operational breadth of a small engineering team.

I think that's worth examining. I do not have a defensible headcount multiplier. If you've come for “one engineer now equals seven,” the marketing department is down the hall, inventing a denominator.

## 1. Typing got cheap. Knowing when to stop didn't.

The interesting part of infrastructure work was never remembering every flag.

It's recognising that a database replica needs to catch up before another node goes down. That keeping an old backend doesn't keep its data current. That a successful request through a proxy might prove the fallback works, not the migration.

Those distinctions are experience doing its job. None disappears because something else can type faster.

An agent can investigate configurations, compare alternatives, write a bounded change, run checks and update documentation. That's useful work. I don't need to pretend it's merely fancy autocomplete to preserve my dignity.

But somebody still has to decide what matters, what evidence is sufficient, which dependencies come first and where the request ends.

“Make this better” is not a scope. It's an invitation to return from lunch and discover a platform initiative.

My job is increasingly to turn a fuzzy concern into something another operator could execute and I could meaningfully accept. The agent makes that discipline more valuable, not less necessary.

## 2. Three things the pair actually delivered

The strongest evidence I have isn't a benchmark. It's work with artifacts and limitations attached.

### Small services moved to BSD

In [the previous post](/posts/bsd-a-separate-vlan-and-an-agent-that-has-to-show-its-work/), I described moving suitable services to BSD while keeping Linux where the workload fit it better.

The result included service placement, proxy changes, direct backend checks and operating notes. The old backends weren't immediately discarded.

That last sentence could support a very comforting lie: “rollback is handled.”

For a static site, returning traffic to the old server can be straightforward. For an application whose database was copied at cutover, the old instance can become stale as soon as someone changes something. A backup destination in a proxy isn't a data-recovery plan.

The delivered work mattered. So did refusing the stronger claim.

That is the division I want: use the agent's capacity to perform the connected implementation work; use experienced review to insist that the recovery story matches the actual state. The earlier article records successful direct endpoint checks, not a universal failover or restore proof.

### Work acquired an approval interface

We also built a private workflow separating investigation, options, an exact execution plan, approval and acceptance.

That produced code, tests and records instead of another paragraph saying the agent should please be careful.

The supported automatic operations are deliberately narrow. An investigation request isn't permission to deploy. A numbered option isn't an executable approval. An accepted assessment isn't an implemented control.

The useful artifact isn't “an AI ticket system.” It's a way to keep the meaning of yes from expanding halfway through a job.

### A convincing watchdog story got corrected

Then there was [the recorder watchdog](/posts/my-watchdog-restarted-my-nvr-141-times/).

The published analysis checked a restart counter against the journal and separated different preceding failures. It also backed away from a stronger, more satisfying claim that all those restarts were false.

Missing recording segments didn't establish broken storage. A passing read didn't establish healthy writes. A configured dashboard panel didn't establish that anybody had watched it.

The valuable output was not just a polished explanation. It was an explanation made less certain where the evidence demanded it.

That's an awkward productivity story. Some of the work consists of taking confident sentences out. They don't show up nicely on a chart, but I'd rather remove an unsupported claim than automate it.

## 3. Management became an interface

Here's the loop I'm trying to make ordinary:

**Evidence → options → exact scope → authorization → execution → verification → acceptance.**

Not every job needs a committee. A routine, well-understood change can be brief. It still needs a shared understanding of what is being changed and what would demonstrate success.

A finding has to explain:

- What was actually observed.
- What failure or attack path that observation supports.
- The smallest reasonable change.
- How we will check the intended result and the workload we must preserve.

Without that, an agent can generate a mountain of plausible concerns. Congratulations: we've automated my inbox.

The same discipline applies after implementation. A diff is evidence that text changed. A test result is evidence for the paths that test exercised. A live request is evidence for that request. None automatically proves the other two.

Acceptance is the point where I decide whether the result meets the scope, rather than letting “the agent finished talking” become our release criterion.

There is also a distinction between rejecting a proposal and discovering it was never authorised. The first can be useful exploration. The second means the execution boundary failed. Counting both as ordinary rework would hide the more serious problem.

## 4. Instructions are not a fence

I give the agent instructions. Plenty of them. The accumulated list has the energy of a landlord describing what the previous tenant did to the kitchen.

Instructions are useful for consistency. They are not the same as permissions.

“Don't make that change” and “the execution mechanism cannot express that change” are different controls. “Ask me first” and “an independent mechanism checks an authenticated approval for this exact operation” are different controls too.

The routine handler uses a fixed operation catalogue rather than treating issue text as shell. Approval is tied to a particular plan; changed relevant state invalidates it. More consequential operations remain separately supervised.

Those properties constrain that handler. They do not, by themselves, prove that the whole agent runtime is contained.

Likewise, a designated administrative path and a separate network segment are design elements, not a complete isolation acceptance report. A diagram doesn't generate denial evidence. Calling two programs “investigator” and “executor” doesn't create an operating-system security boundary between them.

I'm deliberately not publishing a victory lap about complete containment. This article is about how I'm changing the working relationship, not certifying the finished security of every component.

The standard is boring: establish which operation a control permits, which it denies and what evidence proves that boundary. Then keep the claim inside that evidence.

## 5. A room full of agents isn't independent review

This is where the small-team comparison starts to break down.

The work can span investigation, implementation, tests, documentation and operational checks. That resembles several roles. It doesn't establish that I have several independently accountable engineers.

Another model reviewing the first model's work can catch mistakes. It can also share the same blind spot, accept the same false premise or become very impressed by the first model's explanation.

Two confident answers aren't independent measurements just because they arrived in separate chat windows.

Nor does parallel execution remove my own bottleneck. If every result requires reconstruction before I can trust it, I haven't gained a team. I've acquired a review queue with excellent formatting.

The operator's absence matters too. Would this arrangement handle an unfamiliar incident safely without me? Who challenges a bad architectural premise? Who owns the risk decision when the evidence is ambiguous?

Those aren't answered by spawning more workers.

What I can reasonably describe is **one experienced operator with considerably more execution capacity**. Whether that becomes reliable team-like output depends on review cost, correction rates and how much judgment still funnels through that one person.

## 6. The number I haven't measured is my attention

I haven't recorded active human review time well enough to tell you how many hours this saves. I don't have a credible before-and-after baseline, either.

Conversation timestamps won't rescue that. The gap between a request and a reply might include execution, waiting, me making coffee or me ignoring the phone. It isn't a timesheet.

Commit counts are no better. One useful bounded change can take several commits. A hundred generated edits can still be the wrong change.

So here's what I'd measure for a proper follow-up:

1. **Accepted outcomes.** Separate investigations, tested code, documentation and changes actually deployed and verified.
2. **Human attention.** Record real review and intervention time, not the age of a ticket.
3. **Rework.** Include rejected proposals, factual corrections, scope mistakes and recovery from failed changes.
4. **Verification cost.** Could I assess the evidence directly, or did I have to redo the investigation?
5. **Authority failures.** Track attempts to cross the approved scope separately from ordinary implementation bugs.

That's a proposed measurement approach, not a new collector I quietly installed to make an article more scientific.

Until those records exist, I can show the work and discuss its shape. I cannot honestly convert it into salaries, full-time equivalents or a percentage improvement.

Missing numbers limit the claim. They don't require pretending nothing useful happened.

## 7. If you want to try the useful version

Start with a job whose result you already know how to evaluate. Not because the agent must stay junior forever, but because you need a working quality bar before delegating execution against it.

Then:

- **Define the finish line before the work.** Include what must remain unchanged.
- **Ask for options before authorising a consequential change.** An investigation is not a blank cheque.
- **Keep routine execution narrow.** Expand the catalogue after evidence, not enthusiasm.
- **Require evidence at the right layer.** Written configuration, passing tests and running behaviour answer different questions.
- **Keep recovery independent of the agent.** It mustn't be the only operator capable of fixing its own administrative path.
- **Retain the corrections.** A system that remembers only its successes is writing a sales deck, not an operating history.

And expect to manage it. You don't get to exchange a keyboard for an approval button and call the remaining work solved.

## Still my problem

This is a follow-up to the published workflow and incident records, not a new benchmark. I reread those records and the current approval documentation for this draft. I did not run a fresh containment exercise, outage drill or productivity study to write it.

The useful change is that more of my experience can be expressed as scope, sequencing, constraints and acceptance while the agent handles more execution. Whether the review burden makes that a good trade remains something to measure honestly.

I haven't stopped being the sysadmin.

I've stopped assuming being the sysadmin means I have to personally type every command.

Unfortunately, it still means the stupid decisions are my problem. Even when the machine made them very quickly.
