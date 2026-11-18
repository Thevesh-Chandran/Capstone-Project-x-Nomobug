"""Read displayed sheet values and the underlying dates in one Sheets response."""
from datetime import date, timedelta


DATE_COLUMNS = {"REFUND": {0: "refund_cell_date", 4: "purchase_cell_date"},
                "SALES": {3: "sale_close_cell_date"},
                "B2B FOLLOW UP": {13: "lead_close_cell_date"}}


def read_dated_tab(service, spreadsheet_id, tab, header_row):
    result = service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=[f"'{tab}'"],
        fields="sheets(data(rowData(values(formattedValue,effectiveValue,effectiveFormat(numberFormat(type))))))"
    ).execute(num_retries=2)
    values, dates = [], []
    for index, row in enumerate(result["sheets"][0]["data"][0].get("rowData", []), 1):
        cells = row.get("values", [])
        display = [cell.get("formattedValue", "") for cell in cells]
        while display and not display[-1]:
            display.pop()
        values.append(display)
        if index <= header_row:
            continue
        record = {}
        for column, label in DATE_COLUMNS[tab].items():
            cell = cells[column] if column < len(cells) else {}
            number = cell.get("effectiveValue", {}).get("numberValue")
            kind = cell.get("effectiveFormat", {}).get("numberFormat", {}).get("type")
            record[label] = ((date(1899, 12, 30) + timedelta(days=int(number))).isoformat()
                             if kind in {"DATE", "DATE_TIME"} and isinstance(number, (int, float))
                             and 0 < number < 100000 else "")
        dates.append(record)
    while values and not values[-1]:
        values.pop()
    return values, dates[:len(values)-header_row]
