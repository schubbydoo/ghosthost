# Sensor Ports (PIR) — Wiring and Testing

Verified 2026-10-18 on the Nosferatu prop's PIR board (marked **QY1702**) plugged into the
**left** sensor port.

## Jack pinout (3.5mm stereo TRS)

| Plug contact | PIR wire | Board pad | Function |
|---|---|---|---|
| **Tip** | white | `+` | Power (3.3V on this prop) |
| **Ring** | blue | `OUT` | Signal — idles LOW, pulses HIGH on motion |
| **Sleeve** | green | `-` | Ground |

Same convention as the SFX box sensor jacks (J3–J5): Tip = power, Ring = signal, Sleeve = GND.
A sensor from either project plugs into the other's port as far as pinout goes. The supply
voltage and signal handling differ — see the comparison below.

## Port to GPIO

| Port | GPIO (BCM) | Internal pull | Empty-port reading |
|---|---|---|---|
| `sensor_port_left` | 9 | pull-down | 0 |
| `sensor_port_right` | 25 | pull-up | 1 |

`src/hardware/sensor_manager.py` fires a performance on a **rising edge (LOW → HIGH)**, then
applies debounce and `sensors.cooldown_period`.

The PIR output is brief: waving produced HIGH pulses well under a second, sometimes several in a
row. The cooldown absorbs the repeats.

## Testing a port

`tools/sensor_test.py` prints the starting level of both ports, then every level change:

```
python3 -u tools/sensor_test.py      # on the Pi; Ctrl+C to stop
```

It can run while the service is running. Each port should read as in the table above when
nothing is plugged in. With the PIR plugged in and idle, the left port should read 0. Waving
should show `0 -> 1 -> 0`.

Plugging in or wiggling a plug can bounce the line and trigger a performance. That is expected
and is not a PIR reading.

## What went wrong the first time (so you can skip it)

The left port read **1 permanently** with the PIR plugged in, and waving changed nothing. It
looked like a dead sensor. It was a wiring problem: after the plug was rewired to match the
pinout above, the port idled at 0 and responded to motion. I did not record which wires were
wrong before the fix, but a stuck-HIGH signal line is the classic sign of the supply reaching
Ring, from Tip and Ring swapped or a plug not fully seated.

Diagnosis, in order:

1. **Unplug the PIR.** The left port should read 0 (pull-down). If it still reads 1, the problem
   is the port or the jack wiring, not the PIR.
2. **Read Ring (blue / OUT) against Sleeve with a meter,** powered and idle. It should be ~0V.
   Reading the same as Tip means the supply is on the signal line.
3. **Read Tip (white / +) against Sleeve.** Should be a steady 3.3V. 0V means no power and
   nothing else will work.
4. **Never put more than 3.3V on a signal line.** GPIO pins on the Pi are not 5V tolerant, and
   this port has no level shifter (see below).

The QY1702 board has no delay pot, no sensitivity pot and no retrigger jumper, so there is
nothing to tune on it.

## Comparison with the SFX box sensor ports

Source: `~/SFX box/sfx-box-wiring.md` (v0.9) and `sfx-box-harness.md`.

| | Ghost Host | SFX box (J3–J5) |
|---|---|---|
| Jack | 3.5mm TRS | 3.5mm TRS |
| Pinout | Tip = +, Ring = OUT, Sleeve = GND | Same |
| Tip voltage | 3.3V (per bench check) | 5V (4.9V measured) |
| Signal path | Ring straight to GPIO (as far as I know) | Ring → 1K → MMBT3904 transistor → GPIO, via a plug-in daughter board |
| Level shifting | None known; the PIR must output 3.3V | Yes: any 0–5V sensor output is safe |
| Polarity | Active-high, rising edge fires | **Inverted** by the transistor: motion = GPIO LOW, ports set active-low in the web UI |
| Internal pull | Left pull-down, right pull-up (inconsistent) | Pull-up on all three |
| Hot-plug protection | None known | 22Ω on the 5V feed |
| GPIOs | 9, 25 | 17, 27, 22 |

So the **pinout is the same, but the electrical design is not**. The SFX box was built to accept
nearly any sensor; the Ghost Host port is a direct connection and only suits a 3.3V sensor.

Notes:
- Plugging a Ghost Host PIR into an SFX box port works electrically (5V on Tip is fine for most
  PIR boards, but check the QY1702 supply rating first). Set the port **active-low** in the SFX
  web UI.
- Plugging an SFX box sensor that outputs 5V into the Ghost Host would put 5V on a GPIO. Don't.
- The SFX box doc has the same diagnosis for a stuck-HIGH line: a Ring reading of 5V means Tip's
  supply is reaching the signal line, from a plug not fully seated or Tip and Ring swapped.
- The SFX box also had a first sensor that was faulty and held the line active. Its self-test
  was shorting Ring to Tip (never Tip to Sleeve).
  **That self-test does not apply here.** The Ghost Host port has no 1K series resistor, so
  shorting Ring to Tip would put the 3.3V supply straight onto a GPIO. Don't use it here.

## Open items

- Whether the Ghost Host side has any series resistor or protection between Ring and the GPIO
  has not been checked. The table above says "none known" because nothing in this repo records
  it.
- The right port has not been tested with a real sensor. It uses a pull-up, so it idles HIGH and
  a sensor on it would not fire on its first edge the same way. Revisit if a second PIR is added.
