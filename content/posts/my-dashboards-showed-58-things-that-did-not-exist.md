---
title: "My Dashboards Showed 58 Things That Didn't Exist"
description: "Seven Home Assistant dashboards referenced missing live states. Six tests kept the cleanup from hiding unavailable devices."
date: 2026-11-06T15:51:00+01:00
draft: false
categories: ["Lab Notes"]
tags: ["Home Assistant", "Dashboards", "Homelab", "Automation", "Testing"]
---

I have written a lot lately about monitoring that [stayed green while things were dead](/posts/nothing-was-red-and-three-things-were-dead/) and a watchdog that [restarted a recorder 141 times on a guess](/posts/my-watchdog-restarted-my-nvr-141-times/). This week's is the dumb little cousin of both: a pile of dashboards that kept **showing me things that were not there**.

Not broken things. Not offline things. Things that don't exist. Tiles pointing at entity IDs absent from Home Assistant's live states, sitting on dashboards I look at on purpose, being confidently wrong at me.

## The count

On November 3 I wrote a small script that asks Home Assistant for its current entity states, then walks every dashboard config looking for references to entities that aren't in that list. First run, preview mode, no writes.

The registered dashboards: ten. Dashboards with at least one reference absent from those states: **seven**. Counting each missing ID once per dashboard: **111 dashboard/entity references**. Unique missing entity IDs across them: **58**.

That's from the saved pre-cleanup configurations and the cleanup result file. Per dashboard, the worst one had 40 distinct missing IDs and another had 39. Two of the seven were my curated ones. The other five were older generations I'd already marked "superseded" and then, being a coward, never removed.

What were the ghosts? Sorted by name pattern, nothing cleverer:

- **45** belonged to a car integration: door and window sensors, tyre warnings, fuel and service data, a lock, and a handful of buttons. Current dashboards reference car entities under a *different* naming scheme, so my inference is that the integration was set up again at some point and the old names never came back. I did not trace when. That would be a nice story and I don't have it.
- **7** were phone and watch sensors, disabled or gone.
- **5** were AdGuard Home entities, in a lab where DNS has been Pi-hole for ages.
- **1** was a Pi-hole group switch that no longer exists.

I'm not going to pretend I know the history of each. I know this much: Home Assistant's `get_states` didn't have them, and the dashboards did.

## Regret 1: a ghost tile is an unreliable narrator

Here's what bothers me. One of my dashboards has a maintenance view whose whole job is "tell me what's broken": offline devices, low batteries, things that need attention. A dashboard like that only works if what it shows means something. Four of the ghost references lived on it, and dozens more on the older dashboards around it.

When some of what you see is permanent noise, you learn to stop looking at it. A signal that's always on is a signal you tuned out, which is the [same failure as last time](/posts/nothing-was-red-and-three-things-were-dead/) wearing a different hat. I didn't screenshot the before state, so I can't tell you exactly how each tile rendered. I can tell you the config referenced entities that didn't exist, and I can't honestly claim I ever read every one of those tiles.

## Regret 2: "missing" and "unavailable" are not the same word

This is the part where the script could have been a disaster, and the reason the post is worth writing.

Home Assistant has two different failure shapes:

- **Missing**: the entity ID isn't in `get_states` at all. There is no current state for that tile to display.
- **Unavailable**: the entity exists in the state list, and its state is literally `unavailable`. A device or integration isn't supplying a usable reading. That's a live problem to investigate, not a stale reference to tidy away.

Missing from states does **not** prove an entity was permanently deleted. Disabled entities can lack a state, and an integration can be temporarily absent. This script doesn't establish the history. That's why preview and human review matter: an absent ID is a cleanup candidate, not a death certificate.

The naive cleanup is "remove everything that looks red." That would have deleted exactly the tiles whose job is to tell me a purifier fell off Wi-Fi. So the rule is: **presence in `get_states` is the test, not the state value.** An entity that's present and unavailable stays on the dashboard. The script only removes references to entities that are absent from the list.

And there's a legacy air quality view that still shows unavailable purifier sensors. It's still there after the cleanup. That's deliberate. Those sensors still have state entries; some readings are unavailable. A cleanup that makes the offline thing disappear is not a cleanup, it's a cover-up.

## Regret 3: deleting one tile can change what a card *does*

The part I'd have gotten wrong if I'd written it in a hurry. Lovelace has conditional cards: "show this card only if entity X is in state Y." If X is a ghost and you just delete the condition, the card loses its guard and **shows up unconditionally**. A control that was supposed to appear only in some situation now sits there all the time.

So the rule in the script: if a condition references a missing entity, the whole conditional card goes, not just the condition. There's a test for exactly this, and it's the one I'm most glad exists.

The helper has six unit tests. In plain English:

1. A missing tile is removed; an existing one is kept; the input isn't mutated.
2. A present-but-unavailable entity is preserved.
3. An entity list is pruned entry by entry.
4. A missing condition never turns a conditional card unconditional.
5. A container left empty (and a heading left with nothing under it) is removed.
6. Running it twice changes nothing.

I ran those six this run; they pass. That's all "pass" means here: the pure function does what the tests say. I didn't write a test for every Lovelace card type, and there are plenty I don't use.

## The mechanics, so you can copy it

- Fetch `get_states` and the dashboard list over the WebSocket API.
- **Back up every dashboard config to a timestamped directory first**, before any write.
- Compute the pruned config; if it equals the old one, skip.
- On `--apply`: re-read the dashboard and abort if it changed since the backup (somebody else editing), save through the supported `lovelace/config/save` call, then read it back and assert it matches and that pruning it again finds nothing.
- Don't touch the entity registry, integrations, automations or resources. This only edits dashboards, because those are the only thing I wanted to be wrong about.

Default is preview. You have to ask for `--apply`.

After applying, the notes record an API readback with no missing references across the registered dashboards, plus a browser pass over the 15 remaining views in the seven touched dashboards. I'm quoting those from my own commit notes; I didn't redo the browser pass for this article.

## And then I checked again, because of course

Writing this, I ran the script again in preview mode from a scratch copy, so nothing in the repo moved and nothing was applied. Three days after the cleanup it found **two dashboards with one new ghost each**: the same missing update entity, referenced on a maintenance dashboard and on an older media-ops one.

I don't know why that entity is gone. I haven't looked, and I'm not going to claim a cause. The point stands without one: **dashboards rot as the system under them changes, and a cleanup is a snapshot, not a state.** I cleaned house and three days later a new thing walked out of it.

I left it alone. It's a single tile, and the script already refuses to touch anything I haven't asked it to.

## What I still don't know

- When each of the 58 ghosts was born. I have the result file, not a timeline.
- Whether the ghosts ever hid a real problem from me. I never measured it.
- Whether the new ghost is a removed integration, a renamed entity, or a finished update. Could be any.

## If you want to copy it

- Treat "entity not in states" and "entity unavailable" as different events with different owners. One is a reference to review. The other is a live device or integration problem to investigate.
- Preview first, back up always, apply on request. A dashboard config is state, and state needs a rollback.
- Conditions are guards. Deleting the guard is not deleting the guarded thing.
- Write the idempotence test. If running your cleanup twice changes something, you have a different bug.
- Put the check on a schedule or accept that the ghosts come back. I haven't done the schedule. Writing "I should" in a blog post is, I'm told, how most automation starts.

Fifty-eight things absent from live states, on dashboards I kept around. Ricky Gervais would say that's just most meetings. I'd say it's a dashboard, and I'm the one who built it.
