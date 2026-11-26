"""Demand forecast and Shrinkage shown inside the teammate's HTML page, with real data injected."""
import json

import streamlit as st
import streamlit.components.v1 as components

from app import htmlpage

FORECAST_JS = r"""
(function () {
const FC = __FC__;
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
function fresh(sel) { const el = $(sel); const n = el.cloneNode(false); el.parentNode.replaceChild(n, el); return n; }
$$('#view-forecast .pill, #view-shrinkage .pill').forEach(e => e.textContent = 'Live data');
const prod = fresh('#fc-product'), per = fresh('#fc-period');
prod.innerHTML = FC.items.map((p, i) => `<option value="${i}">${esc(p.name)} (${esc(p.category)})</option>`).join('');
per.innerHTML = [14, 28, 60].map(d => `<option value="${d}"${d === 28 ? ' selected' : ''}>Last ${d} days</option>`).join('');
const lab = per.parentElement.querySelector('.label'); if (lab) lab.textContent = 'History shown';
const head = $('#view-forecast .head p');
if (head) head.textContent = 'Compare recent demand with the next 7 days, then read it against the stock you hold.';
const muted = $$('#view-forecast .stats .muted'); if (muted[0]) muted[0].textContent = 'Next 7 days';
const note = $('#view-forecast .note span:last-child');
if (note) note.innerHTML = '<b>XGBoost 7-day forecast.</b> The model forecasts 7 days ahead. The history selector only changes how much past demand is shown.';
function render() {
  const p = FC.items[+prod.value], H = +per.value;
  const hist = p.hist.slice(-H), hl = p.hl.slice(-H), n = p.fc.length;
  lineChart($('#fc-chart'), [
    { data: [...hist, ...Array(n).fill(null)], cls: 'a' },
    { data: [...Array(hist.length - 1).fill(null), hist[hist.length - 1], ...p.fc], cls: 'b' }],
    [...hl, ...p.fl], hist.length - 1);
  $('#fc-title').textContent = `${p.name} - last ${hist.length} days and the next ${n} days, units per day`;
  const avgH = mean(p.hist.slice(-14)), avgF = mean(p.fc);
  const down = avgF < avgH, delta = avgH > 0 ? Math.round(Math.abs(avgF - avgH) / avgH * 100) : 0;
  $('#fc-trend').className = `trend ${down ? 'dn' : 'up'}`; $('#fc-trend').innerHTML = icon(down ? 'down' : 'up');
  $('#fc-text').innerHTML = avgH > 0
    ? `Projected demand for <b>${esc(p.name)}</b> is <b>${down ? 'down' : 'up'} ${delta}%</b> versus the last 14 days, averaging about ${avgF.toFixed(1)} units a day.`
    : `${esc(p.name)} sold nothing in the last 14 days. The forecast averages about ${avgF.toFixed(1)} units a day.`;
  let c;
  if (p.stock === null) c = 'No stock count has been recorded for this item yet.';
  else {
    const cover = avgF > 0 ? (p.stock / avgF) : null;
    c = `Stock on hand is <b>${p.stock} units</b>` + (cover === null ? '.' : `, roughly <b>${cover.toFixed(1)} days</b> of cover at forecast demand.`);
    if (p.target !== null) c += `<br>Suggested order: <b>${Math.max(0, Math.round(p.target - p.stock))} units</b> (target ${Math.round(p.target)} minus on hand).`;
    if (p.shelf !== null && cover !== null && cover > p.shelf) c += `<br><span class="badge s-low">Perishable: stock outlasts ${Math.round(p.shelf)}-day shelf life</span>`;
  }
  $('#fc-cover').innerHTML = c;
  const cls = { 'Healthy': 's-healthy', 'Low': 's-low', 'Critical': 's-low', 'Out of stock': 's-out' };
  $('#fc-status').innerHTML = `<span class="badge ${cls[p.status] || ''}">${esc(p.status)}</span>`;
  $('#fc-units').textContent = Math.round(p.fc.reduce((x, y) => x + y, 0));
  $('#fc-reorder').textContent = p.min === null ? '-' : Math.round(p.min);
}
prod.addEventListener('change', render); per.addEventListener('change', render);
render(); showView('forecast');
})();
"""

SHRINK_JS = r"""
(function () {
const SH = __SH__;
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
$$('#view-shrinkage .pill').forEach(e => e.textContent = 'Live data');
const head = $('#view-shrinkage .head p');
if (head) head.textContent = 'Each flag is a day when more stock disappeared than forecast demand can explain, judged against that item\'s own usual variability.';
const L = $$('#view-shrinkage .grid4 .label'), M = $$('#view-shrinkage .grid4 .muted');
['Flagged days', 'Expected units', 'Counted units', 'Variance'].forEach((t, i) => { if (L[i]) L[i].textContent = t; });
[SH.items + ' items affected', 'Counted plus estimated missing', 'On the flagged days'].forEach((t, i) => { if (M[i]) M[i].textContent = t; });
const TH = $$('#view-shrinkage thead th');
['Product', 'Department', 'Counted before', 'Delivered', 'Sold', 'Expected stock', 'Counted', 'Variance', 'Severity / review'].forEach((t, i) => { if (TH[i]) TH[i].textContent = t; });
$('#sh-flagged').textContent = SH.flagged; $('#sh-exp').textContent = SH.expected; $('#sh-cnt').textContent = SH.counted;
$('#sh-var').textContent = SH.variance + ' units'; $('#sh-val').textContent = SH.value + ' at retail value';
const n = v => v === null ? '-' : v;
$('#sh-body').innerHTML = SH.rows.map(r => {
  const v = r.counted === null || r.expected === null ? null : r.counted - r.expected;
  const pct = v === null || r.expected <= 0 ? 0 : Math.floor(Math.abs(v) / r.expected * 100);
  return `<tr><td><b>${esc(r.name)}</b><br><small>${esc(r.id)} - ${esc(r.date)}</small></td><td>${esc(r.category)}</td>
    <td>${n(r.opening)}</td><td>${n(r.received)}</td><td>${n(r.sold)}</td><td>${n(r.expected)}</td><td>${n(r.counted)}</td>
    <td style="color:var(--${pct >= 50 ? 'red' : 'amber'})">${v === null ? '-' : v + ' (' + pct + '%)'}</td><td>${esc(r.severity)} - ${esc(r.review)}</td></tr>`;
}).join('');
showView('shrinkage');
})();
"""


def _page(view, role, js, key, payload):
    text = htmlpage.build(view, role)
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    tag = "<script>" + js.replace(key, data) + "</script>"
    i = text.rfind("</body>")
    return text[:i] + tag + text[i:] if i != -1 else text + tag


def role():
    return (st.session_state.get("user") or {}).get("role", "Cashier")


def forecast_page(payload):
    return _page("forecast", role(), FORECAST_JS, "__FC__", payload)


def shrinkage_page(payload):
    return _page("shrinkage", role(), SHRINK_JS, "__SH__", payload)


def forecast(payload, height=840):
    components.html(forecast_page(payload), height=height, scrolling=True)


def shrinkage(payload, n_rows):
    components.html(shrinkage_page(payload), height=330 + 64 * max(n_rows, 1), scrolling=True)