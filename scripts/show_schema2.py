import sqlite3
c = sqlite3.connect("data/stockwise.db")
for name, sql in c.execute("select name, sql from sqlite_master where type='table' and name in ('detections','investigations','stock_counts','deliveries','write_offs')"):
    print(sql, "\n")
print("detections flagged sample:", c.execute("select * from detections where flag=1 limit 2").fetchall())
print("investigations sample:", c.execute("select * from investigations limit 2").fetchall())
print("investigation statuses:", c.execute("select status, count(*) from investigations group by status").fetchall())
