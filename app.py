"""Frontend: main Tkinter window with one tab per feature."""

import csv
import sqlite3
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

from database import Database
from widgets import MedicineDialog, make_tree


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pharmacy Inventory Manager")
        self.geometry("980x600")
        self.db = Database()

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", rowheight=24)
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)

        self.build_medicines_tab()
        self.build_sales_tab()
        self.build_alerts_tab()
        self.build_forecast_tab()
        self.build_suppliers_tab()

        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.refresh_all())
        self.refresh_all()
        self.after(500, self.startup_alert)

    # ---------------------------------------------------------------- helpers
    def selected(self, tree):
        sel = tree.selection()
        return sel[0] if sel else None

    def refresh_all(self):
        self.load_medicines()
        self.load_alerts()
        self.load_forecast()
        self.load_suppliers()
        self.load_sales()
        self.load_sale_combo()

    def startup_alert(self):
        exp = self.db.expiry_alerts(30)
        low = self.db.low_stock()
        if exp or low:
            messagebox.showwarning(
                "Alerts",
                f"{len(exp)} batch(es) expired / expiring within 30 days.\n"
                f"{len(low)} item(s) at or below reorder level.\n\nSee the Alerts tab.",
            )

    # ---------------------------------------------------------- medicines tab
    def build_medicines_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Medicines")

        top = ttk.Frame(tab)
        top.pack(fill="x", pady=6, padx=6)
        ttk.Label(top, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.load_medicines())
        ttk.Entry(top, textvariable=self.search_var, width=30).pack(side="left", padx=6)
        ttk.Button(top, text="Add", command=self.add_med).pack(side="left", padx=2)
        ttk.Button(top, text="Edit", command=self.edit_med).pack(side="left", padx=2)
        ttk.Button(top, text="Delete", command=self.delete_med).pack(side="left", padx=2)
        ttk.Button(top, text="Receive Stock", command=self.receive_stock).pack(side="left", padx=2)
        ttk.Button(top, text="Export CSV", command=self.export_csv).pack(side="right", padx=2)

        cols = ("ID", "Name", "Batch", "Category", "Price", "Qty", "Reorder", "Expiry", "Supplier")
        frame, self.med_tree = make_tree(tab, cols, [40, 180, 70, 110, 70, 60, 70, 100, 150])
        frame.pack(fill="both", expand=True, padx=6, pady=4)
        self.med_tree.tag_configure("expired", background="#f8d7da")
        self.med_tree.tag_configure("soon", background="#fff3cd")
        self.med_tree.tag_configure("low", background="#d1ecf1")

    def load_medicines(self):
        self.med_tree.delete(*self.med_tree.get_children())
        today = date.today()
        for r in self.db.get_medicines(self.search_var.get().strip()):
            exp = datetime.strptime(r["expiry_date"], "%Y-%m-%d").date()
            tag = ""
            if exp < today:
                tag = "expired"
            elif (exp - today).days <= 30:
                tag = "soon"
            elif r["quantity"] <= r["reorder_level"]:
                tag = "low"
            self.med_tree.insert(
                "", "end", iid=str(r["medicine_id"]),
                values=(r["medicine_id"], r["name"], r["batch_no"], r["category"],
                        f"{r['price']:.2f}", r["quantity"], r["reorder_level"],
                        r["expiry_date"], r["supplier"]),
                tags=(tag,),
            )

    def add_med(self):
        d = MedicineDialog(self, self.db)
        self.wait_window(d)
        if d.result:
            self.refresh_all()

    def edit_med(self):
        iid = self.selected(self.med_tree)
        if not iid:
            return messagebox.showinfo("Select", "Select a medicine first.")
        rec = next(r for r in self.db.get_medicines() if str(r["medicine_id"]) == iid)
        d = MedicineDialog(self, self.db, rec)
        self.wait_window(d)
        if d.result:
            self.refresh_all()

    def delete_med(self):
        iid = self.selected(self.med_tree)
        if not iid:
            return messagebox.showinfo("Select", "Select a medicine first.")
        if messagebox.askyesno("Confirm", "Delete this medicine and its sales history?"):
            self.db.delete_medicine(int(iid))
            self.refresh_all()

    def receive_stock(self):
        iid = self.selected(self.med_tree)
        if not iid:
            return messagebox.showinfo("Select", "Select a medicine first.")
        win = tk.Toplevel(self)
        win.title("Receive Stock")
        win.grab_set()
        ttk.Label(win, text="Quantity received:").grid(row=0, column=0, padx=10, pady=10)
        qv = tk.StringVar()
        ttk.Entry(win, textvariable=qv, width=10).grid(row=0, column=1, padx=10)

        def ok():
            try:
                q = int(qv.get())
                if q <= 0:
                    raise ValueError
            except ValueError:
                return messagebox.showerror("Invalid", "Enter a positive whole number.", parent=win)
            self.db.receive_stock(int(iid), q)
            win.destroy()
            self.refresh_all()

        ttk.Button(win, text="Add to stock", command=ok).grid(row=1, column=0, columnspan=2, pady=8)

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ID", "Name", "Batch", "Category", "Price", "Qty", "Reorder", "Expiry", "Supplier"])
            for r in self.db.get_medicines():
                w.writerow([r["medicine_id"], r["name"], r["batch_no"], r["category"], r["price"],
                            r["quantity"], r["reorder_level"], r["expiry_date"], r["supplier"]])
        messagebox.showinfo("Exported", f"Saved to {path}")

    # -------------------------------------------------------------- sales tab
    def build_sales_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Sales")

        form = ttk.LabelFrame(tab, text="New sale")
        form.pack(fill="x", padx=6, pady=6)
        self.sale_med = tk.StringVar()
        self.sale_qty = tk.StringVar(value="1")
        ttk.Label(form, text="Medicine:").grid(row=0, column=0, padx=6, pady=8)
        self.sale_combo = ttk.Combobox(form, textvariable=self.sale_med, state="readonly", width=45)
        self.sale_combo.grid(row=0, column=1, padx=6)
        ttk.Label(form, text="Qty:").grid(row=0, column=2, padx=6)
        ttk.Entry(form, textvariable=self.sale_qty, width=8).grid(row=0, column=3)
        ttk.Button(form, text="Sell", command=self.do_sale).grid(row=0, column=4, padx=10)

        frame, self.sales_tree = make_tree(tab, ("Date", "Medicine", "Qty", "Total"), [110, 250, 60, 100])
        frame.pack(fill="both", expand=True, padx=6, pady=4)
        self.sale_ids = []

    def load_sale_combo(self):
        meds = self.db.get_medicines()
        self.sale_ids = [m["medicine_id"] for m in meds]
        self.sale_combo["values"] = [
            f"{m['name']} (batch {m['batch_no']}) - stock {m['quantity']}" for m in meds
        ]

    def load_sales(self):
        self.sales_tree.delete(*self.sales_tree.get_children())
        for r in self.db.sales_report():
            self.sales_tree.insert("", "end", values=(r["sale_date"], r["name"], r["qty"], f"{r['total']:.2f}"))

    def do_sale(self):
        idx = self.sale_combo.current()
        if idx < 0:
            return messagebox.showinfo("Select", "Choose a medicine.")
        try:
            qty = int(self.sale_qty.get())
            if qty <= 0:
                raise ValueError("Quantity must be positive.")
            total = self.db.record_sale(self.sale_ids[idx], qty)
        except ValueError as e:
            return messagebox.showerror("Cannot sell", str(e))
        messagebox.showinfo("Sale recorded", f"Total: Rs. {total:.2f}")
        self.refresh_all()

    # ------------------------------------------------------------- alerts tab
    def build_alerts_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Alerts")

        top = ttk.Frame(tab)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="Expiry within (days):").pack(side="left")
        self.exp_days = tk.StringVar(value="30")
        ttk.Entry(top, textvariable=self.exp_days, width=6).pack(side="left", padx=6)
        ttk.Button(top, text="Refresh", command=self.load_alerts).pack(side="left")

        ttk.Label(tab, text="Expired / Expiring", style="Title.TLabel").pack(anchor="w", padx=8)
        f1, self.exp_tree = make_tree(tab, ("Medicine", "Batch", "Qty", "Expiry", "Days left", "Status"),
                                      [200, 80, 60, 100, 80, 120])
        f1.pack(fill="both", expand=True, padx=6, pady=4)
        self.exp_tree.tag_configure("expired", background="#f8d7da")
        self.exp_tree.tag_configure("soon", background="#fff3cd")

        ttk.Label(tab, text="Low stock", style="Title.TLabel").pack(anchor="w", padx=8)
        f2, self.low_tree = make_tree(tab, ("Medicine", "Batch", "Qty", "Reorder level"), [200, 80, 60, 110])
        f2.pack(fill="both", expand=True, padx=6, pady=4)

    def load_alerts(self):
        try:
            days = int(self.exp_days.get())
        except ValueError:
            days = 30
        self.exp_tree.delete(*self.exp_tree.get_children())
        for a in self.db.expiry_alerts(days):
            self.exp_tree.insert("", "end", values=a, tags=("expired" if a[4] < 0 else "soon",))
        self.low_tree.delete(*self.low_tree.get_children())
        for r in self.db.low_stock():
            self.low_tree.insert("", "end", values=tuple(r))

    # ----------------------------------------------------------- forecast tab
    def build_forecast_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Demand Forecast")
        top = ttk.Frame(tab)
        top.pack(fill="x", padx=6, pady=6)
        self.fc_window = tk.StringVar(value="14")
        self.fc_horizon = tk.StringVar(value="7")
        ttk.Label(top, text="History window (days):").pack(side="left")
        ttk.Entry(top, textvariable=self.fc_window, width=5).pack(side="left", padx=4)
        ttk.Label(top, text="Forecast next (days):").pack(side="left", padx=(10, 0))
        ttk.Entry(top, textvariable=self.fc_horizon, width=5).pack(side="left", padx=4)
        ttk.Button(top, text="Run forecast", command=self.load_forecast).pack(side="left", padx=10)

        f, self.fc_tree = make_tree(
            tab, ("Medicine", "In stock", "Sold (window)", "Avg/day", "Forecast", "Action"),
            [200, 80, 110, 80, 80, 180])
        f.pack(fill="both", expand=True, padx=6, pady=4)
        self.fc_tree.tag_configure("order", background="#fff3cd")

    def load_forecast(self):
        try:
            w, h = max(1, int(self.fc_window.get())), max(1, int(self.fc_horizon.get()))
        except ValueError:
            w, h = 14, 7
        self.fc_tree.delete(*self.fc_tree.get_children())
        for r in self.db.forecast(w, h):
            need = r["forecast"] > r["quantity"]
            action = f"Order ~{int(r['forecast'] - r['quantity'])} more" if need else "OK"
            self.fc_tree.insert("", "end",
                                values=(r["name"], r["quantity"], r["sold"], r["avg_daily"],
                                        int(r["forecast"]), action),
                                tags=("order",) if need else ())

    # ---------------------------------------------------------- suppliers tab
    def build_suppliers_tab(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Suppliers")
        form = ttk.LabelFrame(tab, text="Add supplier")
        form.pack(fill="x", padx=6, pady=6)
        self.sv = {k: tk.StringVar() for k in ("Name", "Phone", "Email")}
        for i, k in enumerate(self.sv):
            ttk.Label(form, text=k + ":").grid(row=0, column=i * 2, padx=4, pady=8)
            ttk.Entry(form, textvariable=self.sv[k], width=20).grid(row=0, column=i * 2 + 1, padx=4)
        ttk.Button(form, text="Add", command=self.add_supplier).grid(row=0, column=6, padx=8)
        ttk.Button(form, text="Delete selected", command=self.del_supplier).grid(row=0, column=7, padx=4)

        f, self.sup_tree = make_tree(tab, ("ID", "Name", "Phone", "Email"), [40, 220, 120, 220])
        f.pack(fill="both", expand=True, padx=6, pady=4)

    def load_suppliers(self):
        self.sup_tree.delete(*self.sup_tree.get_children())
        for s in self.db.get_suppliers():
            self.sup_tree.insert("", "end", iid=str(s["supplier_id"]),
                                 values=(s["supplier_id"], s["name"], s["phone"], s["email"]))

    def add_supplier(self):
        name = self.sv["Name"].get().strip()
        if not name:
            return messagebox.showerror("Invalid", "Supplier name is required.")
        try:
            self.db.add_supplier(name, self.sv["Phone"].get().strip(), self.sv["Email"].get().strip())
        except sqlite3.IntegrityError:
            return messagebox.showerror("Error", "Supplier already exists.")
        for v in self.sv.values():
            v.set("")
        self.refresh_all()

    def del_supplier(self):
        iid = self.selected(self.sup_tree)
        if iid and messagebox.askyesno("Confirm", "Delete this supplier?"):
            self.db.delete_supplier(int(iid))
            self.refresh_all()
