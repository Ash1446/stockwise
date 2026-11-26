import sqlite3
c = sqlite3.connect("data/stockwise.db")
for name, sql in c.execute("select name, sql from sqlite_master where type='table' and name in ('transactions','transaction_items','day_close')"):
    print(sql, "\n")
print("sales last date:", c.execute("select max(date) from sales").fetchone()[0])
print("stock_counts last date:", c.execute("select max(date) from stock_counts").fetchone()[0])
print("deliveries last date:", c.execute("select max(date) from deliveries").fetchone()[0])
print("transactions rows:", c.execute("select count(*) from transactions").fetchone()[0])
print("purchase limits set:", c.execute("select count(*) from item_settings where purchase_limit is not null").fetchone()[0])
