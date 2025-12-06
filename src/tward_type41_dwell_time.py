"""
T-Ward Type 41 Dwell Time Analysis Module
작업자별 공간 체류시간 분석
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def render_tward41_dwell_time(st):
    print("🏠 >>> render_tward41_dwell_time called - NEW VERSION")
    """T-Ward Type 41 Dwell Time Analysis 탭 렌더링"""
    
    st.markdown("### ⏱️ T-Ward Type 41 Dwell Time Analysis")
    st.info("🕐 Worker space occupancy time analysis by individual T-Ward")
    
    # Occupancy Analysis 결과 확인
    if 'tward41_analysis_results' not in st.session_state:
        st.warning("⚠️ No Type 41 analysis results found. Please run Occupancy Analysis first.")
        st.markdown("**Steps to generate dwell time analysis:**")
        st.markdown("1. Go to **Occupancy Analysis** tab")
        st.markdown("2. Run the analysis with your T-Ward Type 41 data")
        st.markdown("3. Return to this tab to generate dwell time analysis")
        return
    
    try:
        analysis_results = st.session_state['tward41_analysis_results']
        activity_analysis = analysis_results['activity_analysis']
        
        if activity_analysis is None or activity_analysis.empty:
            st.error("No activity analysis data available for dwell time calculation.")
            return
        
        st.success("✅ Activity data loaded successfully!")
        
        # Dwell Time 분석 수행
        with st.spinner("Calculating dwell times for all T-Wards..."):
            dwell_results = analyze_dwell_times(activity_analysis)
            
            if dwell_results:
                # 결과 표시
                display_dwell_time_results(st, dwell_results)
                
                # 필터링 정보 표시 (적용된 경우)
                if st.session_state.get('tward41_filtering_applied', False):
                    display_dwell_filtering_info(st)
            else:
                st.warning("Unable to calculate dwell times.")
                
    except Exception as e:
        st.error(f"Error in basic filtered statistics: {str(e)}")

def display_dwell_filtering_info(st):
    """체류시간 분석에서 필터링 정보 표시"""
    
    original_count = st.session_state.get('tward41_original_twards', 0)
    filtered_count = st.session_state.get('tward41_filtered_twards', 0)
    removed_count = st.session_state.get('tward41_removed_twards', 0)
    min_dwell_time = st.session_state.get('tward41_min_dwell_time', 0)
    
    if original_count > 0:
        st.markdown("---")
        st.markdown("### 🔍 Dwell Time Analysis - Filtering Applied")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Analyzed T-Wards", filtered_count)
        with col2:
            st.metric("Excluded T-Wards", removed_count)
        with col3:
            inclusion_rate = (filtered_count / original_count) * 100
            st.metric("Inclusion Rate", f"{inclusion_rate:.1f}%")
        
        st.info(f"📊 The above analysis includes only T-Wards with ≥{min_dwell_time} minutes dwell time")

def analyze_dwell_times(activity_analysis):
    """체류시간 분석"""
    
    try:
        print("=== Dwell Time Analysis Debug ===")
        print(f"Total activity records: {len(activity_analysis)}")
        print(f"Activity status distribution: {activity_analysis['activity_status'].value_counts().to_dict()}")
        
        # T-Ward별 체류시간 계산
        dwell_data = []
        
        # 각 T-Ward별로 처리
        tward_count = 0
        for mac in activity_analysis['mac'].unique():
            tward_count += 1
            mac_data = activity_analysis[activity_analysis['mac'] == mac]
            
            # Active 상태인 데이터만 체류시간에 포함 (비활성화 상태 제외)
            try:
                # pandas Series 비교를 명시적으로 처리
                activity_mask = mac_data['activity_status'] == 'Active'
                occupied_data = mac_data[activity_mask]
            except Exception as e:
                print(f"Error filtering activity_status for {mac}: {e}")
                print(f"Activity status unique values: {mac_data['activity_status'].unique()}")
                occupied_data = pd.DataFrame()  # 빈 DataFrame
            
            if tward_count <= 3:  # 처음 3개 T-Ward만 디버깅
                print(f"\nT-Ward {mac}:")
                print(f"  Total records: {len(mac_data)}")
                print(f"  Occupied records: {len(occupied_data)}")
                if not occupied_data.empty:
                    building_counts = occupied_data['building'].value_counts().to_dict()
                    print(f"  Building distribution: {building_counts}")
            
            if not occupied_data.empty:
                # Building별 체류시간 계산
                building_dwell = {}
                level_dwell = {}
                spacetype_dwell = {}  # 공간 유형별 체류시간 (Rest Area, Smoking Area 등)
                
                for _, row in occupied_data.iterrows():
                    building = row['building']
                    level = row['level']
                    space_type = row.get('space_type', 'Unknown')  # 공간 유형 정보
                    
                    # Building 체류시간 누적 (1분 = 1분)
                    if pd.notna(building) and str(building) != 'Unknown':
                        if building not in building_dwell:
                            building_dwell[building] = 0
                        building_dwell[building] += 1
                    
                    # Level 체류시간 누적
                    if pd.notna(building) and pd.notna(level) and str(building) != 'Unknown' and str(level) != 'Unknown':
                        level_key = f"{building}-{level}"
                        if level_key not in level_dwell:
                            level_dwell[level_key] = 0
                        level_dwell[level_key] += 1
                    
                    # Space Type 체류시간 누적 (Cluster의 특별한 공간들)
                    if pd.notna(space_type) and str(space_type) != 'Unknown' and building == 'Cluster':
                        spacetype_key = f"{building}-{space_type}"
                        if spacetype_key not in spacetype_dwell:
                            spacetype_dwell[spacetype_key] = 0
                        spacetype_dwell[spacetype_key] += 1
                
                if tward_count <= 3:
                    print(f"  Building dwell times: {building_dwell}")
                    print(f"  Level dwell times: {level_dwell}")
                
                # T-Ward별 체류시간 데이터 저장
                for building, minutes in building_dwell.items():
                    dwell_data.append({
                        'mac': mac,
                        'space': building,
                        'space_type': 'Building',
                        'dwell_minutes': minutes,
                        'dwell_hours': round(minutes / 60, 2)
                    })
                
                for level_key, minutes in level_dwell.items():
                    dwell_data.append({
                        'mac': mac,
                        'space': level_key,
                        'space_type': 'Level',
                        'dwell_minutes': minutes,
                        'dwell_hours': round(minutes / 60, 2)
                    })
                
                for spacetype_key, minutes in spacetype_dwell.items():
                    dwell_data.append({
                        'mac': mac,
                        'space': spacetype_key,
                        'space_type': 'Space_Type',
                        'dwell_minutes': minutes,
                        'dwell_hours': round(minutes / 60, 2)
                    })
        
        dwell_df = pd.DataFrame(dwell_data)
        
        if dwell_df.empty:
            print("No dwell data generated!")
            return None
        
        print(f"\nDwell DataFrame created: {len(dwell_df)} records")
        print("Space type distribution:", dwell_df['space_type'].value_counts().to_dict())
        print("Space distribution:", dwell_df['space'].value_counts().to_dict())
        print(f"Dwell minutes range: {dwell_df['dwell_minutes'].min()} - {dwell_df['dwell_minutes'].max()}")
        print(f"Sample dwell data:\n{dwell_df.head(10)}")
        
        # 최소 체류시간 필터링 적용
        min_dwell_time = st.session_state.get('tward41_min_dwell_time', 0)
        
        print(f"🔍 Minimum dwell time filter: {min_dwell_time} minutes")
        print(f"Before filtering: {len(dwell_df)} records")
        
        # 최소 체류시간 이상인 데이터만 필터링
        if min_dwell_time > 0:
            dwell_df_filtered = dwell_df[dwell_df['dwell_minutes'] >= min_dwell_time]
            print(f"After filtering: {len(dwell_df_filtered)} records")
        else:
            dwell_df_filtered = dwell_df
            
        # 통계 계산 (필터링된 데이터 사용)
        statistics = calculate_dwell_statistics(dwell_df_filtered)
        
        # 히스토그램 데이터 생성 (필터링된 데이터 사용)
        histogram_data = generate_dwell_histogram(dwell_df_filtered)
        
        return {
            'dwell_df': dwell_df_filtered,  # 필터링된 데이터 반환
            'statistics': statistics,
            'histogram_data': histogram_data
        }
        
    except Exception as e:
        st.error(f"Error in dwell time analysis: {str(e)}")
        return None

def calculate_dwell_statistics(dwell_df):
    """체류시간 통계 계산"""
    
    statistics = {}
    
    # 공간 타입별 통계
    for space_type in dwell_df['space_type'].unique():
        type_data = dwell_df[dwell_df['space_type'] == space_type]
        
        for space in type_data['space'].unique():
            space_data = type_data[type_data['space'] == space]
            
            stats = {
                'total_workers': len(space_data),
                'min_dwell_minutes': space_data['dwell_minutes'].min(),
                'max_dwell_minutes': space_data['dwell_minutes'].max(),
                'avg_dwell_minutes': round(space_data['dwell_minutes'].mean(), 1),
                'median_dwell_minutes': space_data['dwell_minutes'].median(),
                'std_dwell_minutes': round(space_data['dwell_minutes'].std(), 1),
                'min_dwell_hours': round(space_data['dwell_hours'].min(), 2),
                'max_dwell_hours': round(space_data['dwell_hours'].max(), 2),
                'avg_dwell_hours': round(space_data['dwell_hours'].mean(), 2)
            }
            
            statistics[f"{space_type}_{space}"] = stats
    
    return statistics

def generate_dwell_histogram(dwell_df):
    """체류시간 히스토그램 데이터 생성 (30분 단위)"""
    
    histogram_data = {}
    
    for space_type in dwell_df['space_type'].unique():
        type_data = dwell_df[dwell_df['space_type'] == space_type]
        
        for space in type_data['space'].unique():
            space_data = type_data[type_data['space'] == space]
            
            print(f"Debug: {space_type}_{space} - 체류시간 데이터")
            print(f"  최소값: {space_data['dwell_minutes'].min()}")
            print(f"  최대값: {space_data['dwell_minutes'].max()}")
            print(f"  평균값: {space_data['dwell_minutes'].mean():.1f}")
            print(f"  데이터 개수: {len(space_data)}")
            print(f"  샘플 데이터: {sorted(space_data['dwell_minutes'].tolist())[:10]}")
            
            # 30분 단위 구간 생성 (올바른 구간 설정)
            max_minutes = space_data['dwell_minutes'].max()
            
            # 구간을 명확하게 설정: [0,30), [30,60), [60,90), ...
            bins = list(range(0, int(max_minutes) + 31, 30))
            if bins[-1] < max_minutes:
                bins.append(bins[-1] + 30)
            
            print(f"  Bins: {bins}")
            
            # 구간별 카운트
            counts, bin_edges = np.histogram(space_data['dwell_minutes'], bins=bins)
            
            print(f"  Counts: {counts}")
            print(f"  Bin edges: {bin_edges}")
            
            # 구간 레이블 생성 (정확한 구간 표시)
            labels = []
            for i in range(len(bin_edges) - 1):
                start = int(bin_edges[i])
                end = int(bin_edges[i+1]) - 1
                if i == len(bin_edges) - 2:  # 마지막 구간
                    labels.append(f"{start}-{int(bin_edges[i+1])} min")
                else:
                    labels.append(f"{start}-{end} min")
            
            print(f"  Labels: {labels}")
            
            histogram_data[f"{space_type}_{space}"] = {
                'labels': labels,
                'counts': counts,
                'bins': bins,
                'raw_data': space_data['dwell_minutes'].tolist()  # 디버깅용
            }
    
    return histogram_data

def display_dwell_time_results(st, dwell_results):
    """체류시간 분석 결과 표시"""
    
    dwell_df = dwell_results['dwell_df']
    statistics = dwell_results['statistics']
    histogram_data = dwell_results['histogram_data']
    
    # 통계 표시
    st.markdown("### 📊 Dwell Time Statistics")
    
    # Building별 통계
    st.markdown("#### Building-level Statistics")
    building_stats = []
    for key, stats in statistics.items():
        if key.startswith('Building_'):
            space_name = key.replace('Building_', '')
            building_stats.append({
                'Space': space_name,
                'Total Workers': stats['total_workers'],
                'Min (min)': stats['min_dwell_minutes'],
                'Max (min)': stats['max_dwell_minutes'],
                'Avg (min)': stats['avg_dwell_minutes'],
                'Median (min)': stats['median_dwell_minutes'],
                'Std Dev (min)': stats['std_dwell_minutes'],
                'Avg (hours)': stats['avg_dwell_hours']
            })
    
    if building_stats:
        building_df = pd.DataFrame(building_stats)
        st.dataframe(building_df, use_container_width=True)
    
    # Level별 통계
    st.markdown("#### Level-specific Statistics")
    level_stats = []
    for key, stats in statistics.items():
        if key.startswith('Level_'):
            space_name = key.replace('Level_', '')
            level_stats.append({
                'Space': space_name,
                'Total Workers': stats['total_workers'],
                'Min (min)': stats['min_dwell_minutes'],
                'Max (min)': stats['max_dwell_minutes'],
                'Avg (min)': stats['avg_dwell_minutes'],
                'Median (min)': stats['median_dwell_minutes'],
                'Std Dev (min)': stats['std_dwell_minutes'],
                'Avg (hours)': stats['avg_dwell_hours']
            })
    
    if level_stats:
        level_df = pd.DataFrame(level_stats)
        st.dataframe(level_df, use_container_width=True)
    
    # Space Type별 통계 (Cluster building 등의 특수 공간)
    st.markdown("#### Space Type Statistics")
    spacetype_stats = []
    for key, stats in statistics.items():
        if key.startswith('Space_Type_'):
            space_name = key.replace('Space_Type_', '')
            spacetype_stats.append({
                'Space Type': space_name,
                'Total Workers': stats['total_workers'],
                'Min (min)': stats['min_dwell_minutes'],
                'Max (min)': stats['max_dwell_minutes'],
                'Avg (min)': stats['avg_dwell_minutes'],
                'Median (min)': stats['median_dwell_minutes'],
                'Std Dev (min)': stats['std_dwell_minutes'],
                'Avg (hours)': stats['avg_dwell_hours']
            })
    
    if spacetype_stats:
        spacetype_df = pd.DataFrame(spacetype_stats)
        st.dataframe(spacetype_df, use_container_width=True)
    
    # T-Ward별 체류시간 그래프 표시
    st.markdown("### 📊 T-Ward Individual Dwell Time Charts")
    display_tward_dwell_charts(st, dwell_df)
    
    # CSV 다운로드 버튼
    generate_csv_download(st, dwell_df)
    
    # 히스토그램 표시
    st.markdown("### 📊 Dwell Time Distribution (30-minute intervals)")
    
    # Building별 히스토그램
    building_histograms = {k: v for k, v in histogram_data.items() if k.startswith('Building_')}
    if building_histograms:
        st.markdown("#### Building-level Distribution")
        display_histograms(st, building_histograms, "Building")
    
    # Level별 히스토그램
    level_histograms = {k: v for k, v in histogram_data.items() if k.startswith('Level_')}
    if level_histograms:
        st.markdown("#### Level-specific Distribution")
        display_histograms(st, level_histograms, "Level")
    
    # Space Type별 히스토그램
    spacetype_histograms = {k: v for k, v in histogram_data.items() if k.startswith('Space_Type_')}
    if spacetype_histograms:
        st.markdown("#### Space Type Distribution")
        display_histograms(st, spacetype_histograms, "Space_Type")
    
    # 분석 정보
    st.markdown("### ℹ️ Dwell Time Analysis Information")
    st.info("""
    **Dwell Time Analysis (Type 41)**
    - **Dwell Time**: 1분 단위로 Present/Active 상태인 시간 누적
    - **Building Level**: 전체 건물 내 체류시간
    - **Level Specific**: 특정 층별 체류시간
    - **Space Type**: 특수 공간 유형별 체류시간 (Rest Area, Smoking Area 등)
    - **30-minute Intervals**: 체류시간을 30분 단위로 구간화하여 분포 표시
    - **Statistics**: 최소/최대/평균/중앙값/표준편차 제공
    """)

def generate_csv_download(st, dwell_df):
    """T-Ward별 체류시간 CSV 다운로드 생성"""
    
    # 각 T-Ward별로 데이터 통합
    tward_data = {}
    unique_macs = sorted(dwell_df['mac'].unique())  # MAC 주소 정렬
    
    # 동적으로 모든 건물 및 레벨 찾기
    available_buildings = sorted(dwell_df[dwell_df['space_type'] == 'Building']['space'].unique())
    available_levels = sorted(dwell_df[dwell_df['space_type'] == 'Level']['space'].unique())
    
    for _, row in dwell_df.iterrows():
        mac = row['mac']
        space = row['space']
        space_type = row['space_type']
        dwell_minutes = row['dwell_minutes']
        
        if mac not in tward_data:
            # MAC 주소 대신 T-Ward 번호 사용
            tward_number = unique_macs.index(mac) + 1
            tward_data[mac] = {'T-Ward': f'T-Ward {tward_number}'}
            
            # 모든 건물에 대한 컬럼 동적 생성
            for building in available_buildings:
                tward_data[mac][f'{building} Dwell Time (min)'] = 0
            
            # 모든 레벨에 대한 컬럼 동적 생성
            for level in available_levels:
                tward_data[mac][f'{level} Dwell Time (min)'] = 0
        
        # 데이터 매핑
        if space_type == 'Building':
            tward_data[mac][f'{space} Dwell Time (min)'] = dwell_minutes
        elif space_type == 'Level':
            tward_data[mac][f'{space} Dwell Time (min)'] = dwell_minutes
    
    # DataFrame 생성
    csv_df = pd.DataFrame(list(tward_data.values()))
    
    # 활성화 상태만 측정하므로 검증 로직 제거 (Present 상태 제외로 인한 불일치는 정상)
    
    if not csv_df.empty:
        # 첫 번째 건물의 체류시간 기준으로 정렬 (보통 WWT가 첫 번째)
        if available_buildings:
            primary_building = available_buildings[0]  # 첫 번째 건물 사용
            sort_column = f'{primary_building} Dwell Time (min)'
            csv_df = csv_df.sort_values(sort_column, ascending=False).reset_index(drop=True)
        
        st.markdown("### 📥 Download T-Ward Dwell Time Data")
        
        # CSV 변환
        csv_data = csv_df.to_csv(index=False)
        
        st.download_button(
            label="📥 Download T-Ward Dwell Time CSV",
            data=csv_data,
            file_name=f"tward_dwell_time_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            help="Download T-Ward dwell time data in CSV format"
        )
        
        # 프리뷰 테이블 표시
        st.markdown("#### 📋 Data Preview (Top 10)")
        st.dataframe(csv_df.head(10), use_container_width=True)
        
        # 통계 정보 - 모든 건물에 대한 통계 표시
        total_twards = len(csv_df)
        
        # 각 건물별 총 체류시간 계산
        building_stats = []
        for building in available_buildings:
            building_column = f'{building} Dwell Time (min)'
            if building_column in csv_df.columns:
                total_time = csv_df[building_column].sum()
                building_stats.append(f"{building}: {total_time} min ({total_time/60:.1f} hours)")
        
        stats_text = f"Total T-Wards: {total_twards}"
        if building_stats:
            stats_text += " | " + " | ".join(building_stats)
        
        st.info(stats_text)

def display_tward_dwell_charts(st, dwell_df):
    """T-Ward별 누적 체류시간 그래프 표시"""
    
    # 각 공간별로 데이터 분리
    spaces_to_plot = []
    
    # Building 데이터
    building_data = dwell_df[dwell_df['space_type'] == 'Building']
    for space in building_data['space'].unique():
        space_data = building_data[building_data['space'] == space]
        if not space_data.empty:
            spaces_to_plot.append((space, space_data, 'Building'))
    
    # Level 데이터
    level_data = dwell_df[dwell_df['space_type'] == 'Level']
    for space in level_data['space'].unique():
        space_data = level_data[level_data['space'] == space]
        if not space_data.empty:
            spaces_to_plot.append((space, space_data, 'Level'))
    
    # 각 공간별로 별도 그래프 생성
    for space_name, space_data, space_type in spaces_to_plot:
        # 체류시간 큰 순서로 정렬
        sorted_data = space_data.sort_values('dwell_minutes', ascending=False)
        
        st.markdown(f"#### {space_name} - T-Ward Dwell Time Chart")
        
        # 그래프 생성
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # 막대 그래프
        bars = ax.bar(range(len(sorted_data)), sorted_data['dwell_minutes'], 
                     color='#1f77b4', alpha=0.7, edgecolor='black')
        
        # X축 설정 (라벨 제거로 가독성 향상)
        ax.set_xticks([])  # X축 틱 제거
        ax.set_xticklabels([])  # X축 라벨 제거
        
        # Y축 설정
        ax.set_ylabel('Cumulative Dwell Time (Minutes)', fontsize=12, fontweight='bold')
        ax.set_xlabel('T-Ward Index (Sorted by Dwell Time)', fontsize=12, fontweight='bold')
        
        # 제목 설정
        total_twards = len(sorted_data)
        total_time = sorted_data['dwell_minutes'].sum()
        avg_time = sorted_data['dwell_minutes'].mean()
        
        ax.set_title(f'{space_name} - Individual T-Ward Dwell Times\n'
                    f'Total: {total_twards} T-Wards, {total_time} min ({total_time/60:.1f}h), '
                    f'Average: {avg_time:.1f} min ({avg_time/60:.1f}h)',
                    fontsize=14, fontweight='bold', pad=20)
        
        # 격자 추가
        ax.grid(True, axis='y', alpha=0.3)
        
        # Y축 범위 조정
        max_minutes = sorted_data['dwell_minutes'].max()
        ax.set_ylim(0, max_minutes * 1.15)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        
        # 상위 10개 T-Ward 데이터 테이블 표시 (MAC 주소 없이)
        st.markdown(f"##### Top 10 T-Wards in {space_name}")
        top10_data = sorted_data.head(10)[['dwell_minutes', 'dwell_hours']].copy()
        top10_data.columns = ['Dwell Time (min)', 'Dwell Time (hours)']
        top10_data.index = [f'T-Ward {i+1}' for i in range(len(top10_data))]
        st.dataframe(top10_data, use_container_width=True)

def display_histograms(st, histogram_data, space_type):
    """히스토그램 표시"""
    
    # 공간별로 서브플롯 생성
    spaces = list(histogram_data.keys())
    n_spaces = len(spaces)
    
    if n_spaces == 0:
        return
    
    # 적절한 서브플롯 레이아웃 계산
    n_cols = min(2, n_spaces)
    n_rows = (n_spaces + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 4 * n_rows))
    if n_spaces == 1:
        axes = [axes]
    elif n_rows == 1:
        axes = axes if n_cols > 1 else [axes]
    else:
        axes = axes.flatten()
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    for i, (key, data) in enumerate(histogram_data.items()):
        space_name = key.replace(f'{space_type}_', '')
        
        ax = axes[i]
        bars = ax.bar(range(len(data['labels'])), data['counts'], 
                     color=colors[i % len(colors)], alpha=0.7)
        
        ax.set_title(f'{space_name} - T-Ward Dwell Time Chart', 
                    fontweight='bold')
        ax.set_ylabel('Number of Workers')
        
        # x축에 체류시간 구간 라벨 추가 (4구간마다, 즉 2시간 간격)
        dwell_labels = []
        dwell_positions = []
        for i in range(0, len(data['labels']), 4):  # 4구간마다 (30분 * 4 = 2시간 간격)
            if i < len(data['labels']):
                # 체류시간 구간 라벨에서 시작 시간 추출
                label = data['labels'][i]
                if '-' in label:
                    start_time = label.split('-')[0]
                    dwell_labels.append(f'{start_time}min+')
                else:
                    dwell_labels.append(label)
                dwell_positions.append(i)
        
        ax.set_xticks(dwell_positions)
        ax.set_xticklabels(dwell_labels, rotation=45)
        ax.set_xlabel('Dwell Time (Minutes)')
        ax.grid(True, alpha=0.3)
        
        # Y축 범위 조정
        ax.set_ylim(0, max(data['counts']) * 1.15 if len(data['counts']) > 0 and data['counts'].any() else 1)
    
    # 사용하지 않는 서브플롯 숨기기
    for i in range(len(spaces), len(axes)):
        axes[i].set_visible(False)
    
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()
    
    # 디버깅 정보 표시
    st.markdown("#### 🔍 Histogram Debug Information")
    for key, data in histogram_data.items():
        space_name = key.replace(f'{space_type}_', '')
        if 'raw_data' in data:
            raw_data = data['raw_data']
            st.write(f"**{space_name}**: {len(raw_data)} workers")
            st.write(f"  - Min: {min(raw_data)} min, Max: {max(raw_data)} min, Avg: {sum(raw_data)/len(raw_data):.1f} min")
            st.write(f"  - Distribution: {dict(zip(data['labels'], data['counts']))}")

def display_filtered_dwell_time_results(st, activity_analysis):
    """30분 이상 체류한 T-Ward만 필터링하여 Dwell Time 결과 표시"""
    
    st.markdown("---")
    st.markdown("### 📊 Filtered Dwell Time Analysis (30+ minutes)")
    st.info("🔍 Analysis results showing only T-Wards with 30+ minutes dwell time")
    
    try:
        # T-Ward별 체류시간 계산 (분 단위)
        mac_dwell_times = activity_analysis.groupby('mac')['minute_bin'].nunique()
        
        # 30분 이상 체류한 T-Ward만 필터링
        filtered_macs = mac_dwell_times[mac_dwell_times >= 30].index.tolist()
        
        if not filtered_macs:
            st.warning("⚠️ No T-Wards found with 30+ minutes dwell time")
            return
        
        # 필터링된 활동 데이터
        filtered_activity = activity_analysis[activity_analysis['mac'].isin(filtered_macs)]
        
        st.markdown(f"**📈 Filtered Analysis Summary**: {len(filtered_macs)} T-Wards with 30+ minutes dwell time")
        
        # 필터링 정보 표시
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Original T-Wards", len(mac_dwell_times))
        with col2:
            st.metric("Filtered T-Wards", len(filtered_macs))
        with col3:
            filter_rate = (len(filtered_macs) / len(mac_dwell_times)) * 100
            st.metric("Filter Rate", f"{filter_rate:.1f}%")
        
        # 필터링된 결과로 체류시간 분석 시도
        try:
            filtered_dwell_results = analyze_dwell_times(filtered_activity)
            
            if filtered_dwell_results and 'statistics' in filtered_dwell_results:
                # 필터링된 통계 표시
                display_filtered_dwell_statistics(st, filtered_dwell_results['statistics'])
                
                # 필터링된 히스토그램 표시
                if 'histogram_data' in filtered_dwell_results:
                    display_filtered_dwell_histogram(st, filtered_dwell_results['histogram_data'])
            else:
                st.warning("Unable to calculate filtered dwell time statistics.")
                
        except Exception as e:
            st.error(f"Error in filtered dwell time calculation: {str(e)}")
            st.info("Showing basic filtered statistics instead...")
            
            # 기본 필터링 통계 표시
            st.info("💡 Basic filtered statistics:")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Original T-Wards", len(mac_dwell_times))
            with col2:
                st.metric("Filtered T-Wards", len(filtered_macs))
            with col3:
                filter_rate = (len(filtered_macs) / len(mac_dwell_times)) * 100
                st.metric("Filter Rate", f"{filter_rate:.1f}%")
            
    except Exception as e:
        st.error(f"Error in filtered dwell time analysis: {str(e)}")

def display_filtered_dwell_statistics(st, statistics):
    """필터링된 체류시간 통계 표시"""
    
    st.markdown("#### 📊 Filtered Dwell Time Statistics")
    
    # 통계 테이블 표시
    stats_df = pd.DataFrame(statistics).T
    stats_df.columns = ['Workers', 'Min (min)', 'Max (min)', 'Avg (min)', 'Median (min)', 'Std (min)', 'Min (hr)', 'Max (hr)', 'Avg (hr)']
    
    # 숫자 포맷팅 (정수 컬럼 제외)
    numeric_cols = ['Min (min)', 'Max (min)', 'Avg (min)', 'Median (min)', 'Std (min)', 'Min (hr)', 'Max (hr)', 'Avg (hr)']
    for col in numeric_cols:
        if col in stats_df.columns:
            stats_df[col] = pd.to_numeric(stats_df[col], errors='coerce').round(2)
    
    st.dataframe(stats_df, use_container_width=True)

def display_filtered_dwell_histogram(st, histogram_data):
    """필터링된 체류시간 히스토그램 표시"""
    
    st.markdown("#### 📊 Filtered Dwell Time Distribution")
    
    # 공간 타입 결정
    space_types = list(set([key.split('_')[0] for key in histogram_data.keys() if '_' in key]))
    
    for space_type in space_types:
        st.markdown(f"##### 🏢 Filtered {space_type.upper()} Dwell Time Distribution")
        
        # 해당 공간 타입의 데이터만 필터링
        space_data = {k: v for k, v in histogram_data.items() if k.startswith(f'{space_type}_')}
        
        if not space_data:
            st.write(f"No filtered data available for {space_type}")
            continue
        
        # 서브플롯 수 계산
        n_spaces = len(space_data)
        if n_spaces == 0:
            continue
            
        cols = min(3, n_spaces)
        rows = (n_spaces + cols - 1) // cols
        
        fig, axes = plt.subplots(rows, cols, figsize=(5*cols, 4*rows))
        if rows == 1 and cols == 1:
            axes = [axes]
        elif rows == 1:
            axes = axes
        else:
            axes = axes.flatten()
        
        # 히스토그램 그리기
        for i, (space_key, data) in enumerate(space_data.items()):
            if i >= len(axes):
                break
                
            space_name = space_key.replace(f'{space_type}_', '')
            
            if 'counts' in data and 'bins' in data:
                axes[i].bar(data['bins'][:-1], data['counts'], 
                           width=np.diff(data['bins']), alpha=0.7, color='steelblue')
                axes[i].set_title(f'Filtered {space_name}')
                axes[i].set_xlabel('Dwell Time (minutes)')
                axes[i].set_ylabel('Count')
                axes[i].grid(True, alpha=0.3)
            else:
                axes[i].text(0.5, 0.5, f'No filtered data\nfor {space_name}', 
                           ha='center', va='center', transform=axes[i].transAxes)
                axes[i].set_title(f'Filtered {space_name}')
        
        # 빈 서브플롯 숨기기
        for i in range(n_spaces, len(axes)):
            axes[i].set_visible(False)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
