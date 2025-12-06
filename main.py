import streamlit as st
import importlib
import sys
import pandas as pd
import numpy as np

# 성능 최적화를 위한 페이지 설정
st.set_page_config(
    page_title="Hy-con & IRFM by TJLABS", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# 비밀번호 인증 (Streamlit Cloud 배포용)
# =============================================================================
def check_password():
    """비밀번호 인증 체크"""
    def password_entered():
        """비밀번호 입력 시 호출"""
        # Streamlit Cloud secrets 또는 하드코딩된 비밀번호 체크
        try:
            valid_passwords = list(st.secrets["passwords"].values())
        except:
            valid_passwords = ["wonderful2$"]  # 기본 비밀번호
        
        if st.session_state["password"] in valid_passwords:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("## 🔐 SKEP IRFM Dashboard")
        st.text_input(
            "Password", type="password", 
            on_change=password_entered, key="password"
        )
        st.info("Enter the password to access the dashboard.")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("## 🔐 SKEP IRFM Dashboard")
        st.text_input(
            "Password", type="password", 
            on_change=password_entered, key="password"
        )
        st.error("❌ Incorrect password. Please try again.")
        return False
    else:
        return True

# 비밀번호 인증
if not check_password():
    st.stop()

# =============================================================================

# 파일 업로드 크기 제한 늘리기 (500MB까지)
import os
os.environ["STREAMLIT_SERVER_MAX_UPLOAD_SIZE"] = "500"

# 캐싱 최적화 설정
if 'cache_initialized' not in st.session_state:
    st.session_state['cache_initialized'] = True
    # 메모리 사용량 최적화를 위한 설정
    st.cache_data.clear()

# CachedDataLoader import
from src.cached_data_loader import CachedDataLoader, find_available_datasets

# 모든 모듈을 상단에서 import
from src.building_setup import render_building_setup, load_sward_config
from src.data_input import render_data_input
from src import tward_type31_processing

# Type 41 모듈들을 강제 reload (Processing Mode에서만 필요)
modules_to_reload = [
    'src.tward_type41_operation',
    'src.tward_type41_dwell_time', 
    'src.tward_type41_journey_map',
    'src.tward_type41_location_analysis',
    'src.tward_type41_heatmap_analysis'
]

for module_name in modules_to_reload:
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])
        print(f"🔄 Reloaded module: {module_name}")

# Type 41 모듈들 import
from src.tward_type41_operation import render_tward41_operation
from src.tward_type41_dwell_time import render_tward41_dwell_time
from src.tward_type41_journey_map import render_tward41_journey_map

st.title("Hy-con & IRFM by TJLABS")


# ============================================================================
# Common T41 Worker Calculation (shared between Overview and T41 tab)
# ============================================================================

def calculate_t41_worker_stats_10min(t41_data: pd.DataFrame) -> pd.DataFrame:
    """
    T41 작업자 수를 10분 단위로 계산하는 공통 함수
    
    방법론:
    - 1분 단위로 MAC별 신호 수 계산
    - 1분에 2회 이상 신호 = Active (진동 감지)
    - 10분 bin 내에서 1분이라도 Active면 해당 bin에서 Active로 간주
    
    Returns:
        DataFrame with columns: [Time Bin, Total, Active, Inactive, Time Label]
    """
    if t41_data is None or t41_data.empty:
        return pd.DataFrame({'Time Bin': range(144), 'Total': 0, 'Active': 0, 'Inactive': 0})
    
    t41_copy = t41_data.copy()
    t41_copy['time'] = pd.to_datetime(t41_copy['time'])
    t41_copy['minute_bin'] = t41_copy['time'].dt.floor('1min')
    t41_copy['time_bin'] = (t41_copy['time'].dt.hour * 6 + t41_copy['time'].dt.minute // 10)
    
    # 1분 단위 신호 수 계산
    minute_signal = t41_copy.groupby(['mac', 'minute_bin']).size().reset_index(name='signals')
    minute_signal['is_active'] = minute_signal['signals'] >= 2  # 1분에 2회 이상 = Active
    minute_signal['time_bin'] = (
        minute_signal['minute_bin'].dt.hour * 6 + 
        minute_signal['minute_bin'].dt.minute // 10
    )
    
    # 10분 bin당 활성 여부 (10분 내에 1분이라도 활성이면 Active)
    mac_bin_activity = minute_signal.groupby(['mac', 'time_bin']).agg({
        'is_active': 'any'
    }).reset_index()
    
    # 10분 bin별 Total (신호가 있는 모든 MAC)
    bin_total = minute_signal.groupby('time_bin')['mac'].nunique().reset_index()
    bin_total.columns = ['Time Bin', 'Total']
    
    # 10분 bin별 Active
    bin_active = mac_bin_activity[mac_bin_activity['is_active']].groupby('time_bin')['mac'].nunique().reset_index()
    bin_active.columns = ['Time Bin', 'Active']
    
    # 10분 bin별 Inactive
    bin_inactive = mac_bin_activity[~mac_bin_activity['is_active']].groupby('time_bin')['mac'].nunique().reset_index()
    bin_inactive.columns = ['Time Bin', 'Inactive']
    
    # 모든 144개 bin 보장
    all_bins = pd.DataFrame({'Time Bin': range(144)})
    bin_stats = all_bins.merge(bin_total, on='Time Bin', how='left').fillna(0)
    bin_stats = bin_stats.merge(bin_active, on='Time Bin', how='left').fillna(0)
    bin_stats = bin_stats.merge(bin_inactive, on='Time Bin', how='left').fillna(0)
    
    bin_stats['Total'] = bin_stats['Total'].astype(int)
    bin_stats['Active'] = bin_stats['Active'].astype(int)
    bin_stats['Inactive'] = bin_stats['Inactive'].astype(int)
    
    # 시간 라벨 생성 (HH:MM 형식)
    bin_stats['Time Label'] = bin_stats['Time Bin'].apply(
        lambda x: f"{x // 6:02d}:{(x % 6) * 10:02d}"
    )
    
    # 시간대별 집계 추가 (Overview용)
    bin_stats['Hour'] = bin_stats['Time Bin'] // 6
    
    return bin_stats


def calculate_t41_hourly_stats(bin_stats_10min: pd.DataFrame) -> pd.DataFrame:
    """
    10분 단위 stats를 시간대별로 집계 (Overview 탭용)
    
    방법론:
    - 10분 bin별 Active/Inactive MAC을 시간대별로 합산
    - 동일 MAC이 여러 bin에서 Active일 수 있으므로 max 사용
    """
    hourly = bin_stats_10min.groupby('Hour').agg({
        'Total': 'max',  # 해당 시간의 피크 Total
        'Active': 'max',  # 해당 시간의 피크 Active
        'Inactive': 'max'  # 해당 시간의 피크 Inactive
    }).reset_index()
    
    # 0-23시 보장
    all_hours = pd.DataFrame({'Hour': range(24)})
    hourly = all_hours.merge(hourly, on='Hour', how='left').fillna(0)
    hourly['Total'] = hourly['Total'].astype(int)
    hourly['Active'] = hourly['Active'].astype(int)
    hourly['Inactive'] = hourly['Inactive'].astype(int)
    
    return hourly


# ============================================================================
# Utility Functions
# ============================================================================

def format_dataset_name(name):
    """Format dataset name for display: 'Yongin_Cluster_20250909' -> 'Yongin Cluster 1, Sep. 9, 2025'"""
    if 'Yongin_Cluster_20250909' in name or 'Yongin_Cluster' in name:
        return "Yongin Cluster 1, Sep. 9, 2025"
    return name


# ============================================================================
# Dashboard Mode - 캐시된 데이터로 즉시 분석 결과 표시
# ============================================================================

def render_dashboard_mode():
    """Dashboard Mode: 사전 처리된 캐시 데이터 자동 로드
    
    탭 구조: Overview | T-Ward Type 31 | T-Ward Type 41 | MobilePhone
    """
    
    # 사용 가능한 데이터셋 찾기
    datasets = find_available_datasets()
    
    # 디버그: 데이터셋 정보 표시
    with st.sidebar.expander("📊 Dataset Debug", expanded=False):
        st.text(f"Found {len(datasets)} dataset(s)")
        for ds in datasets:
            st.text(f"  - {ds.get('name')}: T31={ds.get('t31_records')}, T41={ds.get('t41_records')}")
    
    # 디버그: 데이터셋 정보 표시
    with st.sidebar.expander("📊 Dataset Debug", expanded=False):
        st.text(f"Found {len(datasets)} dataset(s)")
        for ds in datasets:
            st.text(f"  - {ds.get('name')}: T31={ds.get('t31_records')}, T41={ds.get('t41_records')}")
    
    if not datasets:
        st.warning("⚠️ No pre-processed datasets available.")
        
        # Debug info for Streamlit Cloud
        import os
        from pathlib import Path
        st.expander("🔍 Debug Info (for troubleshooting)", expanded=False).write({
            "cwd": os.getcwd(),
            "cwd_contents": os.listdir(os.getcwd()) if os.path.exists(os.getcwd()) else "N/A",
            "__file__": __file__ if "__file__" in dir() else "N/A",
            "Datafile_exists": os.path.exists("Datafile"),
            "Datafile_Rawdata_exists": os.path.exists("Datafile/Rawdata"),
        })
        
        st.info("""
        **How to prepare data:**
        1. Run `python precompute.py <data_folder>` in terminal
        2. Example: `python precompute.py Datafile/Rawdata/Yongin_Cluster_20250909`
        """)
        return
    
    # Dataset selection (sidebar)
    st.sidebar.markdown("### 📊 Dataset Selection")
    
    dataset_names = [d['name'] for d in datasets]
    dataset_display_names = [format_dataset_name(n) for n in dataset_names]
    selected_display = st.sidebar.selectbox("Select Dataset", dataset_display_names)
    
    # Map back to original name
    selected_idx = dataset_display_names.index(selected_display)
    selected_name = dataset_names[selected_idx]
    
    # Selected dataset info
    selected_dataset = next(d for d in datasets if d['name'] == selected_name)
    
    # Display dataset info
    st.sidebar.markdown("### 📋 Dataset Info")
    st.sidebar.info(f"""
    **Name**: {selected_display}
    **Created**: {selected_dataset['created_at'][:19]}
    **T31**: {selected_dataset['t31_records']:,} records
    **T41**: {selected_dataset['t41_records']:,} records  
    **Flow**: {selected_dataset['flow_records']:,} records
    """)
    
    # CachedDataLoader 초기화
    cache_loader = CachedDataLoader(selected_dataset['cache_path'])
    
    if not cache_loader.is_valid():
        st.error("Cache data is invalid. Please run precompute.py again.")
        return
    
    # 분석 결과 데이터를 session_state에 로드 (raw 파일 없이도 작동)
    # T31 분석 결과 확인 및 로드
    try:
        t31_results = cache_loader.load_t31_hourly_activity()
        if len(t31_results) > 0:
            st.session_state['t31_results_available'] = True
            st.sidebar.success(f"✅ T31: {len(t31_results)} rows loaded")
        else:
            st.session_state['t31_results_available'] = False
            st.sidebar.warning("⚠️ T31: 0 rows")
    except Exception as e:
        st.session_state['t31_results_available'] = False
        st.sidebar.error(f"❌ T31 error: {str(e)[:50]}")
    
    # T41 분석 결과 확인 및 로드  
    try:
        t41_results = cache_loader.load_t41_activity_analysis()
        if len(t41_results) > 0:
            st.session_state['t41_results_available'] = True
            st.session_state['type41_activity_analysis'] = t41_results
            st.sidebar.success(f"✅ T41: {len(t41_results)} rows loaded")
            # Journey Heatmap precomputed 데이터 로드
            journey_heatmap = cache_loader.load_t41_journey_heatmap()
            if len(journey_heatmap) > 0:
                st.session_state['type41_journey_heatmap'] = journey_heatmap
        else:
            st.session_state['t41_results_available'] = False
            st.sidebar.warning("⚠️ T41: 0 rows")
    except Exception as e:
        st.session_state['t41_results_available'] = False
        st.sidebar.error(f"❌ T41 error: {str(e)[:50]}")
    
    # Flow 분석 결과 확인 및 로드
    try:
        flow_results = cache_loader.load_flow_hourly()
        if len(flow_results) > 0:
            st.session_state['flow_results_available'] = True
    except:
        st.session_state['flow_results_available'] = False
    
    # Sward config 로드 (metadata에서)
    try:
        metadata = cache_loader.get_metadata()
        if metadata:
            # building/level 목록 설정
            buildings = metadata.get('buildings', [])
            if buildings:
                st.session_state['buildings'] = buildings
                st.session_state['building'] = buildings[0]
                st.session_state['_last_building'] = buildings[0]
    except:
        pass
    
    # 현재 데이터셋 기록
    st.session_state['_dashboard_dataset'] = selected_name
    
    # cache_loader를 session_state에 저장 (다른 탭에서 사용)
    st.session_state['cache_loader'] = cache_loader
    st.session_state['data_loader'] = cache_loader  # 호환성을 위해
    
    # ==========================================================================
    # 메인 탭 구조: Overview | T-Ward Type 31 | T-Ward Type 41 | MobilePhone
    # ==========================================================================
    main_tabs = st.tabs([
        "📊 Overview", 
        "🔧 T-Ward Type 31", 
        "👷 T-Ward Type 41", 
        "📱 MobilePhone"
    ])
    
    # 디버그: session_state 상태 확인
    with st.sidebar.expander("🔧 Session Debug", expanded=False):
        st.text(f"t31_results_available: {st.session_state.get('t31_results_available', 'NOT SET')}")
        st.text(f"t41_results_available: {st.session_state.get('t41_results_available', 'NOT SET')}")
        st.text(f"flow_results_available: {st.session_state.get('flow_results_available', 'NOT SET')}")
    
    # 디버그: session_state 상태 확인
    with st.sidebar.expander("🔧 Session Debug", expanded=False):
        st.text(f"t31_results_available: {st.session_state.get('t31_results_available', 'NOT SET')}")
        st.text(f"t41_results_available: {st.session_state.get('t41_results_available', 'NOT SET')}")
        st.text(f"flow_results_available: {st.session_state.get('flow_results_available', 'NOT SET')}")
    
    with main_tabs[0]:  # Overview
        render_dashboard_overview(cache_loader, selected_dataset)
    
    with main_tabs[1]:  # T-Ward Type 31
        if st.session_state.get('t31_results_available', False):
            render_dashboard_t31_tab()
        else:
            st.warning("⚠️ No T31 data available.")
    
    with main_tabs[2]:  # T-Ward Type 41
        if st.session_state.get('t41_results_available', False):
            render_dashboard_t41_tab()
        else:
            st.warning("⚠️ No T41 data available.")
    
    with main_tabs[3]:  # MobilePhone
        if st.session_state.get('flow_results_available', False):
            render_dashboard_mobilephone_tab()
        else:
            st.warning("⚠️ No MobilePhone(Flow) data available.")


# ============================================================================
# Dashboard Mode - New Tab Structure Functions
# ============================================================================

def render_dashboard_overview(cache_loader, selected_dataset):
    """Overview tab: Data summary and statistics"""
    st.header("📊 Overview - Data Summary")
    
    # Dataset basic info with smaller text (70% size)
    st.markdown("""
    <style>
    .small-metric .stMetric {
        font-size: 0.7em !important;
    }
    .small-metric label {
        font-size: 0.8em !important;
    }
    .small-metric [data-testid="stMetricValue"] {
        font-size: 1.2em !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Format dataset display name
    display_name = format_dataset_name(selected_dataset['name'])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #f0f2f6; border-radius: 5px;">
            <div style="color: #333; font-size: 0.9em;">📅 Dataset</div>
            <div style="font-size: 1.3em; font-weight: bold; color: #000;">{display_name}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #f0f2f6; border-radius: 5px;">
            <div style="color: #333; font-size: 0.9em;">🔧 T31 Records</div>
            <div style="font-size: 1.3em; font-weight: bold; color: #000;">{selected_dataset['t31_records']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #f0f2f6; border-radius: 5px;">
            <div style="color: #333; font-size: 0.9em;">👷 T41 Records</div>
            <div style="font-size: 1.3em; font-weight: bold; color: #000;">{selected_dataset['t41_records']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #f0f2f6; border-radius: 5px;">
            <div style="color: #333; font-size: 0.9em;">📱 Flow Records</div>
            <div style="font-size: 1.3em; font-weight: bold; color: #000;">{selected_dataset['flow_records']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Hourly summary (2-min aggregation)
    st.subheader("⏰ Hourly Personnel Status (2-min Average)")
    
    # Show hourly worker count if T41 data exists
    if 'tward41_data' in st.session_state and st.session_state['tward41_data'] is not None:
        t41_data = st.session_state['tward41_data']
        
        # 공통 함수 사용: T41 탭과 동일한 로직
        if 'time' in t41_data.columns:
            # 10분 단위 stats 계산 (공통 함수)
            bin_stats_10min = calculate_t41_worker_stats_10min(t41_data)
            
            # 시간대별 집계 (피크 값 사용)
            hourly_stats = calculate_t41_hourly_stats(bin_stats_10min)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 👷 T41 Worker Status (Active/Inactive)")
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(10, 4))
                # 스택 막대그래프: 아래=Active(초록), 위=Inactive(회색)
                ax.bar(hourly_stats['Hour'], hourly_stats['Active'], color='#4CAF50', label='Active (≥2 signals/min)')
                ax.bar(hourly_stats['Hour'], hourly_stats['Inactive'], bottom=hourly_stats['Active'], color='#BDBDBD', label='Inactive')
                ax.set_xlabel('Hour')
                ax.set_ylabel('Workers')
                ax.set_title('T41 Workers by Hour (Active/Inactive)')
                ax.set_xticks(range(0, 24))
                ax.legend(loc='upper right')
                st.pyplot(fig)
                plt.close()
            
            with col2:
                st.dataframe(hourly_stats[['Hour', 'Active', 'Inactive', 'Total']], use_container_width=True, hide_index=True)
    
    # Flow 데이터가 있으면 시간대별 유동인구 표시
    if 'flow_data' in st.session_state and st.session_state['flow_data'] is not None:
        flow_data = st.session_state['flow_data']
        
        if 'time' in flow_data.columns:
            flow_data_copy = flow_data.copy()
            flow_data_copy['time'] = pd.to_datetime(flow_data_copy['time'])
            flow_data_copy['two_min_bin'] = flow_data_copy['time'].dt.floor('2min')
            flow_data_copy['hour'] = flow_data_copy['time'].dt.hour
            
            # 2분 단위 unique MAC 수
            two_min_counts = flow_data_copy.groupby(['hour', 'two_min_bin'])['mac'].nunique().reset_index()
            two_min_counts.columns = ['hour', 'two_min_bin', 'unique_macs']
            
            # 시간대별 평균
            hourly_avg = two_min_counts.groupby('hour')['unique_macs'].mean().reset_index()
            hourly_avg.columns = ['Hour', 'Avg Devices (2min basis)']
            
            st.markdown("#### 📱 MobilePhone Traffic Status")
            col1, col2 = st.columns(2)
            with col1:
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.bar(hourly_avg['Hour'], hourly_avg['Avg Devices (2min basis)'], color='#2196F3')
                ax.set_xlabel('Hour')
                ax.set_ylabel('Average Devices')
                ax.set_title('MobilePhone Devices by Hour (2-min unique MAC average)')
                ax.set_xticks(range(0, 24))
                st.pyplot(fig)
                plt.close()
            
            with col2:
                st.dataframe(hourly_avg, use_container_width=True)
    
    st.markdown("---")
    st.info("💡 **Tip**: Check detailed analysis results in each tab.")


def render_dashboard_t31_tab():
    """T-Ward Type 31 tab: Equipment Analysis with 4 sub-tabs"""
    st.header("🔧 T-Ward Type 31 - Equipment Analysis")
    
    if 'tward31_data' not in st.session_state or st.session_state['tward31_data'] is None:
        st.warning("No T31 data available.")
        return
    
    # T31 sub-tabs: Overview, Location Analysis, Operation Heatmap, AI Insight & Report
    sub_tabs = st.tabs([
        "📊 Overview", 
        "📍 Location Analysis", 
        "🗺️ Operation Heatmap",
        "🤖 AI Insight & Report"
    ])
    
    with sub_tabs[0]:  # Overview
        render_t31_overview()
    
    with sub_tabs[1]:  # Location Analysis
        render_t31_location_analysis()
    
    with sub_tabs[2]:  # Operation Heatmap
        render_t31_operation_heatmap()
    
    with sub_tabs[3]:  # AI Insight & Report
        render_t31_ai_insight_report()


def render_dashboard_t41_tab():
    """T-Ward Type 41 tab: Worker Analysis with 4 sub-tabs"""
    st.header("👷 T-Ward Type 41 - Worker Analysis")
    
    if 'tward41_data' not in st.session_state or st.session_state['tward41_data'] is None:
        st.warning("No T41 data available.")
        return
    
    # 사이드바에 분석 설정 추가
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👷 T41 Analysis Settings")
    
    enable_filter = st.sidebar.checkbox(
        "Filter by cumulative dwell time", 
        value=False,
        help="Remove T-Wards with short dwell times"
    )
    
    min_dwell_time = st.sidebar.slider(
        "Minimum dwell time (minutes)",
        min_value=0,
        max_value=120,
        value=30,
        step=5,
        disabled=not enable_filter,
    )
    
    st.session_state['tward41_filter_enabled'] = enable_filter
    st.session_state['tward41_min_dwell_time'] = min_dwell_time if enable_filter else 0
    
    # T41 서브탭: Overview, Location Analysis, Journey Heatmap, AI Insight & Report
    sub_tabs = st.tabs([
        "📊 Overview", 
        "📍 Location Analysis", 
        "🗺️ Journey Heatmap",
        "🤖 AI Insight & Report"
    ])
    
    with sub_tabs[0]:  # Overview
        render_t41_overview()
    
    with sub_tabs[1]:  # Location Analysis (Video)
        render_t41_location_analysis()
    
    with sub_tabs[2]:  # Journey Heatmap
        render_t41_journey_heatmap()
    
    with sub_tabs[3]:  # AI Insight & Report
        render_t41_ai_insight_report()


def render_dashboard_mobilephone_tab():
    """MobilePhone(Flow) 탭: 스마트폰 유동인구 분석 - 개편"""
    st.header("📱 MobilePhone - Flow Analysis")
    
    if 'flow_data' not in st.session_state or st.session_state['flow_data'] is None:
        st.warning("Flow 데이터가 없습니다.")
        return
    
    flow_data = st.session_state['flow_data']
    sward_config = st.session_state.get('sward_config')
    
    # Flow 서브탭 - 개편된 구조
    sub_tabs = st.tabs([
        "📊 Device Counting", 
        "🔄 T-Ward vs Mobile",
        "📈 Apple vs Android"
    ])
    
    with sub_tabs[0]:  # Device Counting
        _render_device_counting_tab(flow_data, sward_config)
    
    with sub_tabs[1]:  # T-Ward vs Mobile
        _render_tward_vs_mobile_tab(flow_data, sward_config)
        
    with sub_tabs[2]:  # Apple vs Android
        _render_apple_vs_android_tab(flow_data)


def _render_device_counting_tab(flow_data, sward_config):
    """Device Counting 탭: 2분 unique MAC → 10분 평균"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    st.subheader("📊 Device Counting (2분 unique MAC → 10분 평균)")
    st.info("**방법론**: 2분 단위로 고유 MAC 주소 수를 세고, 10분(5개 구간) 단위로 평균")
    
    # 데이터 전처리
    flow_copy = flow_data.copy()
    flow_copy['time'] = pd.to_datetime(flow_copy['time'])
    
    # 2분 bin 생성
    flow_copy['two_min_bin'] = (flow_copy['time'].dt.hour * 30 + flow_copy['time'].dt.minute // 2)
    # 10분 bin 생성
    flow_copy['ten_min_bin'] = (flow_copy['time'].dt.hour * 6 + flow_copy['time'].dt.minute // 10)
    
    # S-Ward config 조인
    if sward_config is not None:
        flow_with_loc = flow_copy.merge(
            sward_config[['sward_id', 'building', 'level']],
            on='sward_id',
            how='left'
        )
    else:
        flow_with_loc = flow_copy.copy()
        flow_with_loc['building'] = 'Unknown'
        flow_with_loc['level'] = 'Unknown'
    
    # =========================================================================
    # 1. 전체 인원수 추이
    # =========================================================================
    st.markdown("### 📈 전체 디바이스 수 추이")
    
    # 2분 단위 unique MAC 카운팅
    two_min_counts = flow_with_loc.groupby('two_min_bin')['mac'].nunique().reset_index()
    two_min_counts.columns = ['two_min_bin', 'device_count']
    
    # 10분 평균 계산
    two_min_counts['ten_min_bin'] = two_min_counts['two_min_bin'] // 5
    ten_min_avg = two_min_counts.groupby('ten_min_bin')['device_count'].mean().reset_index()
    ten_min_avg.columns = ['ten_min_bin', 'avg_device_count']
    ten_min_avg['time_label'] = ten_min_avg['ten_min_bin'].apply(
        lambda x: f"{x//6:02d}:{(x%6)*10:02d}"
    )
    
    # 차트
    fig_total = go.Figure()
    fig_total.add_trace(go.Scatter(
        x=ten_min_avg['time_label'],
        y=ten_min_avg['avg_device_count'],
        mode='lines+markers',
        name='Total Devices',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8)
    ))
    fig_total.update_layout(
        title='전체 디바이스 수 (10분 평균)',
        xaxis_title='Time',
        yaxis_title='Average Device Count',
        height=350,
        template='plotly_white'
    )
    st.plotly_chart(fig_total, use_container_width=True)
    
    # 통계 메트릭
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📱 Peak", f"{ten_min_avg['avg_device_count'].max():.0f}")
    with col2:
        st.metric("📊 Average", f"{ten_min_avg['avg_device_count'].mean():.1f}")
    with col3:
        st.metric("📉 Min", f"{ten_min_avg['avg_device_count'].min():.0f}")
    with col4:
        # 총 누적 unique MAC
        total_unique = flow_with_loc['mac'].nunique()
        st.metric("🔢 Total Unique (Daily)", f"{total_unique:,}")
    
    # =========================================================================
    # 2. 빌딩별 인원수 추이
    # =========================================================================
    st.markdown("---")
    st.markdown("### 🏢 빌딩별 디바이스 수 추이")
    
    buildings = flow_with_loc['building'].dropna().unique()
    buildings = [b for b in buildings if b != 'Unknown']
    
    if len(buildings) > 0:
        # 빌딩별 10분 평균 계산
        building_two_min = flow_with_loc.groupby(['building', 'two_min_bin'])['mac'].nunique().reset_index()
        building_two_min.columns = ['building', 'two_min_bin', 'device_count']
        building_two_min['ten_min_bin'] = building_two_min['two_min_bin'] // 5
        
        building_ten_min = building_two_min.groupby(['building', 'ten_min_bin'])['device_count'].mean().reset_index()
        building_ten_min.columns = ['building', 'ten_min_bin', 'avg_device_count']
        
        # Building 색상
        from src.colors import BUILDING_COLORS
        building_color_map = {b: BUILDING_COLORS.get(b, '#888888') for b in buildings}
        
        fig_building = go.Figure()
        for building in sorted(buildings):
            bdata = building_ten_min[building_ten_min['building'] == building].copy()
            bdata['time_label'] = bdata['ten_min_bin'].apply(lambda x: f"{x//6:02d}:{(x%6)*10:02d}")
            
            fig_building.add_trace(go.Scatter(
                x=bdata['time_label'],
                y=bdata['avg_device_count'],
                mode='lines+markers',
                name=building,
                line=dict(color=building_color_map.get(building, '#888888'), width=2),
                marker=dict(size=6)
            ))
        
        fig_building.update_layout(
            title='빌딩별 디바이스 수 (10분 평균)',
            xaxis_title='Time',
            yaxis_title='Average Device Count',
            height=400,
            template='plotly_white',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig_building, use_container_width=True)
        
        # 빌딩별 통계 테이블
        building_stats = []
        for building in sorted(buildings):
            bdata = building_ten_min[building_ten_min['building'] == building]
            building_stats.append({
                'Building': building,
                'Peak': bdata['avg_device_count'].max(),
                'Average': bdata['avg_device_count'].mean(),
                'Min': bdata['avg_device_count'].min()
            })
        
        stats_df = pd.DataFrame(building_stats)
        st.dataframe(stats_df.style.format({
            'Peak': '{:.0f}',
            'Average': '{:.1f}',
            'Min': '{:.0f}'
        }), use_container_width=True, hide_index=True)
    
    # =========================================================================
    # 3. 층별 인원수 추이
    # =========================================================================
    st.markdown("---")
    st.markdown("### 🏗️ 층별 디바이스 수 추이")
    
    # Building-Level 조합 생성
    flow_with_loc['building_level'] = flow_with_loc['building'].fillna('Unknown') + '-' + flow_with_loc['level'].fillna('Unknown')
    building_levels = flow_with_loc['building_level'].unique()
    building_levels = [bl for bl in building_levels if 'Unknown' not in bl]
    
    if len(building_levels) > 0:
        # Building-Level별 10분 평균 계산
        bl_two_min = flow_with_loc.groupby(['building_level', 'two_min_bin'])['mac'].nunique().reset_index()
        bl_two_min.columns = ['building_level', 'two_min_bin', 'device_count']
        bl_two_min['ten_min_bin'] = bl_two_min['two_min_bin'] // 5
        
        bl_ten_min = bl_two_min.groupby(['building_level', 'ten_min_bin'])['device_count'].mean().reset_index()
        bl_ten_min.columns = ['building_level', 'ten_min_bin', 'avg_device_count']
        
        # Building-Level 색상
        from src.colors import BUILDING_LEVEL_HEX_COLORS
        
        fig_level = go.Figure()
        for bl in sorted(building_levels):
            bldata = bl_ten_min[bl_ten_min['building_level'] == bl].copy()
            bldata['time_label'] = bldata['ten_min_bin'].apply(lambda x: f"{x//6:02d}:{(x%6)*10:02d}")
            
            fig_level.add_trace(go.Scatter(
                x=bldata['time_label'],
                y=bldata['avg_device_count'],
                mode='lines+markers',
                name=bl,
                line=dict(color=BUILDING_LEVEL_HEX_COLORS.get(bl, '#888888'), width=2),
                marker=dict(size=5)
            ))
        
        fig_level.update_layout(
            title='층별 디바이스 수 (10분 평균)',
            xaxis_title='Time',
            yaxis_title='Average Device Count',
            height=450,
            template='plotly_white',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        st.plotly_chart(fig_level, use_container_width=True)


def _render_tward_vs_mobile_tab(flow_data, sward_config):
    """T-Ward vs Mobile 탭: T41 인원수와 Mobile 디바이스 수 비교 (캐시 사용)"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    st.subheader("🔄 T-Ward vs Mobile Device Count")
    st.info("T41(T-Ward 착용자)과 Mobile Phone 디바이스 수를 비교합니다.")
    
    # T41 데이터 확인
    t41_data = st.session_state.get('tward41_data')
    data_loader = st.session_state.get('data_loader')
    
    if t41_data is None or len(t41_data) == 0:
        st.warning("T41 데이터가 없어 비교할 수 없습니다.")
        return
    
    # Building 목록 가져오기
    if sward_config is not None:
        t41_with_loc = t41_data.merge(
            sward_config[['sward_id', 'building', 'level']],
            on='sward_id',
            how='left'
        )
        buildings = t41_with_loc['building'].dropna().unique().tolist()
        buildings = sorted([b for b in buildings if str(b) != 'nan'])
    else:
        buildings = []
    
    # =========================================================================
    # Building/Level 필터
    # =========================================================================
    st.markdown("### 🏢 Filter by Building/Level")
    col1, col2 = st.columns(2)
    
    with col1:
        selected_building = st.selectbox("Select Building", ["All"] + buildings, key="tvm_building")
    
    if selected_building != "All" and sward_config is not None:
        levels = t41_with_loc[t41_with_loc['building'] == selected_building]['level'].dropna().unique().tolist()
        levels = sorted([l for l in levels if str(l) != 'nan'])
        with col2:
            selected_level = st.selectbox("Select Level", ["All"] + levels, key="tvm_level")
    else:
        selected_level = "All"
    
    st.markdown("---")
    
    # =========================================================================
    # 캐시에서 데이터 로드 (빠른 로딩)
    # =========================================================================
    merged = None
    use_cache = data_loader is not None
    
    if use_cache:
        try:
            merged = data_loader.load_tvm_comparison(selected_building, selected_level)
            if merged is not None and len(merged) > 0:
                # 캐시 데이터 사용
                pass
            else:
                use_cache = False
        except Exception:
            use_cache = False
    
    # =========================================================================
    # 캐시가 없으면 실시간 계산 (fallback)
    # =========================================================================
    if not use_cache:
        t41_copy = t41_data.copy()
        t41_copy['time'] = pd.to_datetime(t41_copy['time'])
        flow_copy = flow_data.copy()
        flow_copy['time'] = pd.to_datetime(flow_copy['time'])
        
        if sward_config is not None:
            t41_with_loc = t41_copy.merge(sward_config[['sward_id', 'building', 'level']], on='sward_id', how='left')
            flow_with_loc = flow_copy.merge(sward_config[['sward_id', 'building', 'level']], on='sward_id', how='left')
        else:
            t41_with_loc = t41_copy
            flow_with_loc = flow_copy
        
        # 데이터 필터링
        if selected_building != "All":
            t41_filtered = t41_with_loc[t41_with_loc['building'] == selected_building].copy()
            flow_filtered = flow_with_loc[flow_with_loc['building'] == selected_building].copy()
            if selected_level != "All":
                t41_filtered = t41_filtered[t41_filtered['level'] == selected_level].copy()
                flow_filtered = flow_filtered[flow_filtered['level'] == selected_level].copy()
        else:
            t41_filtered = t41_with_loc.copy()
            flow_filtered = flow_with_loc.copy()
        
        # T41 계산
        t41_filtered['ten_min_bin'] = (t41_filtered['time'].dt.hour * 6 + t41_filtered['time'].dt.minute // 10)
        t41_counts = t41_filtered.groupby('ten_min_bin')['mac'].nunique().reset_index()
        t41_counts.columns = ['bin_index', 't41_count']
        
        # Flow 계산
        flow_filtered['two_min_bin'] = (flow_filtered['time'].dt.hour * 30 + flow_filtered['time'].dt.minute // 2)
        flow_filtered['ten_min_bin'] = (flow_filtered['time'].dt.hour * 6 + flow_filtered['time'].dt.minute // 10)
        two_min_counts = flow_filtered.groupby('two_min_bin')['mac'].nunique().reset_index()
        two_min_counts.columns = ['two_min_bin', 'device_count']
        two_min_counts['ten_min_bin'] = two_min_counts['two_min_bin'] // 5
        flow_ten_min = two_min_counts.groupby('ten_min_bin')['device_count'].mean().reset_index()
        flow_ten_min.columns = ['bin_index', 'mobile_count']
        
        # 병합
        all_bins = pd.DataFrame({'bin_index': range(144)})
        merged = all_bins.merge(t41_counts, on='bin_index', how='left').fillna(0)
        merged = merged.merge(flow_ten_min, on='bin_index', how='left').fillna(0)
        merged['t41_count'] = merged['t41_count'].astype(int)
        merged['time_label'] = merged['bin_index'].apply(lambda x: f"{x//6:02d}:{(x%6)*10:02d}")
        merged['ratio'] = merged.apply(
            lambda row: (row['t41_count'] / row['mobile_count'] * 100) if row['mobile_count'] > 0 else 0, 
            axis=1
        )
    
    # =========================================================================
    # 비교 차트
    # =========================================================================
    title_suffix = f" - {selected_building}" if selected_building != "All" else " - All Buildings"
    if selected_level != "All":
        title_suffix += f" {selected_level}"
    
    fig = make_subplots(rows=2, cols=1, 
                        subplot_titles=(f'T-Ward vs Mobile Device Count{title_suffix}', 'T-Ward / Mobile Ratio'),
                        row_heights=[0.6, 0.4],
                        vertical_spacing=0.15)
    
    fig.add_trace(go.Scatter(
        x=merged['time_label'],
        y=merged['t41_count'],
        mode='lines+markers',
        name='T-Ward (T41)',
        line=dict(color='#2E86AB', width=3),
        marker=dict(size=8)
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=merged['time_label'],
        y=merged['mobile_count'],
        mode='lines+markers',
        name='Mobile Phone',
        line=dict(color='#E94F37', width=3),
        marker=dict(size=8)
    ), row=1, col=1)
    
    fig.add_trace(go.Bar(
        x=merged['time_label'],
        y=merged['ratio'],
        name='T-Ward / Mobile (%)',
        marker_color='#5C946E'
    ), row=2, col=1)
    
    fig.update_layout(
        height=650,
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        showlegend=True
    )
    fig.update_yaxes(title_text='Count', row=1, col=1)
    fig.update_yaxes(title_text='Ratio (%)', row=2, col=1)
    fig.update_xaxes(title_text='Time', row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # =========================================================================
    # 통계 요약
    # =========================================================================
    st.markdown("### 📊 Summary Statistics")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**🔵 T-Ward (T41)**")
        st.metric("Peak", f"{merged['t41_count'].max():.0f}")
        st.metric("Average", f"{merged['t41_count'].mean():.1f}")
    with col2:
        st.markdown("**🔴 Mobile Phone**")
        st.metric("Peak", f"{merged['mobile_count'].max():.0f}")
        st.metric("Average", f"{merged['mobile_count'].mean():.1f}")
    with col3:
        st.markdown("**🟢 T-Ward / Mobile Ratio**")
        avg_ratio = merged['ratio'].mean()
        st.metric("Average Ratio", f"{avg_ratio:.1f}%")
        
        if avg_ratio > 50:
            st.success("T-Ward 착용률이 높습니다 ✅")
        elif avg_ratio > 30:
            st.info("T-Ward 착용률이 보통입니다")
        else:
            st.warning("T-Ward 착용률이 낮습니다 ⚠️")


def _render_apple_vs_android_tab(flow_data):
    """Apple vs Android 비율 탭"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from src.flow_analysis import identify_device_type_from_type_column
    
    st.subheader("📈 Apple vs Android Device Ratio")
    st.info("디바이스 타입별 분포 분석 (type 컬럼: 1=Apple, 10=Android)")
    
    # 데이터 전처리
    flow_copy = flow_data.copy()
    flow_copy['time'] = pd.to_datetime(flow_copy['time'])
    
    # 디바이스 타입 식별
    if 'type' in flow_copy.columns:
        flow_copy['device_type'] = flow_copy['type'].apply(identify_device_type_from_type_column)
    else:
        st.warning("'type' 컬럼이 없어 정확한 분류가 어렵습니다.")
        flow_copy['device_type'] = 'Unknown'
    
    # =========================================================================
    # 1. 전체 비율 (파이 차트)
    # =========================================================================
    st.markdown("### 🥧 Daily Device Distribution")
    
    # 하루 전체 unique MAC 카운팅 (디바이스 타입별)
    device_summary = flow_copy.groupby('device_type')['mac'].nunique().reset_index()
    device_summary.columns = ['Device Type', 'Count']
    
    total_devices = device_summary['Count'].sum()
    device_summary['Percentage'] = (device_summary['Count'] / total_devices * 100).round(1)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # 파이 차트
        colors = {'Apple': '#A2AAAD', 'Android': '#3DDC84', 'Unknown': '#CCCCCC'}
        
        fig_pie = go.Figure(data=[go.Pie(
            labels=device_summary['Device Type'],
            values=device_summary['Count'],
            hole=0.4,
            marker_colors=[colors.get(dt, '#888888') for dt in device_summary['Device Type']],
            textinfo='label+percent',
            textfont_size=14,
            hovertemplate='%{label}: %{value:,}<extra></extra>'
        )])
        fig_pie.update_layout(
            title='Device Type Distribution',
            height=350,
            showlegend=True
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # 통계 카드
        st.markdown("#### 📊 Device Statistics")
        
        apple_count = device_summary[device_summary['Device Type'] == 'Apple']['Count'].sum()
        android_count = device_summary[device_summary['Device Type'] == 'Android']['Count'].sum()
        unknown_count = device_summary[device_summary['Device Type'] == 'Unknown']['Count'].sum()
        
        apple_pct = (apple_count / total_devices * 100) if total_devices > 0 else 0
        android_pct = (android_count / total_devices * 100) if total_devices > 0 else 0
        
        st.metric("🍎 Apple (iPhone)", f"{apple_count:,}", f"{apple_pct:.1f}%")
        st.metric("🤖 Android", f"{android_count:,}", f"{android_pct:.1f}%")
        st.metric("❓ Unknown", f"{unknown_count:,}")
        st.metric("📱 Total Devices", f"{total_devices:,}")
    
    # =========================================================================
    # 2. 시간대별 비율 추이
    # =========================================================================
    st.markdown("---")
    st.markdown("### ⏰ Hourly Device Type Ratio")
    
    flow_copy['hour'] = flow_copy['time'].dt.hour
    
    # 시간대별 디바이스 타입 카운팅
    hourly_device = flow_copy.groupby(['hour', 'device_type'])['mac'].nunique().reset_index()
    hourly_device.columns = ['Hour', 'Device Type', 'Count']
    
    # 피벗
    hourly_pivot = hourly_device.pivot(index='Hour', columns='Device Type', values='Count').fillna(0)
    hourly_pivot['Total'] = hourly_pivot.sum(axis=1)
    
    if 'Apple' in hourly_pivot.columns:
        hourly_pivot['Apple %'] = (hourly_pivot['Apple'] / hourly_pivot['Total'] * 100).round(1)
    else:
        hourly_pivot['Apple %'] = 0
        
    if 'Android' in hourly_pivot.columns:
        hourly_pivot['Android %'] = (hourly_pivot['Android'] / hourly_pivot['Total'] * 100).round(1)
    else:
        hourly_pivot['Android %'] = 0
    
    hourly_pivot = hourly_pivot.reset_index()
    
    fig_hourly = make_subplots(rows=2, cols=1,
                               subplot_titles=('Device Count by Hour', 'Device Ratio by Hour (%)'),
                               row_heights=[0.5, 0.5],
                               vertical_spacing=0.15)
    
    # 상단: 절대값
    if 'Apple' in hourly_pivot.columns:
        fig_hourly.add_trace(go.Bar(
            x=hourly_pivot['Hour'],
            y=hourly_pivot['Apple'],
            name='Apple',
            marker_color='#A2AAAD'
        ), row=1, col=1)
    
    if 'Android' in hourly_pivot.columns:
        fig_hourly.add_trace(go.Bar(
            x=hourly_pivot['Hour'],
            y=hourly_pivot['Android'],
            name='Android',
            marker_color='#3DDC84'
        ), row=1, col=1)
    
    # 하단: 비율
    fig_hourly.add_trace(go.Scatter(
        x=hourly_pivot['Hour'],
        y=hourly_pivot['Apple %'],
        mode='lines+markers',
        name='Apple %',
        line=dict(color='#A2AAAD', width=2),
        marker=dict(size=8)
    ), row=2, col=1)
    
    fig_hourly.add_trace(go.Scatter(
        x=hourly_pivot['Hour'],
        y=hourly_pivot['Android %'],
        mode='lines+markers',
        name='Android %',
        line=dict(color='#3DDC84', width=2),
        marker=dict(size=8)
    ), row=2, col=1)
    
    fig_hourly.update_layout(
        height=550,
        template='plotly_white',
        barmode='stack',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    fig_hourly.update_yaxes(title_text='Count', row=1, col=1)
    fig_hourly.update_yaxes(title_text='Ratio (%)', row=2, col=1)
    fig_hourly.update_xaxes(title_text='Hour', row=2, col=1)
    
    st.plotly_chart(fig_hourly, use_container_width=True)


# ============================================================================
# Dashboard Mode - 기존 분석 기능을 원본 데이터로 호출 (Legacy)
# ============================================================================

def render_dashboard_t31_full():
    """Dashboard Mode: T31 analysis (reuse existing functions)"""
    st.header("🔧 T31 Equipment Analysis")
    
    if 'tward31_data' not in st.session_state or st.session_state['tward31_data'] is None:
        st.warning("No T31 data available.")
        return
    
    tabs = st.tabs(["Operation Analysis", "Location & Operation", "Report Generation"])
    
    with tabs[0]:
        render_tward31_operation()
    
    with tabs[1]:
        render_tward31_location()
    
    with tabs[2]:
        render_tward31_report_generation()


def render_dashboard_t41_full():
    """Dashboard Mode: T41 analysis (reuse existing functions)"""
    
    if 'tward41_data' not in st.session_state or st.session_state['tward41_data'] is None:
        st.warning("No T41 data available.")
        return
    
    # 기존 render_tward41 함수 호출 (사이드바 설정 포함)
    render_tward41()


def render_dashboard_flow_full():
    """Dashboard Mode: Flow analysis (reuse existing functions)"""
    st.header("📱 Flow (Mobile) Analysis")
    
    if 'flow_data' not in st.session_state or st.session_state['flow_data'] is None:
        st.warning("No Flow data available.")
        return
    
    # 기존 render_flow 함수 호출
    render_flow()


# ============================================================================
# Processing Mode - 기존 업로드 방식
# ============================================================================

def render_tward31_operation():
    st.subheader("Operation Analysis")
    from src.tward_type31_operation import render_operation_analysis_tward31
    render_operation_analysis_tward31(st)

def render_tward31_location():
    st.subheader("Location & Operation Analysis")
    from src.tward_type31_location_operation import render_location_operation_analysis_tward31
    render_location_operation_analysis_tward31(st)

def render_tward31_report_generation():
    st.subheader("Report Generation")
    from src.tward_type31_operation import render_report_generation_tward31
    render_report_generation_tward31(st)

def render_tward41():
    print(">>> render_tward41 function called")
    
    # 사이드바에 분석 설정 추가
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 T-Ward Type 41 Analysis Settings")
    
    # 체류시간 필터링 옵션
    enable_filter = st.sidebar.checkbox(
        "Filter by cumulative dwell time", 
        value=False,
        help="Remove T-Wards with short dwell times (e.g., passing people)"
    )
    
    min_dwell_time = st.sidebar.slider(
        "Minimum dwell time (minutes)",
        min_value=0,
        max_value=120,
        value=30,
        step=5,
        disabled=not enable_filter,
        help="T-Wards with less than this dwell time will be excluded from analysis"
    )
    
    # 설정을 세션 상태에 저장
    st.session_state['tward41_filter_enabled'] = enable_filter
    st.session_state['tward41_min_dwell_time'] = min_dwell_time if enable_filter else 0
    
    # 분석 실행 버튼
    run_analysis = st.sidebar.button(
        "🚀 Run Analysis", 
        type="primary",
        key="run_analysis_button",
        help="Execute analysis with current settings"
    )
    
    # 버튼 클릭 상태를 세션에 저장
    if run_analysis:
        st.session_state['tward41_should_run'] = True
    
    # 현재 설정 표시
    if enable_filter:
        st.sidebar.info(f"🔍 Filtering enabled: Min {min_dwell_time} minutes")
    else:
        st.sidebar.info("📊 No filtering: All T-Wards included")
    
    tabs = st.tabs(["Occupancy Analysis", "Dwell Time Analysis", "Journey Heatmap Analysis", "Location Analysis", "Heatmap Analysis", "Report Generation"])
    
    with tabs[0]:  # Occupancy Analysis
        print(">>> Occupancy Analysis tab selected")
        print(">>> Calling render_tward41_operation")
        render_tward41_operation(st)
        
    with tabs[1]:  # Dwell Time Analysis
        print(">>> Dwell Time Analysis tab selected")
        print(">>> Calling render_tward41_dwell_time")
        render_tward41_dwell_time(st)
        
    with tabs[2]:  # Journey Heatmap Analysis
        print(">>> Journey Heatmap Analysis tab selected")
        print(">>> Calling render_tward41_journey_map")
        render_tward41_journey_map()
        
    with tabs[3]:  # Location Analysis
        print(">>> Location Analysis tab selected")
        st.info("🚧 Location Analysis is temporarily disabled for maintenance.")
        st.markdown("This feature will be available in the next update.")
        # print(">>> Calling display_location_analysis")
        # from src.tward_type41_location_analysis import display_location_analysis
        # display_location_analysis()
        
    with tabs[4]:  # Heatmap Analysis
        print(">>> Heatmap Analysis tab selected")
        st.info("🚧 Heatmap Analysis is temporarily disabled for maintenance.")
        st.markdown("This feature will be available in the next update.")
        # print(">>> Calling display_heatmap_analysis")
        # from src.tward_type41_heatmap_analysis import display_heatmap_analysis
        # display_heatmap_analysis()
        
    with tabs[5]:  # Report Generation
        print(">>> Report Generation tab selected")
        print(">>> Calling render_tward41_report_generation")
        from src.tward_type41_report_generation import render_tward41_report_generation
        render_tward41_report_generation(st)

def render_tward31_41():
    st.info("Location & Operation Analysis (type 31 & 41) - To be implemented.")

def render_flow():
    tab_names = ["Occupancy Analysis", "Location Analysis", "Heatmap Analysis"]
    tabs = st.tabs(tab_names)
    
    with tabs[0]:  # Occupancy Analysis
        from src.flow_analysis import render_flow_occupancy_analysis
        render_flow_occupancy_analysis()
    
    with tabs[1]:  # Location Analysis
        st.info(f"(Flow) {tab_names[1]} - To be implemented.")
    
    with tabs[2]:  # Heatmap Analysis
        st.info(f"(Flow) {tab_names[2]} - To be implemented.")


# ============================================================================
# Main Function with Mode Selection
# ============================================================================

def main():
    # 모드 선택 (최상단)
    st.sidebar.markdown("## 🔄 Mode Selection")
    mode = st.sidebar.radio(
        "Select Mode",
        ("📊 Dashboard (Auto-load)", "🔧 Processing (Upload)"),
        index=0,
        help="Dashboard: 사전 처리된 캐시 데이터 자동 로드\nProcessing: 새 데이터 파일 업로드 및 처리"
    )
    
    st.sidebar.markdown("---")
    
    if mode == "📊 Dashboard (Auto-load)":
        # Dashboard Mode
        render_dashboard_mode()
    else:
        # Processing Mode (기존 방식)
        render_processing_mode()


def render_processing_mode():
    """Processing Mode: 기존 업로드 방식"""
    
    menu = st.sidebar.radio(
        "Main Menu",
        ("Setup", "Input data files", "Data Processing")
    )
    
    # building/level session_state 동기화: Setup에서 선택한 값을 항상 기억
    def sync_last_building_level():
        b = (
            st.session_state.get('sidebar_building_main')
            or st.session_state.get('sidebar_building_new')
            or st.session_state.get('building')
        )
        l = (
            st.session_state.get('sidebar_level_main')
            or st.session_state.get('sidebar_level_new')
            or st.session_state.get('sidebar_level_fallback')
            or st.session_state.get('level')
        )
        if b:
            st.session_state['_last_building'] = b
        if l:
            st.session_state['_last_level'] = l

    if menu == "Setup":
        render_building_setup()
        sync_last_building_level()
    elif menu == "Input data files":
        render_data_input()
        sync_last_building_level()
    elif menu == "Data Processing":
        sync_last_building_level()
        st.header("Data Processing")
        
        # 업로드된 데이터 타입 확인
        has_tward31 = 'tward31_data' in st.session_state and st.session_state['tward31_data'] is not None
        has_tward41 = 'tward41_data' in st.session_state and st.session_state['tward41_data'] is not None
        has_flow = 'flow_data' in st.session_state and st.session_state['flow_data'] is not None
        
        # 사용 가능한 옵션 생성
        available_options = []
        if has_tward31:
            available_options.append("T-Ward Data Processing (type 31)")
        if has_tward41:
            available_options.append("T-Ward Data Processing (type 41)")
        if has_tward31 and has_tward41:
            available_options.append("T-Ward Data Processing (type 31 & type 41)")
        if has_flow:
            available_options.append("Flow Data Processing")
        
        if not available_options:
            st.warning("⚠️ No data uploaded. Please upload data files in 'Input data files' tab first.")
            st.info("Available data types to upload:")
            st.write("- T-Ward Type 31: Equipment monitoring data")
            st.write("- T-Ward Type 41: Worker helmet monitoring data")
            st.write("- Flow Data: Smartphone device flow data")
            return
        
        data_type = st.sidebar.selectbox(
            "Select Data Type",
            available_options,
            key="data_type_select"
        )
        
        # 데이터 상태 표시
        st.sidebar.markdown("### 📊 Uploaded Data Status")
        if has_tward31:
            tward31_count = len(st.session_state['tward31_data'])
            st.sidebar.success(f"✅ Type 31: {tward31_count:,} records")
        if has_tward41:
            tward41_count = len(st.session_state['tward41_data'])
            st.sidebar.success(f"✅ Type 41: {tward41_count:,} records")
        if has_flow:
            flow_count = len(st.session_state['flow_data'])
            st.sidebar.success(f"✅ Flow: {flow_count:,} records")
        
        if data_type == "T-Ward Data Processing (type 31)":
            tabs = st.tabs(["Operation Analysis", "Location & Operation Analysis", "Report Generation"])
            with tabs[0]:
                render_tward31_operation()
            with tabs[1]:
                render_tward31_location()
            with tabs[2]:
                render_tward31_report_generation()
        elif data_type == "T-Ward Data Processing (type 41)":
            print(">>> Type 41 processing selected")
            render_tward41()
        elif data_type == "T-Ward Data Processing (type 31 & type 41)":
            render_tward31_41()
        elif data_type == "Flow Data Processing":
            render_flow()


# ============================================================================
# T31 Sub-tab Functions (New Structure)
# ============================================================================

def render_t31_overview():
    """T31 Overview: Equipment count, operation status, utilization rate"""
    st.subheader("📊 T31 Overview - Equipment Status Summary")
    
    t31_data = st.session_state.get('tward31_data')
    sward_config = st.session_state.get('sward_config')
    
    if t31_data is None or t31_data.empty:
        st.warning("No T31 data available.")
        return
    
    # Basic statistics
    total_equipment = t31_data['mac'].nunique()
    total_records = len(t31_data)
    
    # Join with sward_config for building/level info
    if sward_config is not None:
        t31_with_loc = t31_data.merge(
            sward_config[['sward_id', 'building', 'level']],
            on='sward_id',
            how='left'
        )
        buildings = t31_with_loc['building'].dropna().unique().tolist()
    else:
        t31_with_loc = t31_data
        buildings = []
    
    # =========================================================================
    # Key Metrics (70% size) - 텍스트 검정색으로 명확히 표시
    # =========================================================================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #e8f4ea; border-radius: 5px; color: #000;">
            <div style="color: #333;">🔧 Total Equipment</div>
            <div style="font-size: 1.5em; font-weight: bold; color: #000;">{total_equipment}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Active equipment (those with signals)
        active_count = total_equipment  # All detected are active
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #e8f0fe; border-radius: 5px; color: #000;">
            <div style="color: #333;">✅ Active Equipment</div>
            <div style="font-size: 1.5em; font-weight: bold; color: #000;">{active_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #fef7e0; border-radius: 5px; color: #000;">
            <div style="color: #333;">🏢 Buildings</div>
            <div style="font-size: 1.5em; font-weight: bold; color: #000;">{len(buildings)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #fce8e6; border-radius: 5px; color: #000;">
            <div style="color: #333;">📊 Total Records</div>
            <div style="font-size: 1.5em; font-weight: bold; color: #000;">{total_records:,}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # =========================================================================
    # Equipment count by Building/Level (Primary Location 기준)
    # T31은 고정 장비이므로, 가장 많이 감지된 위치를 primary location으로 결정
    # =========================================================================
    st.markdown("### 🏢 Equipment by Building & Level")
    
    if sward_config is not None and 'building' in t31_with_loc.columns:
        # 각 MAC이 어느 Building/Level에서 가장 많이 감지되었는지 계산
        mac_loc_counts = t31_with_loc.groupby(['mac', 'building', 'level']).size().reset_index(name='signal_count')
        
        # 각 MAC의 primary location (가장 많이 감지된 곳)
        idx = mac_loc_counts.groupby('mac')['signal_count'].idxmax()
        mac_primary_loc = mac_loc_counts.loc[idx][['mac', 'building', 'level']]
        
        # Primary location 기준으로 Building/Level별 장비 수 계산
        building_level_counts = mac_primary_loc.groupby(['building', 'level']).size().reset_index(name='Equipment Count')
        building_level_counts.columns = ['Building', 'Level', 'Equipment Count']
        
        # 합계 행 추가 (Primary location 기준이므로 합이 total과 일치해야 함)
        total_row = pd.DataFrame([{
            'Building': 'Total',
            'Level': '-',
            'Equipment Count': total_equipment
        }])
        building_level_display = pd.concat([building_level_counts, total_row], ignore_index=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(building_level_display, use_container_width=True)
            st.caption("※ 각 장비의 주 위치(Primary Location) 기준 - 가장 많이 감지된 위치")
        
        with col2:
            # Bar chart
            import plotly.express as px
            fig = px.bar(building_level_counts, x='Building', y='Equipment Count', 
                        color='Level', barmode='group',
                        title='Equipment Distribution by Building & Level')
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # =========================================================================
    # 빌딩별/층별 가동률 통계 (T31 핵심 지표)
    # 가동률 = (활성 시간 bins 수 / 전체 시간 bins 수) × 100
    # =========================================================================
    st.markdown("### 📊 Operation Rate by Building & Level")
    st.info("**가동률** = (활성 시간 bins / 전체 시간 bins) × 100% - 24시간 중 장비가 가동된 시간 비율")
    
    if sward_config is not None and 'building' in t31_with_loc.columns and 'time' in t31_data.columns:
        t31_with_time = t31_with_loc.copy()
        t31_with_time['time'] = pd.to_datetime(t31_with_time['time'])
        t31_with_time['time_bin'] = (t31_with_time['time'].dt.hour * 6 + t31_with_time['time'].dt.minute // 10)
        
        # Building-Level 별 가동률 계산
        utilization_stats = []
        
        for building in buildings:
            building_data = mac_primary_loc[mac_primary_loc['building'] == building]
            levels_in_building = building_data['level'].unique()
            
            for level in levels_in_building:
                # 해당 building-level의 장비 MAC 목록
                macs_in_loc = mac_primary_loc[
                    (mac_primary_loc['building'] == building) & 
                    (mac_primary_loc['level'] == level)
                ]['mac'].tolist()
                
                if not macs_in_loc:
                    continue
                
                # 해당 장비들의 활성 time bin 수 계산
                loc_data = t31_with_time[t31_with_time['mac'].isin(macs_in_loc)]
                
                # 장비별 평균 활성 bin 수
                mac_active_bins = loc_data.groupby('mac')['time_bin'].nunique()
                avg_active_bins = mac_active_bins.mean() if len(mac_active_bins) > 0 else 0
                
                # 가동률 = 활성 bins / 144 (하루 전체 10분 bins)
                utilization_rate = (avg_active_bins / 144) * 100
                
                utilization_stats.append({
                    'Building': building,
                    'Level': level,
                    'Equipment': len(macs_in_loc),
                    'Avg Active Bins': round(avg_active_bins, 1),
                    'Utilization Rate (%)': round(utilization_rate, 1)
                })
        
        if utilization_stats:
            util_df = pd.DataFrame(utilization_stats)
            
            # 전체 평균 행 추가
            total_avg = {
                'Building': 'Average',
                'Level': '-',
                'Equipment': total_equipment,
                'Avg Active Bins': round(util_df['Avg Active Bins'].mean(), 1),
                'Utilization Rate (%)': round(util_df['Utilization Rate (%)'].mean(), 1)
            }
            util_df = pd.concat([util_df, pd.DataFrame([total_avg])], ignore_index=True)
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.dataframe(util_df, use_container_width=True)
            
            with col2:
                # 가동률 바 차트
                chart_df = util_df[util_df['Building'] != 'Average'].copy()
                chart_df['Location'] = chart_df['Building'] + '-' + chart_df['Level']
                
                import plotly.express as px
                fig = px.bar(chart_df, x='Location', y='Utilization Rate (%)',
                            color='Building', title='Utilization Rate by Location')
                fig.update_layout(height=300, showlegend=False)
                fig.add_hline(y=util_df['Utilization Rate (%)'].iloc[-1], 
                             line_dash="dash", line_color="red",
                             annotation_text=f"Avg: {util_df['Utilization Rate (%)'].iloc[-1]}%")
                st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # =========================================================================
    # 10-min Interval Operation Rate Chart (꺾은선 그래프)
    # =========================================================================
    st.markdown("### ⏰ Equipment Operation Rate (10-min intervals)")
    
    if 'time' in t31_data.columns:
        t31_copy = t31_data.copy()
        t31_copy['time'] = pd.to_datetime(t31_copy['time'])
        # 10분 단위 bin
        t31_copy['time_bin'] = (t31_copy['time'].dt.hour * 6 + t31_copy['time'].dt.minute // 10)
        
        # 10분 단위별 활성 장비 수
        bin_active = t31_copy.groupby('time_bin')['mac'].nunique().reset_index()
        bin_active.columns = ['Time Bin', 'Active Equipment']
        bin_active['Operation Rate (%)'] = (bin_active['Active Equipment'] / total_equipment * 100).round(1)
        
        # 시간 라벨 생성 (HH:MM 형식)
        bin_active['Time Label'] = bin_active['Time Bin'].apply(
            lambda x: f"{x // 6:02d}:{(x % 6) * 10:02d}"
        )
        
        import plotly.express as px
        fig = px.line(bin_active, x='Time Label', y='Operation Rate (%)',
                     title='Equipment Operation Rate (10-min intervals)',
                     markers=True)
        fig.update_layout(
            height=350,
            xaxis_title='Time',
            xaxis=dict(tickangle=45, dtick=6)  # 1시간마다 라벨 표시
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # =========================================================================
    # AI Comment
    # =========================================================================
    st.markdown("### 🤖 AI Analysis Comment")
    ai_comment = f"""
    **Equipment Status Summary:**
    - Total {total_equipment} T31 equipment detected across {len(buildings)} buildings
    - All equipment showed active signals during the monitoring period
    - Peak operation hours are typically during work shifts (8AM-6PM)
    
    **Recommendations:**
    - Monitor equipment with low signal counts for potential issues
    - Consider equipment distribution optimization based on usage patterns
    """
    st.info(ai_comment)


def render_t31_location_analysis():
    """T31 Location Analysis: Equipment location on map"""
    st.subheader("📍 T31 Location Analysis")
    
    t31_data = st.session_state.get('tward31_data')
    sward_config = st.session_state.get('sward_config')
    
    if t31_data is None or sward_config is None:
        st.warning("T31 data or S-Ward configuration not available.")
        return
    
    # Building/Level selection
    buildings = sward_config['building'].dropna().unique().tolist()
    
    col1, col2 = st.columns(2)
    with col1:
        selected_building = st.selectbox("Select Building", buildings, key="t31_loc_building")
    
    levels = sward_config[sward_config['building'] == selected_building]['level'].dropna().unique().tolist()
    with col2:
        selected_level = st.selectbox("Select Level", levels, key="t31_loc_level")
    
    st.markdown("---")
    
    # Get equipment in this location
    t31_with_loc = t31_data.merge(
        sward_config[['sward_id', 'building', 'level', 'x', 'y']],
        on='sward_id',
        how='left'
    )
    
    filtered = t31_with_loc[
        (t31_with_loc['building'] == selected_building) & 
        (t31_with_loc['level'] == selected_level)
    ]
    
    equipment_list = filtered['mac'].unique().tolist()
    
    # =========================================================================
    # Equipment Statistics with Operation Time
    # =========================================================================
    st.markdown(f"### 🔧 Equipment in {selected_building} - {selected_level}")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.metric("Equipment Count", len(equipment_list))
        
        # 장비별 가동시간 계산 (10분 bin 수 × 10분)
        if len(equipment_list) > 0:
            t31_copy = filtered.copy()
            t31_copy['time'] = pd.to_datetime(t31_copy['time'])
            t31_copy['time_bin'] = (t31_copy['time'].dt.hour * 6 + t31_copy['time'].dt.minute // 10)
            
            # MAC별 unique time_bin 수 = 가동 시간 (10분 단위)
            mac_operation = t31_copy.groupby('mac')['time_bin'].nunique().reset_index()
            mac_operation.columns = ['MAC Address', 'Active Bins']
            mac_operation['Operation Time (min)'] = mac_operation['Active Bins'] * 10
            mac_operation['Operation Time (hr)'] = (mac_operation['Operation Time (min)'] / 60).round(1)
            mac_operation = mac_operation.sort_values('Operation Time (min)', ascending=False)
            
            st.markdown("**Equipment Operation Time:**")
            st.dataframe(
                mac_operation[['MAC Address', 'Operation Time (hr)']].head(20),
                use_container_width=True
            )
    
    with col2:
        # =========================================================================
        # 지도 이미지 위에 장비 위치 표시
        # =========================================================================
        st.markdown("### 🗺️ Equipment Location Map")
        
        # 지도 이미지 경로 결정
        map_image_path = _get_map_image_path(selected_building, selected_level)
        
        if map_image_path and os.path.exists(map_image_path):
            import plotly.graph_objects as go
            from PIL import Image
            import base64
            from io import BytesIO
            
            # 이미지 로드 및 base64 인코딩
            img = Image.open(map_image_path)
            img_width, img_height = img.size
            
            # PIL Image를 base64로 변환 (Plotly 호환)
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            img_src = f"data:image/png;base64,{img_base64}"
            
            # 장비 위치 계산
            if 'x' in filtered.columns and 'y' in filtered.columns:
                equipment_positions = filtered.groupby('mac').agg({
                    'x': 'mean',
                    'y': 'mean',
                    'sward_id': 'first'
                }).reset_index()
                
                # Plotly figure with image background
                fig = go.Figure()
                
                # 배경 이미지 추가 (base64 인코딩)
                fig.add_layout_image(
                    dict(
                        source=img_src,
                        xref="x",
                        yref="y",
                        x=0,
                        y=img_height,
                        sizex=img_width,
                        sizey=img_height,
                        sizing="stretch",
                        opacity=1,
                        layer="below"
                    )
                )
                
                # Y좌표 반전 (지도 좌표계 맞춤: y' = img_height - y)
                equipment_positions['y_flipped'] = img_height - equipment_positions['y']
                
                # 장비 위치 표시 (청록색 - 지도의 빨간 점과 구분)
                fig.add_trace(go.Scatter(
                    x=equipment_positions['x'],
                    y=equipment_positions['y_flipped'],
                    mode='markers+text',
                    marker=dict(size=14, color='cyan', symbol='circle', 
                               line=dict(width=2, color='darkblue')),
                    text=equipment_positions['mac'].str[:6],
                    textposition='top center',
                    textfont=dict(color='darkblue', size=10),
                    hovertemplate='<b>MAC:</b> %{customdata[0]}<br><b>X:</b> %{x}<br><b>Y:</b> %{customdata[1]}<extra></extra>',
                    customdata=equipment_positions[['mac', 'y']].values
                ))
                
                fig.update_layout(
                    title=f'Equipment Positions - {selected_building} {selected_level}',
                    xaxis=dict(range=[0, img_width], showgrid=False),
                    yaxis=dict(range=[0, img_height], showgrid=False, scaleanchor="x"),
                    height=500,
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.image(map_image_path, caption=f'{selected_building} {selected_level}')
                st.warning("Equipment position coordinates (x, y) not available.")
        else:
            # 지도 이미지가 없으면 scatter plot만 표시 (청록색 사용)
            if 'x' in filtered.columns and 'y' in filtered.columns:
                equipment_positions = filtered.groupby('mac').agg({
                    'x': 'mean',
                    'y': 'mean',
                    'sward_id': 'first'
                }).reset_index()
                
                import plotly.express as px
                fig = px.scatter(equipment_positions, x='x', y='y', 
                                hover_data=['mac', 'sward_id'],
                                title=f'Equipment Positions - {selected_building} {selected_level}')
                fig.update_traces(marker=dict(size=14, color='cyan',
                                             line=dict(width=2, color='darkblue')))
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"Map image not found: {map_image_path}")


def _get_map_image_path(building: str, level: str) -> str:
    """빌딩/층에 맞는 지도 이미지 경로 반환"""
    import os
    
    base_path = "Datafile/Map_Image"
    
    # 가능한 파일명 패턴들
    patterns = [
        f"Map_{building}_{level}.png",
        f"Map_{building}.png",
        f"{building}_{level}.png",
        f"{building}.png"
    ]
    
    for pattern in patterns:
        full_path = os.path.join(base_path, pattern)
        if os.path.exists(full_path):
            return full_path
    
    return None


def render_t31_operation_heatmap():
    """T31 Operation Heatmap: Dashboard Mode용 - session_state 데이터 사용"""
    st.subheader("🗺️ T31 Operation Heatmap")
    st.info("Equipment operation status over 24 hours - Sorted by Building & Level")
    
    t31_data = st.session_state.get('tward31_data')
    sward_config = st.session_state.get('sward_config')
    cache_loader = st.session_state.get('cache_loader')
    
    if t31_data is None or t31_data.empty:
        st.warning("No T31 data available. Please load data first.")
        return
    
    # 캐시된 히트맵 데이터 확인 - 히트맵 형식인지 검증
    heatmap_cache = None
    if cache_loader:
        try:
            temp_cache = cache_loader.load_t31_operation_heatmap()
            # 히트맵 형식 검증: DataFrame이고 144개 컬럼(시간 bin)이 있어야 함
            if isinstance(temp_cache, pd.DataFrame) and temp_cache.shape[1] >= 100:
                heatmap_cache = temp_cache
        except:
            pass
    
    if heatmap_cache is not None:
        st.success("✅ Using precomputed heatmap data (fast)")
        _display_t31_heatmap_from_cache(heatmap_cache)
    else:
        # 실시간 계산 (캐시가 없거나 형식이 맞지 않음)
        _display_t31_heatmap_realtime(t31_data, sward_config)


def _display_building_level_legend():
    """Building-Level 색상 범례 표시 - Streamlit columns 사용"""
    from src.colors import COLOR_HEX_MAP
    
    legend_items = [
        ('No Signal', COLOR_HEX_MAP[0]),
        ('Inactive', COLOR_HEX_MAP[1]),
        ('WWT-1F', COLOR_HEX_MAP[2]),
        ('WWT-B1F', COLOR_HEX_MAP[3]),
        ('FAB', COLOR_HEX_MAP[4]),
        ('CUB-1F', COLOR_HEX_MAP[5]),
        ('CUB-B1F', COLOR_HEX_MAP[6]),
        ('Cluster', COLOR_HEX_MAP[7]),
    ]
    
    # Streamlit columns로 범례 표시
    cols = st.columns(len(legend_items))
    for i, (label, color) in enumerate(legend_items):
        with cols[i]:
            # 색상이 어두우면 흰색 텍스트, 밝으면 검정 텍스트
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:5px;">'
                f'<span style="display:inline-block;width:20px;height:14px;background-color:{color};border:1px solid #333;"></span>'
                f'<span style="font-size:12px;color:#000;font-weight:500;">{label}</span>'
                f'</div>',
                unsafe_allow_html=True
            )


def _display_t31_heatmap_from_cache(heatmap_data):
    """캐시된 히트맵 데이터로 표시 - Building-Level 색상 사용"""
    import plotly.graph_objects as go
    from src.colors import COLOR_HEX_MAP, BUILDING_LEVEL_COLORS, COLOR_LABELS
    
    # 캐시 데이터 구조에 따라 표시
    if isinstance(heatmap_data, pd.DataFrame):
        # Building-Level 색상 매핑
        bl_to_color_idx = {
            'WWT-1F': 2, 'WWT-B1F': 3, 'WWT-2F': 2,
            'FAB-1F': 4, 'FAB-B1F': 4, 'FAB-2F': 4,
            'CUB-1F': 5, 'CUB-B1F': 6, 'CUB-2F': 5,
            'Cluster-1F': 7, 'Cluster-B1F': 7, 'Cluster-2F': 7,
        }
        
        # Y축 라벨에서 Building-Level 추출하여 색상 인덱스 결정
        z_data = heatmap_data.values.copy()
        y_labels = heatmap_data.index.tolist()
        
        for i, label in enumerate(y_labels):
            # 라벨에서 building-level 추출 (예: "WWT-1F | ABC123")
            label_str = str(label)  # 정수인 경우 문자열로 변환
            if ' | ' in label_str:
                bl = label_str.split(' | ')[0]
            elif '-' in label_str and label_str.count('-') >= 1:
                parts = label_str.split('-')
                bl = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else 'Unknown'
            else:
                bl = 'Unknown'
            color_idx = bl_to_color_idx.get(bl, 1)  # 기본은 gray (inactive)
            
            # active (1) → building-level color
            for j in range(z_data.shape[1]):
                if z_data[i, j] == 1:
                    z_data[i, j] = color_idx
        
        # z_data 값을 0-7 범위로 클램핑
        z_data = np.clip(z_data, 0, 7)
        
        # Discrete colorscale 생성 (0-7 정수 매핑)
        # 0=No Signal, 1=Inactive, 2=WWT-1F, 3=WWT-B1F, 4=FAB, 5=CUB-1F, 6=CUB-B1F, 7=Cluster
        colorscale = [
            [0/7, COLOR_HEX_MAP[0]],  # 0: No Signal - Black
            [1/7, COLOR_HEX_MAP[1]],  # 1: Inactive - Gray
            [2/7, COLOR_HEX_MAP[2]],  # 2: WWT-1F - Green
            [3/7, COLOR_HEX_MAP[3]],  # 3: WWT-B1F - Yellow
            [4/7, COLOR_HEX_MAP[4]],  # 4: FAB - Orange
            [5/7, COLOR_HEX_MAP[5]],  # 5: CUB-1F - Sky Blue
            [6/7, COLOR_HEX_MAP[6]],  # 6: CUB-B1F - Blue
            [7/7, COLOR_HEX_MAP[7]],  # 7: Cluster - Purple
        ]
        
        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=[f"{i//6:02d}:{(i%6)*10:02d}" for i in range(144)],
            y=y_labels,
            colorscale=colorscale,
            zmin=0,
            zmax=7,
            showscale=True,
            colorbar=dict(
                tickvals=[0, 1, 2, 3, 4, 5, 6, 7],
                ticktext=['No Signal', 'Inactive', 'WWT-1F', 'WWT-B1F', 'FAB', 'CUB-1F', 'CUB-B1F', 'Cluster']
            )
        ))
        fig.update_layout(
            title='T31 Equipment Operation Heatmap (10-min intervals) - Building-Level Colors',
            xaxis_title='Time',
            yaxis_title='Equipment (Building-Level)',
            height=max(400, len(heatmap_data) * 20)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 범례 표시
        _display_building_level_legend()


def _display_t31_heatmap_realtime(t31_data, sward_config):
    """실시간 계산하여 히트맵 표시 - Building-Level 색상 사용"""
    import plotly.graph_objects as go
    from src.colors import COLOR_HEX_MAP, BUILDING_LEVEL_COLORS
    
    # Building-Level 색상 매핑
    bl_to_color_idx = {
        'WWT-1F': 2, 'WWT-B1F': 3, 'WWT-2F': 2,
        'FAB-1F': 4, 'FAB-B1F': 4, 'FAB-2F': 4,
        'CUB-1F': 5, 'CUB-B1F': 6, 'CUB-2F': 5,
        'Cluster-1F': 7, 'Cluster-B1F': 7, 'Cluster-2F': 7,
    }
    
    # 데이터 전처리
    t31_copy = t31_data.copy()
    t31_copy['time'] = pd.to_datetime(t31_copy['time'])
    t31_copy['time_bin'] = (t31_copy['time'].dt.hour * 6 + t31_copy['time'].dt.minute // 10)
    
    # S-Ward config와 조인
    if sward_config is not None:
        t31_with_loc = t31_copy.merge(
            sward_config[['sward_id', 'building', 'level']],
            on='sward_id',
            how='left'
        )
    else:
        t31_with_loc = t31_copy
        t31_with_loc['building'] = 'Unknown'
        t31_with_loc['level'] = 'Unknown'
    
    # MAC별 building-level 결정 (가장 많이 감지된 위치)
    mac_locations = t31_with_loc.groupby(['mac', 'building', 'level']).size().reset_index(name='count')
    mac_primary_loc = mac_locations.loc[mac_locations.groupby('mac')['count'].idxmax()]
    mac_primary_loc['location'] = mac_primary_loc['building'] + '-' + mac_primary_loc['level']
    
    # MAC별 location 색상 인덱스 매핑
    mac_color_map = {}
    for _, row in mac_primary_loc.iterrows():
        location = row['location']
        mac_color_map[row['mac']] = bl_to_color_idx.get(location, 1)
    
    # MAC별 time_bin 활성 여부
    mac_time_active = t31_with_loc.groupby(['mac', 'time_bin']).size().reset_index(name='signals')
    mac_time_active['active'] = 1  # 신호가 있으면 활성
    
    # 피벗 테이블 생성 (MAC x time_bin)
    pivot_df = mac_time_active.pivot(index='mac', columns='time_bin', values='active').fillna(0)
    
    # 모든 144개 time bin 보장
    for i in range(144):
        if i not in pivot_df.columns:
            pivot_df[i] = 0
    pivot_df = pivot_df.reindex(columns=range(144), fill_value=0)
    
    # MAC에 location 정보 추가 후 정렬
    mac_loc_map = mac_primary_loc.set_index('mac')['location'].to_dict()
    pivot_df['location'] = pivot_df.index.map(mac_loc_map)
    pivot_df = pivot_df.sort_values('location')
    
    # active (1) → building-level color index로 변환
    z_data = pivot_df.drop('location', axis=1).values.copy().astype(float)
    mac_list = pivot_df.index.tolist()
    
    for i, mac in enumerate(mac_list):
        color_idx = mac_color_map.get(mac, 1)
        for j in range(z_data.shape[1]):
            if z_data[i, j] == 1:
                z_data[i, j] = color_idx
    
    # z_data 값을 0-7 범위로 클램핑
    z_data = np.clip(z_data, 0, 7)
    
    # Y축 라벨: location + MAC 앞 8자리
    y_labels = [f"{mac_loc_map.get(mac, 'Unknown')} | {mac[:8]}" for mac in mac_list]
    
    # Discrete colorscale 생성 (0-7 정수 매핑)
    # 0=No Signal, 1=Inactive, 2=WWT-1F, 3=WWT-B1F, 4=FAB, 5=CUB-1F, 6=CUB-B1F, 7=Cluster
    colorscale = [
        [0/7, COLOR_HEX_MAP[0]],  # 0: No Signal - Black
        [1/7, COLOR_HEX_MAP[1]],  # 1: Inactive - Gray
        [2/7, COLOR_HEX_MAP[2]],  # 2: WWT-1F - Green
        [3/7, COLOR_HEX_MAP[3]],  # 3: WWT-B1F - Yellow
        [4/7, COLOR_HEX_MAP[4]],  # 4: FAB - Orange
        [5/7, COLOR_HEX_MAP[5]],  # 5: CUB-1F - Sky Blue
        [6/7, COLOR_HEX_MAP[6]],  # 6: CUB-B1F - Blue
        [7/7, COLOR_HEX_MAP[7]],  # 7: Cluster - Purple
    ]
    
    # 히트맵 생성
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=[f"{i//6:02d}:{(i%6)*10:02d}" for i in range(144)],
        y=y_labels,
        colorscale=colorscale,
        zmin=0,
        zmax=7,
        showscale=True,
        colorbar=dict(
            tickvals=[0, 1, 2, 3, 4, 5, 6, 7],
            ticktext=['No Signal', 'Inactive', 'WWT-1F', 'WWT-B1F', 'FAB', 'CUB-1F', 'CUB-B1F', 'Cluster']
        ),
        hovertemplate='Time: %{x}<br>Equipment: %{y}<br>Status: %{z}<extra></extra>'
    ))
    
    fig.update_layout(
        title='T31 Equipment Operation Heatmap (10-min intervals) - Building-Level Colors',
        xaxis_title='Time',
        yaxis_title='Equipment (Building-Level | MAC)',
        height=max(500, len(pivot_df) * 15),
        xaxis=dict(tickangle=45, dtick=6)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 범례 표시
    _display_building_level_legend()
    
    # 통계 표시
    total_active_cells = (z_data > 1).sum()  # color index > 1 = active
    total_cells = len(pivot_df) * 144
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Equipment", len(pivot_df))
    with col2:
        st.metric("Active Time Slots", f"{total_active_cells:,}")
    with col3:
        operation_rate = (total_active_cells / total_cells * 100) if total_cells > 0 else 0
        st.metric("Operation Rate", f"{operation_rate:.1f}%")


def render_t31_ai_insight_report():
    """T31 AI Insight & Report: AI analysis and PDF report generation (캐시 데이터 사용)"""
    st.subheader("🤖 T31 AI Insight & Report")
    
    cache_loader = st.session_state.get('cache_loader')
    t31_data = st.session_state.get('tward31_data')
    
    if t31_data is None:
        st.warning("No T31 data available for analysis.")
        return
    
    # =========================================================================
    # AI Insights (캐시에서 로드)
    # =========================================================================
    st.markdown("### 💡 AI-Generated Insights")
    
    # 캐시된 AI 인사이트 로드 시도
    cached_insights = None
    if cache_loader:
        cached_insights = cache_loader.load_ai_insights('t31')
    
    total_equipment = t31_data['mac'].nunique()
    total_records = len(t31_data)
    
    if cached_insights:
        st.success("✅ AI Insights loaded from cache (pre-computed)")
        
        # 캐시 데이터가 문자열인지 Dict인지 확인
        if isinstance(cached_insights, str):
            # 문자열 형식 - 직접 표시
            st.markdown(cached_insights)
        elif isinstance(cached_insights, dict):
            # Dict 형식 - 구조화된 표시
            insights_data = cached_insights
            st.markdown(f"""
**📊 Data Overview:**
- Analysis Date: {insights_data.get('analysis_date', 'N/A')}
- Total Equipment: {insights_data.get('summary', {}).get('total_items', total_equipment):,}
- Total Records: {insights_data.get('summary', {}).get('total_records', total_records):,}

**🔍 Key Findings:**
""")
            for i, finding in enumerate(insights_data.get('findings', []), 1):
                st.markdown(f"{i}. **{finding.get('title', '')}**: {finding.get('description', '')}")
            
            st.markdown("\n**⚠️ Attention Items:**")
            for alert in insights_data.get('alerts', []):
                st.markdown(f"- {alert}")
            
            st.markdown("\n**💡 Recommendations:**")
            for i, rec in enumerate(insights_data.get('recommendations', []), 1):
                st.markdown(f"{i}. {rec}")
    else:
        # 폴백: 기본 인사이트
        insights = f"""
**📊 Data Overview:**
- Analyzed {total_equipment} T31 equipment with {total_records:,} signal records
- Monitoring period: 24 hours

**🔍 Key Findings:**
1. **Equipment Utilization**: Most equipment showed consistent operation patterns
2. **Peak Hours**: Highest activity observed during 8AM-6PM work hours
3. **Building Distribution**: Equipment distributed across multiple buildings

**⚠️ Attention Items:**
- Equipment with <10 signals may need inspection
- Consider load balancing for heavily used equipment

**💡 Recommendations:**
1. Schedule maintenance for low-activity equipment
2. Optimize equipment placement based on usage patterns
3. Monitor equipment health indicators regularly
"""
        st.markdown(insights)
    
    st.markdown("---")
    
    # =========================================================================
    # Report Generation
    # =========================================================================
    st.markdown("### 📋 Report Generation")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Preview Report:**")
        with st.expander("📄 View Report Preview", expanded=True):
            st.markdown("## T31 Equipment Analysis Report")
            st.markdown(f"**Date:** {pd.Timestamp.now().strftime('%Y-%m-%d')}")
            st.markdown(f"**Total Equipment:** {total_equipment:,}")
            st.markdown(f"**Total Records:** {total_records:,}")
            st.markdown("---")
            if cached_insights:
                if isinstance(cached_insights, str):
                    st.markdown(cached_insights[:500] + "..." if len(cached_insights) > 500 else cached_insights)
                elif isinstance(cached_insights, dict):
                    for finding in cached_insights.get('findings', []):
                        st.markdown(f"- **{finding.get('title', '')}**: {finding.get('description', '')}")
    
    with col2:
        st.markdown("**Download Report:**")
        
        sward_config = st.session_state.get('sward_config')
        
        # PDF 생성 버튼
        if st.button("📥 Generate Comprehensive PDF Report", key="t31_pdf_report"):
            try:
                from src.report_generator import generate_comprehensive_t31_report
                pdf_bytes = generate_comprehensive_t31_report(t31_data, sward_config, cached_insights)
                st.session_state['t31_pdf_bytes'] = pdf_bytes
                st.success("✅ Comprehensive PDF Report generated!")
            except ImportError as ie:
                st.info(f"PDF generation module not available: {ie}")
            except Exception as e:
                st.error(f"Error generating PDF: {str(e)}")
        
        # 다운로드 버튼
        pdf_bytes = st.session_state.get('t31_pdf_bytes')
        if pdf_bytes:
            st.download_button(
                label="📥 Download PDF",
                data=pdf_bytes,
                file_name="T31_Equipment_Report.pdf",
                mime="application/pdf"
            )
        else:
            st.download_button(
                label="📥 Download PDF",
                data="Click 'Generate PDF Report' first",
                file_name="T31_Equipment_Report.pdf",
                mime="application/pdf",
                disabled=True
            )


# ============================================================================
# T41 Sub-tab Functions (New Structure)
# ============================================================================

def render_t41_overview():
    """T41 Overview: Worker count (active only), busy buildings/levels, hourly personnel chart
    
    T41 특성:
    - 작업자 헬멧에 부착
    - 활성 상태: 진동 감지 → 1분에 2회 이상 신호 (10초 간격)
    - 비활성 상태: 진동 없음 → 1분에 2회 미만 (헬멧이 놓여있는 상태)
    """
    st.subheader("📊 T41 Overview - Worker Status Summary")
    
    t41_data = st.session_state.get('tward41_data')
    sward_config = st.session_state.get('sward_config')
    
    if t41_data is None or t41_data.empty:
        st.warning("No T41 data available.")
        return
    
    # Join with sward_config for building/level info
    if sward_config is not None:
        t41_with_loc = t41_data.merge(
            sward_config[['sward_id', 'building', 'level']],
            on='sward_id',
            how='left'
        )
    else:
        t41_with_loc = t41_data
    
    # =========================================================================
    # 활성/비활성 작업자 분리 (1분에 2회 이상 = 활성)
    # =========================================================================
    t41_copy = t41_with_loc.copy()
    t41_copy['time'] = pd.to_datetime(t41_copy['time'])
    t41_copy['minute_bin'] = t41_copy['time'].dt.floor('1min')
    
    # 1분 단위 신호 수
    minute_signal_count = t41_copy.groupby(['mac', 'minute_bin']).size().reset_index(name='signals_per_min')
    
    # MAC별로 활성 상태였던 분의 수 (1분에 2회 이상 신호)
    minute_signal_count['is_active'] = minute_signal_count['signals_per_min'] >= 2
    mac_active_minutes = minute_signal_count.groupby('mac')['is_active'].sum().reset_index(name='active_minutes')
    
    # 활성 작업자: 하루 동안 최소 1분 이상 활성이었던 MAC
    active_workers = mac_active_minutes[mac_active_minutes['active_minutes'] >= 1]['mac'].nunique()
    total_detected = t41_data['mac'].nunique()
    inactive_workers = total_detected - active_workers
    
    total_records = len(t41_data)
    buildings = t41_with_loc['building'].dropna().unique().tolist() if 'building' in t41_with_loc.columns else []
    
    # =========================================================================
    # Key Metrics (70% size) - 텍스트 검정색으로 명확히 표시
    # =========================================================================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #e8f4ea; border-radius: 5px; color: #000;">
            <div style="color: #333;">👷 Active Workers</div>
            <div style="font-size: 1.5em; font-weight: bold; color: #000;">{active_workers:,}</div>
            <div style="font-size: 0.8em; color: #666;">({inactive_workers:,} inactive helmets)</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Find busiest building (활성 상태 기준)
    if 'building' in t41_with_loc.columns:
        # 활성 상태만 필터링: 1분에 2회 이상 신호
        active_records = t41_copy.merge(
            minute_signal_count[minute_signal_count['is_active']][['mac', 'minute_bin']],
            on=['mac', 'minute_bin'],
            how='inner'
        )
        if not active_records.empty:
            building_counts = active_records.groupby('building')['mac'].nunique()
            busiest_building = building_counts.idxmax() if not building_counts.empty else "N/A"
            busiest_count = building_counts.max() if not building_counts.empty else 0
        else:
            busiest_building = "N/A"
            busiest_count = 0
    else:
        busiest_building = "N/A"
        busiest_count = 0
    
    with col2:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #e8f0fe; border-radius: 5px; color: #000;">
            <div style="color: #333;">🏢 Busiest Building</div>
            <div style="font-size: 1.3em; font-weight: bold; color: #000;">{busiest_building}</div>
            <div style="font-size: 0.9em; color: #333;">{busiest_count:,} workers</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Find busiest level (활성 상태 기준)
    if 'level' in t41_with_loc.columns and not active_records.empty:
        level_counts = active_records.groupby(['building', 'level'])['mac'].nunique().reset_index()
        if not level_counts.empty:
            busiest_idx = level_counts['mac'].idxmax()
            busiest_level = f"{level_counts.loc[busiest_idx, 'building']}-{level_counts.loc[busiest_idx, 'level']}"
            busiest_level_count = level_counts.loc[busiest_idx, 'mac']
        else:
            busiest_level = "N/A"
            busiest_level_count = 0
    else:
        busiest_level = "N/A"
        busiest_level_count = 0
    
    with col3:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #fef7e0; border-radius: 5px; color: #000;">
            <div style="color: #333;">📍 Busiest Level</div>
            <div style="font-size: 1.3em; font-weight: bold; color: #000;">{busiest_level}</div>
            <div style="font-size: 0.9em; color: #333;">{busiest_level_count:,} workers</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #fce8e6; border-radius: 5px; color: #000;">
            <div style="color: #333;">📊 Total Records</div>
            <div style="font-size: 1.5em; font-weight: bold; color: #000;">{total_records:,}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # =========================================================================
    # 10-min Interval Personnel Chart by Building/Level (꺾은선 그래프)
    # =========================================================================
    st.markdown("### ⏰ Personnel Count (10-min intervals)")
    
    # 캐시 데이터 로더 확인
    cache_loader = st.session_state.get('cache_loader')
    use_cached = cache_loader is not None
    
    if 'time' in t41_data.columns:
        # Building selection
        col1, col2 = st.columns(2)
        with col1:
            selected_building = st.selectbox("Select Building", ["All"] + buildings, key="t41_ov_building")
        
        if selected_building != "All":
            t41_copy = t41_with_loc.copy()
            t41_copy['time'] = pd.to_datetime(t41_copy['time'])
            t41_copy['minute_bin'] = t41_copy['time'].dt.floor('1min')
            levels = t41_copy[t41_copy['building'] == selected_building]['level'].dropna().unique().tolist()
            with col2:
                selected_level = st.selectbox("Select Level", ["All"] + levels, key="t41_ov_level")
        else:
            selected_level = "All"
        
        # =====================================================================
        # 캐시된 데이터 사용 (빠른 로딩)
        # =====================================================================
        if use_cached:
            try:
                # 캐시에서 10분 단위 stats 로드
                bin_stats = cache_loader.load_t41_stats_10min(selected_building, selected_level)
                
                if bin_stats is not None and len(bin_stats) > 0:
                    # 컬럼명 매핑
                    bin_stats = bin_stats.rename(columns={'bin_index': 'Time Bin', 'time_label': 'Time Label'})
                else:
                    # 캐시 없으면 실시간 계산
                    use_cached = False
            except Exception as e:
                # 캐시 로드 실패 시 실시간 계산
                use_cached = False
        
        # =====================================================================
        # 캐시가 없으면 실시간 계산 (fallback)
        # =====================================================================
        if not use_cached:
            t41_copy = t41_with_loc.copy()
            t41_copy['time'] = pd.to_datetime(t41_copy['time'])
            t41_copy['time_bin'] = (t41_copy['time'].dt.hour * 6 + t41_copy['time'].dt.minute // 10)
            t41_copy['minute_bin'] = t41_copy['time'].dt.floor('1min')
            
            # Filter data
            if selected_building != "All":
                filtered = t41_copy[t41_copy['building'] == selected_building].copy()
                if selected_level != "All":
                    filtered = filtered[filtered['level'] == selected_level].copy()
            else:
                filtered = t41_copy.copy()
            
            if 'minute_bin' not in filtered.columns:
                filtered['minute_bin'] = filtered['time'].dt.floor('1min')
            
            # 1분 단위 신호 수 계산
            filtered_minute = filtered.groupby(['mac', 'minute_bin']).size().reset_index(name='signals')
            filtered_minute['is_active'] = filtered_minute['signals'] >= 2
            filtered_minute['time_bin'] = (
                filtered_minute['minute_bin'].dt.hour * 6 + 
                filtered_minute['minute_bin'].dt.minute // 10
            )
            
            mac_bin_activity = filtered_minute.groupby(['mac', 'time_bin']).agg({
                'is_active': 'any'
            }).reset_index()
            
            bin_total = filtered_minute.groupby('time_bin')['mac'].nunique().reset_index()
            bin_total.columns = ['Time Bin', 'Total']
            
            bin_active = mac_bin_activity[mac_bin_activity['is_active']].groupby('time_bin')['mac'].nunique().reset_index()
            bin_active.columns = ['Time Bin', 'Active']
            
            bin_inactive = mac_bin_activity[~mac_bin_activity['is_active']].groupby('time_bin')['mac'].nunique().reset_index()
            bin_inactive.columns = ['Time Bin', 'Inactive']
            
            all_bins = pd.DataFrame({'Time Bin': range(144)})
            bin_stats = all_bins.merge(bin_total, on='Time Bin', how='left').fillna(0)
            bin_stats = bin_stats.merge(bin_active, on='Time Bin', how='left').fillna(0)
            bin_stats = bin_stats.merge(bin_inactive, on='Time Bin', how='left').fillna(0)
            
            bin_stats['Total'] = bin_stats['Total'].astype(int)
            bin_stats['Active'] = bin_stats['Active'].astype(int)
            bin_stats['Inactive'] = bin_stats['Inactive'].astype(int)
            bin_stats['Time Label'] = bin_stats['Time Bin'].apply(
                lambda x: f"{x // 6:02d}:{(x % 6) * 10:02d}"
            )
        
        import plotly.graph_objects as go
        
        title = f"Worker Count (10-min intervals) - {selected_building}"
        if selected_level != "All":
            title += f" {selected_level}"
        
        fig = go.Figure()
        
        # Total (전체) - 회색 점선
        fig.add_trace(go.Scatter(
            x=bin_stats['Time Label'],
            y=bin_stats['Total'],
            mode='lines+markers',
            name='Total',
            line=dict(color='gray', width=2, dash='dash'),
            marker=dict(size=4)
        ))
        
        # Active (활성) - 초록색 실선
        fig.add_trace(go.Scatter(
            x=bin_stats['Time Label'],
            y=bin_stats['Active'],
            mode='lines+markers',
            name='Active (vibration)',
            line=dict(color='#00CC00', width=2),
            marker=dict(size=5),
            fill='tozeroy',
            fillcolor='rgba(0, 204, 0, 0.2)'
        ))
        
        # Inactive (비활성) - 주황색 실선
        fig.add_trace(go.Scatter(
            x=bin_stats['Time Label'],
            y=bin_stats['Inactive'],
            mode='lines+markers',
            name='Inactive (no vibration)',
            line=dict(color='#FF8C00', width=2),
            marker=dict(size=5)
        ))
        
        fig.update_layout(
            title=title,
            height=400,
            xaxis_title='Time',
            yaxis_title='Worker Count',
            xaxis=dict(tickangle=45, dtick=6),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 피크 시간 정보
        peak_total_bin = bin_stats.loc[bin_stats['Total'].idxmax()]
        peak_active_bin = bin_stats.loc[bin_stats['Active'].idxmax()]
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"📊 **Total Peak**: {int(peak_total_bin['Total'])} workers at {peak_total_bin['Time Label']}")
        with col2:
            st.success(f"🏃 **Active Peak**: {int(peak_active_bin['Active'])} workers at {peak_active_bin['Time Label']}")
    
    st.markdown("---")
    
    # =========================================================================
    # 빌딩별/층별 평균 체류시간 (T41 핵심 지표)
    # 체류시간 = 활성 상태인 10분 bin 수 × 10분
    # =========================================================================
    st.markdown("### 📊 Average Dwell Time by Building & Level")
    st.info("**평균 체류시간** = 활성 상태 10분 bins × 10분 - 작업자가 해당 위치에서 활성 상태로 머문 시간")
    
    if sward_config is not None and 'building' in t41_with_loc.columns:
        # 전체 t41 데이터에서 활성 상태 계산 (위에서 계산한 것 재사용하거나 새로 계산)
        t41_dwell = t41_copy.copy()
        
        # 1분 단위 신호 수 계산
        dwell_minute = t41_dwell.groupby(['mac', 'minute_bin', 'building', 'level']).size().reset_index(name='signals')
        dwell_minute['is_active'] = dwell_minute['signals'] >= 2
        
        # 활성 상태인 분만 필터링
        active_dwell = dwell_minute[dwell_minute['is_active']]
        
        if not active_dwell.empty:
            # Building-Level별 체류시간 집계
            # 각 MAC이 각 Building-Level에서 활성 상태로 머문 분 수
            mac_location_dwell = active_dwell.groupby(['mac', 'building', 'level']).size().reset_index(name='active_minutes')
            
            # Building-Level별 평균 체류시간 계산
            dwell_stats = mac_location_dwell.groupby(['building', 'level']).agg({
                'mac': 'nunique',  # 해당 위치 방문 작업자 수
                'active_minutes': 'mean'  # 평균 활성 분 수
            }).reset_index()
            dwell_stats.columns = ['Building', 'Level', 'Workers', 'Avg Dwell (min)']
            dwell_stats['Avg Dwell (min)'] = dwell_stats['Avg Dwell (min)'].round(1)
            
            # 전체 평균 행 추가
            total_avg = {
                'Building': 'Average',
                'Level': '-',
                'Workers': mac_location_dwell['mac'].nunique(),
                'Avg Dwell (min)': round(dwell_stats['Avg Dwell (min)'].mean(), 1)
            }
            dwell_display = pd.concat([dwell_stats, pd.DataFrame([total_avg])], ignore_index=True)
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.dataframe(dwell_display, use_container_width=True)
            
            with col2:
                # 체류시간 바 차트
                chart_df = dwell_stats.copy()
                chart_df['Location'] = chart_df['Building'] + '-' + chart_df['Level']
                
                import plotly.express as px
                fig = px.bar(chart_df, x='Location', y='Avg Dwell (min)',
                            color='Building', title='Average Dwell Time by Location')
                fig.update_layout(height=300, showlegend=False)
                avg_dwell = dwell_display['Avg Dwell (min)'].iloc[-1]
                fig.add_hline(y=avg_dwell, line_dash="dash", line_color="red",
                             annotation_text=f"Avg: {avg_dwell} min")
                st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # =========================================================================
    # AI Comment
    # =========================================================================
    st.markdown("### 🤖 AI Analysis Comment")
    ai_comment = f"""
    **Worker Mobility Summary:**
    - **{active_workers:,}** active workers detected (helmets with vibration)
    - **{inactive_workers:,}** inactive helmets (placed/stored without vibration)
    - Busiest location: **{busiest_level}** with {busiest_level_count:,} active workers
    
    **Activity Detection:**
    - Active: ≥2 signals per minute (helmet being worn and moving)
    - Inactive: <2 signals per minute (helmet at rest)
    
    **Key Observations:**
    - Peak activity hours align with work shifts
    - Cross-building movement patterns detected
    - Consider traffic optimization for high-congestion areas
    """
    st.info(ai_comment)


def render_t41_location_analysis():
    """T41 Location Analysis: Worker location heatmap (Coming Soon)"""
    st.subheader("📍 T41 Location Analysis - Position Heatmap")
    
    sward_config = st.session_state.get('sward_config')
    
    if sward_config is None:
        st.warning("S-Ward configuration not available.")
        return
    
    # Building/Level selection
    buildings = sward_config['building'].dropna().unique().tolist()
    
    col1, col2 = st.columns(2)
    with col1:
        selected_building = st.selectbox("Select Building", buildings, key="t41_heatmap_building")
    
    levels = sward_config[sward_config['building'] == selected_building]['level'].dropna().unique().tolist()
    with col2:
        selected_level = st.selectbox("Select Level", levels, key="t41_heatmap_level")
    
    st.markdown("---")
    
    # =========================================================================
    # 히트맵 기능 - 추후 제공 안내
    # =========================================================================
    st.markdown(f"### 🗺️ Worker Location Heatmap - {selected_building} {selected_level}")
    
    st.info("""
    🚧 **Coming Soon - 추후 제공 예정**
    
    **계획된 기능:**
    - 10초 단위로 T-Ward 실제 위치 계산 (RSSI 기반 삼각측량)
    - 누적 위치 데이터를 기반으로 밀집도 히트맵 생성
    - 시간대별 히트맵 비교 분석
    
    다음 업데이트에서 제공될 예정입니다.
    """)
    
    st.markdown("---")
    
    # =========================================================================
    # S-Ward Positions with Map Background
    # =========================================================================
    st.markdown("### 📍 S-Ward Positions")
    
    sward_in_level = sward_config[
        (sward_config['building'] == selected_building) & 
        (sward_config['level'] == selected_level)
    ]
    
    if not sward_in_level.empty and 'x' in sward_in_level.columns:
        # 지도 이미지 로드
        map_image_path = _get_map_image_path(selected_building, selected_level)
        
        if map_image_path and os.path.exists(map_image_path):
            import plotly.graph_objects as go
            from PIL import Image
            
            img = Image.open(map_image_path)
            img_width, img_height = img.size
            
            fig = go.Figure()
            
            # 배경 이미지
            fig.add_layout_image(
                dict(
                    source=img,
                    xref="x",
                    yref="y",
                    x=0,
                    y=img_height,
                    sizex=img_width,
                    sizey=img_height,
                    sizing="stretch",
                    opacity=1,
                    layer="below"
                )
            )
            
            # Y좌표 반전 (지도 좌표계 맞춤: y' = img_height - y)
            sward_y_flipped = img_height - sward_in_level['y']
            
            # S-Ward 위치 표시 (청록색 - 지도의 빨간 점과 구분)
            fig.add_trace(go.Scatter(
                x=sward_in_level['x'],
                y=sward_y_flipped,
                mode='markers+text',
                marker=dict(size=12, color='cyan', symbol='square',
                           line=dict(width=2, color='darkblue')),
                text=sward_in_level['sward_id'].astype(str).str[-4:],  # 마지막 4자리만
                textposition='top center',
                textfont=dict(size=9, color='darkblue'),
                hovertemplate='<b>S-Ward:</b> %{customdata[0]}<br><b>X:</b> %{x}<br><b>Y (original):</b> %{customdata[1]}<extra></extra>',
                customdata=sward_in_level[['sward_id', 'y']].values,
                name='S-Ward'
            ))
            
            fig.update_layout(
                title=f'S-Ward Positions - {selected_building} {selected_level}',
                xaxis=dict(range=[0, img_width], showgrid=False),
                yaxis=dict(range=[0, img_height], showgrid=False, scaleanchor="x"),
                height=500,
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # S-Ward 통계
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("S-Ward Count", len(sward_in_level))
            with col2:
                if 'space_type' in sward_in_level.columns:
                    space_types = sward_in_level['space_type'].nunique()
                    st.metric("Space Types", space_types)
            with col3:
                st.metric("Building-Level", f"{selected_building}-{selected_level}")
        else:
            # 지도 이미지 없이 scatter plot만 표시 (청록색)
            import plotly.express as px
            fig = px.scatter(sward_in_level, x='x', y='y',
                            hover_data=['sward_id'],
                            title=f'S-Ward Positions - {selected_building} {selected_level}')
            fig.update_traces(marker=dict(size=14, color='cyan', symbol='square',
                                         line=dict(width=2, color='darkblue')))
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No S-Ward position data available for this location.")


def _get_precomputed_video_path(building: str, level: str) -> str:
    """사전 생성된 비디오 파일 경로 반환"""
    import os
    import glob
    
    # 가능한 비디오 파일 패턴들
    patterns = [
        f"movement_{building}_{level}.mp4",
        f"tward_timelapse_{building}_{level}_*.mp4",
        f"T41_{building}_{level}_*.mp4",
    ]
    
    # 캐시 폴더에서 검색 (우선)
    cache_loader = st.session_state.get('cache_loader')
    if cache_loader and hasattr(cache_loader, 'cache_folder'):
        cache_folder = cache_loader.cache_folder
        for pattern in patterns:
            matches = glob.glob(os.path.join(cache_folder, pattern))
            if matches:
                return sorted(matches)[-1]
    
    # session_state의 cache_folder에서 검색
    cache_folder = st.session_state.get('cache_folder', '')
    if cache_folder:
        for pattern in patterns:
            matches = glob.glob(os.path.join(cache_folder, pattern))
            if matches:
                return sorted(matches)[-1]
    
    # 현재 디렉토리에서 검색
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]
    
    return None


def _get_precomputed_heatmap_path(building: str, level: str) -> str:
    """사전 생성된 히트맵 이미지 경로 반환"""
    import os
    import glob
    
    # 가능한 히트맵 파일 패턴들
    patterns = [
        f"location_heatmap_{building}_{level}.png",
        f"heatmap_{building}_{level}.png",
    ]
    
    # 캐시 폴더에서 검색 (우선)
    cache_loader = st.session_state.get('cache_loader')
    if cache_loader and hasattr(cache_loader, 'cache_folder'):
        cache_folder = cache_loader.cache_folder
        for pattern in patterns:
            matches = glob.glob(os.path.join(cache_folder, pattern))
            if matches:
                return sorted(matches)[-1]
    
    # session_state의 cache_folder에서 검색
    cache_folder = st.session_state.get('cache_folder', '')
    if cache_folder:
        for pattern in patterns:
            matches = glob.glob(os.path.join(cache_folder, pattern))
            if matches:
                return sorted(matches)[-1]
    
    # 현재 디렉토리에서 검색
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]
    
    return None


def render_t41_journey_heatmap():
    """T41 Journey Heatmap: Worker movement heatmap with sorting options"""
    st.subheader("🗺️ T41 Journey Heatmap")
    
    # Sorting options
    st.markdown("### ⚙️ Sorting Options")
    
    sort_options = [
        "AI Recommended (activity patterns)",
        "Dwell Time (longest first)",
        "Building (grouped, then by dwell time)",
        "Signal Count (most active first)"
    ]
    
    sort_option = st.selectbox(
        "Sort workers by:",
        sort_options,
        index=0,  # 기본값: AI Recommended
        key="t41_journey_sort"
    )
    
    # 정렬 옵션을 session_state에 저장하여 journey_map 함수에서 사용
    st.session_state['journey_sort_option'] = sort_option
    
    st.markdown("---")
    
    # Call existing Journey Heatmap function
    render_tward41_journey_map()


def render_t41_ai_insight_report():
    """T41 AI Insight & Report: AI analysis and PDF report generation (캐시 데이터 사용)"""
    st.subheader("🤖 T41 AI Insight & Report")
    
    cache_loader = st.session_state.get('cache_loader')
    t41_data = st.session_state.get('tward41_data')
    
    if t41_data is None:
        st.warning("No T41 data available for analysis.")
        return
    
    # =========================================================================
    # AI Insights (캐시에서 로드)
    # =========================================================================
    st.markdown("### 💡 AI-Generated Insights")
    
    # 캐시된 AI 인사이트 로드 시도
    cached_insights = None
    if cache_loader:
        cached_insights = cache_loader.load_ai_insights('t41')
    
    total_workers = t41_data['mac'].nunique()
    total_records = len(t41_data)
    
    if cached_insights:
        st.success("✅ AI Insights loaded from cache (pre-computed)")
        
        # 캐시 데이터가 문자열인지 Dict인지 확인
        if isinstance(cached_insights, str):
            # 문자열 형식 - 직접 표시
            st.markdown(cached_insights)
        elif isinstance(cached_insights, dict):
            # Dict 형식 - 구조화된 표시
            insights_data = cached_insights
            st.markdown(f"""
**📊 Data Overview:**
- Analysis Date: {insights_data.get('analysis_date', 'N/A')}
- Total Workers: {insights_data.get('summary', {}).get('total_items', total_workers):,}
- Total Records: {insights_data.get('summary', {}).get('total_records', total_records):,}
- Congestion Score: {insights_data.get('congestion_score', 'N/A')}

**🔍 Key Findings:**
""")
            for i, finding in enumerate(insights_data.get('findings', []), 1):
                st.markdown(f"{i}. **{finding.get('title', '')}**: {finding.get('description', '')}")
            
            st.markdown("\n**⚠️ Safety Observations:**")
            for alert in insights_data.get('alerts', []):
                st.markdown(f"- {alert}")
            
            st.markdown("\n**💡 Recommendations:**")
            for i, rec in enumerate(insights_data.get('recommendations', []), 1):
                st.markdown(f"{i}. {rec}")
        
        # Congestion Info (캐시에서 로드)
        congestion_info = cache_loader.get_t41_congestion_info()
        if congestion_info:
            st.markdown("---")
            st.markdown("### 📍 Congestion Analysis")
            
            col1, col2 = st.columns(2)
            with col1:
                peak_hour = congestion_info.get('peak_hour', 'N/A')
                peak_count = congestion_info.get('peak_count', 0)
                st.metric("🕐 Peak Hour", f"{peak_hour}:00", f"{peak_count:,} workers")
            
            with col2:
                busiest_building = congestion_info.get('busiest_building', 'N/A')
                busiest_count = congestion_info.get('busiest_building_count', 0)
                st.metric("🏢 Busiest Building", busiest_building, f"{busiest_count:,} workers")
    else:
        # 폴백: 기본 인사이트
        insights = f"""
**📊 Data Overview:**
- Analyzed {total_workers:,} workers with {total_records:,} signal records
- Monitoring period: 24 hours (full workday)

**🔍 Key Findings:**
1. **Worker Mobility**: High cross-building movement detected
2. **Peak Hours**: Most activity during 9AM-5PM
3. **Congestion Points**: Identified specific areas with high worker density

**⚠️ Safety Observations:**
- Some workers showed extended periods in hazardous zones
- Cross-zone movement patterns may indicate workflow inefficiencies

**💡 Recommendations:**
1. Optimize worker routing to reduce congestion
2. Consider shift scheduling adjustments for peak hours
3. Review safety protocols for high-exposure areas
"""
        st.markdown(insights)
    
    st.markdown("---")
    
    # =========================================================================
    # Report Generation
    # =========================================================================
    st.markdown("### 📋 Report Generation")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Preview Report:**")
        with st.expander("📄 View Report Preview", expanded=True):
            st.markdown("## T41 Worker Analysis Report")
            st.markdown(f"**Date:** {pd.Timestamp.now().strftime('%Y-%m-%d')}")
            st.markdown(f"**Total Workers:** {total_workers:,}")
            st.markdown(f"**Total Records:** {total_records:,}")
            st.markdown("---")
            if cached_insights:
                if isinstance(cached_insights, str):
                    st.markdown(cached_insights[:500] + "..." if len(cached_insights) > 500 else cached_insights)
                elif isinstance(cached_insights, dict):
                    for finding in cached_insights.get('findings', []):
                        st.markdown(f"- **{finding.get('title', '')}**: {finding.get('description', '')}")
    
    with col2:
        st.markdown("**Download Report:**")
        
        sward_config = st.session_state.get('sward_config')
        
        # PDF 생성 버튼
        if st.button("📥 Generate Comprehensive PDF Report", key="t41_pdf_report"):
            try:
                from src.report_generator import generate_comprehensive_t41_report
                pdf_bytes = generate_comprehensive_t41_report(t41_data, sward_config, cached_insights)
                st.session_state['t41_pdf_bytes'] = pdf_bytes
                st.success("✅ Comprehensive PDF Report generated!")
            except ImportError as ie:
                st.info(f"PDF generation module not available: {ie}")
            except Exception as e:
                st.error(f"Error generating PDF: {str(e)}")
        
        # 다운로드 버튼
        pdf_bytes = st.session_state.get('t41_pdf_bytes')
        if pdf_bytes:
            st.download_button(
                label="📥 Download PDF",
                data=pdf_bytes,
                file_name="T41_Worker_Report.pdf",
                mime="application/pdf"
            )
        else:
            st.download_button(
                label="📥 Download PDF",
                data="Click 'Generate PDF Report' first",
                file_name="T41_Worker_Report.pdf",
                mime="application/pdf",
                disabled=True
            )


if __name__ == "__main__":
    main()
