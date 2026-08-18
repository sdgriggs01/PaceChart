# Pace Chart

## Inputs
- A list of athletes, scraped from [the roster page](https://xc.greenhopetrackxc.com/index.php/athletes/roster)
- A list of races with results, scraped from [the schedule page](https://xc.greenhopetrackxc.com/index.php/schedule/view)
- A list of training paces


## Outputs
- A PDF with a table per gender, where each athlete has a row with the selected training paces

## Methodologies
- The methodology for the calculator is contained within the Calculator.htm file, a report has been generated at Calculator-Methodologies.md. Only the Training Paces (not the Equivilent Race Performance) will be used.

## User Workflow
 1. The application will generate a table where the rows are athletes & the columns are meets with results. If an athlete has no result for that meet, the cell is blank. If there is a result, the cell will have a checkbox (unchecked). There will be a quick action button that will select the most recent result for each athlete. A user can check or uncheck any result
 2. There will be a list of paces (to be defined later) that can be enabled or disabled
 3. When the user presses "Calc" it takes the average of each athletes selected results (converting 3000m marks to 5km marks). 
 4. Then using the calculated 5k value, all training paces are generated
 5. A PDF table is created where each athlete has a row, with their paces listed