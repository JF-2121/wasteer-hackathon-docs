import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 1. CONFIG & CONSTANTS ---
# Define baseline operational constraints based on LiDAR bunker scans
st.set_page_config(page_title="BunkerIQ Control", layout="wide")

TARGET_CV = 10.0 # MJ/kg: Ideal operational energy density for the furnace
MAX_BUNKER_VOLUME_M3 = 13297.7 # Fixed physical limit of the waste bunker
INITIAL_VOLUME_M3 = 4183.7
AVERAGE_BUNKER_DENSITY_KG_M3 = 400.0  
INITIAL_MASS_KG = INITIAL_VOLUME_M3 * AVERAGE_BUNKER_DENSITY_KG_M3

# --- 2. DATA ENGINE ---
@st.cache_data
def load_data():
    """
    Processes the raw shipment data using a Mass-Energy Balance Model.
    The model accounts for waste input and continuous incineration output,
    ensuring CV drift is corrected based on thermodynamic mass-balance principles.
    """
    df = pd.read_csv('cleaned_shipments.csv')
    df['timestamp'] = pd.to_datetime(df['shipment__entry_timestamp'], format='mixed', errors='coerce')
    df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    
    # Normalizing inputs for consistent energy density calculation
    df['weight_kg'] = pd.to_numeric(df['shipment__weight'], errors='coerce').fillna(0)
    df['cv'] = pd.to_numeric(df['calorific_value'], errors='coerce').fillna(TARGET_CV)
    
    # Calculate constant incineration burn rate (Tons/hr) from historical throughput
    total_time_hrs = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds() / 3600.0
    burn_rate = df['weight_kg'].sum() / total_time_hrs if total_time_hrs > 0 else 25000.0
    
    # Iterative Simulation: Models the bunker as a dynamic thermodynamic control volume
    current_mass, current_energy = INITIAL_MASS_KG, INITIAL_MASS_KG * TARGET_CV
    mass_list, energy_list = [], []
    prev_time = df['timestamp'].iloc[0]
    
    for _, row in df.iterrows():
        # Calculate energy removal proportional to the current average CV of the bunker
        dt_hrs = (row['timestamp'] - prev_time).total_seconds() / 3600.0
        mass_burned = dt_hrs * burn_rate
        avg_cv = current_energy / current_mass if current_mass > 0 else row['cv']
        
        # State Update: Incoming trucks + Continuous incineration output
        current_mass = max(0, current_mass + row['weight_kg'] - mass_burned)
        current_energy = max(0, current_energy + (row['weight_kg'] * row['cv']) - (mass_burned * avg_cv))
        
        mass_list.append(current_mass)
        energy_list.append(current_energy)
        prev_time = row['timestamp']
        
    df['current_mass'] = mass_list
    df['rolling_cv'] = [e/m if m > 0 else TARGET_CV for e, m in zip(energy_list, mass_list)]
    df['current_vol'] = (df['current_mass'] / AVERAGE_BUNKER_DENSITY_KG_M3).clip(0, MAX_BUNKER_VOLUME_M3)
    
    return df, burn_rate

# Execute Engine
df, BURN_RATE = load_data()

# --- 3. UI LAYOUT ---
st.title("BunkerIQ: Live Operations")
st.markdown("### Operational Dashboard | Mass-Energy Balance Simulation")

# State Management for the automated "Digital Twin" playback
if 'idx' not in st.session_state: st.session_state.idx = 1
if 'play' not in st.session_state: st.session_state.play = False

# Sidebar Controls
st.sidebar.header("Simulation Settings")
if st.sidebar.button("▶ Play"): st.session_state.play = True
if st.sidebar.button("⏸ Pause"): st.session_state.play = False
fps = st.sidebar.slider("Playback Speed (FPS):", 1, 50, 10)
idx = st.sidebar.slider("Timeline Control:", 1, len(df)-1, value=st.session_state.idx)
st.session_state.idx = idx

# Current Snapshot Selection
row = df.iloc[idx]
rem_vol = MAX_BUNKER_VOLUME_M3 - row['current_vol']
fill_pct = (row['current_vol'] / MAX_BUNKER_VOLUME_M3) * 100

# Top-level KPI Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Bunker Mass", f"{row['current_mass']/1000:,.0f} t")
m2.metric("Remaining Headroom", f"{rem_vol:,.0f} m³")
m3.metric("Current Energy (CV)", f"{row['rolling_cv']:.2f} MJ/kg")
m4.metric("Capacity Status", f"{fill_pct:.1f}%")

# Main Dashboard View
l, r = st.columns(2)
with l:
    st.subheader("Bunker Utilization Gauge")
    fig = go.Figure(go.Indicator(mode="gauge+number", value=fill_pct, title={'text': "Capacity Load (%)"}, gauge={'axis':{'range':[0,100]}, 'bar':{'color':"#00b8ff" if fill_pct<80 else "#ff003c"}}))
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Capacity Analysis (Problem 1)")
    cap_df = pd.DataFrame([{"Material": r.description, "Max Tons": round((rem_vol * r.density)/1000, 1)} for r in [
        type('obj', (object,), {'description': 'RDF', 'density': 200}),
        type('obj', (object,), {'description': 'Mixed MSW', 'density': 350}),
        type('obj', (object,), {'description': 'C&D Waste', 'density': 800})
    ]])
    st.dataframe(cap_df, use_container_width=True)

with r:
    st.subheader("Optimization Advice (Problem 2)")
    if abs(row['rolling_cv'] - TARGET_CV) > 0.1:
        needed = (row['current_mass'] * (TARGET_CV - row['rolling_cv'])) / (15.0 - TARGET_CV)
        if needed > 0:
            st.error(f"Dispatch Crane: Add RDF (15 MJ/kg)")
            st.metric("Required Correction", f"{needed:,.0f} kg")
            st.progress(min(needed / (rem_vol * 200), 1.0))
    else: st.success("Bunker status stable: Plant operating at peak efficiency.")

# Timeline visualization
st.subheader("Bunker Capacity & Energy Stability")
fig_t = make_subplots(specs=[[{"secondary_y": True}]])
fig_t.add_trace(go.Scatter(x=df['timestamp'], y=df['current_vol'], name="Volume", fill='tozeroy', line={'color':'#00b8ff'}), secondary_y=False)
fig_t.add_trace(go.Scatter(x=df['timestamp'], y=df['rolling_cv'], name="CV", line={'color':'#ff00ff', 'width':3}), secondary_y=True)
fig_t.add_vline(x=row['timestamp'], line_dash="dash", line_color="white")
fig_t.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=20,b=0))
st.plotly_chart(fig_t, use_container_width=True)

# Auto-playback logic
if st.session_state.play and st.session_state.idx < len(df) - 1:
    time.sleep(1.0 / fps)
    st.session_state.idx += 1
    st.rerun()