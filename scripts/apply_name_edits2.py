import sys, shutil, py_compile
sys.path.insert(0, ".")
from stockwise import catalog

first = next(iter(catalog.CATALOG.values()))
print("catalogue fields:", sorted(first))

EDITS = {
 r"app\views\stock_counts.py": [
  ('from app import ui', 'from app import ui\nfrom stockwise import catalog'),
  ('ids = sorted(items["item_id"])',
   'ids = sorted((i for i in items["item_id"] if i in catalog.CATALOG), key=ui.name_of)'),
  ('item = st.selectbox("Item", ids, index=ids.index(wanted) if wanted in ids else 0)',
   'item = st.selectbox("Item", ids, index=ids.index(wanted) if wanted in ids else 0, format_func=ui.name_of)\n    st.caption(f"Item code: {item}")'),
 ],
 r"app\views\shrinkage.py": [
  ('from stockwise import auth', 'from stockwise import auth, catalog'),
  ('date_str = day.strftime("%Y-%m-%d")',
   'date_str = day.strftime("%Y-%m-%d")\n        st.markdown(f"**{ui.name_of(item)}**")\n        st.caption(f"Item code: {item}")'),
  ('f"Saved: {item} on {day:%d %b %Y} marked {new_status}."',
   'f"Saved: {ui.name_of(item)} on {day:%d %b %Y} marked {new_status}."'),
 ],
}
if "price" in first:
    EDITS[r"app\views\shrinkage.py"].append(
      ('flags["price"] = flags["item_id"].map(snap["price"])',
       'flags["price"] = flags["item_id"].map(lambda i: catalog.CATALOG.get(i, {}).get("price")).astype(float)'))
else:
    print("NOTE: no 'price' field in the catalogue, so the Shrinkage value is left unchanged")

for path, edits in EDITS.items():
    shutil.copy(path, path + ".bak_names2")
    text = open(path, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in edits:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new.replace("\n", nl))
            print("OK     ", path, "|", old[:55])
        else:
            print("SKIPPED", path, f"(found {n}x)", "|", old[:55])
    open(path, "w", encoding="utf-8", newline="").write(text)
    py_compile.compile(path, doraise=True)
print("all files compile")
