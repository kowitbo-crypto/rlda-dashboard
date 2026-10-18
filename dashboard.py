import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from pyproj import Transformer

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(page_title="RLDA Dashboard - Google Sheets", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main-header { font-size: 24px; font-weight: bold; color: #0077cc; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">RLDA v11.2.4 | Dashboard (UTM Zone 48N)</div>', unsafe_allow_html=True)

# ==========================================
# 2. Helper Functions
# ==========================================
SHEET_ID = "1wkOIwvJGbsWz3MccBgFMIng9NqJ5v9HQ5yw_bfv1eMY"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

@st.cache_data(ttl=5)
def load_google_sheet(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        
        num_cols = ['DI_No', 'KM_m', 'Northing', 'Easting', 'RailLevel', 
                    'DrainInvertLevel', 'LevelTopUdrain', 'ManholeLevelBottom',
                    'UpstreamInvertHU', 'DownstreamInvertHD', 'Lp', 'W_emb', 
                    'ExistingGroundLevel', 'DrainBase_m', 'WaterLevel_m']
        
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        df = df.dropna(subset=['DI_No', 'Northing', 'Easting'])
        
        transformer = Transformer.from_crs("epsg:32648", "epsg:4326", always_xy=True)
        
        df['Lat'], df['Lng'] = np.nan, np.nan
        if not df.empty:
            lng, lat = transformer.transform(df['Easting'].values, df['Northing'].values)
            df['Lng'] = lng
            df['Lat'] = lat
            
        return df
    except Exception as e:
        st.error(f"❌ ไม่สามารถโหลดข้อมูลได้: {e}")
        return None

def format_km(km_text):
    try:
        val = float(km_text)
        return f"{int(val//1000)}+{val%1000:06.3f}"
    except:
        return str(km_text)

# ==========================================
# 3. Main Layout
# ==========================================
st.sidebar.header("⚙️ Data Source")
st.sidebar.info("เชื่อมต่อกับ Google Sheets (Live) - UTM Zone 48N")
if st.sidebar.button("🔄 ดึงข้อมูลใหม่ (Refresh)"):
    st.cache_data.clear()

df = load_google_sheet(CSV_URL)

if df is not None:
    st.sidebar.success(f"โหลดสำเร็จ: {len(df)} จุด")
    
    col_map, col_info = st.columns([2, 1])
    
    with col_map:
        st.subheader("🗺️ Plan View (Satellite)")
        
        if df.empty:
            st.warning("⚠️ ไม่พบข้อมูลพิกัดที่ถูกต้อง")
        else:
            center_lat = df['Lat'].mean()
            center_lng = df['Lng'].mean()
            
            # ---------------------------------------------------------
            # [เปลี่ยนแผนที่] ใช้ Esri World Imagery (Satellite)
            # ---------------------------------------------------------
            m = folium.Map(
                location=[center_lat, center_lng], 
                zoom_start=15, 
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri, Maxar, Earthstar Geographics"
            )
            
            # วาดเส้นทาง (ใช้สีแดงเข้มหรือสีส้มเพื่อให้ตัดกับภาพถ่ายดาวเทียม)
            route_coords = df[['Lat', 'Lng']].values.tolist()
            folium.PolyLine(route_coords, color="#FF4500", weight=4, opacity=0.9).add_to(m)
            
            for idx, row in df.iterrows():
                di_no = row['DI_No']
                has_di = row.get('HasDI', 0)
                marker_color = 'green' if has_di == 1 else 'gray'
                
                # เพิ่มพื้นหลังสีขาวให้ตัวหนังสือในป๊อปอัปเพื่อให้อ่านง่ายบนภาพถ่าย
                popup_html = f"<div style='background-color:white; padding:5px; border-radius:5px;'><b>DI {int(di_no)}</b><br>KM: {format_km(row['KM_m'])}</div>"
                
                folium.Marker(
                    location=[row['Lat'], row['Lng']],
                    popup=folium.Popup(popup_html, max_width=200),
                    tooltip=f"DI {int(di_no)}",
                    icon=folium.Icon(color=marker_color, icon='info-sign')
                ).add_to(m)
            
            map_data = st_folium(m, width=800, height=500, returned_objects=["last_object_clicked"])
    
    with col_info:
        st.subheader("📋 Data Inspector")
        
        if not df.empty:
            di_list = df['DI_No'].tolist()
            selected_di = st.selectbox("เลือกจุด DI:", di_list, index=0)
            
            if map_data.get('last_object_clicked') is not None:
                click_lat = map_data['last_object_clicked']['lat']
                click_lng = map_data['last_object_clicked']['lng']
                
                df['dist'] = np.sqrt((df['Lat'] - click_lat)**2 + (df['Lng'] - click_lng)**2)
                closest_idx = df['dist'].idxmin()
                selected_di = df.loc[closest_idx, 'DI_No']
            
            selected_row = df[df['DI_No'] == selected_di].iloc[0]
            
            info_df = pd.DataFrame({
                "Parameter": [
                    "DI_No", "KM_Text", "Northing", "Easting", 
                    "Rail Level", "Drain Invert", "Drain Base (m)", "Water Level (m)", 
                    "Drain Top", "HasDI"
                ],
                "Value": [
                    f"{selected_row.get('DI_No', '')}",
                    format_km(selected_row.get('KM_m', '')),
                    f"{selected_row.get('Northing', 0):.3f}",
                    f"{selected_row.get('Easting', 0):.3f}",
                    f"{selected_row.get('RailLevel', 0):.3f}",
                    f"{selected_row.get('DrainInvertLevel', 0):.3f}",
                    f"{selected_row.get('DrainBase_m', 0):.3f}",
                    f"{selected_row.get('WaterLevel_m', 0):.3f}",
                    f"{selected_row.get('LevelTopUdrain', 0):.3f}",
                    f"{selected_row.get('HasDI', 0)}"
                ]
            })
            st.dataframe(info_df, hide_index=True, use_container_width=True, height=350)
        else:
            st.info("ไม่มีข้อมูล DI_No ในไฟล์")

    # ---------------------------------------------------------
    # กราฟ Profile
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📈 Longitudinal Profile")
    
    if not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['KM_m'], y=df['RailLevel'], mode='lines+markers', name='Rail Level', line=dict(color='#d9534f', width=2)))
        if 'DrainInvertLevel' in df.columns:
            fig.add_trace(go.Scatter(x=df['KM_m'], y=df['DrainInvertLevel'], mode='lines+markers', name='Drain Invert', line=dict(color='#0077cc', width=2)))
        if 'DrainBase_m' in df.columns:
            fig.add_trace(go.Scatter(x=df['KM_m'], y=df['DrainBase_m'], mode='lines+markers', name='Drain Base', line=dict(color='#7b1fa2', width=2, dash='dash')))
        if 'WaterLevel_m' in df.columns:
            fig.add_trace(go.Scatter(x=df['KM_m'], y=df['WaterLevel_m'], mode='lines+markers', name='Water Level (HGL)', line=dict(color='#2e7d32', width=2)))
        if 'ExistingGroundLevel' in df.columns:
            fig.add_trace(go.Scatter(x=df['KM_m'], y=df['ExistingGroundLevel'], mode='lines', name='Existing Ground', line=dict(color='#9ccc65', width=2, dash='dot')))
        
        fig.add_trace(go.Scatter(x=[selected_row['KM_m']], y=[selected_row['RailLevel']], mode='markers', name='Selected Node', marker=dict(color='red', size=14, symbol='star', line=dict(color='black', width=1))))
        
        fig.update_layout(
            title="Longitudinal Profile (Elevation vs Chainage)",
            xaxis_title="Chainage (m)",
            yaxis_title="Elevation (m.msl)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

else:
    st.error("เกิดข้อผิดพลาดในการโหลดข้อมูล")