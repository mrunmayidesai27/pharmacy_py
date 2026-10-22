"""Backend: all SQLite logic for the Pharmacy Inventory Manager."""

import random
import sqlite3
from datetime import date, datetime, timedelta

DB_FILE = "pharmacy.db"


class Database:
    def __init__(self, path=DB_FILE):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self.seed_if_empty()

    # ------------------------------------------------------------------ schema
    def create_tables(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS suppliers (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                phone       TEXT,
                email       TEXT
            );

            CREATE TABLE IF NOT EXISTS medicines (
                medicine_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                batch_no      TEXT NOT NULL,
                category      TEXT,
                price         REAL NOT NULL CHECK (price >= 0),
                quantity      INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
                reorder_level INTEGER NOT NULL DEFAULT 10,
                expiry_date   TEXT NOT NULL,           -- YYYY-MM-DD
                supplier_id   INTEGER,
                UNIQUE (name, batch_no),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS sales (
                sale_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id INTEGER NOT NULL,
                qty         INTEGER NOT NULL CHECK (qty > 0),
                total       REAL NOT NULL,
                sale_date   TEXT NOT NULL,             -- YYYY-MM-DD
                FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS purchases (
                purchase_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id   INTEGER NOT NULL,
                qty           INTEGER NOT NULL CHECK (qty > 0),
                purchase_date TEXT NOT NULL,
                FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
                    ON DELETE CASCADE
            );
            """
        )
        self.conn.commit()

    def seed_if_empty(self):
        """Insert demo data on first run so the app is not empty."""
        if self.conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]:
            return
        today = date.today()
        self.conn.executemany(
            "INSERT INTO suppliers(name, phone, email) VALUES (?,?,?)",
            [
                ("MedPlus Distributors", "9800000001", "sales@medplus.example"),
                ("HealthFirst Pharma", "9800000002", "info@healthfirst.example"),
            ],
        )
        # name, batch, category, price, qty, reorder, days_to_expiry, supplier
        sample = [
            ("Paracetamol 500mg", "B101", "Analgesic", 12.5, 120, 30, 400, 1),
            ("Amoxicillin 250mg", "B102", "Antibiotic", 45.0, 8, 20, 25, 2),
            ("Cetirizine 10mg", "B103", "Antihistamine", 18.0, 60, 15, 200, 1),
            ("Ibuprofen 400mg", "B104", "Analgesic", 22.0, 40, 15, -5, 2),
            ("ORS Sachet", "B105", "Electrolyte", 10.0, 200, 50, 18, 1),
        ]
        for n, b, c, p, q, r, days, s in sample:
            exp = (today + timedelta(days=days)).isoformat()
            self.conn.execute(
                """INSERT INTO medicines(name,batch_no,category,price,quantity,
                   reorder_level,expiry_date,supplier_id) VALUES (?,?,?,?,?,?,?,?)""",
                (n, b, c, p, q, r, exp, s),
            )
        # fake sales history so the forecast has data to work with
        random.seed(1)
        for mid in range(1, 6):
            price = self.conn.execute(
                "SELECT price FROM medicines WHERE medicine_id=?", (mid,)
            ).fetchone()[0]
            for d in range(30, 0, -1):
                q = random.randint(0, 6)
                if q:
                    self.conn.execute(
                        "INSERT INTO sales(medicine_id,qty,total,sale_date) VALUES (?,?,?,?)",
                        (mid, q, q * price, (today - timedelta(days=d)).isoformat()),
                    )
        self.conn.commit()

    # --------------------------------------------------------------- suppliers
    def get_suppliers(self):
        return self.conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()

    def add_supplier(self, name, phone, email):
        self.conn.execute(
            "INSERT INTO suppliers(name,phone,email) VALUES (?,?,?)", (name, phone, email)
        )
        self.conn.commit()

    def delete_supplier(self, supplier_id):
        self.conn.execute("DELETE FROM suppliers WHERE supplier_id=?", (supplier_id,))
        self.conn.commit()

    # --------------------------------------------------------------- medicines
    def get_medicines(self, search=""):
        like = f"%{search}%"
        return self.conn.execute(
            """SELECT m.*, COALESCE(s.name,'-') AS supplier
               FROM medicines m LEFT JOIN suppliers s USING (supplier_id)
               WHERE m.name LIKE ? OR m.category LIKE ? OR m.batch_no LIKE ?
               ORDER BY m.name""",
            (like, like, like),
        ).fetchall()

    def add_medicine(self, name, batch, cat, price, qty, reorder, expiry, supplier_id):
        self.conn.execute(
            """INSERT INTO medicines(name,batch_no,category,price,quantity,
               reorder_level,expiry_date,supplier_id) VALUES (?,?,?,?,?,?,?,?)""",
            (name, batch, cat, price, qty, reorder, expiry, supplier_id),
        )
        self.conn.commit()

    def update_medicine(self, mid, name, batch, cat, price, qty, reorder, expiry, supplier_id):
        self.conn.execute(
            """UPDATE medicines SET name=?,batch_no=?,category=?,price=?,quantity=?,
               reorder_level=?,expiry_date=?,supplier_id=? WHERE medicine_id=?""",
            (name, batch, cat, price, qty, reorder, expiry, supplier_id, mid),
        )
        self.conn.commit()

    def delete_medicine(self, mid):
        self.conn.execute("DELETE FROM medicines WHERE medicine_id=?", (mid,))
        self.conn.commit()

    # ------------------------------------------------------------ transactions
    def record_sale(self, mid, qty):
        """Sell qty units atomically. Raises ValueError on a rule violation."""
        try:
            self.conn.execute("BEGIN")
            row = self.conn.execute(
                "SELECT price, quantity, expiry_date FROM medicines WHERE medicine_id=?",
                (mid,),
            ).fetchone()
            if row is None:
                raise ValueError("Medicine not found.")
            if row["expiry_date"] < date.today().isoformat():
                raise ValueError("This batch is expired and cannot be sold.")
            if qty > row["quantity"]:
                raise ValueError(f"Only {row['quantity']} units in stock.")
            self.conn.execute(
                "UPDATE medicines SET quantity = quantity - ? WHERE medicine_id=?",
                (qty, mid),
            )
            self.conn.execute(
                "INSERT INTO sales(medicine_id,qty,total,sale_date) VALUES (?,?,?,?)",
                (mid, qty, qty * row["price"], date.today().isoformat()),
            )
            self.conn.commit()
            return qty * row["price"]
        except Exception:
            self.conn.rollback()
            raise

    def receive_stock(self, mid, qty):
        try:
            self.conn.execute("BEGIN")
            self.conn.execute(
                "UPDATE medicines SET quantity = quantity + ? WHERE medicine_id=?", (qty, mid)
            )
            self.conn.execute(
                "INSERT INTO purchases(medicine_id,qty,purchase_date) VALUES (?,?,?)",
                (mid, qty, date.today().isoformat()),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ------------------------------------------------------- alerts & forecast
    def expiry_alerts(self, days=30):
        today = date.today()
        limit = (today + timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT medicine_id, name, batch_no, quantity, expiry_date
               FROM medicines WHERE expiry_date <= ? ORDER BY expiry_date""",
            (limit,),
        ).fetchall()
        out = []
        for r in rows:
            left = (datetime.strptime(r["expiry_date"], "%Y-%m-%d").date() - today).days
            status = "EXPIRED" if left < 0 else "Expiring soon"
            out.append((r["name"], r["batch_no"], r["quantity"], r["expiry_date"], left, status))
        return out

    def low_stock(self):
        return self.conn.execute(
            """SELECT name, batch_no, quantity, reorder_level FROM medicines
               WHERE quantity <= reorder_level ORDER BY quantity"""
        ).fetchall()

    def forecast(self, window=14, horizon=7):
        """Moving average: avg daily sales over the last `window` days * horizon."""
        since = (date.today() - timedelta(days=window)).isoformat()
        return self.conn.execute(
            """SELECT m.name, m.quantity,
                      COALESCE(SUM(s.qty),0) AS sold,
                      ROUND(COALESCE(SUM(s.qty),0) * 1.0 / ?, 2) AS avg_daily,
                      ROUND(COALESCE(SUM(s.qty),0) * 1.0 / ? * ?, 0) AS forecast
               FROM medicines m
               LEFT JOIN sales s ON s.medicine_id = m.medicine_id AND s.sale_date >= ?
               GROUP BY m.medicine_id ORDER BY forecast DESC""",
            (window, window, horizon, since),
        ).fetchall()

    def sales_report(self):
        return self.conn.execute(
            """SELECT s.sale_date, m.name, s.qty, s.total
               FROM sales s JOIN medicines m USING (medicine_id)
               ORDER BY s.sale_id DESC LIMIT 200"""
        ).fetchall()
