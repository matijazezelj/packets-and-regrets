---
title: "My Inventory Tool Filed a Complaint About Its Own Artwork"
description: "I upgraded a rack inventory tool, every device grew a warning triangle, and the honest fix was not the one-click one."
date: 2026-09-30T12:00:00+02:00
draft: false
categories: ["Field Notes"]
tags: ["Inventory", "Homelab", "Automation", "Source of Truth", "RackPad"]
---

Everything was green. Every device was online, every monitor passed, and every single row in the inventory had a small warning triangle next to it.

The tooltip said: **Physical layout · Needs attention.**

Nothing was broken. The tool was complaining about its own artwork.

## How I got there

I wanted one place that knows what the lab is: devices, ports, cables, VLANs, Wi-Fi, services, the rack. Not a wiki that drifts, not a spreadsheet nobody opens, not my memory, which has a documented history of losing to my own notes.

The plan was boring on purpose:

1. Populate it from **live sources**: the hypervisors, the network controller, the compose files in git.
2. Keep it fresh with a timer instead of good intentions.
3. Never write down anything I could not verify.

That last rule did most of the work, and it is also why the inventory is smaller than it could have been. It does not invent switch ports, serial numbers or cable endpoints. If the controller could not prove both ends of a cable, there is no cable.

## The upgrade that added 55 warnings

Then I upgraded the tool. The new version draws a front-panel picture for every device and maps each port to a slot on it. Devices that existed before the feature got an auto-generated layout, and the tool marks anything that only has a generic layout as needing attention.

That was 55 devices. Fifty-five triangles.

Here is the part worth writing down. There were three ways out:

- **Ignore it.** Legitimate. It is a to-do badge, and it does not touch monitoring, IPAM or cabling.
- **Stamp everything "accurate" with the generic layout.** One API call, and every triangle disappears.
- **Build a real template** for each device that actually sits in the rack.

The second option is a lie with a green checkmark on it. A source of truth that says "verified" about a drawing nobody verified is worse than one that admits it has not looked. I did not do that.

## What "accurate" should mean

I built templates for the seven things that live in the rack: the gateway, the core switch, the NAS, the UPS, two patch panels and the drawers. Port counts and connector types came from the network controller, not from a datasheet I half remembered.

Two rules kept it from turning into a mess:

- **The script refuses to create or unmap ports.** If a template slot has no matching real port, it aborts instead of quietly inventing one.
- **It is idempotent.** I ran it twice. The second run updated the templates and changed nothing else: same port count, same cable count.

I also took a database backup first, because "I can always fix it later" is what people say before they cannot.

The drawings are schematic. The port counts are real; where each port sits on the faceplate is approximate. That is what `accurate` means here: the ports are mapped correctly. It does not mean the picture would fool someone holding the hardware.

## Where the guessing showed up

The mistakes were more useful than the plan.

I put the gateway in the rack at **2U**, because that is how tall the plain version of that product is. The unit in the rack is the Pro variant, which is **1U**. The controller's model code said so the entire time. I trusted the shape I remembered over the identifier I had in front of me.

That is the general failure mode of "fill in the obvious": the obvious thing is a guess wearing a confident face. Every field I could not source stayed empty until the owner of the rack, who is the only one who has ever looked at it, told me the truth: two drawers, a 2U one on top, a 5U one below, and one Proxmox node living in a desktop case next to the rack instead of in it.

I would never have guessed the desktop case.

## Two monitors watching one thing

While I was in there I added health checks to the inventory: a ping per managed device, plus TCP and HTTP probes mirroring the existing uptime checks.

That gives me two systems watching the same services. This is how you end up with two dashboards disagreeing at 3 AM. The rule is simple: the uptime monitor **alerts**, the inventory **remembers**. If a device has an active monitor in the inventory, that monitor owns its status, and the sync stops overwriting it from other sources.

Devices that are powered off on purpose are marked as maintenance rather than offline. A machine you turned off is not an outage; it is a decision.

## What I took from it

- **A green check should have a definition.** If it is easy to make the warning disappear, ask what the warning was protecting.
- **Empty fields are data.** "Unknown" is honest, and it tells you where to go look. A plausible guess hides the gap.
- **Sync the boring parts, ask a human for the rest.** Machines are great at port speeds and terrible at "which drawer is the modem in."
- **Idempotence is a safety feature.** If running it twice is scary, you are not done writing it.

The inventory still has gaps: patch panel port counts, a modem's model number, a couple of serials. They are labelled as gaps. That is the version I trust, and it is a boring sentence to end a post on, which is probably the point.
