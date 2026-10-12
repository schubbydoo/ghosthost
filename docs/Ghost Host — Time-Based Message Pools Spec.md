# Ghost Host — Pool Schedules Spec

Oct 11, 2026 · @Steve Schubert

The one new feature is a **schedule**: a sensor port (or network trigger) can point at a schedule instead of a single pool, and the schedule switches pools at set local times. You set it up before the party and it runs on its own from the Pi's clock, with nothing to start on the night. Everything else in the Ghost Host control panel stays as it is.

## What already exists (no changes)

The control panel at ghosthost.local:8000 already has the building blocks; the schedule reuses them as they are.

| Existing feature | What it does today | How schedules use it |
| --- | --- | --- |
| Audio files | Upload, default audio, per-file mouth-sync timestamps | Every file in a scheduled pool still needs timestamps |
| Greeting Pools | Named file lists, played in shuffle order with no repeats until all play | Each schedule step points at one existing pool |
| Sensor Assignments | Left and Right ports each pick a pool, or none for default audio | The dropdown gains schedules as choices |
| Network Triggers | Named trigger with ID, file or pool, enabled flag | Its pool dropdown gains schedules too; new trigger actions for host overrides |
| Sensor Cooldown | One cooldown in seconds for both ports | Unchanged (see open question on per-port cooldown) |
| Idle look-around, volume, WiFi | Prop behavior and setup | Unchanged |

Your existing clips (NosferatuClue.wav, NosferatuClueFloyd.wav, NosferatuPuzzleSolved.wav and the rest) can be dropped into the new clue pools as they are.

## New: schedules and play order

A **schedule** is an ordered list of steps. Each step names an existing pool and the local time it takes over, such as 8:30 PM. Two small additions make it work:

1. **Schedules**, a new saved object alongside pools.
2. **Play order on pools**: the current shuffle stays the default, and a new "In order" option plays the pool's files top to bottom, then loops. Clues need this; greetings keep shuffle.

No cumulative logic is needed in code. To let later players still hear early clues, build each later pool to include the earlier files, e.g. Clues 2 = the tier 1 clues plus the new ones.

Stored alongside the existing pools (field names are suggestions; match your current settings file). The times are placeholders for a 7 PM party:

```json
{
  "timezone": "America/New_York",
  "pools": {
    "Entry":   { "files": ["NosferatuAnnouncement.wav", "..."], "order": "shuffle" },
    "Clues 1": { "files": ["clue_servants.wav", "clue_four_letters.wav", "clue_dial_letters.wav"], "order": "in_order" },
    "Clues 2": { "files": ["clue_servants.wav", "clue_four_letters.wav", "clue_dial_letters.wav", "clue_glass_T.wav", "clue_T_is_eight.wav"], "order": "in_order" },
    "Clues 3": { "files": ["...Clues 2 files...", "clue_word_is_time.wav"], "order": "in_order" }
  },
  "schedules": {
    "Curse Clues": {
      "active_date": "2026-10-31",
      "night_rollover": "06:00",
      "steps": [
        { "at": "00:00", "pool": "Clues 1" },
        { "at": "20:30", "pool": "Clues 2" },
        { "at": "21:30", "pool": "Clues 3" }
      ]
    }
  },
  "sensor_assignments": {
    "left":  { "pool": "Entry" },
    "right": { "schedule": "Curse Clues" }
  },
  "schedule_override": { "step": null, "set_at": null }
}
```

Three schedule settings carry the logic:

- **at**: the local time a step takes over. A step at 00:00 or earlier than the rest is the starting pool.
- **night\_rollover**: times before this hour count as after midnight of the same party night, so a 12:30 AM step sorts after 11 PM. Default 06:00.
- **active\_date** (optional): the schedule only escalates on that party night. On any other day it stays on the first step, so testing the prop the week before never gives away the final clue. Leave it blank to run the same times every night.

A sensor assignment holds either a pool or a schedule, never both. Existing settings files with only a pool load unchanged.

## New: control panel additions

Four changes to the page, placed next to the sections they extend.

| Where | Addition |
| --- | --- |
| Greeting Pools | A Play order dropdown per pool: Shuffle (default) or In order |
| New section after Greeting Pools: **Schedules** | Add Schedule, a name, an optional Active date, then rows of (Starts at time, Pool dropdown) with add and remove row buttons. Save Schedule, Delete Schedule. Rows sort by time of night on save. |
| Sensor Assignments | Each port's dropdown lists pools, then schedules under a divider, e.g. "Schedule: Curse Clues" |
| New section at the top under Status: **Schedule Status** | The Pi's current local time with a sync badge (Synced, or Clock not set in red), each scheduled port's active pool and when the next step starts. Buttons: Set Clock, Advance to Next Step, Return to Automatic. |

On party night you don't need to touch the panel at all. Schedule Status is there to glance at the clock badge before guests arrive, and to push clues forward early if everyone is stuck.

**Network triggers** get two action types in addition to playing a file or pool: Advance Step and Return to Automatic, so a phone shortcut can nudge the clues without opening the panel.

## New: what happens on a trigger

Only one step is new: resolving a schedule to a pool. After that, the existing pool playback and mouth sync run unchanged.

1. **Existing:** the sensor fires and the global cooldown is checked.
2. **New, resolve the pool.** If the port's assignment is a pool, use it. If it's a schedule:
   1. If a manual override step is set, use that step.
   2. If the Pi's clock isn't synced, use the first step.
   3. If the schedule has an Active date and tonight isn't that party night, use the first step.
   4. Otherwise, convert the current local time to minutes into the party night (times before the rollover hour add 24 hours), and use the last step whose start time has passed. Before any step has started, use the first step.
3. **New, handle a step change.** If the resolved pool differs from the last one this port played, reset that pool's position. For an In order pool, start at the first file not in the previous pool, so the next press gives the new clue instead of replaying old ones. For a Shuffle pool, start a fresh shuffle.
4. **Existing:** pick the next file from the pool by its play order, play it with its timestamps, and start the cooldown.

Playback position is kept per pool, so if both ports ever point at the same schedule, they share one sequence of clues.

## New: local time and keeping the clock right

Schedules run from the Pi's local time, so the whole feature depends on that clock being right. The Pi has no battery-backed clock: it gets the time from the internet over WiFi (NTP) after it boots. On Homenet1 that normally takes a few seconds.

| Situation | What the prop does |
| --- | --- |
| Booted with internet, NTP synced | Runs the schedule normally; badge shows Synced |
| No internet, clock set by hand | Runs the schedule normally; badge shows Set manually |
| No internet, clock not set | Plays the first step only and shows Clock not set in red, so a wrong clock can't jump to the final clue |
| Sync or manual set arrives later | Switches to the correct step on the next trigger |
| Reboot mid-party with internet | Comes back at the right step once NTP syncs; nothing to do |
| Reboot mid-party without internet | Back to Clock not set; set the clock again (see below) |

**Setting the clock by hand.** For a venue without internet, connect your phone to the GhostHostAP network, open the control panel, and use **Set Clock** on Schedule Status. It offers two ways:

1. **Use this phone's time** (one tap). The page sends the phone's current time to the Pi. It's accurate to within a second or two, since the phone gets its time from the cell network.
2. **Enter a time.** A date and time field for when there's no phone time to borrow.

On the Pi, the endpoint sets the system clock (for example `date -s @<epoch seconds>`, which needs a sudoers entry for the web app's user) and marks the clock as manually set until the next reboot. NTP stays enabled, so if the prop later reaches the internet, NTP takes over and the badge changes to Synced.

A manually set clock doesn't survive a power cycle, because the Pi has nowhere to keep time while it's off. For venue work, a DS3231 real-time clock module removes that step: set it once, and the Pi reads the correct time from it at every boot.

**Checking sync.** On Raspberry Pi OS, `timedatectl show -p NTPSynchronized` returns yes once the time is trustworthy. Set the timezone to America/New\_York so step times read as local time. Without an internet connection the Pi can't use NTP; see Setting the clock by hand above.

**Daylight saving.** Clocks fall back at 2:00 AM on Sunday, November 1, 2026, the morning after Halloween. Use the system timezone (not a fixed offset) and avoid steps between 1:00 and 2:00 AM that night, since that hour happens twice.

**Override.** Advance to Next Step is saved to the settings file so it survives a reboot. It clears itself at the next rollover hour, so it never carries into the next day.

**Status endpoint.** A small JSON status (local time, sync state, active step and pool per port, next change) feeds the Schedule Status panel and lets you check it from a phone.

## Edge cases and tests

- **Step changes mid-clip.** The playing clip finishes; the new pool applies on the next trigger.
- **Pool deleted while a schedule uses it.** Block the delete and name the schedule that uses it.
- **File in a pool has no timestamps.** Show a warning on the Schedules section, the same way pools note it today.
- **Before the first step's time.** The first step plays, so the port is never silent in the afternoon.
- **Two steps at the same time.** Refuse the save and highlight both rows.

Test with a hidden **Test time** field on Schedule Status: when set, the schedule uses that local time and date instead of the real clock, and the badge shows TEST in place of Synced. Clearing it returns to real time.

- [ ] Right port on Curse Clues, test time 6:45 PM on Oct 31: presses play Clues 1 in order and loop.
- [ ] Test time 8:31 PM: the next press plays the first new Clues 2 file.
- [ ] Test time 12:15 AM on Nov 1: still treated as Halloween night, stays on Clues 3.
- [ ] Test time 9:45 PM on Oct 24 with Active date Oct 31: stays on Clues 1.
- [ ] Advance to Next Step jumps ahead; it clears itself after 6:00 AM.
- [ ] Boot with WiFi off: badge shows Clock not set and only Clues 1 plays; turn WiFi on and the correct step returns.
- [ ] Left port on the Entry pool still shuffles exactly as before.
- [ ] On GhostHostAP with no internet, Use this phone's time sets the clock; badge shows Set manually and the schedule follows it.
- [ ] Enter a time by hand; the active step matches that time.
- [ ] Reboot without internet: badge returns to Clock not set and only the first step plays until the clock is set again.

Open questions:

- The global cooldown suits the pressure pad but may feel slow for the clue button. Should each port get its own cooldown?
- Should the Entry pool weight the curse clip so it plays more often than flavor lines, or is shuffle fine?
- Is the clue button wired to one of the existing Left or Right ports, or does it need a third input?
