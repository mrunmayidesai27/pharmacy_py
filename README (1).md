# Pharmacy Inventory Manager (Tkinter + SQLite)

Desktop version of the pharmacy DBMS project. No external packages needed
(Tkinter and sqlite3 ship with Python 3).

## Run
```
python pharmacy_app.py
```
A `pharmacy.db` file is created on first run with sample data.
Delete it to reset.

## Features
- Medicines: add, edit, delete, search, export CSV (rows colour-coded: red = expired, yellow = expiring in 30 days, blue = low stock)
- Sales: stock-checked, expiry-checked, done in a transaction (rollback on error)
- Receive stock (purchases)
- Alerts: expiry and low-stock
- Demand forecast: moving average of recent sales, suggests reorder quantity
- Suppliers

## Tables
suppliers, medicines, sales, purchases (foreign keys + CHECK constraints)

## Files
- pharmacy_app.py : backend (`Database` class) + frontend (`App` class)
