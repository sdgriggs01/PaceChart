# Track Mode — Implementation Plan

## Context

PaceChart currently supports only cross-country: it scrapes `xc.greenhopetrackxc.com`,
converts every selected result to a 5000m-equivalent time, and generates training
paces from that. The coach also wants the same tool usable during the outdoor
track season, using **1600m and 3200m** (the standard track distance-squad
anchor events, plus any other 1600m+ event the site posts, e.g. a rare 3000m)
as the input, instead of a 5k XC race.

Four decisions from the repo owner constrain this plan and are treated as fixed:

1. **Reference distance**: any track result of **1600m/mile or longer** is
   converted to a **3000m-equivalent** time via the calculator's existing
   `equivalent_performances(...)["3000m"]` — the same function already used
   for XC's 5000m conversion, just reading a different table key. Results
   shorter than 1600m (sprints, hurdles, jumps, throws) are out of scope.
2. **Scope of this task**: plan only. No code, no stub modules.
3. **Roster separation**: Track mode scrapes its own roster/schedule/results
   from `track.greenhopetrackxc.com`, fully independent of XC data. No
   merging of one athlete's XC and track results.
4. The app ends up with two modes — XC (existing, unchanged) and Track (new)
   — selected via a mode toggle in the GUI, whose concrete shape this plan
   proposes.

No changes to `calculator.py` are needed anywhere in this plan — see
"Calculator reuse" below.

## Track site structure (verified against the live site, 2026-08-19)

All URLs below were fetched directly (`curl` with a browser User-Agent,
matching the existing scraper's `DEFAULT_HEADERS`; both sites 200'd with it).
`track.greenhopetrackxc.com` is the **same CMS/template family** as the XC
site — same Bootstrap classes, same footer copyright — but the meet-results
page template differs meaningfully from the XC one (details below), so it is
not a drop-in reparameterization of `scraper.py`'s results parsing.

### Roster page — identical structure to XC

`https://track.greenhopetrackxc.com/index.php/athletes/roster` — fetched, 200.
Same shape as `xc.greenhopetrackxc.com`'s roster: `<div class="tab-pane" id="boys">`
/ `id="girls"`, each containing `<h4 class="title-divider">` headings per
class year followed by a `<table class="table table-condensed">` of
`<a href=".../athletes/view/ID">Last, First</a>` rows. Example observed:

```html
<div class="tab-pane" id="boys">
  <h4 class="title-divider"><span>Seniors</span><br/><small>Class of 2026</small></h4>
  <table class="table table-condensed">
    ...
    <td><a href="https://track.greenhopetrackxc.com/index.php/athletes/view/12514">Gabriel Cardenas</a></td>
```

`scraper.py`'s `parse_roster` logic (find `#boys`/`#girls`, then
`h4.title-divider` → next `table` → rows with an `athletes/view/(\d+)` link)
applies **unchanged**, just against a different base URL and a disjoint set
of athlete IDs (track roster IDs are the site's own numbering, not
guaranteed to line up with XC roster IDs for the same person).

### Schedule page — identical structure to XC

`https://track.greenhopetrackxc.com/index.php/schedule/view` — fetched, 200.
Same single `<table>`, one row per meet, columns Day/Date/Time/Meet/Location/
Boys-link/Girls-link. Example row (2026 outdoor season, confirmed already
posted as of 2026-08-19):

```html
<td>Thursday</td>
<td>03/05/26</td>
<td>03:30 PM</td>
<td>Battle for 55 Dual</td>
<td>Panther Creek HS. Cary NC</td>
<td><a href="https://track.greenhopetrackxc.com/index.php/meet/view/1306/M">Boys</a></td>
<td><a href="https://track.greenhopetrackxc.com/index.php/meet/view/1306/F">Girls</a></td>
```

The full 2026 outdoor schedule (17 meets, 03/05/26 through 06/11/26,
including "Patriots Invitational", conference/regional/state championships,
and New Balance Nationals) parses cleanly with `parse_schedule`'s existing
`%m/%d/%y` date format and `cells[5]`/`cells[6]` link-cell logic — **unchanged**.
One naming difference to note: result-link URLs are `/meet/view/{id}/M` or
`/F` (vs. XC's own per-meet URL scheme) — irrelevant to parsing since the
code always follows whatever `href` is present, but worth documenting since
it confirms track meet IDs (`1306`, `1307`, ...) are a separate numbering
space from XC meet IDs.

### Meet results page — DIFFERENT structure from XC

This is where a track scraper cannot just reuse `scraper.py`'s results
parsing. Fetched and inspected three 2026 meets across different meet types:

- `https://track.greenhopetrackxc.com/index.php/meet/view/1306/M` — "Battle
  for 55 Dual" (dual meet)
- `https://track.greenhopetrackxc.com/index.php/meet/view/1308/M` — "Patriots
  Invitational" (invitational)
- `https://track.greenhopetrackxc.com/index.php/meet/view/1320/M` and `/F` —
  "Quad City 7 Conference Championships" (championship meet, both genders)

Findings, consistent across all three meet types and both genders:

**1. Heat headings are plain `<h4>`, not `<h4 class="title">`.** Example, verbatim:

```html
<h4>1600m Run</h4>
    <table class="table table-striped table-condensed table-bordered">
        <tbody>
            <tr>
                <td align="right">1</td>
                <td align="right">5:03.79</td>
                <td><a href="https://track.greenhopetrackxc.com/index.php/athletes/view/12655">
                    Graham Severson</a>
                    <small>(Green Hope)</small>
                </td>
            </tr>
```

Full list of `<h4>` event headings seen across the three meets: `Long Jump`,
`Triple Jump`, `High Jump`, `Pole Vault`, `Discus`, `Shot Put`, `100m Dash`,
`200m Dash`, `400m Dash`, `800m Run`, `1600m Run`, `3200m Run`, `110m Hurdles`,
`300m Hurdles`, `4x100m Relay`, `4x200m Relay`, `4x400m Relay`,
`4x800m Relay`. Naming pattern for running events is `"{distance}m {Dash|Run|Hurdles}"`
— sprints/hurdles use "Dash"/"Hurdles", the two events we care about
("800m Run", "1600m Run", "3200m Run") use "Run". No event was ever labeled
"Mile" or "1600 Meter Run" — it is consistently the bare `NNNNm Run` form. No
"3000m" event was observed in any of the three meets checked, but the site's
own event catalog can't be assumed exhaustive from three samples — the
detection rule below should not hardcode only 1600/3200.

**2. There is no `<thead>`/`<th>` anywhere on the results page**, and no team-scoring
table (checked: no `Pts`, `Score`, or `<th>` text found in any of the three
fetched pages). Every results table is exactly:

```html
<table class="table table-striped table-condensed table-bordered">
    <tbody>
        <tr>
            <td align="right">{place}</td>
            <td align="right">{time or field mark}</td>
            <td>{athlete link (+ team name in <small>)}</td>
        </tr>
        ...
```

i.e. **3 columns (Place, Time, Runner)**, not XC's 4 (Pos, Pts, Time,
Runner). This means:
- `_find_results_table`'s XC strategy (find a `<thead>` containing "Runner")
  **does not work on the track site** — there is no thead to find. The
  correct strategy here is structural adjacency: each `<h4>` is immediately
  followed by exactly one results `<table>` before the next `<h4>` (both
  observed nested inside `<div class="col-md-4">` group wrappers) — take
  `heading.find_next_sibling("table")` (or `find_next("table")`, since no
  other tag intervenes) rather than searching by header text.
- Column indices differ from XC: cell 0 = place, cell 1 = time, cell 2 =
  runner (XC's `_parse_time_to_seconds` on `cells[2]` / runner-link on
  `cells[3]` must become `cells[1]` / `cells[2]` for track).
- Time format observed: `5:03.79`, `4:43.06` (M:SS.hh) for 1600m/3200m —
  same `_parse_time_to_seconds` logic (split on `:`) works unchanged.

**3. Both boys and girls run 1600m and 3200m at every meet type checked**
(dual, invitational, conference championship) — event list did not vary by
gender. (Not independently confirmed for the regional/state meets or the
early-season non-conference invitationals, since only these three were
fetched, but no gender asymmetry appeared in any sample.)

**4. Relay entries are a real misdetection risk and must be explicitly
excluded**, not just relied on to fall outside a distance filter by luck.
Example, verbatim, from `4x200m Relay`:

```html
<td><a href="https://track.greenhopetrackxc.com/index.php/athletes/view/12970">
    Green Hope 'A'</a>
    <br/><small><small>1</small>&nbsp;<a href=".../athletes/view/12819">Everett&nbsp;Bruce</a></small>
    <br/><small><small>2</small>&nbsp;<a href=".../athletes/view/12703">Rohan&nbsp;Bhavsar</a></small>
    ...
```

The first `<a>` in a relay's "Runner" cell links to a synthetic team-entry ID
(`12970`, "Green Hope 'A'"), not an individual athlete, followed by real
per-leg athlete links inside nested `<small>` tags. If a distance parser
naively regexes the heading text for `\d+` before `m`, `4x800m Relay` would
extract `800` (matching mid-distance leg count, not the whole event) — safe
in this case only because 800 < 1600, but a hypothetical `4x1600m Relay` /
distance-medley-style event would extract `1600` and pass the 1600m+ filter,
producing a fabricated "individual" result out of a team time attributed to
a non-athlete ID. **The detection rule must exclude any heading containing
"Relay" outright**, regardless of what distance the regex would extract —
see next section.

## Distance detection / filtering logic

Given the real label formats above (`"{distance}m {Dash|Run|Hurdles}"` for
track running events, no "K"/kilometer notation used anywhere), track mode
needs a **new** regex, distinct from XC's `_DISTANCE_RE = r"([\d.]+)\s*K"`:

```python
_TRACK_DISTANCE_RE = re.compile(r"^(\d+)\s*m\s+Run\b", re.IGNORECASE)
```

Proposed rule per `<h4>` heading, in order:

1. Reject outright if the heading text contains `"relay"` (case-insensitive)
   — regardless of any distance the text might otherwise appear to contain.
   This is a hard exclusion, checked before distance extraction, per the
   relay risk above.
2. Match `_TRACK_DISTANCE_RE` anchored at the start of the heading text.
   Anchoring to `^` and requiring `\s+Run\b` (not just any `m`) means "800m
   Run" is correctly matched-but-then-filtered-by-distance, while "100m
   Dash" and "300m Hurdles" never match at all — belt-and-suspenders beyond
   just the distance threshold, since it also guards against a differently
   labeled future field/throw event that happens to contain a 4-digit
   number followed by "m" somewhere later in the string (e.g. a meet/venue
   name).
3. If matched, parse the captured group as meters, divide by 1000 for km.
   Keep the heat only if `distance_km >= 1.6` (mirrors the XC threshold
   concept, just at the 1600m cut rather than "any XC race distance").
4. Everything else (field events, sprints <1600m, hurdles) is skipped — same
   "heat produced no distance match → skip" pattern `parse_meet_results`
   already uses for XC's `_DISTANCE_RE`.

This naturally captures "1600m Run" → 1.6 km and "3200m Run" → 3.2 km from
the observed data, and would also capture a hypothetical future "3000m Run"
or "5000m Run" heat without code changes, consistent with the reference
distance being determined dynamically (not hardcoded to exactly two
distances).

## Calculator reuse

**No changes to `calculator.py`.** `equivalent_performances(perf)` already
returns a `"3000m"` key (multiplier 1.0 — 3000m is the model's internal
anchor distance, per `Calculator-Methodology.md` §6) for any input
`Performance`, and `training_paces(perf)` is already distance-agnostic — it
only depends on `vo2_like(perf)`, which is derived from whatever
`Performance` it's given. Track mode needs a "3k-equivalent" instead of
"5k-equivalent" input, and both are just different keys read off the same
existing table.

The only new logic lives in `models.py`, mirroring the existing 5k helpers
exactly:

```python
def to_3k_equivalent_minutes(result: RaceResult) -> float:
    predicted = equivalent_performances(result.to_performance())
    return predicted["3000m"]

def average_3k_equivalent(athlete: Athlete) -> Performance | None:
    selected = athlete.selected_results()
    if not selected:
        return None
    converted_times = [to_3k_equivalent_minutes(r) for r in selected]
    avg_time_min = sum(converted_times) / len(converted_times)
    return Performance(distance_km=3.0, time_min=avg_time_min)
```

`training_paces()` is then called on this `Performance` exactly as
`app_state.calculate()` already does for the XC 5k case — no changes needed
there beyond picking which averaging function to call (see Architecture).

## Proposed architecture

New/changed files:

- **`src/pacechart/track_scraper.py`** (new, parallel to `scraper.py`).
  Reuses `parse_roster` / `fetch_roster` and `parse_schedule` /
  `fetch_schedule` from `scraper.py` as-is (pass a different
  `ROSTER_URL`/`SCHEDULE_URL` — either by adding a `base_url` parameter to
  the existing functions, or by importing and calling them with track URLs;
  since the parsing logic is identical, prefer **parameterizing
  `scraper.py`'s existing functions with a `roster_url`/`schedule_url`
  argument** over copy-pasting them, to avoid duplicate logic that could
  drift). What track mode needs newly implemented:
  - `TRACK_ROSTER_URL = "https://track.greenhopetrackxc.com/index.php/athletes/roster"`
  - `TRACK_SCHEDULE_URL = "https://track.greenhopetrackxc.com/index.php/schedule/view"`
  - `_TRACK_DISTANCE_RE` and the relay-exclusion check (see above)
  - `_find_track_results_table(heading)`: `heading.find_next_sibling("table")`
    (or `find_next("table")`) instead of XC's thead-text search
  - `parse_track_meet_results(html, meet) -> list[tuple[int, RaceResult]]`:
    same outer loop shape as `parse_meet_results`, but iterating plain
    `<h4>` (not `<h4 class="title">`), applying the relay/distance filter
    above, and reading `cells[0]`=place, `cells[1]`=time, `cells[2]`=runner
    link (3-column layout, not XC's 4-column Pos/Pts/Time/Runner)
  - `fetch_track_meet_results(...)`: thin wrapper, same shape as
    `fetch_meet_results`
  - `attach_results` is generic over `Athlete`/`RaceResult` already — reuse
    unchanged.

- **`src/pacechart/models.py`**: add `to_3k_equivalent_minutes` and
  `average_3k_equivalent` as shown above, alongside the existing 5k
  versions (both kept — XC mode still needs its own).

- **`src/pacechart/app_state.py`**: `AppState` needs a mode concept.
  Proposed minimal shape: add a `Mode` enum (`XC`, `TRACK`) and a `mode:
  Mode` field on `AppState`, plus make `calculate()` branch on it:

  ```python
  class Mode(Enum):
      XC = "xc"
      TRACK = "track"

  def calculate(self) -> None:
      averager = average_5k_equivalent if self.mode is Mode.XC else average_3k_equivalent
      ...
          performance = averager(athlete)
  ```

  This is preferred over fully parallel `XcAppState`/`TrackAppState` classes
  because everything downstream of `computed_performance` (pace generation,
  enabled-pace selection, grouping, PDF layout) is **already** distance-
  agnostic — `training_paces()` doesn't care whether it was handed a 5k-
  equivalent or 3k-equivalent `Performance`, and the 11×9 zone/distance grid
  (Mile/1600m/.../200m — all sub-1600m training splits) is exactly the same
  target grid for both modes (a track athlete's training paces are still
  expressed as Mile/1600m/800m/etc. splits, same as an XC athlete's). The
  only things that differ by mode are (a) which scraper module/URLs to load
  from, (b) which averaging function to call, (c) minor label text (see GUI
  section). A single `AppState` with a `mode` field keeps all of that
  shared code shared and avoids duplicating `enable_all_paces`,
  `toggle_paces_for_*`, `sorted_enabled_paces`, `select_most_recent_all`,
  etc.
  - `AppState.athletes` / `AppState.scheduled_meets` hold whichever mode's
    data is currently loaded (loading track data replaces XC data in the
    same fields) — consistent with decision 3 (no merging): the two data
    sets are never held or averaged together, just never-simultaneously.
  - `meets_with_results_for` / `athletes_by_gender` etc. are unchanged;
    they already operate generically on whatever's loaded.

- **`src/pacechart/gui.py`**: the "Load" step needs to call
  `track_scraper.fetch_roster`/`fetch_schedule`/`fetch_track_meet_results`
  instead of `scraper`'s when in Track mode — see GUI section below.

- **`src/pacechart/pdf.py`**: no structural change expected — it already
  operates on `AppState`/`computed_paces` generically. The only candidate
  change is cosmetic: if the PDF or its filename/header should say "Track"
  vs. "XC" mode, `generate_pdf` would take the mode (or a label) to print in
  the header — worth deciding at implementation time, not load-bearing to
  the calculation.

## GUI/workflow changes

Design.md's workflow (steps 1-5) is unchanged in shape for either mode; the
new decision is *which site to load from* and *which reference distance/
zone label to display*. Proposed integration into the existing tab flow:

- Add a **mode toggle** (e.g. a segmented control or two radio buttons,
  "XC" / "Track") in `_build_controls()`, next to the existing Load button,
  since mode must be picked **before** Load (it determines which URLs to
  fetch). Changing the mode after data is already loaded should clear
  `athletes`/`scheduled_meets`/computed results (switching modes is
  effectively "start over" — consistent with decision 3, no cross-mode
  merging).
- Results grid tab (step 1, "Athletes × Meets" grid): **rows are keyed by
  (athlete, event distance), not just athlete, in track mode.** Meet columns
  stay as-is (same "one checkbox per meet" shape), but an athlete with
  results at more than one distance (e.g. both a 1600m and a 3200m across
  the season) gets one display row per distinct distance, e.g. "A. Lee
  (1600m)" and "A. Lee (3200m)" as separate rows, each with checkboxes only
  in the meet columns where that athlete has a result at that specific
  distance. This is a **display-only** grouping — `models.py`'s
  `Athlete`/`RaceResult` are unchanged (still one flat `results: list[RaceResult]`
  per athlete; `selected` still lives on the `RaceResult`); a new grouping
  helper (e.g. `AppState.track_grid_rows(gender) -> list[tuple[Athlete, float, list[RaceResult]]]`,
  grouping `athlete.results` by `distance_km`) produces the display rows for
  `gui.py` to render. "Select most recent" and Calc are unaffected: Calc still
  averages *all* of an athlete's selected results (across every display row)
  into one 3000m-equivalent `Performance`, so a coach who checks both a 1600m
  and a 3200m result for the same athlete gets both blended into that
  athlete's single output row, same as selecting two different meets does
  today. The distance used for a row's label comes from the same
  `_TRACK_DISTANCE_RE`-derived `distance_km` already stored on each
  `RaceResult` — no hardcoding to exactly "1600m or 3200m", so a rare third
  distance (e.g. a future 3000m heat) would get its own row automatically.
  A track athlete who only ran sprints/field events all season produces zero
  rows (nothing in `results` survived the scraper's distance filter), same
  effective outcome as an XC athlete with no results — no special-casing
  needed for that case.
- Paces tab (step 2) and template save/load: unchanged — the 11×9 zone/
  distance grid is identical for both modes (see Architecture rationale).
- Calc button (step 3-4): unchanged UI, dispatches to
  `average_3k_equivalent` instead of `average_5k_equivalent` per
  `AppState.mode`.
- Output tab / PDF (step 5): unchanged structurally; consider adding a
  small "Track" vs "XC" label in the PDF header/footer purely for coach
  clarity when printed side by side across a season.
- No track-specific "which events counted per meet" UI beyond what's
  already needed for the same-meet-multiple-events gap above — the existing
  per-result checkbox already lets the coach choose which specific results
  (now possibly including both a 1600m and 3200m from the same meet) get
  included in the average, once the multi-result-per-meet grid gap is
  resolved.

## Open questions — resolved

All items below were open in the first draft of this plan; each has now
been either decided (with the repo owner) or independently re-verified
against the live site. Nothing remains open.

- **Same-meet multiple-events gap — resolved, decision: split grid rows by
  (athlete, distance).** See "GUI/workflow changes" above: track mode's
  results grid shows one row per (athlete, event distance) rather than one
  row per athlete, so a 1600m result and a 3200m result at the same meet
  get independent checkboxes. Purely a display/grouping change — no
  `models.py` changes.
- **Distance regex generality — resolved, confirmed across 5 meets, not
  just the original 3.** Additionally fetched the 2026 NCHSAA 8A State
  Championships (`meet/view/1322`, both `/M` and `/F`) and an early-season
  non-conference meet, the "NC Runners Elite Tune Up" (`meet/view/1311/M`).
  Event headings at both remain the plain `"{distance}m Run"` form — e.g.
  `<h4>3200m Run</h4>` (state, boys), `<h4>1600m Run</h4>` (state, girls;
  also present at the tune-up meet). No "Mile Run" or other alternate
  label ever appeared. One incidental finding worth documenting: the state
  meet's boys page has no `1600m Run` heading and the girls page has no
  `3200m Run` heading — **meet results pages only include events where a
  Green Hope athlete actually has a result**, not every event on the
  meet's card (expected at a championship meet, where only qualifiers
  race). This needs no special-case handling — it's the same "heading not
  found → no result for that distance" behavior the parser already has for
  every other meet.
- **3000m steeplechase — resolved, decision: exclude by name, matching the
  original recommendation.** Still never observed, even after checking the
  state championship pages (the meet tier where it would most likely
  appear if run at all). Formalizing the earlier recommendation as a fixed
  rule: reject any `<h4>` heading containing "steeplechase"
  (case-insensitive), alongside the "relay" exclusion, in
  `_TRACK_DISTANCE_RE`'s pre-filter.
- **User-Agent / access requirements — resolved, confirmed.** Re-tested
  directly: `requests.get(...)` with `requests`' own default User-Agent
  against `track.greenhopetrackxc.com/index.php/schedule/view` returns
  **406**; the existing browser UA (`scraper.py`'s `DEFAULT_HEADERS`)
  returns 200. Same requirement as the XC site — `track_scraper.py` should
  reuse `_session_with_headers`/`DEFAULT_HEADERS` from `scraper.py` as-is
  rather than redefining them.
- **Track roster IDs vs XC roster IDs — not a question, just a documented
  fact.** Confirmed different numbering spaces per subdomain. Since
  decision 3 forbids merging anyway, this only matters as a reminder: track
  mode must key its `dict[int, Athlete]` off track-site IDs, never XC ones.
- **New, incidental finding (not previously flagged): decorative markup
  inside result cells at championship meets.** The state-meet time cells
  sometimes contain a season-best/qualifying icon ahead of the time, e.g.
  `<td align="right"><small><i class="fa fa-star text-success"></i></small> 5:08.96</td>`.
  This does not require any code change: `.get_text(strip=True)` (already
  how both the existing `_parse_time_to_seconds` caller and the proposed
  track parser read the cell) yields plain `"5:08.96"`, since the `<i>` tag
  contributes no text content. Noted here only so a future implementer
  isn't surprised by the raw HTML if they inspect a championship page
  directly.
