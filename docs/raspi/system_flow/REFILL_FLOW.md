# REFILL_LOGIC.md
> Water Refill State Machine — `_refill_it()` in `process_b.py`
> Evaluated every **100ms**. GPIO 27 relay reflects `refill_active` each tick.

---

```mermaid
flowchart TD

    TICK(["⏱ Loop tick\n100ms"])

    TICK --> CHECK_ACTIVE{refill_active?}

    %% ─── IDLE BRANCH ──────────────────────────────────────────────────────
    CHECK_ACTIVE -- "NO\n(IDLE)" --> CHECK_BUTTON{water_button_pressed?}

    CHECK_BUTTON -- YES --> CHECK_NOT_FULL{water_level\n< 95%?}
    CHECK_NOT_FULL -- NO  --> RELAY_OFF["GPIO 27 → OFF\n💧 Motor OFF\n⛔ tank already full\nno relay pulse, no analytics"]
    CHECK_NOT_FULL -- YES --> START_MANUAL["refill_active = True\n🔘 source: manual\n(app button OR physical keypad '#')"]

    CHECK_BUTTON -- NO  --> CHECK_AUTO{auto_refill\nenabled?}
    CHECK_AUTO -- NO  --> RELAY_OFF
    CHECK_AUTO -- YES --> CHECK_THRESHOLD{water_level ≤\nthreshold?}
    CHECK_THRESHOLD -- NO  --> RELAY_OFF
    CHECK_THRESHOLD -- YES --> SNAPSHOT_AUTO["📸 Snapshot water_level_before_refill\n= current_water_level\n(auto path — no button, so\nsnapshot must happen here)"]
    SNAPSHOT_AUTO --> START_AUTO["refill_active = True\n⚙️ source: auto-refill"]

    %% ─── ACTIVE BRANCH ────────────────────────────────────────────────────
    CHECK_ACTIVE -- "YES\n(REFILLING)" --> CHECK_FULL{water_level ≥\n95%?}

    CHECK_FULL -- NO  --> RELAY_ON["GPIO 27 → ON\n💧 Motor ON\n⚠️ button state IGNORED\n(latch — no flicker)"]
    CHECK_FULL -- YES --> STOP["refill_active = False\n✅ Tank full"]

    %% ─── CONVERGE ─────────────────────────────────────────────────────────
    START_MANUAL --> CHECK_FULL
    START_AUTO   --> CHECK_FULL
    STOP         --> RELAY_OFF

    RELAY_ON  --> ANALYTICS_CHECK
    RELAY_OFF --> ANALYTICS_CHECK

    ANALYTICS_CHECK{"prev_refill_active=True\nAND refill_active=False?"}
    ANALYTICS_CHECK -- YES --> WRITE_ANALYTICS["📊 Push analytics entry\nanalytics/logs/{userUid}\nvolume = water_now − water_before_refill"]
    ANALYTICS_CHECK -- NO  --> NEXT_TICK

    WRITE_ANALYTICS --> NEXT_TICK(["⏱ Next tick"])
```

---

## Snapshot Timing — Manual vs Auto

```mermaid
flowchart TD

    subgraph MANUAL ["Manual button path"]
        M1["water_button_pressed = True\nAND refill_active = False"]
        M1 --> M2["📸 Snapshot BEFORE _refill_it\nwater_level_before_refill = current_water_level"]
        M2 --> M3["_refill_it → refill_active = True"]
        M3 --> M4["Refill runs...\nstops at 95%"]
        M4 --> M5["📊 analytics: water_now − snapshot\n✅ correct volume"]
    end

    subgraph AUTO ["Auto-refill path"]
        A1["water_button_pressed = False\nauto_refill = ON\nwater_level ≤ threshold"]
        A1 --> A2["📸 Snapshot BEFORE _refill_it\nwater_level_before_refill = current_water_level\n⚠️ must happen here — no button event to trigger it"]
        A2 --> A3["_refill_it → refill_active = True"]
        A3 --> A4["Refill runs...\nstops at 95%"]
        A4 --> A5["📊 analytics: water_now − snapshot\n✅ correct volume"]
    end

    subgraph BAD ["❌ Old bug (fixed)"]
        B1["Auto-refill starts"]
        B1 --> B2["No snapshot taken\nwater_level_before_refill = 0.0"]
        B2 --> B3["📊 analytics: water_now − 0.0\n❌ wrong volume"]
    end
```

---

## Button Press Sources

`water_button_pressed` is True when **any** of these fire in the same tick:

```mermaid
flowchart TD

    A["water_button_pressed"] --> B["Physical keypad '#'"]
    A --> C["App button\n(water_app_new_press)"]

    C --> D{"raw_water_timestamp\n≠ last_acted_water_timestamp?"}
    D -- YES --> E["✅ Treat as new press\nAck: last_acted = raw_ts"]
    D -- NO  --> F["❌ Ignored\n(same timestamp, already acted on)\nPrevents 60s spam from is_fresh()"]
```

---

## Auto-Refill vs Manual — Side by Side

```mermaid
flowchart LR

    subgraph MANUAL ["Manual (button)"]
        M1["User presses '#' on keypad\nOR app button"] --> M2["water_button_pressed = True"]
        M2 --> M3{"water_level < 95%?"}
        M3 -- YES --> M4["refill_active = True\nregardless of threshold setting"]
        M3 -- NO  --> M5["❌ No-op\ntank already full"]
        M4 --> M6["Runs until water_level ≥ 95%"]
    end

    subgraph AUTO ["Auto-refill (settings enabled)"]
        A1["auto_refill = ON\nin app settings"] --> A2{"water_level ≤\nthreshold?"}
        A2 -- YES --> A3["refill_active = True\nautomatically"]
        A3 --> A4["Runs until water_level ≥ 95%"]
        A2 -- NO  --> A5["Stays IDLE"]
    end
```

---

## Key Constants & Thresholds

| Constant | Value | Meaning |
|---|---|---|
| `MAX_REFILL_LEVEL` | `95%` | Hard stop — refill always stops here. Also guards manual start. |
| `current_water_threshold_warning` | user setting | Auto-refill triggers at or below this. Keep ≤ 80% to avoid short-cycling. |
| `is_fresh` window | `60s` | How long app button timestamp stays "active" |
| Ack gate | per-timestamp | One press = one action, regardless of `is_fresh` window |
| Loop tick | `100ms` | How often `_refill_it()` is evaluated |

---

## What Was Fixed

| # | Bug | Fix |
|---|---|---|
| 1 | Manual button started pump even when tank was already at 95%+ — caused 1-tick relay pulse and a `volumePercent: 0` analytics entry | Added `current_water_level < MAX_REFILL_LEVEL` guard on manual start path |
| 2 | Auto-refill could short-cycle if `water_threshold_warning` was set close to 95% | No code change — app-side settings should cap threshold at ~80% |
| 3 | Auto-refill never took a `water_level_before_refill` snapshot — analytics always logged wrong volume (`water_now − 0.0`) | Added explicit snapshot block for the auto-refill path before `_refill_it()` runs |