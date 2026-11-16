"""GHL Explorer: click a button, see the latest data from your GHL sub-account.

Read-only. Nothing on this page changes GHL.
Run:  streamlit run app.py
"""

import hmac
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from collect import take_snapshot
from diff import compare, list_snapshots, render_report
from ghl.client import GHLClient, GHLError
from ghl.collectors import (MODELS, field_value, get_companies, get_company_record, get_custom_fields,
                            get_opportunities, get_pipelines)

MODEL_LABELS = {"contact": "Contact", "opportunity": "Opportunity", "business": "Company (business)"}
SETTINGS = ("GHL_TOKEN", "GHL_LOCATION_ID", "APP_USERNAME", "APP_PASSWORD")

st.set_page_config(page_title="GHL Explorer", layout="wide")
st.title("GHL Explorer")
st.caption("Read-only view of your GoHighLevel sub-account. Nothing here changes GHL.")


def load_settings() -> None:
    """On your PC settings come from .env. Online (Streamlit Cloud) they come from Secrets."""
    load_dotenv()
    try:
        for k in SETTINGS:
            if k in st.secrets and not os.getenv(k):
                os.environ[k] = str(st.secrets[k])
    except Exception:
        pass  # no Secrets file: normal on your PC


def require_login() -> bool:
    """Show a login screen if APP_USERNAME and APP_PASSWORD are set. Stops the page until logged in.
    Returns True if a login is configured."""
    user, pw = os.getenv("APP_USERNAME"), os.getenv("APP_PASSWORD")
    if not user or not pw:
        return False
    if st.session_state.get("logged_in"):
        return True

    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        if hmac.compare_digest(u.encode(), user.encode()) and hmac.compare_digest(p.encode(), pw.encode()):
            st.session_state["logged_in"] = True
            st.rerun()
        st.error("Wrong username or password.")
    st.stop()


load_settings()
login_enabled = require_login()


@st.cache_resource
def get_client() -> GHLClient:
    return GHLClient()


try:
    client = get_client()
except GHLError as e:
    st.error(str(e))
    st.stop()



def option_text(o) -> str:
    if isinstance(o, dict):
        return str(o.get("label") or o.get("value") or o.get("name") or "")
    return str(o)


def load(key: str, fn):
    """Run fn() and keep the result (plus the time) in the session."""
    try:
        st.session_state[key] = fn()
        st.session_state[key + "_at"] = datetime.now().strftime("%H:%M:%S")
    except GHLError as e:
        st.error(str(e))


# ---------- Configuration: Custom fields ----------
def custom_fields_page():
    model = st.session_state.get("model", MODELS[0])  # chosen in the sidebar menu
    key = f"fields_{model}"
    st.subheader(f"{MODEL_LABELS[model]} custom fields")

    if st.button("Load latest from GHL", type="primary"):
        load(key, lambda: get_custom_fields(client, model))

    fields = st.session_state.get(key)
    if fields is None:
        st.info("Click the button to load the fields.")
        return
    rows = [{
        "Name": f.get("name"),
        "Key": f.get("fieldKey"),
        "Type": f.get("dataType"),
        "Options": ", ".join(option_text(o) for o in (f.get("picklistOptions") or [])),
        "ID": f.get("id"),
    } for f in fields]
    df = pd.DataFrame(rows, columns=["Name", "Key", "Type", "Options", "ID"])

    search = st.text_input("Search", placeholder="Type part of a name, key or type")
    if search:
        mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, regex=False)).any(axis=1)
        df = df[mask]

    st.caption(f"{len(df)} of {len(rows)} fields · loaded at {st.session_state[key + '_at']}")
    st.dataframe(df, hide_index=True)
    st.download_button("Download CSV", df.to_csv(index=False), file_name=f"{model}_custom_fields.csv", mime="text/csv")


# ---------- Configuration: Pipelines ----------
def pipelines_page():
    st.subheader("Pipelines and stages")

    if st.button("Load latest from GHL", type="primary"):
        load("pipelines", lambda: get_pipelines(client))

    pipelines = st.session_state.get("pipelines")
    if pipelines is None:
        st.info("Click the button to load the pipelines.")
        return
    st.caption(f"{len(pipelines)} pipelines · loaded at {st.session_state['pipelines_at']}")
    for p in pipelines:
        stages = p.get("stages") or []
        with st.expander(f"{p.get('name')}  ·  {len(stages)} stages"):
            st.caption(f"Pipeline ID: {p.get('id')}")
            stage_df = pd.DataFrame(
                [{"#": i + 1, "Stage": s.get("name"), "ID": s.get("id")} for i, s in enumerate(stages)],
                columns=["#", "Stage", "ID"],
            )
            st.dataframe(stage_df, hide_index=True)


# ---------- Monitor: Change log ----------
def change_log_page():
    st.subheader("Change log")
    st.caption("Take a snapshot (read-only), then compare any two saved snapshots.")

    if st.button("Take a new snapshot now", type="primary"):
        try:
            path = take_snapshot(client, log=lambda *_: None)
            st.success(f"Saved snapshot {path.name}")
        except GHLError as e:
            st.error(str(e))

    snaps = list_snapshots()
    if len(snaps) < 2:
        st.info("You need at least 2 snapshots to compare. Click the button above (or run collect.py) "
                "before and after a change.")
        return
    names = [s.name for s in snaps]
    by_name = dict(zip(names, snaps))
    col1, col2 = st.columns(2)
    # key includes the count, so after a new snapshot the dropdowns jump to the newest two
    old_name = col1.selectbox("From (older)", names, index=len(names) - 2, key=f"old_{len(names)}")
    new_name = col2.selectbox("To (newer)", names, index=len(names) - 1, key=f"new_{len(names)}")

    sections = compare(by_name[old_name], by_name[new_name])
    if not sections:
        st.success("No changes between these two snapshots.")
    else:
        st.markdown(f"**{sum(len(c) for _, c in sections)} change(s)**")
        icon = {"Added": "🟢", "Deleted": "🔴", "Renamed": "🟡", "Changed": "🟡", "Reordered": "🟡"}
        for title, changes in sections:
            st.markdown(f"#### {title}")
            for kind, text in changes:
                st.markdown(f"{icon.get(kind, '•')} **{kind}:** {text}")

    st.download_button(
        "Download report",
        render_report(by_name[old_name], by_name[new_name], sections),
        file_name=f"changes_{old_name}_to_{new_name}.md",
        mime="text/markdown",
    )


# ---------- Records: Companies ----------
COMPANY_FIELDS = [  # shown first, in this order; everything else goes under "All company fields"
    ("dealer_id", "Dealer ID"), ("account_status", "Account status"),
    ("active_acquisitions", "Active ACQ"), ("active_recall", "Active RCL"), ("active_bcp", "Active BCP"),
    ("active_monthly_value", "Active monthly value"), ("rollup_last_updated", "Rollup last updated"),
    ("dealer_group", "Dealer group"), ("contracting_entity", "Contracting entity"),
]
INVOICE_ICON = {"paid": "✅ Paid", "sent": "⏳ Sent", "partially paid": "🟡 Partially paid", "past due": "⚠️ Past due"}


def show(v) -> str:
    if isinstance(v, dict) and "value" in v:
        v = v["value"]
    if isinstance(v, list):
        v = ", ".join(str(x) for x in v)
    return "" if v is None else str(v)


def load_records():
    """Companies + all opportunities + the lookups needed to read them."""
    fields = get_custom_fields(client, "opportunity")
    pipes = get_pipelines(client)
    return {
        "companies": get_companies(client),
        "opps": get_opportunities(client),
        "field_keys": {f["id"]: (f.get("fieldKey") or "").removeprefix("opportunity.") for f in fields},
        "pipeline_names": {p["id"]: p.get("name") for p in pipes},
        "stage_names": {s["id"]: s.get("name") for p in pipes for s in (p.get("stages") or [])},
    }


def companies_page():
    st.subheader("Companies")
    st.caption("Live from GHL. Opportunities are matched to a company by Dealer ID.")

    if st.button("Load latest from GHL", type="primary"):
        load("records", load_records)
        st.session_state["company_records"] = {}  # clear cached company details

    data = st.session_state.get("records")
    if data is None:
        st.info("Click the button to load companies and opportunities.")
        return
    companies = data["companies"]
    if not companies:
        st.info("No companies found in this account.")
        return
    st.caption(f"{len(companies)} companies · {len(data['opps'])} opportunities · loaded at {st.session_state['records_at']}")

    by_id = {c["id"]: c for c in companies}
    company_id = st.selectbox("Company", list(by_id), format_func=lambda i: by_id[i].get("name") or i)

    # Company details (one request per company, then kept for this session)
    cache = st.session_state.setdefault("company_records", {})
    if company_id not in cache:
        try:
            cache[company_id] = get_company_record(client, company_id)
        except GHLError as e:
            st.error(str(e))
            return
    props = cache[company_id].get("properties") or {}

    st.markdown("#### Company details")
    cols = st.columns(3)
    for i, (key, label) in enumerate(COMPANY_FIELDS):
        cols[i % 3].markdown(f"**{label}**  \n{show(props.get(key)) or '—'}")
    others = {k: show(v) for k, v in props.items() if k not in dict(COMPANY_FIELDS)}
    if others:
        with st.expander(f"All company fields ({len(props)})"):
            st.dataframe(pd.DataFrame(sorted(others.items()), columns=["Field", "Value"]), hide_index=True)

    # Opportunities with the same Dealer ID
    dealer = show(props.get("dealer_id")).strip()
    st.markdown("#### Opportunities")
    if not dealer:
        st.info("This company has no Dealer ID, so its opportunities can't be matched.")
        return
    rows = []
    for o in data["opps"]:
        v = {data["field_keys"].get(cf.get("id")): field_value(cf) for cf in (o.get("customFields") or [])}
        if show(v.get("dealer_id")).strip() != dealer:
            continue
        invoice = show(v.get("invoice_status"))
        rows.append({
            "Name": o.get("name"),
            "Pipeline": data["pipeline_names"].get(o.get("pipelineId"), ""),
            "Stage": data["stage_names"].get(o.get("pipelineStageId"), ""),
            "Status": o.get("status"),
            "Product": show(v.get("product")),
            "Deal phase": show(v.get("deal_phase")),
            "Invoice": INVOICE_ICON.get(invoice.lower(), invoice),
            "Amount due": show(v.get("amount_due")),
            "Invoice due": show(v.get("invoice_due_date")),
            "Past due": "⚠️" if str(v.get("past_due_flag")).lower() in ("true", "yes", "['yes']") else "",
        })
    if not rows:
        st.info(f"No opportunities have Dealer ID {dealer}.")
        return

    # Billing at a glance
    invoices = [r["Invoice"] for r in rows if r["Invoice"]]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Opportunities", len(rows))
    c2.metric("Invoices paid", sum(i.startswith("✅") for i in invoices))
    c3.metric("Invoices unpaid", sum(not i.startswith("✅") for i in invoices))
    c4.metric("Past due", sum(r["Invoice"].startswith("⚠️") or bool(r["Past due"]) for r in rows))

    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True)
    st.download_button("Download CSV", df.to_csv(index=False), file_name=f"opportunities_{dealer}.csv", mime="text/csv")


# ---------- Sidebar menu ----------
fields_pg = st.Page(custom_fields_page, title="Custom fields", icon=":material/list_alt:", url_path="fields", default=True)
pipelines_pg = st.Page(pipelines_page, title="Pipelines", icon=":material/view_kanban:", url_path="pipelines")
companies_pg = st.Page(companies_page, title="Companies", icon=":material/apartment:", url_path="companies")
changes_pg = st.Page(change_log_page, title="Change log", icon=":material/history:", url_path="changes")

# Streamlit's automatic menu always sits at the top, so we hide it and build our own
current = st.navigation([fields_pg, pipelines_pg, companies_pg, changes_pg], position="hidden")

with st.sidebar:
    # Show the end of the location ID so you can confirm it's the right account
    st.markdown(f"**Location:** `...{client.location_id[-6:]}`")

    st.caption("CONFIGURATION")
    st.page_link(fields_pg)
    if current.url_path == fields_pg.url_path:
        st.selectbox("Object", MODELS, format_func=MODEL_LABELS.get, key="model")
    st.page_link(pipelines_pg)

    st.caption("RECORDS")
    st.page_link(companies_pg)

    st.caption("MONITOR")
    st.page_link(changes_pg)

    st.divider()
    if not login_enabled:
        st.warning("No login set. Fine on your PC, but always set one online.")
    elif st.button("Log out"):
        st.session_state["logged_in"] = False
        st.rerun()

current.run()
