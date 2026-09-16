# Energy ledger

A single-file daily energy balance tracker. Log what you ate, what you lifted, how far you
walked and what you did around the house, and it works out what came in, what your body spent
on each of those, and whether the difference is going on as fat or coming off.

Built around an Indian lacto-vegetarian diet and a push/pull/legs routine, but the food
database and exercise list cover plenty beyond that.

**One file. No build step, no dependencies, no server.** Open `index.html` in a browser.

## What makes it different

Most calorie apps give you a number and hide the reasoning. This one shows every step:
the Mifflin–St Jeor equation with your figures substituted in, each food as quantity ×
kcal per unit, each activity's MET arithmetic, and every rep as mass × 9.81 × distance.
Press **Show every step** to see the whole derivation.

It also refuses to guess. Nothing is estimated until you have entered your height, weight,
age and sex, because resting metabolism is the single largest number in the day and it is
built entirely from those four.

## Features

- **Around 45 foods** with per-unit calories and macros, including both cow and buffalo ghee,
  chapati, curd, paneer, dal, and the usual dry fruits.
- **20 rep-based exercises** computed from mechanical work, not a lookup table. Body-weight
  and loaded reps are logged separately because they are not the same work.
- **Bands, isometric holds and conditioning**, plus walking, running and cycling by distance
  and pace.
- **15 household chores** — cooking, chapatis, utensils, sweeping, mopping, washing clothes,
  stairs. Real expenditure that most trackers throw away.
- **Surplus and deficit partitioning** into fat and lean tissue, with a physiological ceiling
  on how fast muscle can actually be built.
- **Local profiles** for several people on one device, with export and import.
- **Built for touch.** Steppers with 46px tap targets rather than sliders, and every value
  can be typed directly. Press and hold a button to run, accelerating after a moment.
  Collapsible sections, search across every food, exercise and chore, and a ledger that
  slides up as a sheet on phones. Two columns on iPad and desktop.

## The daily rhythm

Set up your body details once, build a typical day, and press **Save as my usual day**.

After that, opening the page loads your usual day already filled in. Change only what was
different — an extra chapati, a session skipped, a longer walk — and a panel at the top
reports each change, what it cost in calories, and how it moved the outcome:

> Against your usual day you took in +330 kcal and spent +196, so the balance moved +134 kcal,
> from +473 to +607. Body fat goes from storing 54 g a day to storing 72 g.

Today's log is saved under today's date, so tomorrow opens fresh from your usual day rather
than inheriting yesterday. **Back to my usual day** undoes the day's changes; **Make today my
new usual** promotes it if your routine has genuinely shifted. Ninety days of history are kept.

## Using it on a phone or tablet

Add it to your home screen (Share → Add to Home Screen on iOS) and it opens full-screen with
no browser chrome. Tap the summary bar at the bottom to pull up the full ledger.

Steppers were chosen over sliders deliberately: a 3,000 ml slider makes every pixel worth
about 10 ml, which is unusable with a thumb. Tap the number itself to type an exact value.

## How the model works

### Resting metabolism

Mifflin–St Jeor, the equation most commonly used in clinical practice:

```
male:    10 × kg + 6.25 × cm − 5 × age + 5
female:  10 × kg + 6.25 × cm − 5 × age − 161
```

On top sits a non-exercise multiplier (18–60% of resting rate) for the parts of your day you
did not log, and the thermic effect of food, which is 9–13% of intake depending on how much
of it is protein.

### Mechanical work in the gym

Each rep is `W = m g h`, where both terms are derived rather than assumed.

Three kinds of number go into this, and the app labels them separately under
**The arithmetic → The physics, precisely**:

**Exact.** `W = ∫F·ds`, which against constant gravity reduces to `mgh`. Over a rep that
returns to its start at rest, `ΔKE = ΔPE = 0`, so net mechanical work is exactly zero
regardless of tempo — tempo changes peak force, not total work. An isometric hold has
`ds = 0` and does exactly zero work. One kilocalorie is 4184 J by definition.

**Measured, with error bars.** Muscular efficiency ≈ 20% (literature range 18–26%).
Eccentric cost ≈ 1/3 of concentric (reported 1/5 to 1/2). A MET is 3.5 ml O₂/kg/min and a
litre of O₂ yields 4.69 kcal on fat, 5.05 on carbohydrate — so `MET × 3.5 × kg / 200`
carries ±4% from fuel mix alone, before anything else.

**Assumed.** Splitting a session into mechanical work plus a 2.6–4.0 MET postural rate,
rather than using the tables' single 5.0 MET for resistance training, avoids double-counting
but is a modelling choice. Segment fractions are population averages. Effective-mass
fractions treat the body as rigid links. Internal work — swinging an unloaded limb — is
ignored entirely.

The practical consequence: work terms are good to a few percent, the work-to-calories
conversion to about a fifth, and the postural terms are both the loosest and the largest.
Comparing your days is far more reliable than trusting any single day's total.

Limb lengths come from standing height using Drillis & Contini segment fractions:

| Segment | Fraction of height |
|---|---|
| Shoulder to wrist | 0.332 |
| Thigh | 0.245 |
| Forearm | 0.146 |
| Shoulder height | 0.818 |
| Centre of mass height | 0.570 |

Travel distance follows from those. A push-up is the instructive case: the body is a rigid
lever turning about the **toe**, so every landmark rises in proportion to its distance from
that pivot. Those distances are standing heights *plus* the ankle-to-toe offset of the
plantar-flexed foot (~0.11 H) — measuring from the sole instead puts the pivot in the wrong
place and understates the work by about 5%. Centre of mass therefore rises `0.680/0.928` of
the shoulder travel, and a plate on the upper back travels 1.26× further than the centre of
mass, so it gets its own term.

Metabolic cost is then:

```
lifting  = W / 0.20                      (muscular efficiency ≈ 20%)
lowering = W × 0.33 / 0.20               (eccentric ≈ a third of concentric)
session  = (MET − 1) × 3.5 × kg / 200 × minutes
total    = (lifting + lowering + session) × 1.06   (afterburn)
```

Lowering does *negative* mechanical work — gravity moves the load, muscle only resists — so
it adds no work but still costs energy. How much depends on tempo, which is a setting.

The honest result of all this: the load you use barely moves the total. Thirty kilos added to
26 push-ups is about 5 kcal. Time under way dominates. Weight is for growth, not for burn.

### Everything else

Timed activities use `(MET − 1) × 3.5 × kg / 200` kcal per minute, with MET values from the
Compendium of Physical Activities. Stair climbing skips MET and uses `m g h` directly at ~23%
efficiency, plus a third again for the descent, because climbing is genuine lifting.

### Where the difference goes

A kilo of body fat holds about 7,700 kcal. Muscle holds only about 1,800 but costs roughly
5,000 to build, since protein synthesis burns energy itself. That asymmetry means a surplus
and a deficit are not mirror images.

**Surplus.** A fraction is routed to muscle based on training experience, protein intake,
sleep and whether you lifted that day — then capped at a physiological ceiling (25 g/day for
beginners, 13 intermediate, 6 advanced). Anything above the ceiling has nowhere to go but fat.

**Deficit.** Split by *mass*, not by energy. Lean tissue carries roughly a quarter the energy
per kilo that fat does, so an energy split wildly overstates muscle loss.

## Accuracy

These are population averages fitted to your measurements. Resting metabolic rate varies by
roughly ±200 kcal between people of identical size. Food values assume typical home portions.
MET tables describe averages, not you.

Use it as a starting hypothesis. Weigh yourself under the same conditions each morning for two
or three weeks, and where the scale disagrees with the prediction, the scale is right.

## Privacy

No server, no account, no analytics, no network request except the web font — and the page
works without it. Every visitor's data lives only in their own browser: yours never sees it,
and theirs never sees anyone else's.

The limits worth stating plainly:

- **It does not follow people between devices.** A profile saved on a phone is not on the laptop.
- **Clearing site data deletes it.** So does private/incognito browsing.
- **iOS Safari deletes it after 7 days of not visiting.** Apple's tracking prevention evicts
  script-writable storage on that schedule. Adding the page to the home screen avoids this,
  and so does visiting weekly. This is the single biggest reason to use **Export**.
- **It is not authentication.** Anyone at that browser can open any profile on it.

## Publishing it

Push `index.html`, `README.md` and `LICENSE` to a repository, then enable Pages under
**Settings → Pages → Source: Deploy from a branch**, pick `main` and `/ (root)`. The site is
live at `https://<user>.github.io/<repo>/` in a minute or two. Nothing needs building.

For a custom domain, add a `CNAME` file containing just the hostname (one line, no protocol),
put the same hostname in Settings → Pages → Custom domain, and add a DNS record at your
registrar:

| Type | Name | Value |
|---|---|---|
| CNAME | `ledger` | `<user>.github.io.` |

Then tick **Enforce HTTPS** once the certificate is issued, which usually takes a few minutes.

**Choose the final URL before sharing it.** Browser storage is bound to the exact origin, so
moving the page from `<user>.github.io` to your own domain later leaves every visitor's saved
profiles behind at the old address. They are not lost, but they are only reachable by visiting
the old URL and exporting.

To work fully offline, delete the two `<link>` tags for Google Fonts. The page falls back to
Georgia and your system sans, and nothing else changes.

## Disclaimer

An estimation tool, not medical or dietary advice. It cannot account for medication, thyroid
or metabolic conditions, pregnancy, injury, or the many other reasons a real body departs from
a population average. Talk to a doctor or a registered dietitian before making large changes
to how you eat or train. Not designed for anyone under 18, and not to be used to drive weight
loss in anyone with a history of disordered eating.

## Licence

MIT. See `LICENSE`.
