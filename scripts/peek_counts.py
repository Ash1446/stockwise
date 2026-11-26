import sqlite3
c = sqlite3.connect(r"data\stockwise.db")
print(c.execute("select count(*), min(date), max(date) from stock_counts").fetchall())
print(c.execute("select item_id, date, counted_stock from stock_counts where date > '2016-05-22'").fetchall())
