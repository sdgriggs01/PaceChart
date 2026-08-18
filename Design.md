# Pace Chart

## Inputs
- A list of athletes, scraped from [the roster page](https://xc.greenhopetrackxc.com/index.php/athletes/roster)
- A list of races with results, scraped from [the schedule page](https://xc.greenhopetrackxc.com/index.php/schedule/view). The schedule page itself only lists meets (date/location) with links to separate boys'/girls' results pages per meet — the actual results require following those links, so this is a two-stage crawl: schedule page → each meet's results page.
- A list of training paces (see Methodologies below for the defined set)


## Outputs
- A PDF with a table per gender, where each athlete has a row with the selected training paces. An athlete with no selected results still gets a row; their pace cells are left blank rather than omitting the athlete.

## Methodologies
- The methodology for the calculator is contained within the Calculator.htm file; a full report has been generated at [Calculator-Methodology.md](Calculator-Methodology.md).
- The whole model (all three distance-regime fatigue curves, the equivalent-performance table, and the training-pace zones) will be implemented, not just the training-pace portion — the equivalent-performance formulas are needed for 3k→5k conversion, and implementing the full model now avoids revisiting this if other input distances or features come up later.
- **5k-equivalent conversion**: every selected result — regardless of its own distance (3000m, 5000m, or otherwise) — is run through the full model (§4's regime selection, then §6's equivalent-performance table) to get its predicted 5000m time: `5k_equivalent_time = equivalent_performances(result)["5000m"]`. This is deliberately not the simplified `3k_time * (5000m_multiplier / 3000m_multiplier)` shortcut — that shortcut skips the regime/decay adjustment the full model applies even to the reference distance itself, which would be inconsistent with using the whole model everywhere else.
- **Training paces**: the full set available, per the methodology report, is 11 intensity zones × 9 display distances:
  - Zones (in increasing intensity): Very Easy (58%), Easy (66%), Moderate (74%), Tempo (82%), Threshold (87%), CV (90%), AP (95%), V.O2 max (100%), 110%, 120%, 130%
  - Distances: Mile, 1600m, 1200m, 1000m, 800m, 600m, 400m, 300m, 200m
  - The user enables/disables individual zone × distance combinations for the PDF output (see workflow step 2).

## User Workflow
 1. The application will generate a table where the rows are athletes & the columns are meets with results. If an athlete has no result for that meet, the cell is blank. If there is a result, the cell will have a checkbox (unchecked). There will be a quick action button that will select the most recent result for each athlete. A user can check or uncheck any result
 2. There will be a list of paces, drawn from the full zone × distance set defined above, that can be enabled or disabled
 3. When the user presses "Calc": for each athlete, every selected result is converted to a 5000m-equivalent time using the 5k-equivalent conversion above, then those converted times are averaged to produce one 5k value per athlete. An athlete with no selected results gets no calculated 5k value.
 4. Then using the calculated 5k value, all enabled training paces are generated. Athletes with no calculated 5k value are skipped (no paces to generate).
 5. A PDF table is created where each athlete has a row, with their paces listed. Athletes with no calculated 5k value still get a row, with blank pace cells.