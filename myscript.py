import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="BunkerIQ Control", layout="wide", initial_sidebar_state="collapsed")

# --- 2. FACILITY CONSTANTS (From LiDAR Analysis) ---
TARGET_CV = 10.0

# LiDAR Derived Constants
MAX_BUNKER_VOLUME_M3 = 13297.7
INITIAL_VOLUME_M3 = 4183.7

# Operational Constants
AVERAGE_BUNKER_DENSITY_KG_M3 = 400.0  
INITIAL_BUNKER_MASS_KG = INITIAL_VOLUME_M3 * AVERAGE_BUNKER_DENSITY_KG_M3
INCINERATION_RATE_KG_HR = 25_000.0  # Plant burns 25 Tons per hour

# --- 3. DATA LOADING & PREPARATION ---
@st.cache_data
def load_and_prep_data():
    df = pd.read_csv('shipments_full_merged.csv')
    
    # Robust date parsing and sorting
    df['timestamp'] = pd.to_datetime(df['shipment__entry_timestamp'], format='mixed', errors='coerce')
    df = df.dropna(subset=['timestamp']) 
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Ensure numerical columns are clean
    df['net_weight'] = pd.to_numeric(df['net_weight'], errors='coerce').fillna(0)
    df['calorific_value'] = pd.to_numeric(df['calorific_value'], errors='coerce').fillna(TARGET_CV)
    df['waste_code_str'] = df['waste_code_str'].astype(str).str.strip()
    
    # Map exact densities for volumetric tracking
    density_map = {
        '191212': 350.0, '200301': 350.0, '180104': 150.0,
        '191210': 200.0, '200307': 100.0, '170904': 800.0,
        '150106': 100.0, '170604': 50.0,  '190801': 600.0
    }
    df['waste_density'] = df['waste_code_str'].map(density_map).fillna(AVERAGE_BUNKER_DENSITY_KG_M3)
    
    # Calculate EXACT volume added by this specific truck
    df['truck_volume_added_m3'] = df['net_weight'] / df['waste_density']
    df['cumulative_added_volume_m3'] = df['truck_volume_added_m3'].cumsum()
    df['cumulative_added_mass_kg'] = df['net_weight'].cumsum()
    
    # Calculate exact incineration out-flow up to this timestamp
    start_time = df['timestamp'].iloc[0]
    df['hours_passed'] = (df['timestamp'] - start_time).dt.total_seconds() / 3600.0
    df['incinerated_mass_kg'] = df['hours_passed'] * INCINERATION_RATE_KG_HR
    df['incinerated_volume_m3'] = df['incinerated_mass_kg'] / AVERAGE_BUNKER_DENSITY_KG_M3
    
    # Live Net Balances
    df['current_mass_kg'] = INITIAL_BUNKER_MASS_KG + df['cumulative_added_mass_kg'] - df['incinerated_mass_kg']
    df['current_mass_kg'] = df['current_mass_kg'].clip(lower=0)
    
    df['current_volume_m3'] = INITIAL_VOLUME_M3 + df['cumulative_added_volume_m3'] - df['incinerated_volume_m3']
    df['current_volume_m3'] = df['current_volume_m3'].clip(lower=0)
    
    # Energy calculations
    df['energy_contribution'] = df['net_weight'] * df['calorific_value']
    df['cumulative_added_energy'] = df['energy_contribution'].cumsum()
    initial_energy = INITIAL_BUNKER_MASS_KG * TARGET_CV
    
    df['rolling_calorific_value'] = df.apply(
        lambda row: (initial_energy + row['cumulative_added_energy']) / (INITIAL_BUNKER_MASS_KG + row['cumulative_added_mass_kg']) 
        if (INITIAL_BUNKER_MASS_KG + row['cumulative_added_mass_kg']) > 0 else TARGET_CV, 
        axis=1
    )
    return df

df = load_and_prep_data()

# --- 4. OPTIMIZATION LOGIC ---
WASTE_PROPERTIES = pd.DataFrame([
    {'waste_code': '191212', 'description': 'Other wastes from mechanical treatment', 'calorific_value': 11.0, 'density': 350},
    {'waste_code': '200301', 'description': 'Mixed MSW', 'calorific_value': 9.5, 'density': 350},
    {'waste_code': '180104', 'description': 'Non-infectious healthcare waste', 'calorific_value': 14.0, 'density': 150},
    {'waste_code': '191210', 'description': 'Combustible waste (refuse derived fuel)', 'calorific_value': 15.0, 'density': 200},
    {'waste_code': '200307', 'description': 'Bulky waste', 'calorific_value': 15.0, 'density': 100},
    {'waste_code': '170904', 'description': 'Mixed construction and demolition waste', 'calorific_value': 13.0, 'density': 800},
    {'waste_code': '150106', 'description': 'Mixed packaging', 'calorific_value': 16.0, 'density': 100},
    {'waste_code': '170604', 'description': 'Insulation materials', 'calorific_value': 18.0, 'density': 50},
    {'waste_code': '190801', 'description': 'Screenings (WWTP waste)', 'calorific_value': 15.0, 'density': 600}
]).set_index('waste_code')

def get_recommendation(current_avg, target=TARGET_CV):
    if current_avg < target:
        candidates = WASTE_PROPERTIES[WASTE_PROPERTIES['calorific_value'] > target].sort_values(by='calorific_value', ascending=False)
    else:
        candidates = WASTE_PROPERTIES[WASTE_PROPERTIES['calorific_value'] < target].sort_values(by='calorific_value', ascending=True)
    
    best_candidate = candidates.iloc[0]
    return best_candidate.name, best_candidate['description'], best_candidate['calorific_value'], best_candidate['density']

# --- 5. UI: HEADER & INTERACTION ---
st.title("BunkerIQ: Smart Waste Management")
st.markdown("---")

st.sidebar.header("Demo Controls")
selected_index = st.sidebar.slider("Select incoming truck delivery:", 1, len(df)-1, len(df)-10)

# Filter data
current_state = df.iloc[:selected_index]
incoming_truck = df.iloc[selected_index]

current_avg_cv = current_state['rolling_calorific_value'].iloc[-1]
current_mass = current_state['current_mass_kg'].iloc[-1]
current_vol = current_state['current_volume_m3'].iloc[-1]

remaining_vol = MAX_BUNKER_VOLUME_M3 - current_vol
fill_percentage = current_vol / MAX_BUNKER_VOLUME_M3
box_color = "#ff003c" if fill_percentage > 0.9 else "#00ff9f"

# --- ANIMATED STATUS BOX ---
html_status_box = f"""
<style>
@keyframes glow {{
    0% {{ box-shadow: 0 0 5px {box_color}; }}
    50% {{ box-shadow: 0 0 20px {box_color}; }}
    100% {{ box-shadow: 0 0 5px {box_color}; }}
}}
.animated-box {{
    background-color: #1e1e1e;
    border: 2px solid {box_color};
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    animation: glow 2s infinite;
    margin-bottom: 25px;
}}
.progress-bg {{
    width: 100%;
    background-color: #333;
    border-radius: 8px;
    height: 35px;
    margin-top: 15px;
    position: relative;
}}
.progress-fill {{
    width: {min(fill_percentage * 100, 100)}%;
    background-color: {box_color};
    height: 100%;
    border-radius: 8px;
    transition: width 0.5s ease-in-out;
}}
.progress-text {{
    position: absolute;
    width: 100%;
    text-align: center;
    top: 6px;
    color: white;
    font-weight: bold;
    font-family: sans-serif;
    text-shadow: 1px 1px 2px black;
    font-size: 16px;
}}
</style>
<div class="animated-box">
    <h2 style="color: white; margin: 0; font-family: sans-serif;">LOAD STATUS: {incoming_truck.get('shipment__license_plate', 'Unknown')}</h2>
    <p style="color: #ccc; font-size: 18px; margin: 5px 0;">
        Dumped: <b>{incoming_truck['net_weight']:,.0f} kg</b> of EWC {incoming_truck.get('waste_code_str', 'N/A')}
    </p>
    <div class="progress-bg">
        <div class="progress-fill"></div>
        <div class="progress-text">{fill_percentage * 100:.1f}% FULL</div>
    </div>
    <p style="color: #aaa; margin-top: 15px; font-size: 16px;">
        Live Volume: <b>{current_vol:,.1f} m³</b> / {MAX_BUNKER_VOLUME_M3:,.1f} m³ &nbsp;&nbsp;|&nbsp;&nbsp; 
        Incineration Rate: <b>{INCINERATION_RATE_KG_HR/1000:,.1f} t/hr</b>
    </p>
</div>
"""
st.markdown(html_status_box, unsafe_allow_html=True)

# Top KPIs
col1, col2, col3 = st.columns(3)
col1.metric("Current Bunker Mass", f"{current_mass / 1000:,.0f} Tons")
col2.metric("Remaining Capacity", f"{remaining_vol:,.1f} m³")
col3.metric("Current Calorific Value", f"{current_avg_cv:.2f} MJ/kg", 
            delta=f"{current_avg_cv - TARGET_CV:.2f} from target", delta_color="inverse")

st.markdown("---")

# --- 6. UI: SPLIT-SCREEN (Input vs. Recommendation) ---
left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Event Impact")
    st.write(f"**Load Calorific Value:** {incoming_truck['calorific_value']} MJ/kg")
    st.write(f"**Specific Density:** {incoming_truck['waste_density']} kg/m³")
    st.write(f"**Volume Added:** {incoming_truck['truck_volume_added_m3']:,.1f} m³")
    
    new_total_mass = current_mass + incoming_truck['net_weight']
    new_total_energy = (current_mass * current_avg_cv) + (incoming_truck['net_weight'] * incoming_truck['calorific_value'])
    projected_cv = new_total_energy / new_total_mass if new_total_mass > 0 else TARGET_CV
    
    st.warning(f"Without compensation, the plant's calorific value will shift to: {projected_cv:.2f} MJ/kg")

with right_col:
    st.subheader("BunkerIQ Recommendation")
    
    if abs(projected_cv - TARGET_CV) < 0.1:
        st.success("Load is perfectly balanced within tolerances. No action required.")
    else:
        rec_code, rec_desc, rec_cv, rec_density = get_recommendation(projected_cv)
        
        # Calculate required mass
        m_add = new_total_mass * ((TARGET_CV - projected_cv) / (rec_cv - TARGET_CV))
        
        if m_add > 0:
            vol_add = m_add / rec_density
            
            if vol_add > remaining_vol:
                st.error(f"CRITICAL: Required compensation ({vol_add:,.1f} m³) exceeds remaining physical capacity ({remaining_vol:,.1f} m³).")
            else:
                st.error("ACTION REQUIRED: Dispatch Crane")
                st.write(f"To restore the plant exactly to {TARGET_CV} MJ/kg:")
                st.metric("Waste Code to Add", f"{rec_code} ({rec_cv} MJ/kg)")
                st.caption(f"Material: {rec_desc}")
                st.metric("Required Mass", f"{m_add:,.0f} kg", f"Requires {vol_add:,.1f} m³ space", delta_color="off")

st.markdown("---")

# --- 7. UI: PLOTLY DUAL-AXIS CHART ---
st.subheader("Bunker Capacity & Energy Stability")

fig = make_subplots(specs=[[{"secondary_y": True}]])

# Area: Current Volume 
fig.add_trace(
    go.Scatter(x=current_state['timestamp'], y=current_state['current_volume_m3'], 
               name="Net Volume (m³)", fill='tozeroy', marker_color='#00b8ff', opacity=0.4),
    secondary_y=False,
)

# Line: Max Capacity Threshold (LiDAR Derived)
fig.add_hline(y=MAX_BUNKER_VOLUME_M3, line_dash="solid", line_color="#ff003c", annotation_text="Max LiDAR Capacity (13,297 m³)", secondary_y=False)

# Line: Rolling Calorific Value
fig.add_trace(
    go.Scatter(x=current_state['timestamp'], y=current_state['rolling_calorific_value'], 
               name="Avg. Calorific Value", mode='lines', line=dict(color='#ff00ff', width=3)),
    secondary_y=True,
)

# Line: Target CV
fig.add_hline(y=TARGET_CV, line_dash="dash", line_color="#00ff9f", annotation_text="Target 10 MJ/kg", secondary_y=True)

# Add marker for current point in time
fig.add_trace(
    go.Scatter(
        x=[current_state['timestamp'].iloc[-1]], 
        y=[current_vol],
        mode='markers',
        marker=dict(size=12, color='white', symbol='cross'),
        name='Current Status',
        showlegend=False
    ),
    secondary_y=False
)

fig.update_layout(
    template="plotly_dark",
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    height=400,
    margin=dict(l=0, r=0, t=30, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

fig.update_yaxes(title_text="Volume (m³)", range=[0, MAX_BUNKER_VOLUME_M3 * 1.1], secondary_y=False)
fig.update_yaxes(title_text="Calorific Value (MJ/kg)", range=[7, 13], secondary_y=True)

st.plotly_chart(fig, use_container_width=True)