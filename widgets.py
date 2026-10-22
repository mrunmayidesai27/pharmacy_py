"""Reusable Tkinter widgets: table builder and the medicine add/edit dialog."""

import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk


def make_tree(parent, columns, widths=None):
    """Return (frame, treeview) with a vertical scrollbar."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
    for i, c in enumerate(columns):
        tree.heading(c, text=c)
        tree.column(c, width=(widths[i] if widths else 110), anchor="w")
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    return frame, tree


class MedicineDialog(tk.Toplevel):
    """Popup used for both adding and editing a medicine."""

    def __init__(self, parent, db, record=None):
        super().__init__(parent)
        self.db, self.record, self.result = db, record, False
        self.title("Edit Medicine" if record else "Add Medicine")
        self.resizable(False, False)
        self.grab_set()

        self.suppliers = db.get_suppliers()
        sup_names = [s["name"] for s in self.suppliers]

        labels = [
            "Name", "Batch No", "Category", "Price", "Quantity",
            "Reorder level", "Expiry (YYYY-MM-DD)", "Supplier",
        ]
        self.vars = {l: tk.StringVar() for l in labels}
        for i, l in enumerate(labels):
            ttk.Label(self, text=l).grid(row=i, column=0, sticky="w", padx=10, pady=4)
            if l == "Supplier":
                w = ttk.Combobox(self, textvariable=self.vars[l], values=sup_names, state="readonly")
            else:
                w = ttk.Entry(self, textvariable=self.vars[l], width=28)
            w.grid(row=i, column=1, padx=10, pady=4)

        if record:
            self.vars["Name"].set(record["name"])
            self.vars["Batch No"].set(record["batch_no"])
            self.vars["Category"].set(record["category"] or "")
            self.vars["Price"].set(record["price"])
            self.vars["Quantity"].set(record["quantity"])
            self.vars["Reorder level"].set(record["reorder_level"])
            self.vars["Expiry (YYYY-MM-DD)"].set(record["expiry_date"])
            self.vars["Supplier"].set(record["supplier"] if record["supplier"] != "-" else "")
        else:
            self.vars["Reorder level"].set(10)
            self.vars["Quantity"].set(0)

        ttk.Button(self, text="Save", command=self.save).grid(
            row=len(labels), column=0, columnspan=2, pady=10
        )

    def save(self):
        v = {k: x.get().strip() for k, x in self.vars.items()}
        try:
            if not v["Name"] or not v["Batch No"]:
                raise ValueError("Name and Batch No are required.")
            price = float(v["Price"])
            qty = int(v["Quantity"])
            reorder = int(v["Reorder level"])
            if price < 0 or qty < 0 or reorder < 0:
                raise ValueError("Price, quantity and reorder level cannot be negative.")
            datetime.strptime(v["Expiry (YYYY-MM-DD)"], "%Y-%m-%d")
            sup_id = next(
                (s["supplier_id"] for s in self.suppliers if s["name"] == v["Supplier"]), None
            )
            args = (v["Name"], v["Batch No"], v["Category"], price, qty, reorder,
                    v["Expiry (YYYY-MM-DD)"], sup_id)
            if self.record:
                self.db.update_medicine(self.record["medicine_id"], *args)
            else:
                self.db.add_medicine(*args)
            self.result = True
            self.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "That medicine + batch already exists.", parent=self)
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e), parent=self)
