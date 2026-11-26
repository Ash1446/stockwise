import sqlite3
c = sqlite3.connect("data/stockwise.db")
for name, sql in c.execute("select name, sql from sqlite_master where type='table' and name in ('forecasts','items','item_settings','sales','expected_demand')"):
    print(sql, "\n")
print("forecasts sample:", c.execute("select * from forecasts limit 2").fetchall())
print("item_settings sample:", c.execute("select * from item_settings limit 2").fetchall())
