// ============================================================
// REPLIT REVIVAL -- Yahoo Finance (Apps Script)
// ============================================================
// Apps Script writes Yahoo data to the Google Sheet ONLY.
//
// Sheet -> Supabase mirroring is handled by the Python script:
//     scripts/sync_gsheet_to_supabase.py
//
// Why: Apps Script's UrlFetchApp forces a "Mozilla/..." User-Agent
// on every outbound request, which Supabase pattern-matches as
// "browser" and rejects all sb_secret_* keys with HTTP 401:
//     "Forbidden use of secret API key in browser"
// We can't override the User-Agent -- Apps Script silently keeps
// its own. So Apps Script can never talk to Supabase directly with
// the new API key system. The Python script does it instead.
// ============================================================


// ============================================================
// HELPER -- get Yahoo crumb + cookies
// ============================================================
function getYahooCrumb_() {
  try {
    var cookieRes = UrlFetchApp.fetch("https://fc.yahoo.com", {
      muteHttpExceptions: true,
      followRedirects: true,
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36" }
    });
    var rawCookies = cookieRes.getAllHeaders()["Set-Cookie"];
    if (!rawCookies) return null;
    if (typeof rawCookies === "string") rawCookies = [rawCookies];
    var cookies = rawCookies.map(function(c) { return c.split(";")[0]; }).join("; ");

    Utilities.sleep(500);

    var crumbRes = UrlFetchApp.fetch("https://query1.finance.yahoo.com/v1/test/getcrumb", {
      muteHttpExceptions: true,
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Cookie": cookies
      }
    });
    var crumb = crumbRes.getContentText().trim();
    if (!crumb || crumb.length < 2) return null;

    Logger.log("Crumb OK: " + crumb);
    return { crumb: crumb, cookies: cookies };

  } catch(e) {
    Logger.log("getYahooCrumb_ error: " + e);
    return null;
  }
}


// ============================================================
// HELPER -- fetch one ticker
// ============================================================
function fetchYahoo_(symbol, auth) {
  try {
    var hosts = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"];
    var host  = hosts[Math.floor(Math.random() * 2)];
    var url   = "https://" + host + "/v8/finance/chart/" + symbol + "?interval=1d&range=1d";
    if (auth && auth.crumb) url += "&crumb=" + encodeURIComponent(auth.crumb);

    var headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
      "Accept": "application/json"
    };
    if (auth && auth.cookies) headers["Cookie"] = auth.cookies;

    var res  = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: headers });
    var code = res.getResponseCode();

    if (code !== 200) {
      Logger.log("HTTP " + code + " for " + symbol);
      return null;
    }

    var json = JSON.parse(res.getContentText());
    if (!json.chart || !json.chart.result || !json.chart.result[0]) return null;

    var meta = json.chart.result[0].meta;
    return {
      close:         meta.regularMarketPrice   != null ? meta.regularMarketPrice   : null,
      open:          meta.regularMarketOpen    != null ? meta.regularMarketOpen    : null,
      high:          meta.regularMarketDayHigh != null ? meta.regularMarketDayHigh : null,
      low:           meta.regularMarketDayLow  != null ? meta.regularMarketDayLow  : null,
      volume:        meta.regularMarketVolume  != null ? meta.regularMarketVolume  : null,
      mcap:          meta.marketCap            != null ? meta.marketCap            : null,
      currency:      meta.currency             != null ? meta.currency             : "USD",
      previousClose: meta.chartPreviousClose   != null ? meta.chartPreviousClose   : null
    };
  } catch(e) {
    Logger.log("fetchYahoo_ error for " + symbol + ": " + e);
    return null;
  }
}


// ============================================================
// NAME MAP
// ============================================================
var NAME_MAP = {
  "BTC-USD":   "Bitcoin",
  "GLD":       "Gold",
  "%5EGSPC":   "S&P 500",
  "%5EIXIC":   "Nasdaq",
  "AAPL":      "AAPL",
  "MSFT":      "MSFT",
  "GOOGL":     "GOOGL",
  "AMZN":      "AMZN",
  "META":      "META",
  "NFLX":      "NFLX",
  "DIS":       "DIS",
  "CMCSA":     "CMCSA",
  "SPOT":      "SPOT",
  "ROKU":      "ROKU",
  "PARA":      "PARA",
  "WBD":       "WBD",
  "TTD":       "TTD",
  "CRTO":      "CRTO",
  "DSP":       "DSP",
  "U":         "U",
  "APP":       "APP",
  "MGNI":      "MGNI",
  "PUBM":      "PUBM",
  "NEXN":      "NEXN",
  "DV":        "DV",
  "IAS":       "IAS",
  "SNAP":      "SNAP",
  "PINS":      "PINS",
  "PSM.DE":    "ProSieben",
  "RRTL.DE":   "RTL Group",
  "A3M.MC":    "Atresmedia",
  "TFI.PA":    "TF1",
  "MFEA.MI":   "MFE",
  "005930.KS": "Samsung",
  "0700.HK":   "Tencent"
};


// ============================================================
// 1. DAILY  ->  sheet "Daily"
// ============================================================
function fetchDaily_AllAssets() {

  var STOCKS = [
    "AAPL","MSFT","GOOGL","AMZN","META","NFLX","DIS","CMCSA",
    "SPOT","ROKU","PARA","WBD","%5EGSPC","%5EIXIC",
    "TTD","CRTO","DSP","U","APP","MGNI","PUBM","NEXN","DV","IAS","SNAP","PINS",
    "PSM.DE","RRTL.DE","A3M.MC","TFI.PA","MFEA.MI",
    "005930.KS","0700.HK"
  ];

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Daily");
  if (!sheet) sheet = ss.insertSheet("Daily");
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["date","close","open","high","low","volume","change %","market cap","currency","asset"]);
  }

  var auth    = getYahooCrumb_();
  var dateObj = new Date();
  var rows    = [];

  for (var i = 0; i < STOCKS.length; i++) {
    var sym = STOCKS[i];
    var d   = fetchYahoo_(sym, auth);
    if (d) {
      var chg = (d.close && d.previousClose) ? (d.close - d.previousClose) / d.previousClose : null;
      rows.push([dateObj, d.close, d.open, d.high, d.low, d.volume, chg, d.mcap, d.currency, NAME_MAP[sym] || sym]);
    }
    Utilities.sleep(300);
  }

  // Gold
  var gld = fetchYahoo_("GLD", auth);
  if (gld) {
    var gldChg = (gld.close && gld.previousClose) ? (gld.close - gld.previousClose) / gld.previousClose : null;
    rows.push([dateObj, gld.close*10, gld.open*10, gld.high*10, gld.low*10, gld.volume, gldChg, null, "USD", "Gold"]);
  }

  // Bitcoin
  var btc = fetchYahoo_("BTC-USD", auth);
  if (btc) {
    var btcChg = (btc.close && btc.previousClose) ? (btc.close - btc.previousClose) / btc.previousClose : null;
    rows.push([dateObj, btc.close, btc.open, btc.high, btc.low, btc.volume, btcChg, btc.mcap, btc.currency, "Bitcoin"]);
  }

  if (rows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
  }
  Logger.log("Daily sheet done -- wrote " + rows.length + " rows");
}


// ============================================================
// 2. INTRADAY  ->  sheet "Minute"
// Note: Samsung (KRX) and Tencent (HKEX) trade different hours
// than US markets -- they'll return data during their own sessions
// ============================================================
function fetchIntraday_AllAssets() {

  var STOCKS = [
    "AAPL","MSFT","GOOGL","AMZN","META","NFLX","DIS","CMCSA",
    "SPOT","ROKU","PARA","WBD","%5EGSPC","%5EIXIC",
    "TTD","CRTO","DSP","U","APP","MGNI","PUBM","NEXN","DV","IAS","SNAP","PINS",
    "PSM.DE","RRTL.DE","A3M.MC","TFI.PA","MFEA.MI",
    "005930.KS","0700.HK"
  ];

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Minute");
  if (!sheet) sheet = ss.insertSheet("Minute");
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["date","close","open","high","low","volume","change %","market cap","currency","asset"]);
  }

  var now         = new Date();
  var roundedDate = new Date(Math.floor(now.getTime() / 300000) * 300000);

  // Duplicate guard
  if (sheet.getLastRow() > 1) {
    var lastVal = sheet.getRange(sheet.getLastRow(), 1).getValue();
    if (lastVal instanceof Date && Math.abs(lastVal.getTime() - roundedDate.getTime()) < 60000) {
      Logger.log("Already written for " + roundedDate + " -- skipping");
      return;
    }
  }

  var utcMins   = now.getUTCHours() * 60 + now.getUTCMinutes();
  var isWeekday = now.getUTCDay() >= 1 && now.getUTCDay() <= 5;

  // US market hours: 13:30-20:00 UTC (810-1200 mins)
  // KRX hours:       00:00-06:30 UTC (0-390 mins)
  // HKEX hours:      01:30-08:00 UTC (90-480 mins)
  var fetchUS  = isWeekday && utcMins >= 810  && utcMins < 1260;
  var fetchKRX = isWeekday && utcMins >= 0    && utcMins < 390;
  var fetchHK  = isWeekday && utcMins >= 90   && utcMins < 480;

  var rows = [];
  var auth = getYahooCrumb_();

  // Always fetch BTC (24/7)
  var btc = fetchYahoo_("BTC-USD", auth);
  if (btc) {
    var btcChg = (btc.close && btc.previousClose) ? (btc.close - btc.previousClose) / btc.previousClose : null;
    rows.push([roundedDate, btc.close, btc.open, btc.high, btc.low, btc.volume, btcChg, btc.mcap, btc.currency, "Bitcoin"]);
  }

  if (fetchUS) {
    var US_STOCKS = [
      "AAPL","MSFT","GOOGL","AMZN","META","NFLX","DIS","CMCSA",
      "SPOT","ROKU","PARA","WBD","%5EGSPC","%5EIXIC",
      "TTD","CRTO","DSP","U","APP","MGNI","PUBM","NEXN","DV","IAS","SNAP","PINS",
      "PSM.DE","RRTL.DE","A3M.MC","TFI.PA","MFEA.MI"
    ];
    for (var i = 0; i < US_STOCKS.length; i++) {
      var sym = US_STOCKS[i];
      var d   = fetchYahoo_(sym, auth);
      if (d) {
        var chg = (d.close && d.previousClose) ? (d.close - d.previousClose) / d.previousClose : null;
        rows.push([roundedDate, d.close, d.open, d.high, d.low, d.volume, chg, d.mcap, d.currency, NAME_MAP[sym] || sym]);
      }
      Utilities.sleep(300);
    }

    // Gold (US hours only)
    var gld = fetchYahoo_("GLD", auth);
    if (gld) {
      var gldChg = (gld.close && gld.previousClose) ? (gld.close - gld.previousClose) / gld.previousClose : null;
      rows.push([roundedDate, gld.close*10, gld.open*10, gld.high*10, gld.low*10, gld.volume, gldChg, null, "USD", "Gold"]);
    }
  }

  if (fetchKRX) {
    var samsung = fetchYahoo_("005930.KS", auth);
    if (samsung) {
      var sChg = (samsung.close && samsung.previousClose) ? (samsung.close - samsung.previousClose) / samsung.previousClose : null;
      rows.push([roundedDate, samsung.close, samsung.open, samsung.high, samsung.low, samsung.volume, sChg, samsung.mcap, samsung.currency, "Samsung"]);
    }
    Utilities.sleep(300);
  }

  if (fetchHK) {
    var tencent = fetchYahoo_("0700.HK", auth);
    if (tencent) {
      var tChg = (tencent.close && tencent.previousClose) ? (tencent.close - tencent.previousClose) / tencent.previousClose : null;
      rows.push([roundedDate, tencent.close, tencent.open, tencent.high, tencent.low, tencent.volume, tChg, tencent.mcap, tencent.currency, "Tencent"]);
    }
  }

  if (!fetchUS && !fetchKRX && !fetchHK) {
    Logger.log("Outside all market hours -- BTC only");
  }

  if (rows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
  }
  Logger.log("Intraday sheet done -- wrote " + rows.length + " rows at " + roundedDate);
}


// ============================================================
// 3. HOLDERS  ->  sheet "Holders"
// ============================================================
function fetchHolders_AllAssets() {

  var HOLDERS_TICKER_MAP = {
    "AAPL":"AAPL", "MSFT":"MSFT", "GOOGL":"GOOGL",
    "AMZN":"AMZN", "META":"META", "NFLX":"NFLX",
    "DIS":"DIS", "CMCSA":"CMCSA", "SPOT":"SPOT",
    "ROKU":"ROKU", "PARA":"PARA", "WBD":"WBD",
    "TTD":"TTD", "CRTO":"CRTO", "U":"U",
    "APP":"APP", "MGNI":"MGNI", "PUBM":"PUBM",
    "DV":"DV", "SNAP":"SNAP", "PINS":"PINS",
    "PSM.DE":"PSM.DE", "RRTL.DE":"RRTL.DE",
    "A3M.MC":"A3M.MC", "TFI.PA":"TFI.PA", "MFEA.MI":"MFEA.MI",
    "005930.KS":"005930.KS", "0700.HK":"0700.HK"
  };

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Holders");
  if (!sheet) sheet = ss.insertSheet("Holders");

  // Only write header if sheet is brand new
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["date_fetched","company","ticker","holder_name","shares","value_usd","pct_out","holder_type"]);
  }

  var auth  = getYahooCrumb_();
  var today = new Date();
  var rows  = [];

  var tickers = Object.keys(HOLDERS_TICKER_MAP);
  for (var i = 0; i < tickers.length; i++) {
    var ticker = tickers[i];

    try {
      var url = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/"
              + HOLDERS_TICKER_MAP[ticker] + "?modules=institutionOwnership,fundOwnership";
      if (auth && auth.crumb) url += "&crumb=" + encodeURIComponent(auth.crumb);

      var headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
      };
      if (auth && auth.cookies) headers["Cookie"] = auth.cookies;

      var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: headers });
      if (res.getResponseCode() !== 200) {
        Logger.log("Holders HTTP " + res.getResponseCode() + " for " + ticker);
        Utilities.sleep(600);
        continue;
      }

      var json   = JSON.parse(res.getContentText());
      var result = json.quoteSummary && json.quoteSummary.result ? json.quoteSummary.result[0] : null;
      if (!result) { Utilities.sleep(600); continue; }

      var instList = result.institutionOwnership && result.institutionOwnership.ownershipList
                   ? result.institutionOwnership.ownershipList : [];
      instList.forEach(function(h) {
        rows.push([today, ticker, HOLDERS_TICKER_MAP[ticker],
          h.organization || null,
          h.position ? h.position.raw : null,
          h.value    ? h.value.raw    : null,
          h.pctHeld  ? h.pctHeld.raw  : null,
          "institutional"]);
      });

      var fundList = result.fundOwnership && result.fundOwnership.ownershipList
                   ? result.fundOwnership.ownershipList : [];
      fundList.forEach(function(h) {
        rows.push([today, ticker, HOLDERS_TICKER_MAP[ticker],
          h.organization || null,
          h.position ? h.position.raw : null,
          h.value    ? h.value.raw    : null,
          h.pctHeld  ? h.pctHeld.raw  : null,
          "fund"]);
      });

    } catch(e) {
      Logger.log("Holders error for " + ticker + ": " + e);
    }

    Utilities.sleep(600);
  }

  if (rows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
  }
  Logger.log("Holders sheet done -- wrote " + rows.length + " rows");
}


// ============================================================
// WEB APP  ->  doGet
// ============================================================
function doGet(e) {
  var params      = (e && e.parameter) ? e.parameter : {};
  var sheetName   = params.sheet  || "Daily";
  var assetFilter = params.asset  || "";
  var days        = Math.min(parseInt(params.days || "365", 10), 3650);

  try {
    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(sheetName);
    if (!sheet) {
      return _jsonResponse({ error: "Sheet not found: " + sheetName });
    }

    var data = sheet.getDataRange().getValues();
    if (data.length < 2) {
      return _jsonResponse({ rows: [], count: 0 });
    }

    var headers = data[0].map(function(h) { return String(h).trim().toLowerCase(); });
    var idx = {};
    headers.forEach(function(h, i) { idx[h] = i; });

    var cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);

    var rows = [];
    for (var i = 1; i < data.length; i++) {
      var row = data[i];

      if (assetFilter && idx["asset"] !== undefined) {
        var rowAsset = String(row[idx["asset"]] || "").trim();
        if (rowAsset !== assetFilter) continue;
      }

      var dateVal = row[idx["date"]];
      if (!(dateVal instanceof Date)) dateVal = new Date(dateVal);
      if (isNaN(dateVal.getTime())) continue;
      if (dateVal < cutoff) continue;

      function col(name) {
        return idx[name] !== undefined ? row[idx[name]] : null;
      }

      rows.push({
        date:       Utilities.formatDate(dateVal, "UTC", "yyyy-MM-dd"),
        close:      col("close")  !== null ? col("close")  : col("price"),
        open:       col("open"),
        high:       col("high"),
        low:        col("low"),
        volume:     col("volume"),
        change_pct: col("change %"),
        market_cap: col("market cap"),
        currency:   col("currency") || "USD",
        asset:      col("asset")    || assetFilter
      });
    }

    return _jsonResponse({ rows: rows, count: rows.length, sheet: sheetName });

  } catch (err) {
    return _jsonResponse({ error: String(err) });
  }
}

function _jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
