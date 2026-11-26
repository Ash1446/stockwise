import shutil, sqlite3
shutil.copy(r"data\stockwise.db", r"data\stockwise.db.bak_strays")
c = sqlite3.connect(r"data\stockwise.db")
item, after = "FOODS_3_080", "2016-05-22"
for t in ("stock_counts", "deliveries", "detections", "investigations"):
    n = c.execute(f"DELETE FROM {t} WHERE item_id=? AND date>?", (item, after)).rowcount
    print(f"{t}: removed {n}")
c.commit()
print(c.execute("select count(*), max(date) from stock_counts").fetchall())
