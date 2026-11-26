import py_compile

EDITS = {
 r"app\views\inventory.py": [
  (r'view[view["item_id"].str.contains(search.strip(), case=False, regex=False)]',
   r'view[view["item_id"].str.contains(search.strip(), case=False, regex=False) | view["item_id"].map(ui.name_of).str.contains(search.strip(), case=False, regex=False)]'),
  (r'view.sort_values("item_id")',
   r'view.loc[view["item_id"].map(ui.name_of).sort_values().index]'),
  (r'st.markdown(f"**{r.item_id}**")',
   r'st.markdown(f"**{ui.name_of(r.item_id)}**  \n:gray[{r.item_id}]")'),
  (r'st.title(item_id)',
   r'st.title(ui.name_of(item_id)); st.caption(item_id)'),
 ],
 r"stockwise\eod.py": [
  (r'"item_id", "item", "qty"', r'"item", "item_id", "qty"'),
  (r'mode, item_id, name, int(qty)', r'mode, name, item_id, int(qty)'),
 ],
 r"app\views\sales_analysis.py": [
  (r'"payment_mode", "item_id", "name", "qty"', r'"payment_mode", "name", "item_id", "qty"'),
 ],
}

for path, edits in EDITS.items():
    text = open(path, encoding="utf-8", newline="").read()
    for old, new in edits:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print("OK     ", path, "|", old[:50])
        else:
            print("SKIPPED", path, f"(found {n}x)", "|", old[:50])
    open(path, "w", encoding="utf-8", newline="").write(text)
    py_compile.compile(path, doraise=True)
print("all files compile")
