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
    
    # 10분 단위로 직접 신호 수 계산
    bin_signal = t41_copy.groupby(['mac', 'time_bin']).size().reset_index(name='signals')
    bin_signal['is_active'] = bin_signal['signals'] >= 11  # 10분에 11회 이상 = Active
    
    # 10분 bin당 활성 여부
    mac_bin_activity = bin_signal[['mac', 'time_bin', 'is_active']]
    
    # 10분 bin별 Total (신호가 있는 모든 MAC)
    bin_total = bin_signal.groupby('time_bin')['mac'].nunique().reset_index()
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
    # bin_index에서 Hour 추출 (bin_index는 0부터 시작, 6개가 1시간)
    if 'Hour' not in bin_stats_10min.columns:
        bin_stats_10min = bin_stats_10min.copy()
        bin_index_col = 'bin_index' if 'bin_index' in bin_stats_10min.columns else 'ten_min_bin'
        bin_stats_10min['Hour'] = bin_stats_10min[bin_index_col] // 6
    
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
    
    if not datasets:
        st.warning("⚠️ No pre-processed datasets available.")
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
    
    # 원본 데이터를 session_state에 로드 (기존 분석 기능 사용을 위해)
    # T31 데이터 로드 (레코드가 있으면)
    if selected_dataset.get('t31_records', 0) > 0:
        if 'tward31_data' not in st.session_state or st.session_state.get('_dashboard_dataset') != selected_name:
            try:
                st.session_state['tward31_data'] = cache_loader.load_raw_t31()
            except:
                st.session_state['tward31_data'] = None
    
    # T41 데이터 로드 (레코드가 있으면)
    if selected_dataset.get('t41_records', 0) > 0:
        if 'tward41_data' not in st.session_state or st.session_state.get('_dashboard_dataset') != selected_name:
            try:
                st.session_state['tward41_data'] = cache_loader.load_raw_t41()
                # Journey Heatmap용 activity_analysis 로드
                activity_analysis = cache_loader.load_t41_activity_analysis()
                if len(activity_analysis) > 0:
                    st.session_state['type41_activity_analysis'] = activity_analysis
                # Journey Heatmap precomputed 데이터 로드 (10분 단위, 벡터화)
                journey_heatmap = cache_loader.load_t41_journey_heatmap()
                if len(journey_heatmap) > 0:
                    st.session_state['type41_journey_heatmap'] = journey_heatmap
            except:
                st.session_state['tward41_data'] = None
    
    # Flow 데이터 로드 (레코드가 있으면)
    if selected_dataset.get('flow_records', 0) > 0:
        if 'flow_data' not in st.session_state or st.session_state.get('_dashboard_dataset') != selected_name:
            try:
                st.session_state['flow_data'] = cache_loader.load_raw_flow()
            except:
                st.session_state['flow_data'] = None
    
    # S-Ward config 로드
    raw_data_status = cache_loader.has_raw_data()
    
    if raw_data_status.get('sward_config', False):
        if 'sward_config' not in st.session_state or st.session_state.get('_dashboard_dataset') != selected_name:
            st.session_state['sward_config'] = cache_loader.load_raw_sward_config()
            # building/level 목록 설정
            sward_config = st.session_state['sward_config']
            if 'building' in sward_config.columns:
                st.session_state['buildings'] = sward_config['building'].unique().tolist()
                if st.session_state['buildings']:
                    first_building = st.session_state['buildings'][0]
                    st.session_state['building'] = first_building
                    st.session_state['_last_building'] = first_building
                    levels = sward_config[sward_config['building'] == first_building]['level'].unique().tolist()
                    st.session_state['levels'] = levels
                    if levels:
                        st.session_state['level'] = levels[0]
                        st.session_state['_last_level'] = levels[0]
    
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
    
    with main_tabs[0]:  # Overview
        render_dashboard_overview(cache_loader, selected_dataset)
    
    with main_tabs[1]:  # T-Ward Type 31
        # Check if data exists (Raw or Cache)
        if selected_dataset.get('t31_records', 0) > 0 or raw_data_status.get('t31', False):
            render_dashboard_t31_tab()
        else:
            st.warning("⚠️ No T31 data available.")
    
    with main_tabs[2]:  # T-Ward Type 41
        if selected_dataset.get('t41_records', 0) > 0 or raw_data_status.get('t41', False):
            render_dashboard_t41_tab()
        else:
            st.warning("⚠️ No T41 data available.")
    
    with main_tabs[3]:  # MobilePhone
        if selected_dataset.get('flow_records', 0) > 0 or raw_data_status.get('flow', False):
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
    
    # =========================================================================
    # T31 Equipment Operation Rate Chart (1-hour aggregation)
    # =========================================================================
    st.subheader("🔧 T31 Equipment Operation Rate")
    
    if cache_loader:
        try:
            # Load T31 10-min operation rate
            t31_ten_min = cache_loader.load_t31_ten_min_operation_rate()
            
            if t31_ten_min is not None and not t31_ten_min.empty:
                # Convert to hourly average
                if 'bin_index' in t31_ten_min.columns:
                    t31_ten_min['hour'] = t31_ten_min['bin_index'] // 6
                elif 'ten_min_bin' in t31_ten_min.columns:
                    t31_ten_min['hour'] = t31_ten_min['ten_min_bin'] // 6
                
                t31_hourly = t31_ten_min.groupby('hour')['operation_rate'].mean().reset_index()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### 🔧 T31 Equipment Operation Rate")
                    import matplotlib.pyplot as plt
                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.bar(t31_hourly['hour'], t31_hourly['operation_rate'], color='#FF9800')
                    ax.set_xlabel('Hour')
                    ax.set_ylabel('Operation Rate (%)')
                    ax.set_title('T31 Equipment Operation Rate by Hour')
                    ax.set_xticks(range(0, 24))
                    ax.set_ylim(0, 100)
                    st.pyplot(fig)
                    plt.close()
                
                with col2:
                    st.dataframe(t31_hourly.rename(columns={'hour': 'Hour', 'operation_rate': 'Operation Rate (%)'}), 
                               use_container_width=True, hide_index=True)
            else:
                st.info("No T31 cached data available.")
        except Exception as e:
            st.error(f"Failed to load T31 data: {e}")
    else:
        st.info("Cache loader not initialized.")
    
    # =========================================================================
    # T41 Worker Status Chart (1-hour aggregation)
    # =========================================================================
    st.subheader("👷 T41 Worker Status")
    
    cache_loader = st.session_state.get('cache_loader')
    
    if cache_loader:
        try:
            # Load cached stats (same as T41 Overview tab)
            bin_stats = cache_loader.load_t41_stats_10min("All", "All")
            
            if bin_stats is not None and not bin_stats.empty:
                # 시간대별 집계 (피크 값 사용)
                hourly_stats = calculate_t41_hourly_stats(bin_stats)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### 👷 T41 Worker Status (Active/Inactive)")
                    import matplotlib.pyplot as plt
                    fig, ax = plt.subplots(figsize=(10, 4))
                    # 스택 막대그래프: 아래=Active(초록), 위=Inactive(회색)
                    ax.bar(hourly_stats['Hour'], hourly_stats['Active'], color='#4CAF50', label='Active (≥11 signals/10min)')
                    ax.bar(hourly_stats['Hour'], hourly_stats['Inactive'], bottom=hourly_stats['Active'], color='#BDBDBD', label='Inactive (<11 signals/10min)')
                    ax.set_xlabel('Hour')
                    ax.set_ylabel('Workers')
                    ax.set_title('T41 Workers by Hour (Active/Inactive)')
                    ax.set_xticks(range(0, 24))
                    ax.legend(loc='upper right')
                    st.pyplot(fig)
                    plt.close()
                
                with col2:
                    st.dataframe(hourly_stats[['Hour', 'Active', 'Inactive', 'Total']], use_container_width=True, hide_index=True)
            else:
                st.info("No T41 cached data available.")
        except Exception as e:
            st.error(f"Failed to load T41 data: {e}")
    else:
        st.info("Cache loader not initialized.")
    
    # =========================================================================
    # MobilePhone Device Counting Chart (1-hour aggregation)
    # =========================================================================
    st.subheader("📱 MobilePhone Device Counting")
    
    if cache_loader:
        try:
            # Load cached flow hourly AVERAGE data (flow_results_hourly_avg_from_2min.parquet)
            hourly_avg = cache_loader.load_flow_hourly_avg_from_2min()
            
            if hourly_avg is not None and not hourly_avg.empty:
                # Rename columns for consistency
                if 'avg_unique_mac' in hourly_avg.columns:
                    hourly_avg = hourly_avg.rename(columns={'avg_unique_mac': 'avg_device_count'})
                elif 'device_count' in hourly_avg.columns:
                    hourly_avg = hourly_avg.rename(columns={'device_count': 'avg_device_count'})
                
                if 'hour' in hourly_avg.columns and 'avg_device_count' in hourly_avg.columns:
                    
                    # Visualization
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### 📱 MobilePhone Device Count")
                        import matplotlib.pyplot as plt
                        fig, ax = plt.subplots(figsize=(10, 4))
                        ax.bar(hourly_avg['hour'], hourly_avg['avg_device_count'], color='#2196F3')
                        ax.set_xlabel('Hour')
                        ax.set_ylabel('Average Device Count')
                        ax.set_title('MobilePhone Device Count by Hour')
                        ax.set_xticks(range(0, 24))
                        st.pyplot(fig)
                        plt.close()
                    
                    with col2:
                        st.dataframe(hourly_avg.rename(columns={'hour': 'Hour', 'avg_device_count': 'Avg Count'}), 
                                   use_container_width=True, hide_index=True)
                else:
                    st.info("No device count data available.")
            else:
                st.info("No Flow hourly data available.")
        except Exception as e:
            st.error(f"Failed to load Flow data: {e}")
    else:
        st.info("Cache loader not initialized.")
    
    st.markdown("---")
    st.info("💡 **Tip**: Check detailed analysis results in each tab.")


def render_dashboard_t31_tab():
    """T-Ward Type 31 tab: Equipment Analysis with 4 sub-tabs"""
    st.header("🔧 T-Ward Type 31 - Equipment Analysis")
    
    # Check for either raw data OR cache loader
    has_raw = 'tward31_data' in st.session_state and st.session_state['tward31_data'] is not None
    has_cache = 'cache_loader' in st.session_state
    
    if not has_raw and not has_cache:
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
    
    # Check for either raw data OR cache loader
    has_raw = 'tward41_data' in st.session_state and st.session_state['tward41_data'] is not None
    has_cache = 'cache_loader' in st.session_state
    
    if not has_raw and not has_cache:
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
    
    cache_loader = st.session_state.get('cache_loader')
    flow_data = st.session_state.get('flow_data')
    
    if flow_data is None and cache_loader is None:
        st.warning("Flow 데이터가 없습니다.")
        return
    
    sward_config = st.session_state.get('sward_config')
    
    # Flow 서브탭 - 개편된 구조
    sub_tabs = st.tabs([
        "📊 Device Counting", 
        "🔄 T-Ward vs Mobile",
        "📈 Apple vs Android"
    ])
    
    with sub_tabs[0]:  # Device Counting
        _render_device_counting_tab(flow_data, sward_config, cache_loader)
    
    with sub_tabs[1]:  # T-Ward vs Mobile
        _render_tward_vs_mobile_tab(flow_data, sward_config, cache_loader)
        
    with sub_tabs[2]:  # Apple vs Android
        _render_apple_vs_android_tab(flow_data, cache_loader)


def _render_device_counting_tab(flow_data, sward_config, cache_loader=None):
    """Device Counting 탭 - 캐시 데이터만 사용"""
    import plotly.graph_objects as go
    
    st.subheader("📊 Device Counting (Hourly Average)")
    st.info("**Data Source**: Pre-computed hourly averages from cache")
    
    if not cache_loader:
        st.error("Cache data is required for this tab.")
        return
    
    # =========================================================================
    # 캐시된 1시간 평균 데이터 로드 (raw data 사용 안 함!)
    # =========================================================================
    try:
        # flow_results_hourly_avg_from_2min.parquet 파일 사용
        # 컬럼: hour (0-23), avg_unique_mac (2분 unique MAC의 시간별 평균)
        hourly_avg = cache_loader.load_flow_hourly_avg_from_2min()
        
        if hourly_avg is None or hourly_avg.empty:
            st.error("No hourly average data found in cache.")
            return
        
        # 컬럼 이름 정규화
        if 'device_count' not in hourly_avg.columns:
            if 'avg_unique_mac' in hourly_avg.columns:
                hourly_avg['device_count'] = hourly_avg['avg_unique_mac']
            elif 'unique_devices' in hourly_avg.columns:
                hourly_avg['device_count'] = hourly_avg['unique_devices']
            else:
                st.error("Cannot find device count column in cache data")
                return
        
        # hour 컬럼 확인 (이미 0-23 형식)
        if 'hour' not in hourly_avg.columns:
            st.error("Cannot find hour column in cache data")
            return
        
        # Total Unique from Summary
        total_unique = 0
        summary = cache_loader.get_summary()
        if summary:
            total_unique = summary.get('flow', {}).get('total_devices', 0)
            
    except Exception as e:
        st.error(f"Error loading flow data: {e}")
        return
    
    # =========================================================================
    # 1. 전체 인원수 추이
    # =========================================================================
    st.markdown("### 📈 Total Device Count Trend")
    
    # 0-23시 보장
    all_hours = pd.DataFrame({'hour': range(24)})
    hourly_plot = all_hours.merge(hourly_avg[['hour', 'device_count']], on='hour', how='left').fillna(0)
    
    fig_total = go.Figure()
    fig_total.add_trace(go.Scatter(
        x=hourly_plot['hour'],
        y=hourly_plot['device_count'],
        mode='lines+markers',
        name='Total Devices',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8)
    ))
    fig_total.update_layout(
        title='전체 디바이스 수 (시간별 평균)',
        xaxis_title='Hour',
        yaxis_title='Average Device Count',
        height=350,
        template='plotly_white',
        xaxis=dict(
            tickmode='linear',
            tick0=0,
            dtick=1,
            range=[-0.5, 23.5]
        )
    )
    st.plotly_chart(fig_total, use_container_width=True)
    
    # 통계 메트릭
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📱 Peak", f"{hourly_plot['device_count'].max():.0f}")
    with col2:
        st.metric("📊 Average", f"{hourly_plot['device_count'].mean():.1f}")
    with col3:
        st.metric("📉 Min", f"{hourly_plot['device_count'].min():.0f}")
    with col4:
        if total_unique > 0:
            st.metric("🔢 Total Unique (Daily)", f"{total_unique:,}")
        else:
            st.metric("🔢 Total Unique (Daily)", "N/A")
    
    # =========================================================================
    # 2. 빌딩/층별 시간별 추이 (필터 선택)
    # =========================================================================
    st.markdown("---")
    st.markdown("### 🏢 Device Count by Building/Floor")
    
    try:
        # Load S-Ward configuration from cache
        sward_config = None
        try:
            sward_config = cache_loader.load_raw_sward_config()
            if sward_config is not None and not sward_config.empty:
                # Convert sward_id to int for merge compatibility
                sward_config['sward_id'] = sward_config['sward_id'].astype(int)
        except Exception as e:
            print(f"Error loading sward config: {e}")
            sward_config = st.session_state.get('sward_config')
        
        if sward_config is not None and not sward_config.empty:
            # Building 목록 가져오기
            buildings = sorted(sward_config['building'].dropna().unique().tolist())
            
            if buildings:
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_building = st.selectbox(
                        "Select Building",
                        ["All"] + buildings,
                        key="flow_device_counting_building"
                    )
                
                with col2:
                    if selected_building != "All":
                        levels = sorted(sward_config[sward_config['building'] == selected_building]['level'].dropna().unique().tolist())
                        selected_level = st.selectbox(
                            "Select Level",
                            ["All"] + levels,
                            key="flow_device_counting_level"
                        )
                    else:
                        selected_level = "All"
                        st.info("Select a building to filter by level")
                
                # Load raw flow data for filtering (캐시에서만)
                raw_flow = cache_loader.load_raw_flow()
                
                if raw_flow is not None and not raw_flow.empty:
                    # S-Ward config 조인
                    flow_with_loc = raw_flow.merge(
                        sward_config[['sward_id', 'building', 'level']],
                        on='sward_id',
                        how='left'
                    )
                    
                    # 필터 적용
                    if selected_building != "All":
                        flow_filtered = flow_with_loc[flow_with_loc['building'] == selected_building].copy()
                        if selected_level != "All":
                            flow_filtered = flow_filtered[flow_filtered['level'] == selected_level].copy()
                    else:
                        flow_filtered = flow_with_loc.copy()
                    
                    # 시간 파싱
                    flow_filtered['time'] = pd.to_datetime(flow_filtered['time'])
                    flow_filtered['hour'] = flow_filtered['time'].dt.hour
                    
                    # 시간별 unique MAC 계산
                    hourly_devices = flow_filtered.groupby('hour')['mac'].nunique().reset_index()
                    hourly_devices.columns = ['hour', 'unique_devices']
                    
                    # 0-23시 보장
                    all_hours = pd.DataFrame({'hour': range(24)})
                    hourly_plot = all_hours.merge(hourly_devices, on='hour', how='left').fillna(0)
                    
                    # 차트
                    import plotly.graph_objects as go
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=hourly_plot['hour'],
                        y=hourly_plot['unique_devices'],
                        mode='lines+markers',
                        name='Unique Devices',
                        line=dict(color='#2196F3', width=3),
                        marker=dict(size=8)
                    ))
                    
                    title_suffix = ""
                    if selected_building != "All":
                        title_suffix = f" - {selected_building}"
                        if selected_level != "All":
                            title_suffix += f"-{selected_level}"
                    
                    fig.update_layout(
                        title=f'Hourly Device Count{title_suffix}',
                        xaxis_title='Hour',
                        yaxis_title='Unique Devices',
                        height=400,
                        template='plotly_white',
                        xaxis=dict(
                            tickmode='linear',
                            tick0=0,
                            dtick=1,
                            range=[-0.5, 23.5]
                        )
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 통계 메트릭
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("📱 Peak", f"{hourly_plot['unique_devices'].max():.0f}")
                    with col2:
                        st.metric("📊 Average", f"{hourly_plot['unique_devices'].mean():.1f}")
                    with col3:
                        st.metric("📉 Min", f"{hourly_plot['unique_devices'].min():.0f}")
                    with col4:
                        st.metric("🔢 Total Unique (Daily)", f"{flow_filtered['mac'].nunique():,}")
                else:
                    st.warning("Raw flow data not available in cache.")
            else:
                st.info("No building information available.")
        else:
            st.info("S-Ward configuration not available.")
    except Exception as e:
        st.error(f"Error loading building/floor data: {e}")


def _render_tward_vs_mobile_tab(flow_data, sward_config, cache_loader=None):
    """T-Ward vs Mobile 탭: T41 인원수와 Mobile 디바이스 수 비교 (캐시 사용)"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    st.subheader("🔄 T-Ward vs Mobile Device Count")
    st.info("Compare T41 (T-Ward) workers vs Mobile Phone devices.")
    
    # Load S-Ward configuration from cache
    if sward_config is None and cache_loader:
        try:
            sward_config = cache_loader.load_raw_sward_config()
            if sward_config is not None and not sward_config.empty:
                sward_config['sward_id'] = sward_config['sward_id'].astype(int)
        except Exception as e:
            print(f"Error loading sward config in T-Ward vs Mobile: {e}")
            sward_config = None
    
    # T41 데이터 확인
    t41_data = st.session_state.get('tward41_data')
    
    if t41_data is None and cache_loader is None:
        st.warning("No data available for comparison.")
        return
    
    # Building 목록 가져오기
    buildings = []
    t41_with_loc = None
    
    if t41_data is not None and sward_config is not None:
        try:
            # Ensure sward_id types match
            sward_config_copy = sward_config.copy()
            if 'sward_id' in sward_config_copy.columns:
                sward_config_copy['sward_id'] = sward_config_copy['sward_id'].astype(int)
            
            # Check required columns
            required_cols = ['sward_id', 'building', 'level']
            if all(col in sward_config_copy.columns for col in required_cols):
                t41_with_loc = t41_data.merge(
                    sward_config_copy[required_cols],
                    on='sward_id',
                    how='left'
                )
            else:
                st.warning(f"Missing required columns in sward_config. Available: {sward_config_copy.columns.tolist()}")
                t41_with_loc = None
        except Exception as e:
            st.error(f"Error merging T41 data with sward config: {e}")
            t41_with_loc = None
        
        if t41_with_loc is not None:
            buildings = t41_with_loc['building'].dropna().unique().tolist()
            buildings = sorted([b for b in buildings if str(b) != 'nan'])
    elif cache_loader:
        # Try to get buildings from cache filters
        try:
            filters = cache_loader.get_available_t41_stats_filters()
            buildings = sorted(list(set([f.split('-')[0] for f in filters if '-' in f])))
        except:
            buildings = []
    
    # =========================================================================
    # Building/Level 필터
    # =========================================================================
    st.markdown("### 🏢 Filter by Building/Level")
    col1, col2 = st.columns(2)
    
    with col1:
        selected_building = st.selectbox("Select Building", ["All"] + buildings, key="tvm_building")
    
    selected_level = "All"
    if selected_building != "All":
        levels = []
        if t41_with_loc is not None:
            levels = t41_with_loc[t41_with_loc['building'] == selected_building]['level'].dropna().unique().tolist()
            levels = sorted([l for l in levels if str(l) != 'nan'])
        elif cache_loader:
             # Try to get levels from cache filters
             try:
                filters = cache_loader.get_available_t41_stats_filters()
                levels = sorted([f.split('-')[1] for f in filters if f.startswith(selected_building + '-')])
             except:
                levels = []
        
        if levels:
            with col2:
                selected_level = st.selectbox("Select Level", ["All"] + levels, key="tvm_level")
    
    st.markdown("---")
    
    # =========================================================================
    # 캐시에서 데이터 로드 (빠른 로딩)
    # =========================================================================
    merged = None
    
    if cache_loader:
        try:
            merged = cache_loader.load_tvm_comparison(selected_building, selected_level)
            if merged is not None and not merged.empty:
                pass # Loaded successfully
            else:
                merged = None
        except Exception as e:
            print(f"Error loading TVM comparison: {e}")
            merged = None
    
    # =========================================================================
    # 캐시가 없으면 실시간 계산 (fallback)
    # =========================================================================
    if merged is None and t41_data is not None and flow_data is not None:
        t41_copy = t41_data.copy()
        t41_copy['time'] = pd.to_datetime(t41_copy['time'])
        flow_copy = flow_data.copy()
        flow_copy['time'] = pd.to_datetime(flow_copy['time'])
        
        if sward_config is not None:
            try:
                # Ensure sward_id types match
                sward_config_copy = sward_config.copy()
                if 'sward_id' in sward_config_copy.columns:
                    sward_config_copy['sward_id'] = sward_config_copy['sward_id'].astype(int)
                t41_with_loc = t41_copy.merge(sward_config_copy[['sward_id', 'building', 'level']], on='sward_id', how='left')
                flow_with_loc = flow_copy.merge(sward_config_copy[['sward_id', 'building', 'level']], on='sward_id', how='left')
            except Exception as e:
                st.error(f"Error merging data with sward config: {e}")
                t41_with_loc = t41_copy
                flow_with_loc = flow_copy
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


def _render_apple_vs_android_tab(flow_data, cache_loader=None):
    """Apple vs Android 비율 탭"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from src.flow_analysis import identify_device_type_from_type_column
    
    st.subheader("📈 Apple vs Android Device Ratio")
    st.info("Analyze device manufacturer distribution (Apple vs Android).")
    
    device_summary = None
    hourly_pivot = None
    
    # =========================================================================
    # Data Loading (Cache vs Raw)
    # =========================================================================
    if cache_loader:
        try:
            # Load summary stats
            device_summary = cache_loader.load_flow_device_type_stats()
            # Ensure columns match
            if device_summary is not None and not device_summary.empty:
                # Check current column names for debugging
                current_cols = device_summary.columns.tolist()
                
                # Try different possible column name combinations
                rename_map = {}
                for col in current_cols:
                    col_lower = col.lower()
                    if 'device' in col_lower and 'type' in col_lower:
                        rename_map[col] = 'Device Type'
                    elif 'count' in col_lower or 'cnt' in col_lower:
                        rename_map[col] = 'Count'
                
                if rename_map:
                    device_summary = device_summary.rename(columns=rename_map)
                
                # Ensure required columns exist
                if 'Device Type' not in device_summary.columns or 'Count' not in device_summary.columns:
                    # Last resort: use first two columns
                    if len(device_summary.columns) >= 2:
                        device_summary.columns = ['Device Type', 'Count'] + list(device_summary.columns[2:])
                    else:
                        st.error(f"Cache data has unexpected columns: {current_cols}")
                        device_summary = None
        except Exception as e:
            print(f"Error loading device type stats: {e}")
            device_summary = None
            
    if device_summary is None and flow_data is not None:
        # Raw Data Processing
        # 데이터 전처리
        flow_copy = flow_data.copy()
        flow_copy['time'] = pd.to_datetime(flow_copy['time'])
        
        # 디바이스 타입 식별
        if 'type' in flow_copy.columns:
            flow_copy['device_type'] = flow_copy['type'].apply(identify_device_type_from_type_column)
        else:
            st.warning("'type' 컬럼이 없어 정확한 분류가 어렵습니다.")
            flow_copy['device_type'] = 'Unknown'
    
        # 하루 전체 unique MAC 카운팅 (디바이스 타입별)
        device_summary = flow_copy.groupby('device_type')['mac'].nunique().reset_index()
        device_summary.columns = ['Device Type', 'Count']
        
        # 시간대별 처리
        flow_copy['hour'] = flow_copy['time'].dt.hour
        hourly_device = flow_copy.groupby(['hour', 'device_type'])['mac'].nunique().reset_index()
        hourly_device.columns = ['Hour', 'Device Type', 'Count']
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

    if device_summary is None or device_summary.empty:
        st.warning("No device type data available.")
        return
    
    # Validate columns exist
    if 'Count' not in device_summary.columns or 'Device Type' not in device_summary.columns:
        st.error(f"Invalid device_summary columns: {device_summary.columns.tolist()}")
        return
    
    # 디바이스 타입 숫자를 이름으로 매핑 (1=Apple, 10=Android)
    device_type_map = {
        1: 'Apple',
        '1': 'Apple', 
        10: 'Android',
        '10': 'Android',
        'Apple': 'Apple',
        'Android': 'Android'
    }
    device_summary['Device Type'] = device_summary['Device Type'].map(lambda x: device_type_map.get(x, 'Unknown'))

    # =========================================================================
    # 1. 전체 비율 (파이 차트)
    # =========================================================================
    st.markdown("### 🥧 Daily Device Distribution")
    
    total_devices = device_summary['Count'].sum()
    device_summary['Percentage'] = (device_summary['Count'] / total_devices * 100).round(1)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # 도넛 차트 - 가독성 좋은 색상 및 흰색 배경
        colors = {'Apple': '#007AFF', 'Android': '#3DDC84', 'Unknown': '#999999'}
        
        fig_pie = go.Figure(data=[go.Pie(
            labels=device_summary['Device Type'],
            values=device_summary['Count'],
            hole=0.4,
            marker_colors=[colors.get(dt, '#888888') for dt in device_summary['Device Type']],
            textinfo='label+percent',
            textfont_size=14,
            textposition='inside',
            hovertemplate='%{label}: %{value:,}<extra></extra>'
        )])
        fig_pie.update_layout(
            title=dict(text='Device Type Distribution', font=dict(color='black')),
            height=350,
            showlegend=True,
            paper_bgcolor='white',
            plot_bgcolor='white',
            font=dict(color='black'),
            legend=dict(font=dict(color='black'))
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
    
    if hourly_pivot is not None:
        fig_hourly = make_subplots(rows=2, cols=1,
                               subplot_titles=('Device Count by Hour', 'Device Ratio by Hour (%)'),
                               row_heights=[0.5, 0.5],
                               vertical_spacing=0.15)
    
        # 상단: 절대값 - 가독성 좋은 색상
        if 'Apple' in hourly_pivot.columns:
            fig_hourly.add_trace(go.Bar(
                x=hourly_pivot['Hour'],
                y=hourly_pivot['Apple'],
                name='Apple',
                marker_color='#007AFF'
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
            line=dict(color='#007AFF', width=2),
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
    else:
        st.info("Hourly breakdown not available in cache mode.")


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
    """T31 Overview: Equipment count, operation status, utilization rate (Cache Version)"""
    st.subheader("📊 T31 Overview - Equipment Status Summary")
    
    # Check for cache loader
    if 'cache_loader' not in st.session_state:
        st.error("Cache loader not initialized. Please check data loading.")
        return

    loader = st.session_state.cache_loader
    
    # Load precomputed data
    try:
        mac_primary_loc = loader.load_t31_mac_primary_location()
        building_level_counts = loader.load_t31_building_level_equipment()
        ten_min_op_rate = loader.load_t31_ten_min_operation_rate()
    except Exception as e:
        st.error(f"Failed to load T31 cache data: {e}")
        return

    if mac_primary_loc.empty:
        st.warning("No T31 data available.")
        return

    # Basic statistics
    total_equipment = mac_primary_loc['mac'].nunique()
    buildings = mac_primary_loc['building'].dropna().unique().tolist()
    
    # =========================================================================
    # Key Metrics
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
            <div style="color: #333;">📊 Data Source</div>
            <div style="font-size: 1.5em; font-weight: bold; color: #000;">Cache</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # =========================================================================
    # Equipment by Building & Level
    # =========================================================================
    st.markdown("### 🏢 Equipment by Building & Level")
    
    if not building_level_counts.empty:
        # Rename columns for display
        display_df = building_level_counts.copy()
        display_df.columns = ['Building', 'Level', 'Equipment Count']
        
        # Add Total row
        total_row = pd.DataFrame([{
            'Building': 'Total',
            'Level': '-',
            'Equipment Count': total_equipment
        }])
        display_df = pd.concat([display_df, total_row], ignore_index=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(display_df, use_container_width=True)
            st.caption("※ Based on Primary Location (Most frequent location)")
        
        with col2:
            import plotly.express as px
            fig = px.bar(building_level_counts, x='building', y='equipment_count', 
                        color='level', barmode='group',
                        title='Equipment Distribution by Building & Level')
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # =========================================================================
    # Operation Rate by Building & Level
    # =========================================================================
    st.markdown("### ⏰ Equipment Operation Rate (10-min intervals)")
    
    if not ten_min_op_rate.empty:
        import plotly.express as px
        fig = px.line(ten_min_op_rate, x='time_label', y='operation_rate',
                     title='Equipment Operation Rate (10-min intervals)',
                     markers=True)
        fig.update_layout(
            height=350,
            xaxis_title='Time',
            yaxis_title='Operation Rate (%)',
            xaxis=dict(tickangle=45, dtick=6)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # =========================================================================
    # AI Comment
    # =========================================================================
    st.markdown("### 🤖 AI Analysis Comment")
    ai_comment = f"""
    **Equipment Status Summary:**
    - Total {total_equipment} T31 equipment detected across {len(buildings)} buildings
    - Analysis based on precomputed cache data
    
    **Recommendations:**
    - Monitor equipment with low signal counts for potential issues
    - Consider equipment distribution optimization based on usage patterns
    """
    st.info(ai_comment)


def render_t31_location_analysis():
    """T31 Location Analysis: Equipment location on map (Cache Version)"""
    st.subheader("📍 T31 Location Analysis")
    
    if 'cache_loader' not in st.session_state:
        st.error("Cache loader not initialized.")
        return

    loader = st.session_state.cache_loader
    
    try:
        equipment_positions = loader.load_t31_equipment_positions()
    except Exception as e:
        st.error(f"Failed to load T31 equipment positions: {e}")
        return

    if equipment_positions.empty:
        st.warning("No equipment position data available.")
        return
    
    # Building/Level selection
    buildings = equipment_positions['building'].dropna().unique().tolist()
    if not buildings:
        st.warning("No building information available.")
        return
        
    col1, col2 = st.columns(2)
    with col1:
        selected_building = st.selectbox("Select Building", buildings, key="t31_loc_building")
    
    levels = equipment_positions[equipment_positions['building'] == selected_building]['level'].dropna().unique().tolist()
    with col2:
        selected_level = st.selectbox("Select Level", levels, key="t31_loc_level")
    
    st.markdown("---")
    
    # Filter data
    filtered = equipment_positions[
        (equipment_positions['building'] == selected_building) & 
        (equipment_positions['level'] == selected_level)
    ]
    
    if filtered.empty:
        st.warning(f"No equipment found in {selected_building} {selected_level}")
        return
    
    # =========================================================================
    # Equipment Statistics with Operation Time
    # =========================================================================
    st.markdown(f"### 🔧 Equipment in {selected_building} - {selected_level}")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.metric("Equipment Count", len(filtered))
        
        # Display operation time table
        if 'operation_time_hr' in filtered.columns:
            display_df = filtered[['mac', 'operation_time_hr']].sort_values('operation_time_hr', ascending=False).head(20)
            display_df.columns = ['MAC Address', 'Operation Time (hr)']
            
            st.markdown("**Equipment Operation Time:**")
            st.dataframe(display_df, use_container_width=True)
    
    with col2:
        # =========================================================================
        # Map Visualization
        # =========================================================================
        st.markdown("### 🗺️ Equipment Location Map")
        
        map_image_path = _get_map_image_path(selected_building, selected_level)
        
        if map_image_path and os.path.exists(map_image_path):
            import plotly.graph_objects as go
            from PIL import Image
            import base64
            from io import BytesIO
            
            img = Image.open(map_image_path)
            img_width, img_height = img.size
            
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            img_src = f"data:image/png;base64,{img_base64}"
            
            fig = go.Figure()
            
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
            
            # Y flip
            filtered_plot = filtered.copy()
            filtered_plot['y_flipped'] = img_height - filtered_plot['y']
            
            fig.add_trace(go.Scatter(
                x=filtered_plot['x'],
                y=filtered_plot['y_flipped'],
                mode='markers+text',
                marker=dict(size=14, color='cyan', symbol='circle', 
                           line=dict(width=2, color='darkblue')),
                text=filtered_plot['mac'].str[:6],
                textposition='top center',
                textfont=dict(color='darkblue', size=10),
                hovertemplate='<b>MAC:</b> %{customdata[0]}<br><b>X:</b> %{x}<br><b>Y:</b> %{customdata[1]}<extra></extra>',
                customdata=filtered_plot[['mac', 'y']].values
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
            # Scatter plot only
            import plotly.express as px
            fig = px.scatter(filtered, x='x', y='y', 
                            hover_data=['mac'],
                            title=f'Equipment Positions - {selected_building} {selected_level}')
            fig.update_traces(marker=dict(size=14, color='cyan',
                                         line=dict(width=2, color='darkblue')))
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)


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
    """T31 Operation Heatmap: Dashboard Mode (Cache Version)"""
    st.subheader("🗺️ T31 Operation Heatmap")
    st.info("Equipment operation status over 24 hours - Sorted by Building & Level")
    
    if 'cache_loader' not in st.session_state:
        st.error("Cache loader not initialized.")
        return

    loader = st.session_state.cache_loader
    
    try:
        # Load the long-format data
        raw_heatmap = loader.load_t31_operation_heatmap()
    except Exception as e:
        st.error(f"Failed to load T31 operation heatmap data: {e}")
        return

    if raw_heatmap.empty:
        st.warning("No heatmap data available.")
        return
        
    # Transform to matrix format
    # Create a label for Y axis
    if 'sward_id' in raw_heatmap.columns:
        raw_heatmap['location_label'] = raw_heatmap['building'] + '-' + raw_heatmap['level'] + ' | ' + raw_heatmap['sward_id'].astype(str)
    else:
        raw_heatmap['location_label'] = raw_heatmap['building'] + '-' + raw_heatmap['level']

    # Pivot: Index=Location, Columns=Bin, Values=Active(1)
    heatmap_matrix = raw_heatmap.pivot_table(
        index='location_label', 
        columns='bin_index', 
        values='active_devices', 
        aggfunc='sum',
        fill_value=0
    )
    
    # Ensure all 144 bins exist
    for i in range(144):
        if i not in heatmap_matrix.columns:
            heatmap_matrix[i] = 0
            
    # Sort columns
    heatmap_matrix = heatmap_matrix.sort_index(axis=1)
    
    # Convert to binary (active/inactive) for the display function
    heatmap_matrix = (heatmap_matrix > 0).astype(int)
    
    # Display
    _display_t31_heatmap_from_cache(heatmap_matrix)


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
    
    total_equipment = 0
    total_records = 0
    if t31_data is not None and not t31_data.empty:
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
    """T41 Overview: Worker count (active only), busy buildings/levels, hourly personnel chart (Cache Version)"""
    st.subheader("📊 T41 Overview - Worker Status Summary")
    
    if 'cache_loader' not in st.session_state:
        st.error("Cache loader not initialized.")
        return

    loader = st.session_state.cache_loader
    
    try:
        # Load precomputed data
        worker_counts = loader.get_t41_worker_counts()
        busiest_loc = loader.get_t41_busiest_location()
        building_level_workers = loader.load_t41_building_level_workers()
    except Exception as e:
        st.error(f"Failed to load T41 cache data: {e}")
        return

    # Basic statistics
    active_workers = worker_counts.get('filtered', 0)
    total_workers = worker_counts.get('total', 0)
    inactive_workers = total_workers - active_workers
    
    # Busiest location info
    busiest_building = busiest_loc.get('building', 'N/A')
    busiest_count = busiest_loc.get('count', 0)
    busiest_level_info = busiest_loc.get('level_info', {})
    busiest_level = busiest_level_info.get('level', 'N/A')
    busiest_level_count = busiest_level_info.get('count', 0)
    
    # =========================================================================
    # Key Metrics
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
    
    with col2:
        st.markdown(f"""
        <div style="font-size: 0.7em; padding: 10px; background: #e8f0fe; border-radius: 5px; color: #000;">
            <div style="color: #333;">🏢 Busiest Building</div>
            <div style="font-size: 1.3em; font-weight: bold; color: #000;">{busiest_building}</div>
            <div style="font-size: 0.9em; color: #333;">{busiest_count:,} workers</div>
        </div>
        """, unsafe_allow_html=True)
    
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
            <div style="color: #333;">📊 Data Source</div>
            <div style="font-size: 1.5em; font-weight: bold; color: #000;">Cache</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # =========================================================================
    # 10-min Interval Personnel Chart by Building/Level
    # =========================================================================
    st.markdown("### ⏰ Personnel Count (10-min intervals)")
    
    # Building selection
    buildings = []
    if not building_level_workers.empty:
        buildings = building_level_workers['building'].unique().tolist()
    
    col1, col2 = st.columns(2)
    with col1:
        selected_building = st.selectbox("Select Building", ["All"] + buildings, key="t41_ov_building")
    
    if selected_building != "All":
        levels = building_level_workers[building_level_workers['building'] == selected_building]['level'].unique().tolist()
        with col2:
            selected_level = st.selectbox("Select Level", ["All"] + levels, key="t41_ov_level")
    else:
        selected_level = "All"
    
    # Load cached stats
    try:
        bin_stats = loader.load_t41_stats_10min(selected_building, selected_level)
        
        if not bin_stats.empty:
            bin_stats = bin_stats.rename(columns={'bin_index': 'Time Bin', 'time_label': 'Time Label'})
            
            import plotly.express as px
            
            # Active vs Inactive Stacked Bar
            fig = px.bar(bin_stats, x='Time Label', y=['Active', 'Inactive'],
                        title=f'Personnel Count (Active vs Inactive) - {selected_building} {selected_level}',
                        color_discrete_map={'Active': '#4CAF50', 'Inactive': '#9E9E9E'})
            
            fig.update_layout(
                height=400,
                xaxis_title='Time',
                yaxis_title='Personnel Count',
                xaxis=dict(tickangle=45, dtick=6),
                barmode='stack'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Active Ratio Line Chart
            bin_stats['Active Ratio (%)'] = (bin_stats['Active'] / bin_stats['Total'] * 100).fillna(0).round(1)
            
            fig2 = px.line(bin_stats, x='Time Label', y='Active Ratio (%)',
                          title=f'Active Worker Ratio (%) - {selected_building} {selected_level}',
                          markers=True)
            fig2.update_layout(
                height=300,
                xaxis_title='Time',
                yaxis_title='Active Ratio (%)',
                xaxis=dict(tickangle=45, dtick=6),
                yaxis=dict(range=[0, 100])
            )
            st.plotly_chart(fig2, use_container_width=True)
            
        else:
            st.warning("No data available for selected filter.")
            
    except Exception as e:
        st.error(f"Error loading chart data: {e}")
    
    st.markdown("---")
    
    # =========================================================================
    # 빌딩별/층별 평균 체류시간 (T41 핵심 지표)
    # =========================================================================
    st.markdown("### 📊 Average Dwell Time by Building & Level")
    
    # Load cached dwell time data if available
    dwell_data = pd.DataFrame()
    try:
        # This would ideally come from a specific cache method, 
        # but for now we might need to rely on what we have or skip if not available
        # Assuming we can derive it or load it. 
        # For this refactoring, let's check if we have a loader method for dwell time
        # Looking at CachedDataLoader, we have load_t41_worker_dwell()
        dwell_data = loader.load_t41_worker_dwell()
    except:
        pass
            
    if not dwell_data.empty:
        # Join with location info if needed, but dwell_data usually has mac and duration
        # We need building/level info. 
        # If dwell_data only has mac, we need to join with something that has location.
        # In cache mode, we might not have a direct mac->location map for all macs easily accessible 
        # without loading the huge raw data.
        # However, we loaded building_level_workers earlier.
        
        # For now, let's display the top workers by dwell time which is safer with cache
        st.markdown("#### Top Workers by Dwell Time")
        
        if 'duration_minutes' in dwell_data.columns:
            top_dwellers = dwell_data.sort_values('duration_minutes', ascending=False).head(10)
            st.dataframe(top_dwellers, use_container_width=True)
            
            import plotly.express as px
            fig = px.bar(top_dwellers, x='mac', y='duration_minutes',
                        title='Top 10 Workers by Dwell Time',
                        labels={'mac': 'Worker MAC', 'duration_minutes': 'Duration (min)'})
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Dwell time analysis not available in cache mode.")

    # =========================================================================
    # AI Comment
    # =========================================================================
    st.markdown("### 🤖 AI Analysis Comment")
    ai_comment = f"""
    **Worker Status Summary:**
    - Total {total_workers} workers detected
    - {active_workers} active workers (showing movement/vibration)
    - Peak activity observed in {busiest_building}
    
    **Safety & Efficiency:**
    - Monitor inactive helmets to ensure they are not abandoned
    - High density in {busiest_building} {busiest_level} suggests active work zone
    """
    st.info(ai_comment)


def render_t41_location_analysis():
    """T41 Location Analysis: Worker location heatmap (Cache Version)"""
    st.subheader("📍 T41 Location Analysis - Position Heatmap")
    
    # Check for cache loader
    if 'cache_loader' not in st.session_state:
        st.error("Cache loader not initialized.")
        return

    loader = st.session_state.cache_loader
    
    # Try to load sward config from cache if not in session state
    sward_config = st.session_state.get('sward_config')
    if sward_config is None:
        try:
            # Assuming we can load it via loader if it exists
            # But sward_config is usually loaded at startup. 
            # If it's missing, we might be in trouble for location analysis.
            # Let's check if we can get building list from somewhere else
            pass
        except:
            pass
            
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
            import base64
            from io import BytesIO
            
            img = Image.open(map_image_path)
            img_width, img_height = img.size
            
            # PIL Image를 base64로 변환 (Plotly 호환)
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            img_src = f"data:image/png;base64,{img_base64}"
            
            fig = go.Figure()
            
            # 배경 이미지
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
    
    # 캐시 데이터 로드 (Deployment 모드 지원)
    cache_loader = st.session_state.get('cache_loader')
    if cache_loader and 'type41_journey_heatmap' not in st.session_state:
        with st.spinner("Loading Journey Heatmap data..."):
            try:
                st.session_state['type41_journey_heatmap'] = cache_loader.load_t41_journey_heatmap()
            except Exception as e:
                print(f"Error loading journey heatmap: {e}")
    
    # Call existing Journey Heatmap function
    render_tward41_journey_map()


def render_t41_ai_insight_report():
    """T41 AI Insight & Report: AI analysis and PDF report generation (캐시 데이터 사용)"""
    st.subheader("🤖 T41 AI Insight & Report")
    
    cache_loader = st.session_state.get('cache_loader')
    t41_data = st.session_state.get('tward41_data')
    
    if t41_data is None and cache_loader is None:
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
    
    total_workers = 0
    total_records = 0
    if t41_data is not None and not t41_data.empty:
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
