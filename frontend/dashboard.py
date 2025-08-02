import streamlit as st
import pandas as pd
import psycopg2
import sys
import os
import plotly.express as px

# Allow importing from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import DB_CONFIG

DB_CONFIG = {
    "host":"localhost",
    "port": 5432,
    "dbname": "shipnest_schema",
    "user": "postgres", # <-- Load from .env
    "password": "admin" # <-- Load from .env
}


st.set_page_config(page_title="ShipNest Dashboard", layout="wide")
# === Fetch Data ===
@st.cache_data
def fetch_data():
    conn = psycopg2.connect(**DB_CONFIG)
    query = """
        SELECT
            s."createdAt"::date AS shipment_date,
            s.shipped,
            s.cost,
            o."shippingCourier",
            p.city AS destination_city
        FROM shipment s
        JOIN "order" o ON o.id = s."orderId"
        JOIN pii p ON p.id = s."shipToId"
    """
    df = pd.read_sql(query, conn)
    conn.close()
    df['shipment_date'] = pd.to_datetime(df['shipment_date'])
    return df

# Load data
df = fetch_data()

# === Defaults for filters ===
min_date = df['shipment_date'].min().date()
max_date = df['shipment_date'].max().date()
all_couriers = df["shippingCourier"].unique().tolist()
all_cities = df["destination_city"].unique().tolist()
status_options = ["All", "Delivered (shipped=True)", "Pending (shipped=False)"]

# === Initialize session state for filters if not present ===
if "start_date" not in st.session_state:
    st.session_state.start_date = min_date
if "end_date" not in st.session_state:
    st.session_state.end_date = max_date
if "selected_couriers" not in st.session_state:
    st.session_state.selected_couriers = all_couriers
if "selected_cities" not in st.session_state:
    st.session_state.selected_cities = all_cities
if "selected_status" not in st.session_state:
    st.session_state.selected_status = "All"

# === Sidebar UI ===
st.sidebar.header("🔎 Filter Your Data")

# Clear button
if st.sidebar.button("🔄 Clear Filters"):
    st.session_state.start_date = min_date
    st.session_state.end_date = max_date
    st.session_state.selected_couriers = all_couriers
    st.session_state.selected_cities = all_cities
    st.session_state.selected_status = "All"
    st.rerun()  # Force rerun to apply reset

# Render widgets with session_state defaults
start_date = st.sidebar.date_input("Start Date", min_value=min_date, max_value=max_date, value=st.session_state.start_date, key="start_date")
end_date = st.sidebar.date_input("End Date", min_value=min_date, max_value=max_date, value=st.session_state.end_date, key="end_date")
selected_couriers = st.sidebar.multiselect("Select Couriers", all_couriers, default=st.session_state.selected_couriers, key="selected_couriers")
selected_cities = st.sidebar.multiselect("Select Cities", all_cities, default=st.session_state.selected_cities, key="selected_cities")
selected_status = st.sidebar.selectbox("Shipment Status", status_options, index=status_options.index(st.session_state.selected_status), key="selected_status")

# === Apply filters ===
filtered = df.copy()
start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)

mask_date = (filtered['shipment_date'] >= start_ts) & (filtered['shipment_date'] <= end_ts)
filtered = filtered[mask_date]

if selected_couriers:
    filtered = filtered[filtered["shippingCourier"].isin(selected_couriers)]
if selected_cities:
    filtered = filtered[filtered["destination_city"].isin(selected_cities)]
if selected_status == "Delivered (shipped=True)":
    filtered = filtered[filtered["shipped"] == True]
elif selected_status == "Pending (shipped=False)":
    filtered = filtered[filtered["shipped"] == False]

# === KPI Calculations ===
total_shipments = len(filtered)
delivered_count = int(filtered['shipped'].sum())
pending_count = total_shipments - delivered_count
total_cost = filtered['cost'].sum()
avg_cost = filtered['cost'].mean() if total_shipments > 0 else 0
min_cost = filtered['cost'].min() if total_shipments > 0 else 0
max_cost = filtered['cost'].max() if total_shipments > 0 else 0

# === KPI Display ===
st.title("📦 ShipNest Shipping Analytics")
st.markdown("### Overview of your Pakistani logistics data")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Shipments", total_shipments)
col2.metric("Delivered", delivered_count)
col3.metric("Pending", pending_count)
col4.metric("Total Cost (PKR)", f"{total_cost:,.0f}")
col5.metric("Avg Cost (PKR)", f"{avg_cost:,.0f}")

col6, col7 = st.columns(2)
col6.metric("Min Cost (PKR)", f"{min_cost:,.0f}")
col7.metric("Max Cost (PKR)", f"{max_cost:,.0f}")

# === Charts ===
st.subheader("📍 Shipments by City")
st.bar_chart(filtered.groupby("destination_city").size())

st.subheader("💰 Cost Over Time")
cost_trend = filtered.groupby("shipment_date")["cost"].sum()
st.line_chart(cost_trend)

st.subheader("📦 Courier Usage Table")
st.dataframe(filtered["shippingCourier"].value_counts())

st.subheader("📦 Courier Usage Breakdown")
courier_counts = filtered["shippingCourier"].value_counts().reset_index()
courier_counts.columns = ["Courier", "Count"]
fig = px.pie(courier_counts, names='Courier', values='Count', title='Courier Distribution')
st.plotly_chart(fig, use_container_width=True)

# === SIMPLE Chatbot Embed for Testing ===
st.markdown("---")
st.subheader("💬 Chat with Shipping Analytics Agent")
st.markdown("Below is the chatbot interface for testing:")
st.components.v1.iframe("http://localhost:8502", height=600, width=700, scrolling=True)
