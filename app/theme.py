"""Shared visual components for Stockwise pages (cards, KPIs, badges, tables)."""
from __future__ import annotations

import html

import streamlit as st

CSS = """
<style>
.sw-eyebrow,.sw-pill,.sw-label,.sw-tbl th{font-family:ui-monospace,Consolas,monospace;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:#6b7686;}
.sw-head{margin-bottom:18px;padding-bottom:16px;border-bottom:1px solid #e6e8ec;}
.sw-row{display:flex;gap:10px;align-items:center;margin-bottom:8px;}
.sw-pill{display:inline-flex;gap:6px;align-items:center;border:1px solid #e6e8ec;border-radius:99px;padding:3px 10px;background:#fff;}
.sw-head h1{font-size:28px;letter-spacing:-.02em;margin:0 0 4px 0;padding:0;color:#0f1b2d;}
.sw-head p{color:#6b7686;margin:0;}
.sw-kpi{background:#fff;border:1px solid #e6e8ec;border-radius:16px;padding:18px 20px;box-shadow:0 1px 2px rgba(15,27,45,.04);}
.sw-metric{font-size:30px;font-weight:700;margin:8px 0 2px 0;letter-spacing:-.02em;color:#0f1b2d;}
.sw-metric.g{color:#15803d;}.sw-metric.a{color:#b45309;}.sw-metric.r{color:#dc2626;}
.sw-sub{color:#6b7686;font-size:12.5px;}
div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border:1px solid #e6e8ec !important;border-radius:16px;box-shadow:0 1px 2px rgba(15,27,45,.04);}
.sw-ct{font-size:15px;font-weight:600;color:#0f1b2d;margin:0;}
.sw-cs{color:#6b7686;font-size:12.5px;margin:2px 0 8px 0;}
.sw-key{display:grid;gap:10px;padding-top:18px;font-size:13.5px;color:#1f2937;}
.sw-key i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px;}
.sw-tbl{overflow:auto;}
.sw-tbl table{width:100%;border-collapse:collapse;text-align:left;font-size:13.5px;}
.sw-tbl th{background:#f4f6f9;padding:11px 14px;font-weight:500;}
.sw-tbl td{padding:12px 14px;border-top:1px solid #e6e8ec;color:#1f2937;}
.sw-tbl td small{color:#6b7686;}
.sw-b{display:inline-block;padding:3px 10px;border-radius:99px;font-size:11px;font-weight:600;}
.sw-b-ok{background:#dcfce7;color:#15803d;}
.sw-b-warn{background:#fef3c7;color:#b45309;}
.sw-b-bad{background:#fee2e2;color:#b91c1c;}
.sw-b-dead{background:#fecaca;color:#7f1d1d;}
.sw-b-low{background:#eef2ff;color:#3730a3;}
.sw-b-none{background:#e5e7eb;color:#4b5563;}
</style>
"""

STATUS_BADGE = {"Healthy": "ok", "Low": "warn", "Critical": "bad", "Out of stock": "dead", "No count": "none"}
SEVERITY_BADGE = {"High": "bad", "Medium": "warn", "Low": "low"}


def esc(x) -> str:
    return html.escape(str(x))


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle_html: str, demo: bool = False) -> None:
    pill = '<span class="sw-pill">Demo data</span>' if demo else ""
    st.markdown(
        f'<div class="sw-head"><div class="sw-row"><span class="sw-eyebrow">{esc(eyebrow)}</span>{pill}</div>'
        f'<h1>{esc(title)}</h1><p>{subtitle_html}</p></div>',
        unsafe_allow_html=True)


def kpi(label: str, value, sub: str = "", tone: str = "") -> str:
    return (f'<div class="sw-kpi"><span class="sw-label">{esc(label)}</span>'
            f'<div class="sw-metric {tone}">{esc(value)}</div><div class="sw-sub">{esc(sub)}</div></div>')


def card_title(title: str, sub: str = "") -> None:
    st.markdown(f'<div class="sw-ct">{esc(title)}</div><div class="sw-cs">{esc(sub)}</div>',
                unsafe_allow_html=True)


def badge(text: str, kind: str) -> str:
    return f'<span class="sw-b sw-b-{kind}">{esc(text)}</span>'


def status_badge(status: str) -> str:
    return badge(status, STATUS_BADGE.get(status, "none"))


def severity_badge(sev: str) -> str:
    return badge(sev, SEVERITY_BADGE.get(sev, "low"))


def key_list(rows) -> str:
    """rows: (colour, label, count, percent)"""
    items = "".join(f'<div><i style="background:{c}"></i>{esc(l)}: <b>{n} ({p}%)</b></div>' for c, l, n, p in rows)
    return f'<div class="sw-key">{items}</div>'


def table(headers, rows) -> str:
    """rows is a list of lists of ready-made HTML cells (escape values with esc())."""
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="sw-tbl"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'