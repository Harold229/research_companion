const PAYWALL_EVENTS_SHEET = "paywall_events";
const INTEREST_LEADS_SHEET = "interest_leads";

const PAYWALL_EVENT_COLUMNS = [
  "timestamp",
  "session_id",
  "event_name",
  "question_initiale",
  "question_reformulee",
  "type_question",
  "framework",
  "wide_count",
  "narrow_count",
  "is_identical",
  "price_shown",
  "price_selected",
  "email",
  "comment",
  "refusal_reason",
  "source",
];

const INTEREST_LEAD_COLUMNS = [
  "timestamp",
  "session_id",
  "event_name",
  "question_initiale",
  "question_reformulee",
  "type_question",
  "framework",
  "price_selected",
  "email",
  "comment",
  "refusal_reason",
  "source",
];

function doGet() {
  return jsonResponse({
    ok: true,
    message: "Paywall webhook is running.",
  });
}

function doPost(e) {
  try {
    const payload = parsePayload_(e);
    const spreadsheet = getSpreadsheet_();

    appendRow_(
      spreadsheet,
      PAYWALL_EVENTS_SHEET,
      PAYWALL_EVENT_COLUMNS,
      payload
    );

    if (shouldWriteInterestLead_(payload)) {
      appendRow_(
        spreadsheet,
        INTEREST_LEADS_SHEET,
        INTEREST_LEAD_COLUMNS,
        payload
      );
    }

    return jsonResponse({
      ok: true,
      event_name: payload.event_name || "",
      wrote_interest_lead: shouldWriteInterestLead_(payload),
    });
  } catch (error) {
    return jsonResponse(
      {
        ok: false,
        error: String(error),
      },
      400
    );
  }
}

function parsePayload_(e) {
  if (!e || !e.postData || !e.postData.contents) {
    throw new Error("Missing JSON payload.");
  }

  const payload = JSON.parse(e.postData.contents);
  if (!payload || typeof payload !== "object") {
    throw new Error("Invalid payload.");
  }

  return normalizePayload_(payload);
}

function normalizePayload_(payload) {
  const normalized = {};
  PAYWALL_EVENT_COLUMNS.forEach((column) => {
    const value = payload[column];
    if (Array.isArray(value)) {
      normalized[column] = value.join(" | ");
    } else if (value === null || typeof value === "undefined") {
      normalized[column] = "";
    } else {
      normalized[column] = String(value);
    }
  });
  return normalized;
}

function shouldWriteInterestLead_(payload) {
  const email = (payload.email || "").trim();
  const selectedPrice = (payload.price_selected || "").trim();
  return Boolean(
    email ||
      payload.event_name === "paywall_click_interest" ||
      payload.event_name === "paywall_click_unlock" ||
      selectedPrice === "5 €" ||
      selectedPrice === "10 €"
  );
}

function getSpreadsheet_() {
  const spreadsheetId = PropertiesService.getScriptProperties().getProperty(
    "SPREADSHEET_ID"
  );
  if (!spreadsheetId) {
    throw new Error("Missing script property SPREADSHEET_ID.");
  }
  return SpreadsheetApp.openById(spreadsheetId);
}

function appendRow_(spreadsheet, sheetName, columns, payload) {
  const sheet = getOrCreateSheet_(spreadsheet, sheetName, columns);
  const row = columns.map((column) => payload[column] || "");
  sheet.appendRow(row);
}

function getOrCreateSheet_(spreadsheet, sheetName, columns) {
  let sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }

  const currentHeaders = sheet
    .getRange(1, 1, 1, columns.length)
    .getValues()[0]
    .map(String);

  const headersMatch = columns.every((column, index) => currentHeaders[index] === column);
  if (!headersMatch) {
    sheet.getRange(1, 1, 1, columns.length).setValues([columns]);
  }

  return sheet;
}

function jsonResponse(payload, statusCode) {
  const output = ContentService.createTextOutput(JSON.stringify(payload));
  output.setMimeType(ContentService.MimeType.JSON);
  return output;
}
