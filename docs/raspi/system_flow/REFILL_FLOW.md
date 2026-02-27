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

    CHECK_BUTTON -- YES --> START_MANUAL["refill_active = True\n🔘 source: manual\n(app button OR physical keypad '#')"]
    CHECK_BUTTON -- NO  --> CHECK_AUTO{auto_refill\nenabled?}

    CHECK_AUTO -- NO  --> RELAY_OFF["GPIO 27 → OFF\n💧 Motor OFF"]
    CHECK_AUTO -- YES --> CHECK_LEVEL{water_level ≤\nthreshold?}

    CHECK_LEVEL -- NO  --> RELAY_OFF
    CHECK_LEVEL -- YES --> START_AUTO["refill_active = True\n⚙️ source: auto-refill"]

    %% ─── ACTIVE BRANCH ────────────────────────────────────────────────────
    CHECK_ACTIVE -- "YES\n(REFILLING)" --> CHECK_FULL{water_level ≥\n95%?}

    CHECK_FULL -- NO  --> RELAY_ON["GPIO 27 → ON\n💧 Motor ON\n⚠️ button state IGNORED\n(latch — no flicker)"]
    CHECK_FULL -- YES --> STOP["refill_active = False\n✅ Tank full"]

    %% ─── CONVERGE ─────────────────────────────────────────────────────────
    START_MANUAL --> CHECK_FULL
    START_AUTO   --> CHECK_FULL
    STOP         --> RELAY_OFF

    RELAY_ON  --> LOG_ANALYTICS
    RELAY_OFF --> LOG_ANALYTICS

    LOG_ANALYTICS{"prev_refill_active=True\nAND refill_active=False?"}
    LOG_ANALYTICS -- YES --> WRITE_ANALYTICS["📊 Push analytics entry\nanalytics/logs/{userUid}\nvolume = water_now − water_before"]
    LOG_ANALYTICS -- NO  --> NEXT_TICK

    WRITE_ANALYTICS --> NEXT_TICK(["⏱ Next tick"])
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
        M2 --> M3["refill_active = True\nregardless of level"]
        M3 --> M4["Runs until\nwater_level ≥ 95%"]
    end

    subgraph AUTO ["Auto-refill (settings enabled)"]
        A1["auto_refill = ON\nin app settings"] --> A2{"water_level ≤\nthreshold?"}
        A2 -- YES --> A3["refill_active = True\nautomatically"]
        A3 --> A4["Runs until\nwater_level ≥ 95%"]
        A2 -- NO  --> A5["Stays IDLE"]
    end
```

---

## Key Constants

| Constant | Value | Meaning |
|---|---|---|
| `MAX_REFILL_LEVEL` | `95%` | Hard stop — refill always stops here |
| `current_water_threshold_warning` | user setting | Auto-refill triggers at or below this level |
| `is_fresh` window | `60s` | How long app button timestamp stays "active" |
| Loop tick | `100ms` | How often `_refill_it()` is evaluated |