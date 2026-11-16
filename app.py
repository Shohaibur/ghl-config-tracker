"""GHL Explorer: click a button, see the latest data from your GHL sub-account.

Read-only. Nothing on this page changes GHL.
Run:  streamlit run app.py
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from ghl.client import GHLClient, GHLError
from ghl.collectors import MODELS, get_custom_fields, get_pipelines

MODEL_LABELS = {"contact": "Contact", "opportunity": "Opportunity", "business": "Company (business)"}

st.set_page_config(page_title="GHL Explorer", layout="wide")
st.title("GHL Explorer")
st.caption("Read-only view of your GoHighLevel sub-account. Nothing here changes GHL.")


@st.cache_resource
def get_client() -> GHLClient:
    return GHLClient()


try:
    client = get_client()
except GHLError as e:
    st.error(str(e))
    st.stop()

# Show the end of the location ID so you can confirm it's the test account
st.sidebar.markdown(f"**Location:** `...{client.location_id[-6:]}`")
view = st.sidebar.radio("What do you want to see?", ["Custom fields", "Pipelines"])


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


# ---------- Custom fields ----------
if view == "Custom fields":
    model = st.sidebar.selectbox("Object", MODELS, format_func=MODEL_LABELS.get)
    key = f"fields_{model}"
    st.subheader(f"{MODEL_LABELS[model]} custom fields")

    if st.button("Load latest from GHL", type="primary"):
        load(key, lambda: get_custom_fields(client, model))

    fields = st.session_state.get(key)
    if fields is None:
        st.info("Click the button to load the fields.")
    else:
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

# ---------- Pipelines ----------
elif view == "Pipelines":
    st.subheader("Pipelines and stages")

    if st.button("Load latest from GHL", type="primary"):
        load("pipelines", lambda: get_pipelines(client))

    pipelines = st.session_state.get("pipelines")
    if pipelines is None:
        st.info("Click the button to load the pipelines.")
    else:
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
