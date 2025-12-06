"""
T-Ward Type 41 Journey Map Analysis Module (Fixed Version)
Worker movement pattern heatmap - 1-minute activity detection, 10-minute aggregation
Fixed inactive (Present) state when helmet is removed
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

# Journey Heatmap Color System - Building-Level based (all combinations)
JOURNEY_COLORS = {
    # Signal status colors
    'no_signal': 0,         # No signal: Black
    'present_inactive': 1,  # Signal received, inactive: Gray
    
    # Building-Level active colors
    'WWT-1F': 2,    # Green
    'WWT-B1F': 3,   # Yellow  
    'FAB-1F': 4,    # Orange
    'CUB-1F': 5,    # Sky blue
    'CUB-B1F': 6,   # Blue
    'Cluster-1F': 7, # Purple
    
    # Additional combinations (depending on data)
    'WWT-2F': 2,    # Same as WWT-1F (Green)
    'FAB-2F': 4,    # Same as FAB-1F (Orange)  
    'FAB-B1F': 4,   # Same as FAB-1F (Orange)
    'CUB-2F': 5,    # Same as CUB-1F (Sky blue)
    'Cluster-2F': 7, # Same as Cluster-1F (Purple)
    'Cluster-B1F': 7 # Same as Cluster-1F (Purple)
}

# Actual color code mapping (exact colors per user requirements)
COLOR_MAP = [
    '#000000',  # 0: Black (No signal)
    '#808080',  # 1: Gray (Signal received, inactive) 
    '#00FF00',  # 2: Green (WWT-1F Active)
    '#FFFF00',  # 3: Yellow (WWT-B1F Active)
    '#FFA500',  # 4: Orange (FAB-1F Active)
    '#87CEEB',  # 5: Sky blue (CUB-1F Active)
    '#0000FF',  # 6: Blue (CUB-B1F Active)
    '#8A2BE2',  # 7: Purple (Cluster Rest Area)
    '#9370DB',  # 8: Medium purple (Cluster Smoking Area)
    '#DDA0DD',  # 9: Light purple (Cluster Restroom)
    '#FFB6C1',  # 10: Pink (Cluster Stairs)
    '#D3D3D3',  # 11: Light gray (Cluster Storage)
    '#FF1493',  # 12: Deep pink (Cluster Entrance/Exit)
]

def get_journey_color_value(row):
    """Return color value for Journey Heatmap"""
    activity_status = row.get('activity_status', 'Unknown')
    building = row.get('building', 'Unknown')
    level = row.get('level', 'Unknown')
    
    # Create Building-Level combination
    building_level = f"{building}-{level}"
    
    # Determine color by activity status
    if pd.isna(activity_status) or activity_status == 'Unknown':
        return JOURNEY_COLORS['no_signal']  # No signal: Black
    elif activity_status == 'Present':
        return JOURNEY_COLORS['present_inactive']  # Signal received, inactive: Gray
    elif activity_status == 'Active':
        # Building-Level active colors
        if building_level in JOURNEY_COLORS:
            return JOURNEY_COLORS[building_level]
        else:
            return JOURNEY_COLORS['present_inactive']  # Undefined space: Gray
    else:
        return JOURNEY_COLORS['no_signal']  # Default: Black

def render_tward41_journey_map():
    """T-Ward Type 41 Journey Map Analysis
    
    Journey Heatmap:
    - X-axis: Time (10-min intervals, 00:00~23:50 = 144 bins)
    - Y-axis: Each worker (one row per MAC address)
    - Color: Which Building-Level the worker was at during that time
    
    Uses precomputed data (type41_journey_heatmap) for fast rendering.
    Falls back to activity_analysis if precomputed data is not available.
    """
    st.subheader("🗺️ T-Ward Type 41 Journey Map Analysis")
    st.write("**Worker movement pattern analysis by time (10-min intervals)**")
    st.write("X-axis: Time (10-min bins) | Y-axis: Workers | Color: Building-Level location")
    
    # Check for precomputed Journey Heatmap data (fast path)
    has_precomputed = 'type41_journey_heatmap' in st.session_state and st.session_state.get('type41_journey_heatmap') is not None
    has_activity = 'type41_activity_analysis' in st.session_state and st.session_state.get('type41_activity_analysis') is not None
    
    if not has_precomputed and not has_activity:
        st.error("⚠️ Journey Heatmap data not available. Please run precompute first.")
        st.info("""
        **Solution:**
        1. Run `python precompute.py <data_folder>` to generate cache
        2. Refresh the dashboard
        """)
        return
    
    # Use precomputed data if available
    if has_precomputed:
        journey_data = st.session_state.type41_journey_heatmap
        st.success("✅ Using precomputed Journey Heatmap data (fast)")
    else:
        journey_data = None
        st.warning("⚠️ Using activity_analysis (slower). Run precompute for better performance.")
    
    # Get activity data for statistics
    data = st.session_state.get('type41_activity_analysis', pd.DataFrame())
    
    # =========================================================================
    # Key Metrics Display (Statistics First)
    # =========================================================================
    st.markdown("### 📊 Worker Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    if has_precomputed and journey_data is not None and not journey_data.empty:
        total_macs = journey_data['mac'].nunique()
        with col1:
            st.metric("Total Workers", f"{total_macs:,}")
        
        if 'building' in journey_data.columns:
            buildings = journey_data['building'].dropna().unique().tolist()
            with col2:
                st.metric("Buildings", f"{len(buildings)}")
        
        active_records = len(journey_data[journey_data['color_code'] > 1])  # color > 1 means active (not no_signal or inactive)
        active_workers = journey_data[journey_data['color_code'] > 1]['mac'].nunique()
        with col3:
            st.metric("Active Workers", f"{active_workers:,}")
        with col4:
            st.metric("Time Bins", f"{len(journey_data):,}")
    elif not data.empty:
        total_macs = data['mac'].nunique()
        with col1:
            st.metric("Total Workers", f"{total_macs:,}")
        
        if 'building' in data.columns:
            buildings = data['building'].dropna().unique().tolist()
            with col2:
                st.metric("Buildings", f"{len(buildings)}")
        
        if 'signal_count' in data.columns:
            active_records = len(data[data['signal_count'] >= 3])
            active_workers = data[data['signal_count'] >= 3]['mac'].nunique()
            with col3:
                st.metric("Active Workers", f"{active_workers:,}")
            with col4:
                st.metric("Active Records", f"{active_records:,}")
    
    st.markdown("---")
    
    # =========================================================================
    # Journey Heatmap Options (minimal)
    # =========================================================================
    st.markdown("### ⚙️ Display Options")
    col1, col2 = st.columns(2)
    
    with col1:
        show_details = st.checkbox("Show Debug Details", value=False)
    
    with col2:
        max_workers = st.slider("Max Workers to Display", min_value=50, max_value=500, value=200, step=50,
                                help="Limit number of workers for performance")
    
    st.markdown("---")
    
    # =========================================================================
    # Auto-generate Journey Heatmap
    # =========================================================================
    st.markdown("### 🗺️ Journey Heatmap")
    st.write("Each row = one worker | Each column = 10-min time slot | Color = Building-Level")
    
    with st.spinner("Generating Journey Heatmap..."):
        try:
            if has_precomputed and journey_data is not None and not journey_data.empty:
                # Fast path: Use precomputed data
                heatmap_result = generate_journey_heatmap_from_cache(journey_data, max_workers, show_details)
            else:
                # Slow path: Generate from activity_analysis
                heatmap_result = generate_integrated_journey_heatmap(data, 'building_level', show_details, max_workers)
            
            if heatmap_result:
                st.session_state['journey_heatmap_result'] = heatmap_result
                st.success(f"✅ Journey Heatmap generated: {heatmap_result['tward_count']} workers")
                display_journey_heatmap(heatmap_result, "T-Ward Journey Heatmap", show_details)
            else:
                st.warning("⚠️ Could not generate heatmap data.")
                    
        except Exception as e:
            st.error(f"❌ Error generating Journey Heatmap: {str(e)}")
            import traceback
            st.text(traceback.format_exc())


def generate_journey_heatmap_from_cache(journey_data: pd.DataFrame, max_workers: int = 200, show_details: bool = False):
    """
    Generate Journey Heatmap from precomputed cache data (FAST)
    
    This function uses the precomputed journey_heatmap data which already has:
    - mac: Worker MAC address
    - bin_index: Time bin (0-143)
    - building_level: Building-Level combination
    - signal_count: Signal count in that bin
    - color_code: Pre-calculated color code
    
    Simply pivots the data into a 2D matrix for visualization.
    Uses pre-sorted cache if available for even faster loading.
    """
    if journey_data is None or journey_data.empty:
        return None
    
    # Get sort option from session_state
    sort_option = st.session_state.get('journey_sort_option', 'AI Recommended (activity patterns)')
    
    # Map sort option to cache key
    sort_key_map = {
        'AI Recommended (activity patterns)': 'ai',
        'Dwell Time (longest first)': 'dwell',
        'Building (grouped, then by dwell time)': 'building',
        'Signal Count (most active first)': 'signal'
    }
    sort_key = sort_key_map.get(sort_option, 'ai')
    
    print(f"\n🚀 Generating Journey Heatmap from cache (max: {max_workers}, sort: {sort_option})")
    
    # =========================================================================
    # Try to load pre-sorted cache (FAST PATH)
    # =========================================================================
    cache_loader = st.session_state.get('cache_loader') or st.session_state.get('data_loader')
    selected_macs = None
    filtered_data = None
    
    if cache_loader is not None:
        try:
            pre_sorted_data = cache_loader.load_journey_heatmap_sorted(sort_key, max_workers)
            if pre_sorted_data is not None and len(pre_sorted_data) > 0 and 'worker_order' in pre_sorted_data.columns:
                print(f"   ✅ Using pre-sorted cache (instant load)")
                # Use worker_order for ordering
                selected_macs = pre_sorted_data.drop_duplicates('mac').sort_values('worker_order')['mac'].tolist()
                filtered_data = pre_sorted_data
        except Exception as e:
            print(f"   ⚠️ Pre-sorted cache not available: {e}")
    
    # =========================================================================
    # Fallback: Calculate sorting on the fly (SLOW PATH)
    # =========================================================================
    if selected_macs is None:
        print(f"   ⚙️ Calculating sorting on the fly...")
        # Calculate worker activity statistics
        worker_stats = journey_data.groupby('mac').agg({
            'signal_count': 'sum',
            'color_code': lambda x: (x > 1).sum()  # Active time bins
        }).reset_index()
        worker_stats.columns = ['mac', 'total_signals', 'active_bins']
        
        # Add building info for building-based sorting
        if 'building' in journey_data.columns:
            worker_building = journey_data.groupby('mac')['building'].agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'Unknown').reset_index()
            worker_stats = worker_stats.merge(worker_building, on='mac', how='left')
        
        # Apply sorting based on option
        if sort_option == "Dwell Time (longest first)":
            worker_stats = worker_stats.sort_values('active_bins', ascending=False)
        elif sort_option == "Building (grouped, then by dwell time)":
            if 'building' in worker_stats.columns:
                worker_stats = worker_stats.sort_values(['building', 'active_bins'], ascending=[True, False])
            else:
                worker_stats = worker_stats.sort_values('active_bins', ascending=False)
        elif sort_option == "AI Recommended (activity patterns)":
            # AI: 활동 패턴 기반 정렬 (active_bins와 signal_count 조합)
            worker_stats['activity_score'] = worker_stats['active_bins'] * 0.7 + worker_stats['total_signals'] * 0.3
            worker_stats = worker_stats.sort_values('activity_score', ascending=False)
        else:  # Signal Count (most active first)
            worker_stats = worker_stats.sort_values('total_signals', ascending=False)
        
        # Limit to max_workers
        if len(worker_stats) > max_workers:
            worker_stats = worker_stats.head(max_workers)
        
        selected_macs = worker_stats['mac'].tolist()
        filtered_data = journey_data[journey_data['mac'].isin(selected_macs)]
    
    if show_details:
        print(f"   Selected {len(selected_macs)} workers (sorted by {sort_option})")
        print(f"   Total bins: {len(filtered_data)}")
    
    # Create 2D matrix: workers × 144 bins
    heatmap_matrix = []
    mac_order = []
    
    for mac in selected_macs:
        mac_data = filtered_data[filtered_data['mac'] == mac]
        
        # Initialize row with no_signal (0)
        row = [0] * 144
        
        # Fill in the color codes for bins where data exists
        for _, record in mac_data.iterrows():
            bin_idx = int(record['bin_index'])
            if 0 <= bin_idx < 144:
                # color_code를 0-7 범위로 클램핑
                color_code = min(max(int(record['color_code']), 0), 7)
                row[bin_idx] = color_code
        
        heatmap_matrix.append(row)
        mac_order.append(mac)
    
    if not heatmap_matrix:
        return None
    
    return {
        'heatmap_data': np.array(heatmap_matrix),
        'mac_order': mac_order,
        'time_bins': list(range(144)),
        'tward_count': len(mac_order)
    }


def get_unique_spaces(data, analysis_level):
    """Return unique space list based on analysis level"""
    if analysis_level == 'building':
        return data['building'].dropna().unique().tolist()
    elif analysis_level == 'space_type':
        return data['space_type'].dropna().unique().tolist()
    else:  # building_level
        building_level = data['building'].astype(str) + '-' + data['level'].astype(str)
        return building_level.dropna().unique().tolist()

def filter_data_by_space(data, analysis_level, space_name):
    """Filter data by analysis level and space name"""
    if analysis_level == 'building':
        return data[data['building'] == space_name]
    elif analysis_level == 'space_type':
        return data[data['space_type'] == space_name]
    else:  # building_level
        building, level = space_name.split('-', 1)
        return data[(data['building'] == building) & (data['level'] == level)]

def generate_integrated_journey_heatmap(data, analysis_level, show_details=False, max_workers=200):
    """Generate integrated Journey Heatmap for all workers
    
    Args:
        data: Activity analysis DataFrame
        analysis_level: 'building_level', 'building', or 'space_type'
        show_details: Whether to show debug info
        max_workers: Maximum number of workers to display (for performance)
    """
    
    if data is None or data.empty:
        return None
    
    print(f"\n🌟 Generating Journey Heatmap (level: {analysis_level}, max: {max_workers})")
    
    # Calculate active dwell time for each worker
    active_data = data[data['activity_status'] == 'Active']
    tward_activity_time = active_data.groupby('mac')['minute_bin'].nunique().reset_index()
    tward_activity_time.columns = ['mac', 'active_minutes']
    
    # Exclude workers with 0 active minutes
    tward_activity_time = tward_activity_time[tward_activity_time['active_minutes'] > 0]
    
    # Sort by active dwell time descending
    tward_activity_time = tward_activity_time.sort_values('active_minutes', ascending=False).reset_index(drop=True)
    
    # Limit to max_workers for performance
    if len(tward_activity_time) > max_workers:
        tward_activity_time = tward_activity_time.head(max_workers)
    
    print(f"🎯 Total workers: {len(tward_activity_time)}")
    if not tward_activity_time.empty:
        print(f"   Active time range: {tward_activity_time['active_minutes'].min()}~{tward_activity_time['active_minutes'].max()} min")
    
    if tward_activity_time.empty:
        return None
    
    # Generate heatmap data for 144 10-min bins
    heatmap_data = []
    
    for _, row in tward_activity_time.iterrows():
        mac = row['mac']
        tward_row = []
        
        # 해당 T-Ward의 데이터 추출
        mac_data = data[data['mac'] == mac]
        
        # 144개 10분 bin에 대해 색상 결정 (수정된 로직 - signal_count 기반)
        for bin_idx in range(144):
            # 🔧 올바른 시간 계산: 0시부터 시작 (bin 0 = 00:00~00:10)
            start_minute = bin_idx * 10  # 0, 10, 20, 30, ...
            end_minute = start_minute + 9  # 9, 19, 29, 39, ...
            
            # ✅ 순차적 판단 로직: 검정 → 회색 → 색상 (Building-Level)
            minute_colors = []  # 10분 동안의 1분별 색상 저장
            
            # 10분 구간을 1분씩 분석하여 각 1분의 색상 결정
            for minute_offset in range(10):
                current_minute = start_minute + minute_offset
                # 🔧 minute_bin 매칭 수정 (정확한 분 단위 매칭)
                minute_data = mac_data[mac_data['minute_bin'] == current_minute]
                
                if minute_data.empty:
                    # 해당 1분 동안 신호 없음 → 검정색
                    minute_colors.append(JOURNEY_COLORS['no_signal'])
                else:
                    # 🔥 핵심 수정: signal_count 기반으로 활성화 판정
                    # signal_count가 없으면 activity_status 사용 (하위 호환성)
                    if 'signal_count' in minute_data.columns:
                        # signal_count >= 3인 데이터만 활성화로 간주
                        active_data_minute = minute_data[minute_data['signal_count'] >= 3]
                        
                        if active_data_minute.empty:
                            # 1-2회 수신 또는 0회 수신 → 회색 (비활성화)
                            minute_colors.append(JOURNEY_COLORS['present_inactive'])
                        else:
                            # 활성화 데이터(3회+)에서 Building-Level 추정
                            building_level_counts = {}
                            for _, data_row in active_data_minute.iterrows():
                                building = data_row.get('building', 'Unknown')
                                level = data_row.get('level', 'Unknown')
                                bl_key = f"{building}-{level}"
                                building_level_counts[bl_key] = building_level_counts.get(bl_key, 0) + 1
                            
                            if building_level_counts:
                                dominant_bl = max(building_level_counts, key=building_level_counts.get)
                                dominant_count = building_level_counts[dominant_bl]
                                total_count = sum(building_level_counts.values())
                                
                                # 🔥 Cluster 매우 엄격 조건: 90% 이상 확실해야만 보라색 적용
                                if 'Cluster' in dominant_bl:
                                    if dominant_count >= total_count * 0.9:
                                        minute_colors.append(JOURNEY_COLORS[dominant_bl])
                                    else:
                                        minute_colors.append(JOURNEY_COLORS['present_inactive'])  # 불확실한 Cluster는 회색
                                elif dominant_bl in JOURNEY_COLORS:
                                    # 다른 Building-Level은 60% 이상이면 색상 적용
                                    if dominant_count >= total_count * 0.6:
                                        minute_colors.append(JOURNEY_COLORS[dominant_bl])
                                    else:
                                        minute_colors.append(JOURNEY_COLORS['present_inactive'])
                                else:
                                    minute_colors.append(JOURNEY_COLORS['present_inactive'])
                            else:
                                minute_colors.append(JOURNEY_COLORS['present_inactive'])
                    else:
                        # signal_count가 없으면 기존 로직 사용 (Active만)
                        status_counts = minute_data['activity_status'].value_counts()
                        has_active = 'Active' in status_counts and status_counts['Active'] > 0
                        
                        if has_active:
                            # Active 데이터만 사용하여 Building-Level 분석
                            building_level_counts = {}
                            active_rows = minute_data[minute_data['activity_status'] == 'Active']
                            for _, data_row in active_rows.iterrows():
                                building = data_row.get('building', 'Unknown')
                                level = data_row.get('level', 'Unknown')
                                bl_key = f"{building}-{level}"
                                building_level_counts[bl_key] = building_level_counts.get(bl_key, 0) + 1
                            
                            if building_level_counts:
                                dominant_bl = max(building_level_counts, key=building_level_counts.get)
                                dominant_count = building_level_counts[dominant_bl]
                                total_count = sum(building_level_counts.values())
                                
                                # Cluster 매우 엄격 조건
                                if 'Cluster' in dominant_bl:
                                    if dominant_count >= total_count * 0.9:
                                        minute_colors.append(JOURNEY_COLORS[dominant_bl])
                                    else:
                                        minute_colors.append(JOURNEY_COLORS['present_inactive'])
                                elif dominant_bl in JOURNEY_COLORS:
                                    if dominant_count >= total_count * 0.6:
                                        minute_colors.append(JOURNEY_COLORS[dominant_bl])
                                    else:
                                        minute_colors.append(JOURNEY_COLORS['present_inactive'])
                                else:
                                    minute_colors.append(JOURNEY_COLORS['present_inactive'])
                            else:
                                minute_colors.append(JOURNEY_COLORS['present_inactive'])
                        else:
                            # Active가 없으면 비활성화 (회색)
                            minute_colors.append(JOURNEY_COLORS['present_inactive'])
            
            # 🎯 순차적 판단: 검정 → 회색 → 가장 많은 Building-Level
            if minute_colors:
                from collections import Counter
                color_counter = Counter(minute_colors)
                
                # 1단계: 검정색이 7분 이상이면 검정색 (10분 중 대부분)
                black_count = color_counter.get(JOURNEY_COLORS['no_signal'], 0)
                if black_count >= 7:
                    final_color = JOURNEY_COLORS['no_signal']
                else:
                    # 2단계: Building-Level 색상이 있는지 확인 (활성화 우선)
                    non_inactive_colors = {color: count for color, count in color_counter.items() 
                                         if color not in [JOURNEY_COLORS['no_signal'], JOURNEY_COLORS['present_inactive']]}
                    
                    if non_inactive_colors:
                        # Building-Level 색상이 있으면, 가장 많은 색상 선택
                        final_color = max(non_inactive_colors, key=non_inactive_colors.get)
                        
                        # 🔥 추가 검증: Cluster 색상인 경우 더 엄격하게
                        if final_color == JOURNEY_COLORS['Cluster-1F'] or final_color == JOURNEY_COLORS.get('Cluster-2F', -1) or final_color == JOURNEY_COLORS.get('Cluster-B1F', -1):
                            # Cluster는 최소 5분 이상 활성화되어야 함
                            cluster_minutes = non_inactive_colors[final_color]  # ✅ 변경 전에 저장
                            if cluster_minutes < 5:
                                final_color = JOURNEY_COLORS['present_inactive']
                    else:
                        # Building-Level 색상이 없으면 회색 (비활성화)
                        final_color = JOURNEY_COLORS['present_inactive']
                
                tward_row.append(final_color)
            else:
                # 데이터가 없으면 검정색
                tward_row.append(JOURNEY_COLORS['no_signal'])
        
        heatmap_data.append(tward_row)
    
    # DataFrame 생성 (T-Ward + 144개 10분 bins)
    columns = ['MAC Address', 'Activity Time (min)'] + [f"T{i:03d}" for i in range(144)]
    
    # MAC과 Active Time 정보 추가
    final_data = []
    for i, (_, row) in enumerate(tward_activity_time.iterrows()):
        mac = row['mac']
        active_minutes = int(row['active_minutes'])
        data_row = [mac, active_minutes] + heatmap_data[i]
        final_data.append(data_row)
    
    heatmap_df = pd.DataFrame(final_data, columns=columns)
    
    # 디버깅: 히트맵 데이터 분포 확인
    if not heatmap_df.empty and show_details:
        time_cols = [col for col in heatmap_df.columns if col.startswith('T')]
        heatmap_matrix = heatmap_df[time_cols]
        
        print(f"🎯 히트맵 매트릭스 생성 완료: {heatmap_matrix.shape} (144개 10분 bins)")
        
        # 색상별 분포 확인
        color_distribution = {}
        for color_name, color_value in JOURNEY_COLORS.items():
            count = (heatmap_matrix == color_value).sum().sum()
            color_distribution[color_name] = count
        
        print("🎨 색상별 분포:")
        for color_name, count in color_distribution.items():
            if count > 0:
                print(f"   {color_name}: {count}개 셀")
    
    return {
        'heatmap_df': heatmap_df,
        'tward_count': len(tward_activity_time),
        'activity_time_range': (tward_activity_time['active_minutes'].min(), tward_activity_time['active_minutes'].max()),
        'analysis_level': analysis_level
    }

def generate_tward_heatmap_data(space_data, space_name, analysis_level, show_details=False):
    """Generate T-Ward heatmap data for specific space (fixed logic)"""
    
    if space_data is None or space_data.empty:
        return None
    
    # Active 상태만의 체류시간 계산
    active_data = space_data[space_data['activity_status'] == 'Active']
    tward_activity_time = active_data.groupby('mac')['minute_bin'].nunique().reset_index()
    tward_activity_time.columns = ['mac', 'active_minutes']
    
    # active_minutes가 0인 T-Ward 제외
    tward_activity_time = tward_activity_time[tward_activity_time['active_minutes'] > 0]
    
    # 활성화 체류시간 기준으로 내림차순 정렬
    tward_activity_time = tward_activity_time.sort_values('active_minutes', ascending=False).reset_index(drop=True)
    
    if tward_activity_time.empty:
        return None
    
    # 144개 10분 bins에 대한 히트맵 데이터 생성
    heatmap_data = []
    
    for _, row in tward_activity_time.iterrows():
        mac = row['mac']
        tward_row = []
        
        # 해당 T-Ward의 데이터 추출
        mac_data = space_data[space_data['mac'] == mac]
        
        # 144개 10분 bin에 대해 색상 결정 (수정된 로직 - signal_count 기반)
        for bin_idx in range(144):
            # 🔧 올바른 시간 계산: 0시부터 시작 (bin 0 = 00:00~00:10)
            start_minute = bin_idx * 10  # 0, 10, 20, 30, ...
            end_minute = start_minute + 9  # 9, 19, 29, 39, ...
            
            # ✅ 순차적 판단 로직: 검정 → 회색 → 색상 (Building-Level)
            minute_colors = []  # 10분 동안의 1분별 색상 저장
            
            # 10분 구간을 1분씩 분석하여 각 1분의 색상 결정
            for minute_offset in range(10):
                current_minute = start_minute + minute_offset
                minute_data = mac_data[mac_data['minute_bin'] == current_minute]
                
                if minute_data.empty:
                    minute_colors.append(JOURNEY_COLORS['no_signal'])
                else:
                    # 🔥 핵심 수정: signal_count 기반으로 활성화 판정
                    if 'signal_count' in minute_data.columns:
                        active_data_minute = minute_data[minute_data['signal_count'] >= 3]
                        
                        if active_data_minute.empty:
                            minute_colors.append(JOURNEY_COLORS['present_inactive'])
                        else:
                            # 활성화 데이터(3회+)에서 Building-Level 추정
                            building_level_counts = {}
                            for _, data_row in active_data_minute.iterrows():
                                building = data_row.get('building', 'Unknown')
                                level = data_row.get('level', 'Unknown')
                                bl_key = f"{building}-{level}"
                                building_level_counts[bl_key] = building_level_counts.get(bl_key, 0) + 1
                            
                            if building_level_counts:
                                dominant_bl = max(building_level_counts, key=building_level_counts.get)
                                dominant_count = building_level_counts[dominant_bl]
                                total_count = sum(building_level_counts.values())
                                
                                if 'Cluster' in dominant_bl:
                                    if dominant_count >= total_count * 0.9:
                                        minute_colors.append(JOURNEY_COLORS[dominant_bl])
                                    else:
                                        minute_colors.append(JOURNEY_COLORS['present_inactive'])
                                elif dominant_bl in JOURNEY_COLORS:
                                    if dominant_count >= total_count * 0.6:
                                        minute_colors.append(JOURNEY_COLORS[dominant_bl])
                                    else:
                                        minute_colors.append(JOURNEY_COLORS['present_inactive'])
                                else:
                                    minute_colors.append(JOURNEY_COLORS['present_inactive'])
                            else:
                                minute_colors.append(JOURNEY_COLORS['present_inactive'])
                    else:
                        # signal_count가 없으면 Active만 사용
                        status_counts = minute_data['activity_status'].value_counts()
                        has_active = 'Active' in status_counts and status_counts['Active'] > 0
                        
                        if has_active:
                            building_level_counts = {}
                            active_rows = minute_data[minute_data['activity_status'] == 'Active']
                            for _, data_row in active_rows.iterrows():
                                building = data_row.get('building', 'Unknown')
                                level = data_row.get('level', 'Unknown')
                                bl_key = f"{building}-{level}"
                                building_level_counts[bl_key] = building_level_counts.get(bl_key, 0) + 1
                            
                            if building_level_counts:
                                dominant_bl = max(building_level_counts, key=building_level_counts.get)
                                dominant_count = building_level_counts[dominant_bl]
                                total_count = sum(building_level_counts.values())
                                
                                if 'Cluster' in dominant_bl:
                                    if dominant_count >= total_count * 0.9:
                                        minute_colors.append(JOURNEY_COLORS[dominant_bl])
                                    else:
                                        minute_colors.append(JOURNEY_COLORS['present_inactive'])
                                elif dominant_bl in JOURNEY_COLORS:
                                    if dominant_count >= total_count * 0.6:
                                        minute_colors.append(JOURNEY_COLORS[dominant_bl])
                                    else:
                                        minute_colors.append(JOURNEY_COLORS['present_inactive'])
                                else:
                                    minute_colors.append(JOURNEY_COLORS['present_inactive'])
                            else:
                                minute_colors.append(JOURNEY_COLORS['present_inactive'])
                        else:
                            minute_colors.append(JOURNEY_COLORS['present_inactive'])
            
            # 🎯 순차적 판단: 검정 → 회색 → 가장 많은 Building-Level
            if minute_colors:
                from collections import Counter
                color_counter = Counter(minute_colors)
                
                black_count = color_counter.get(JOURNEY_COLORS['no_signal'], 0)
                if black_count >= 7:
                    final_color = JOURNEY_COLORS['no_signal']
                else:
                    non_inactive_colors = {color: count for color, count in color_counter.items() 
                                         if color not in [JOURNEY_COLORS['no_signal'], JOURNEY_COLORS['present_inactive']]}
                    
                    if non_inactive_colors:
                        final_color = max(non_inactive_colors, key=non_inactive_colors.get)
                        
                        # Cluster 색상 추가 검증
                        if final_color == JOURNEY_COLORS['Cluster-1F'] or final_color == JOURNEY_COLORS.get('Cluster-2F', -1) or final_color == JOURNEY_COLORS.get('Cluster-B1F', -1):
                            cluster_minutes = non_inactive_colors[final_color]  # ✅ 변경 전에 저장
                            if cluster_minutes < 5:
                                final_color = JOURNEY_COLORS['present_inactive']
                    else:
                        final_color = JOURNEY_COLORS['present_inactive']
                
                tward_row.append(final_color)
            else:
                tward_row.append(JOURNEY_COLORS['no_signal'])
        
        heatmap_data.append(tward_row)
    
    # DataFrame 생성
    columns = ['MAC Address', 'Activity Time (min)'] + [f"T{i:03d}" for i in range(144)]
    
    final_data = []
    for i, (_, row) in enumerate(tward_activity_time.iterrows()):
        mac = row['mac']
        active_minutes = int(row['active_minutes'])
        data_row = [mac, active_minutes] + heatmap_data[i]
        final_data.append(data_row)
    
    heatmap_df = pd.DataFrame(final_data, columns=columns)
    
    return {
        'heatmap_df': heatmap_df,
        'tward_count': len(tward_activity_time),
        'activity_time_range': (tward_activity_time['active_minutes'].min(), tward_activity_time['active_minutes'].max()),
        'analysis_level': analysis_level,
        'space_name': space_name
    }

def analyze_journey_patterns(heatmap_df):
    """Journey Heatmap statistical pattern analysis"""
    
    if heatmap_df is None or heatmap_df.empty:
        return None
    
    # 시간 컬럼만 추출
    time_cols = [col for col in heatmap_df.columns if col.startswith('T')]
    heatmap_matrix = heatmap_df[time_cols].values
    
    analysis_results = {}
    
    # 1. 시간대별 활동 패턴 (각 10분 bin별 활성화 비율)
    time_activity = []
    for bin_idx in range(144):
        col_data = heatmap_matrix[:, bin_idx]
        # 활성화 상태 (색상 2-12, 0=검정/신호없음, 1=회색/비활성)
        active_count = np.sum((col_data >= 2) & (col_data <= 12))
        inactive_count = np.sum(col_data == 1)
        no_signal_count = np.sum(col_data == 0)
        total = len(col_data)
        
        # 🔍 디버깅: 실제로 신호를 받은 작업자 수 (검정색 제외)
        has_signal_count = np.sum(col_data > 0)
        
        time_activity.append({
            'bin': bin_idx,
            'time': f"{(bin_idx * 10) // 60:02d}:{(bin_idx * 10) % 60:02d}",
            'active_ratio': active_count / total if total > 0 else 0,
            'inactive_ratio': inactive_count / total if total > 0 else 0,
            'no_signal_ratio': no_signal_count / total if total > 0 else 0,
            'active_count': active_count,
            'inactive_count': inactive_count,
            'no_signal_count': no_signal_count,
            'has_signal_count': has_signal_count,  # 🆕 신호 있는 작업자 수
            'active_ratio_of_signaled': active_count / has_signal_count if has_signal_count > 0 else 0  # 🆕 신호 받은 작업자 중 활성화 비율
        })
    
    analysis_results['time_activity'] = pd.DataFrame(time_activity)
    
    # 2. 작업자별 활동 패턴 클러스터링
    worker_patterns = []
    for idx, row in heatmap_df.iterrows():
        mac = row['mac'] if 'mac' in row else row['MAC Address']
        activity_time = row['Activity Time (min)']
        
        # 각 작업자의 히트맵 행
        worker_data = heatmap_matrix[idx]
        
        # 통계 계산
        active_bins = np.sum((worker_data >= 2) & (worker_data <= 12))
        inactive_bins = np.sum(worker_data == 1)
        no_signal_bins = np.sum(worker_data == 0)
        
        # 색상별 분포 (각 Building-Level 비율)
        color_distribution = {}
        for color_val in range(13):
            count = np.sum(worker_data == color_val)
            if count > 0:
                color_distribution[color_val] = count
        
        # 주요 활동 공간 (가장 많이 나타난 색상)
        if color_distribution:
            dominant_color = max(color_distribution, key=color_distribution.get)
            dominant_ratio = color_distribution[dominant_color] / 144
        else:
            dominant_color = 0
            dominant_ratio = 0
        
        # 활동 연속성 (연속된 활성화 구간 수)
        active_mask = (worker_data >= 2) & (worker_data <= 12)
        activity_changes = np.sum(np.diff(active_mask.astype(int)) != 0)
        
        # 🆕 공간별 체류시간 계산 (각 색상별 10분 bin 수 → 분으로 환산)
        space_dwell_time = {}
        for color_val in range(2, 13):  # 2-12: 활성화 색상만
            bins_in_space = np.sum(worker_data == color_val)
            if bins_in_space > 0:
                space_dwell_time[color_val] = bins_in_space * 10  # 10분 bin
        
        # 🆕 이동 경로 추출 (색상 전환 시퀀스)
        journey_path = []
        prev_color = -1
        for color_val in worker_data:
            if color_val >= 2 and color_val != prev_color:  # 활성화 색상이고 이전과 다름
                journey_path.append(int(color_val))
                prev_color = color_val
            elif color_val < 2:  # 비활성화/신호없음
                prev_color = -1
        
        # 🆕 공간별 방문 횟수 (연속된 같은 색상은 1회)
        visit_frequency = {}
        for color_val in range(2, 13):
            # 연속된 구간을 하나로 카운트
            mask = (worker_data == color_val).astype(int)
            transitions = np.diff(np.concatenate([[0], mask, [0]]))
            visit_count = np.sum(transitions == 1)  # 시작 지점 개수
            if visit_count > 0:
                visit_frequency[color_val] = visit_count
        
        worker_patterns.append({
            'mac': mac,
            'activity_time': activity_time,
            'active_bins': active_bins,
            'inactive_bins': inactive_bins,
            'no_signal_bins': no_signal_bins,
            'active_ratio': active_bins / 144,
            'dominant_color': dominant_color,
            'dominant_ratio': dominant_ratio,
            'activity_segments': activity_changes // 2,  # 시작/끝 쌍
            'space_dwell_time': space_dwell_time,  # 🆕 공간별 체류시간 (분)
            'journey_path': journey_path,  # 🆕 이동 경로 (색상 시퀀스)
            'visit_frequency': visit_frequency  # 🆕 공간별 방문 횟수
        })
    
    analysis_results['worker_patterns'] = pd.DataFrame(worker_patterns)
    
    # 3. 공간별 이용 패턴 (색상별 총 사용 빈도)
    space_usage = {}
    color_names = {
        0: 'No Signal', 1: 'Inactive',
        2: 'WWT-1F', 3: 'WWT-B1F', 4: 'FAB-1F',
        5: 'CUB-1F', 6: 'CUB-B1F',
        7: 'Cluster Rest Area', 8: 'Cluster Smoking',
        9: 'Cluster Restroom', 10: 'Cluster Stairs',
        11: 'Cluster Storage', 12: 'Cluster Entrance/Exit'
    }
    
    for color_val in range(13):
        count = np.sum(heatmap_matrix == color_val)
        if count > 0:
            space_usage[color_names.get(color_val, f'Unknown-{color_val}')] = {
                'total_count': int(count),
                'percentage': count / (heatmap_matrix.size) * 100
            }
    
    analysis_results['space_usage'] = space_usage
    
    # 4. 작업 시간대 집중도 (07:00-19:00)
    work_start_bin = 42  # 07:00
    work_end_bin = 114   # 19:00
    work_hours_data = heatmap_matrix[:, work_start_bin:work_end_bin]
    non_work_hours_data = np.concatenate([
        heatmap_matrix[:, :work_start_bin],
        heatmap_matrix[:, work_end_bin:]
    ], axis=1)
    
    work_active = np.sum((work_hours_data >= 2) & (work_hours_data <= 12))
    non_work_active = np.sum((non_work_hours_data >= 2) & (non_work_hours_data <= 12))
    
    analysis_results['work_time_concentration'] = {
        'work_hours_active': int(work_active),
        'non_work_hours_active': int(non_work_active),
        'work_hours_ratio': work_active / (work_active + non_work_active) if (work_active + non_work_active) > 0 else 0
    }
    
    return analysis_results

def display_journey_heatmap(heatmap_result, title, show_details=False):
    """Journey Heatmap 시각화 및 결과 표시
    
    Supports two formats:
    1. Cache format: {'heatmap_data': np.array, 'mac_order': list, 'tward_count': int}
    2. Legacy format: {'heatmap_df': pd.DataFrame, 'tward_count': int, 'activity_time_range': tuple}
    """
    
    try:
        tward_count = heatmap_result.get('tward_count', 0)
        
        # Check which format we have
        if 'heatmap_data' in heatmap_result:
            # Cache format - use numpy array directly
            heatmap_data = heatmap_result['heatmap_data']
            mac_order = heatmap_result.get('mac_order', [])
            activity_time_range = (0, 0)  # Not available in cache format
            use_cache_format = True
            
            if heatmap_data is None or len(heatmap_data) == 0:
                st.error("❌ 히트맵 데이터가 비어있습니다.")
                return
                
        elif 'heatmap_df' in heatmap_result:
            # Legacy format - use DataFrame
            heatmap_df = heatmap_result['heatmap_df']
            activity_time_range = heatmap_result.get('activity_time_range', (0, 0))
            use_cache_format = False
            
            if heatmap_df is None or heatmap_df.empty:
                st.error("❌ 히트맵 데이터프레임이 비어있습니다.")
                return
            
            # Extract heatmap_data and mac_order from DataFrame
            time_cols = [col for col in heatmap_df.columns if col.startswith('T') and len(col) == 4]
            if time_cols:
                heatmap_data = heatmap_df[time_cols].values
                mac_order = heatmap_df['mac'].tolist() if 'mac' in heatmap_df.columns else list(range(len(heatmap_df)))
            else:
                st.error("❌ 데이터프레임에 시간 컬럼이 없습니다.")
                return
        else:
            st.error("❌ 지원되지 않는 히트맵 데이터 형식입니다.")
            return
            
    except Exception as e:
        st.error(f"❌ display_journey_heatmap 초기화 오류: {str(e)}")
        import traceback
        st.text(traceback.format_exc())
        return
    
    # =========================================================================
    # Color Legend (히트맵 전에 표시) - 텍스트 검정색으로 명확하게
    # =========================================================================
    st.markdown("#### 🎨 Color Legend")
    legend_html = """
    <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; padding: 10px; background: #f0f0f0; border-radius: 5px;">
        <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #000000; border: 1px solid #333;"></span> <b>No Signal</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #808080; border: 1px solid #333;"></span> <b>Inactive</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #00FF00; border: 1px solid #333;"></span> <b>WWT-1F</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #FFFF00; border: 1px solid #333;"></span> <b>WWT-B1F</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #FFA500; border: 1px solid #333;"></span> <b>FAB</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #87CEEB; border: 1px solid #333;"></span> <b>CUB-1F</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #0000FF; border: 1px solid #333;"></span> <b>CUB-B1F</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #8A2BE2; border: 1px solid #333;"></span> <b>Cluster</b></span>
    </div>
    """
    st.markdown(legend_html, unsafe_allow_html=True)
    
    # =========================================================================
    # Generate Heatmap Visualization
    # =========================================================================
    
    # Time labels (10-min bins: 00:00, 00:10, ... 23:50)
    time_labels = [f"{i//6:02d}:{(i%6)*10:02d}" for i in range(144)]
    
    # Y-axis labels (MAC addresses, shortened)
    y_labels = [f"{mac[:8]}..." if len(str(mac)) > 8 else str(mac) for mac in mac_order]
    
    # Color scale for Building-Level codes (discrete colorscale)
    # color_code 값: 0=No signal, 1=Inactive, 2=WWT-1F, 3=WWT-B1F, 4=FAB, 5=CUB-1F, 6=CUB-B1F, 7=Cluster
    from src.colors import COLOR_HEX_MAP
    
    # Discrete colorscale (0-7 정수 매핑) - T31과 동일
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
    
    # Create Plotly heatmap
    import plotly.graph_objects as go
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data,
        x=time_labels,
        y=y_labels,
        colorscale=colorscale,
        zmin=0,
        zmax=7,
        showscale=True,
        colorbar=dict(
            tickvals=[0, 1, 2, 3, 4, 5, 6, 7],
            ticktext=['No Signal', 'Inactive', 'WWT-1F', 'WWT-B1F', 'FAB', 'CUB-1F', 'CUB-B1F', 'Cluster']
        ),
        hovertemplate='Time: %{x}<br>Worker: %{y}<br>Location Code: %{z}<extra></extra>'
    ))
    
    # 행 높이 고정: 각 행당 12px로 설정 (기존 4px의 3배)
    # MaxWorkers=200 기준 → 총 2400px
    ROW_HEIGHT_PX = 12  # 각 행당 픽셀 수 (3배 증가)
    MIN_HEIGHT = 600    # 최소 높이
    MAX_HEIGHT = 3000   # 최대 높이
    
    # 실제 작업자 수 기반 높이 계산
    calculated_height = tward_count * ROW_HEIGHT_PX
    fixed_height = max(MIN_HEIGHT, min(MAX_HEIGHT, calculated_height))
    
    fig.update_layout(
        title=f'{title} ({tward_count} workers)',
        xaxis_title='Time (10-min bins)',
        yaxis_title='Workers',
        height=fixed_height,
        xaxis=dict(tickangle=45, dtick=6),  # Show label every hour
        yaxis=dict(tickmode='linear', dtick=max(1, tward_count // 30))  # 레이블 간격 조정
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # =========================================================================
    # Statistics
    # =========================================================================
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Workers", f"{tward_count:,}")
    with col2:
        active_cells = np.sum(heatmap_data > 1)  # color > 1 = active (not no_signal or inactive)
        st.metric("Active Time Slots", f"{active_cells:,}")
    with col3:
        coverage = (active_cells / (tward_count * 144) * 100) if tward_count > 0 else 0
        st.metric("Active Coverage", f"{coverage:.1f}%")
    
    # =========================================================================
    # Detailed Analysis (분석 결과 생성) - 임시 비활성화
    # =========================================================================
    # 이 기능은 캐시 형식(use_cache_format=True)에서는 사용할 수 없음
    # Legacy 형식에서만 상세 분석 가능 - 현재 임시 비활성화
    # TODO: 추후 들여쓰기 문제 해결 후 재활성화
    if False:  # show_details and not use_cache_format:
        pass  # 상세 분석 코드 비활성화
    
    # 기본 히트맵만 표시하고 종료
    return
    
    # ==========================================================================
    # 아래 코드는 비활성화됨 (Legacy heatmap visualization)
    # 참고: 상세 분석 기능은 캐시 형식 지원을 위해 별도 함수로 분리 예정
    # ==========================================================================


# 이전 render_tward41_journey_analysis 함수와의 호환성을 위한 별칭
render_tward41_journey_analysis = render_tward41_journey_map

if __name__ == "__main__":
    # 테스트 실행
    print("T-Ward Type 41 Journey Map Analysis Module (Fixed Version) 로드됨")

# 이전 render_tward41_journey_analysis 함수와의 호환성을 위한 별칭
render_tward41_journey_analysis = render_tward41_journey_map

if __name__ == "__main__":
    # 테스트 실행
    print("T-Ward Type 41 Journey Map Analysis Module (Fixed Version) 로드됨")
