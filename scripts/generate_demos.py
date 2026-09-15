"""Generate only synthetic, deterministic demonstration files."""
from pathlib import Path
from datetime import date, timedelta
import csv
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1] / "demo_data"


def main():
    ROOT.mkdir(exist_ok=True)
    fields = ["customer_id", "name", "age", "city", "joined", "spend", "consent", "empty_notes"]
    rows = []
    for i in range(1, 61):
        rows.append([f"C{i:03}", f"Demo Person {i:02}", 20 + i % 45, ["Astana", "Almaty", "Shymkent"][i % 3],
                     (date(2024, 1, 1) + timedelta(days=i)).isoformat(), 25 + (i * 13) % 170, "yes", ""])
    rows[2][1] = "  Demo Person 03 "
    rows[4][2] = ""
    rows[8][3] = "almaty"
    rows[9][3] = " Almaty "
    rows[10][4] = "2024-02-30"
    rows[11][4] = "03/04/2024"
    rows[12][5] = 9800
    rows[13][2] = -4
    rows[14][1] = ""
    rows[15][3] = "   "
    rows[16][4] = "not-a-date"
    rows[17][5] = "inf"
    rows[18][2] = ""
    rows += [rows[0].copy(), rows[1].copy()]
    with (ROOT / "demo_customers.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)
    clean_fields = ["item_id", "category", "quantity", "unit_price"]
    clean_rows = [[f"I{i:03}", ["Office", "Kitchen", "Garden"][i % 3], 10 + i, 5 + i / 2] for i in range(1, 21)]
    with (ROOT / "demo_inventory.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(clean_fields)
        writer.writerows(clean_rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "Customers"
    ws.append(fields)
    for row in rows:
        ws.append([None if x == "" else x for x in row])
    ws = wb.create_sheet("Inventory")
    ws.append(clean_fields)
    for row in clean_rows:
        ws.append(row)
    wb.save(ROOT / "demo_workbook.xlsx")


if __name__ == "__main__":
    main()
