// =====================================================================
// Apps Script: trim old rows from the Google Sheet
// =====================================================================
// PURPOSE
//   Keep the Google Sheet small and fast. Supabase already has the full
//   historical archive, so the sheet only needs the recent tail.
//
// SAFE TO PASTE
//   This is a STANDALONE block. Append it to the bottom of your existing
//   Apps Script file (the Yahoo Finance fetcher). Do NOT replace anything.
//   It does not call or override any existing function.
//
// HOW IT WORKS
//   - Minute sheet:  keep last 3 days, delete older rows
//   - Daily sheet:   keep last 90 days, delete older rows
//   - Holders sheet: untouched (small, only ~1.4K rows)
//   - Stocks & Crypto: untouched (small, yearly data)
//
// HOW TO RUN
//   1. Paste this whole block at the bottom of Code.gs in Apps Script.
//   2. Save (Cmd+S).
//   3. Click "Run" with `trimOldRows` selected to test once manually.
//      Check execution log — should print row counts.
//   4. Set up a daily trigger:
//        Apps Script editor -> Triggers (clock icon, left sidebar)
//        -> Add Trigger
//        -> Function: trimOldRows
//        -> Event source: Time-driven
//        -> Type: Day timer
//        -> Time of day: 4am-5am
//        -> Save
//
// SAFETY
//   - Reads the date column to find a cutoff, deletes only rows OLDER than it
//   - Never touches header row
//   - Never deletes if the sheet is empty
//   - Never deletes if cutoff date couldn't be parsed
// =====================================================================

function trimOldRows() {
  var keepDaysMinute = 3;
  var keepDaysDaily  = 90;

  var ss = SpreadsheetApp.getActiveSpreadsheet();

  trimSheet_(ss, "Minute", keepDaysMinute);
  trimSheet_(ss, "Daily",  keepDaysDaily);
}

function trimSheet_(ss, sheetName, keepDays) {
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    Logger.log("trimSheet_: sheet '" + sheetName + "' not found, skipping");
    return;
  }

  var lastRow = sheet.getLastRow();
  if (lastRow <= 1) {
    Logger.log("trimSheet_: '" + sheetName + "' is empty (lastRow=" + lastRow + ")");
    return;
  }

  // Find the date column from the header row
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var dateColIdx = -1;
  for (var i = 0; i < headers.length; i++) {
    var h = String(headers[i] || "").trim().toLowerCase();
    if (h === "date" || h === "datetime" || h === "ts") {
      dateColIdx = i;
      break;
    }
  }
  if (dateColIdx === -1) {
    Logger.log("trimSheet_: '" + sheetName + "' has no date column, skipping");
    return;
  }

  var cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - keepDays);
  cutoff.setHours(0, 0, 0, 0);

  // Read the entire date column at once (way faster than one cell at a time)
  var dateColValues = sheet.getRange(2, dateColIdx + 1, lastRow - 1, 1).getValues();

  // Find the highest row index whose date is OLDER than the cutoff.
  // We'll delete rows 2 .. (lastOldRow + 1) in one shot.
  var lastOldRowIdx = -1;
  for (var r = 0; r < dateColValues.length; r++) {
    var val = dateColValues[r][0];
    var d = (val instanceof Date) ? val : new Date(val);
    if (isNaN(d.getTime())) continue;
    if (d < cutoff) {
      if (r > lastOldRowIdx) lastOldRowIdx = r;
    }
  }

  if (lastOldRowIdx < 0) {
    Logger.log("trimSheet_: '" + sheetName + "' has no rows older than " + keepDays + " days");
    return;
  }

  // BUT only safe to deleteRows in a contiguous block if the sheet is sorted
  // by date ascending. If not, fall back to per-row deletion (slower but safe).
  var sortedAsc = true;
  var prev = null;
  for (var r2 = 0; r2 < dateColValues.length; r2++) {
    var v = dateColValues[r2][0];
    var dd = (v instanceof Date) ? v : new Date(v);
    if (isNaN(dd.getTime())) continue;
    if (prev !== null && dd < prev) { sortedAsc = false; break; }
    prev = dd;
  }

  if (sortedAsc) {
    // Fast path: delete rows 2 .. lastOldRowIdx+2 in one batch
    var howMany = lastOldRowIdx + 1; // rows to delete (1-indexed count)
    sheet.deleteRows(2, howMany);
    Logger.log("trimSheet_: '" + sheetName + "' fast-deleted " + howMany + " old rows (sorted)");
    return;
  }

  // Slow path: gather all old row indexes, delete bottom-up so indexes don't shift
  var toDelete = [];
  for (var r3 = 0; r3 < dateColValues.length; r3++) {
    var v3 = dateColValues[r3][0];
    var d3 = (v3 instanceof Date) ? v3 : new Date(v3);
    if (isNaN(d3.getTime())) continue;
    if (d3 < cutoff) toDelete.push(r3 + 2); // sheet row number
  }
  toDelete.sort(function(a, b) { return b - a; });
  for (var k = 0; k < toDelete.length; k++) {
    sheet.deleteRow(toDelete[k]);
  }
  Logger.log("trimSheet_: '" + sheetName + "' slow-deleted " + toDelete.length + " old rows");
}
