"""Builds the Dashboard and Shop pages from the teammate's frontend/index.html (same CSS, SVG charts and
cards) with real item names, pictures, rupee prices, stock and demand numbers injected."""
import json
import re
from pathlib import Path

import pandas as pd

from app import ui
from stockwise import catalog, images

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "index.html"
INIT_MARK = "/* ---------- init ---------- */"
INIT_RE = re.compile(r"renderDashboard\(\);\s*renderAttention\(\);\s*renderForecast\(\);\s*"
                     r"renderShrinkage\(\);\s*renderQueue\(\);\s*loadPhotos\(\);")
STATUS_MAP = {"Healthy": "Healthy", "Low": "Low stock", "Critical": "Low stock",
              "Out of stock": "Out of stock", "No count": "No count"}


class TemplateError(Exception):
    pass


CSS_OVERRIDE = """
/* ---- Stockwise: show one page body inside Streamlit ---- */
html,body{height:auto!important;overflow:auto!important;background:transparent!important}
#auth{display:none!important}
#app{display:block!important;height:auto!important}
main{overflow:visible!important;padding:8px 6px 48px!important}
.side{display:none!important}
.mini img{object-fit:contain!important;background:var(--tint)}
"""

JS = """
/* ---------- Stockwise real data ---------- */
const REAL = __REAL__;
Object.assign(TINTS, { Household: '#e4e9f5', Hobbies: '#fbe4ef' });
CATALOG.length = 0;
REAL.catalog.forEach(p => CATALOG.push(p));
thumb = function (p, cls = 'thumb') {
  const img = p.img ? `<img src="${p.img}" alt="${p.name}" loading="lazy" onerror="this.remove()">` : '';
  return `<div class="${cls}" style="--tint:${TINTS[p.category] || '#eef1f5'}"><span>${p.emoji}</span>${img}</div>`;
};
function __realInit() {
  const N = CATALOG.length;
  const admin = REAL.role === 'Admin';
  state.user = { name: admin ? 'Admin' : 'Cashier', role: admin ? 'Manager' : 'Cashier', email: '' };
  $('#auth').classList.add('hidden');
  $('#app').classList.remove('hidden');
  $('#total-sku-count').textContent = N;
  $('#cat-filter').insertAdjacentHTML('beforeend', '<option>Household</option><option>Hobbies</option>');
  renderDashboard();
  lineChart($('#dash-chart'), [{ data: REAL.pulse.actual, cls: 'a' }, { data: REAL.pulse.pred, cls: 'b' }], REAL.pulse.labels);
  const head = $('#view-dashboard .head p');
  if (head) head.textContent = REAL.dashSub;
  const sub = $('#m-total').nextElementSibling;
  if (sub) sub.textContent = 'Across ' + new Set(CATALOG.map(p => p.category)).size + ' categories';
  const cnt = s => CATALOG.filter(p => p.status === s).length;
  const h = cnt('Healthy'), l = cnt('Low stock');
  const hp = h / N * 100, lp = (h + l) / N * 100;
  $('#ring').style.background = `conic-gradient(var(--green) 0 ${hp}%,#f59e0b ${hp}% ${lp}%,var(--red) ${lp}% 100%)`;
  $('#ring div').innerHTML = `<span>${N}<small>SKUS</small></span>`;
  renderAttention();
  renderProducts();
  renderQueue();
  showView(REAL.view);
}
"""


def real_data(role, view):
    snap = ui.snapshot().sort_values("item_id").reset_index(drop=True)
    items = []
    for n, r in snap.iterrows():
        iid = r["item_id"]
        c = catalog.CATALOG[iid]
        stock = 0 if pd.isna(r["stock"]) else int(round(r["stock"]))
        items.append({
            "n": int(n), "id": iid, "name": c["name"], "pack": c["pack"], "category": c["group"],
            "emoji": c["emoji"], "img": images.thumb_uri(iid), "price": int(c["price"]),
            "stock": stock, "status": STATUS_MAP.get(r["status"], "Healthy"),
        })

    sales = ui.table("sales")
    exp = ui.table("expected_demand")
    ids = set(snap["item_id"])
    m = sales[sales["item_id"].isin(ids)].merge(
        exp[exp["item_id"].isin(ids)][["item_id", "date", "expected"]], on=["item_id", "date"])
    g = m.groupby("date")[["units_sold", "expected"]].sum().tail(14)
    pulse = {
        "actual": [int(round(v)) for v in g["units_sold"]],
        "pred": [int(round(v)) for v in g["expected"]],
        "labels": [f"{d.day} {d:%b}" for d in g.index],
    }
    latest = sales["date"].max()
    return {
        "role": role, "view": view, "catalog": items, "pulse": pulse,
        "dashSub": f"Latest data {latest:%d %b %Y}. All {len(items)} items: what is healthy, "
                   "what needs a reorder, and where records disagree.",
    }


def build(view, role):
    if not SRC.exists():
        raise TemplateError(f"{SRC} not found")
    text = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
    if INIT_MARK not in text:
        raise TemplateError("index.html has changed: the init marker was not found")
    if "</style>" not in text:
        raise TemplateError("index.html has changed: no style block found")
    text, n = INIT_RE.subn("__realInit();", text, count=1)
    if n != 1:
        raise TemplateError("index.html has changed: the start-up line was not found")
    payload = json.dumps(real_data(role, view), ensure_ascii=False).replace("</", "<\\/")
    text = text.replace(INIT_MARK, JS.replace("__REAL__", payload) + "\n" + INIT_MARK, 1)
    text = text.replace("</style>", "</style>\n<style>" + CSS_OVERRIDE + "</style>", 1)
    return text