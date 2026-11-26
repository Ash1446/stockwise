import sqlite3
c = sqlite3.connect("data/stockwise.db")
print(c.execute("select category, count(*) from items group by category").fetchall())
print()
for r in c.execute("select item_id, category, round(mean_daily_units,1) from items order by item_id"):
    print(r[0], r[1], r[2])
