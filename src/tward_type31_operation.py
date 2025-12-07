import os
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
import io
import base64
import streamlit as st
from src import tward_type31_processing
from src import tward_type31_integrated_heatmap

def render_operation_analysis_tward31(st):
    # 파일 경로: 세션 또는 output 폴더에서 최신 파일 자동 탐색
    tward31_path = st.session_state.get('tward31_path', None)
    if not tward31_path or not os.path.exists(tward31_path):
        import glob
        data_dir = './output/'
        tward31_files = sorted(glob.glob(os.path.join(data_dir, '*.csv')))
        for f in tward31_files:
            if '31' in os.path.basename(f):
                tward31_path = f
                break
    if not tward31_path or not os.path.exists(tward31_path):
        st.info("Please upload a T-Ward type 31 file in the 'Input data files' menu.")
        return
    
    # 데이터 전처리
    df = pd.read_csv(tward31_path, header=None)
    df = tward_type31_processing.preprocess_tward31(df)
    df = tward_type31_processing.add_time_index(df)
    sward_config = tward_type31_processing.load_sward_config()
    
    # 통합 분석 수행
    analysis_results = tward_type31_processing.unified_tward31_analysis(df, sward_config)
    
    # 결과에서 필요한 데이터 추출
    summary_stats = analysis_results['summary_stats']
    op_rate_df = analysis_results['operation_data']
    location_data = analysis_results['location_data']
    
    # --- Building/Level별 T-Ward 가동률 통계 ---
    # unified_tward31_analysis에서 이미 Building 전체 데이터가 포함되어 있음
    op_sum = summary_stats.copy()
    st.markdown('<span style="font-size:14px;font-weight:bold">Building/Level T-Ward Operation Rate Summary</span>', unsafe_allow_html=True)
    st.dataframe(op_sum, use_container_width=True)
    # --- 시간별(10분 bin) 가동률(%) 그래프 및 표 (최대 RSSI 기준 building/level 인식) ---
    st.markdown('<span style="font-size:13px;font-weight:bold">Operation Rate (%) per 10 Minutes (by Level/Building)</span>', unsafe_allow_html=True)
    
    # 시간별 그래프용 데이터 생성
    op_rate_arr = {}
    count_arr = {}
    
    # 디버깅: op_rate_df 데이터 확인
    print("=== DEBUG: op_rate_df 정보 ===")
    print(f"op_rate_df shape: {op_rate_df.shape}")
    print(f"op_rate_df columns: {op_rate_df.columns.tolist()}")
    print("op_rate_df sample:")
    print(op_rate_df.head(10))
    print(f"time_bin range: {op_rate_df['time_bin'].min()} ~ {op_rate_df['time_bin'].max()}")
    print("building/level 조합:")
    print(op_rate_df.groupby(['building', 'level']).size())
    
    # Building/Level별로 144개 time bin 배열 생성
    for (bldg, lvl), sub in op_rate_df.groupby(['building', 'level']):
        rate_arr = [0.0] * 144
        cnt_arr = [0] * 144
        
        print(f"\n=== DEBUG: {bldg}-{lvl} 데이터 ===")
        print(f"sub shape: {sub.shape}")
        print("sub sample:")
        print(sub[['time_bin', 'Active T-Ward Count', 'Operation Rate (%)']].head())
        
        for _, row in sub.iterrows():
            if row['time_bin'] > 0:  # time_bin이 0이 아닌 경우만
                idx = int(row['time_bin']) - 1
                if 0 <= idx < 144:
                    rate_arr[idx] = row['Operation Rate (%)']
                    cnt_arr[idx] = row['Active T-Ward Count']
                    
        # 배열에 0이 아닌 값이 몇 개나 있는지 확인
        non_zero_rate = sum(1 for x in rate_arr if x > 0)
        non_zero_count = sum(1 for x in cnt_arr if x > 0)
        print(f"Non-zero rate values: {non_zero_rate}, Non-zero count values: {non_zero_count}")
        print(f"Rate array sample: {rate_arr[:10]}...")
        print(f"Count array sample: {cnt_arr[:10]}...")
        
        op_rate_arr[(bldg, lvl)] = rate_arr
        count_arr[(bldg, lvl)] = cnt_arr
    
    if op_rate_arr:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime, timedelta
        
        # 144개 time index에 대한 x축 값 생성 (0~143)
        x_indices = list(range(144))
        time_labels = []
        for i in range(144):
            hour = i // 6
            minute = (i % 6) * 10
            time_labels.append(f"{hour:02d}:{minute:02d}")
        
        print(f"\n=== DEBUG: 시간 라벨 확인 ===")
        print(f"X indices length: {len(x_indices)}")
        print(f"Time labels length: {len(time_labels)}")
        print(f"First 10 indices: {x_indices[:10]}")
        print(f"First 10 time labels: {time_labels[:10]}")
        
        # --- Operation Rate(%) 그래프 (matplotlib) ---
        fig1, ax1 = plt.subplots(figsize=(15, 6))
        
        for (bldg, lvl), rate_data in op_rate_arr.items():
            # 144개 배열 확인
            y_values = []
            for i in range(144):
                if i < len(rate_data):
                    y_values.append(rate_data[i])
                else:
                    y_values.append(0.0)
            
            print(f"\n=== DEBUG: Operation Rate {bldg}-{lvl} ===")
            print(f"Y values length: {len(y_values)}")
            print(f"Non-zero count: {sum(1 for x in y_values if x > 0)}")
            print(f"Max value: {max(y_values)}")
            print(f"First 10 values: {y_values[:10]}")
            
            # matplotlib로 그래프 그리기
            ax1.plot(x_indices, y_values, marker='o', markersize=2, linewidth=1.5, 
                    label=f'Operation Rate {bldg}-{lvl}')
        
        ax1.set_title('Operation Rate (%) per 10 Minutes (by Level/Building)', fontsize=14)
        ax1.set_xlabel('Time (10-min bins)', fontsize=12)
        ax1.set_ylabel('Operation Rate (%)', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # x축 라벨 설정 (12시간마다 표시)
        tick_indices = list(range(0, 144, 36))  # 6시간마다
        tick_labels = [time_labels[i] for i in tick_indices]
        ax1.set_xticks(tick_indices)
        ax1.set_xticklabels(tick_labels)
        
        plt.tight_layout()
        st.pyplot(fig1)
        
        # --- Active T-Ward Count graph (matplotlib) ---
        fig2, ax2 = plt.subplots(figsize=(15, 6))
        
        for (bldg, lvl), count_data in count_arr.items():
            # 144개 배열 확인
            y_values = []
            for i in range(144):
                if i < len(count_data):
                    y_values.append(int(count_data[i]))
                else:
                    y_values.append(0)
            
            print(f"\n=== DEBUG: Active Count {bldg}-{lvl} ===")
            print(f"Y values length: {len(y_values)}")
            print(f"Non-zero count: {sum(1 for x in y_values if x > 0)}")
            print(f"Max value: {max(y_values)}")
            print(f"First 10 values: {y_values[:10]}")
            print(f"Sum of all values: {sum(y_values)}")
            
            # matplotlib로 그래프 그리기
            ax2.plot(x_indices, y_values, marker='o', markersize=2, linewidth=1.5, 
                    label=f'Active T-Ward Count {bldg}-{lvl}')
        
        ax2.set_title('Active T-Ward Count per 10 Minutes (by Level/Building)', fontsize=14)
        ax2.set_xlabel('Time (10-min bins)', fontsize=12)
        ax2.set_ylabel('Active T-Ward Count', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # x축 라벨 설정 (6시간마다 표시)
        ax2.set_xticks(tick_indices)
        ax2.set_xticklabels(tick_labels)
        
        plt.tight_layout()
        st.pyplot(fig2)
        
        # 데이터프레임 표시용으로 변환
        display_df = op_rate_df.pivot_table(
            index='time_bin', 
            columns=['building', 'level'], 
            values=['Active T-Ward Count', 'Operation Rate (%)'],
            fill_value=0
        )
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info('Unable to generate time-binned Operation Rate data. (No data available)')
    
    # 통합 분석 결과를 세션에 저장 (Location Analysis에서 재사용)
    st.session_state['tward31_analysis_results'] = analysis_results
    
    # --- Operation Heatmap 추가 ---
    st.markdown('<span style="font-size:13px;font-weight:bold">Operation Heatmap - T-Ward Activity Overview</span>', unsafe_allow_html=True)
    
    # 각 Building/Level별로 Operation Heatmap 생성
    render_operation_heatmap(location_data, summary_stats)
    
    # === Integrated T-Ward Type 31 Operation Heatmap ===
    st.markdown("---")
    st.markdown("### 🔥 Integrated T-Ward Type 31 Operation Heatmap")
    st.markdown("**All T-Wards in one heatmap with Building-Level color coding**")
    
    try:
        print("🔍 Starting integrated heatmap generation")
        
        # Use location_data which already has is_active information (like existing heatmaps)
        print(f"🔍 Using location_data with {len(location_data)} records")
        print(f"🔍 Location data columns: {location_data.columns.tolist()}")
        print(f"🔍 Active records in location_data: {len(location_data[location_data['is_active'] == True])}")
        
        df_integrated = location_data.copy()
        
        # location_data already has building, level, and is_active columns
        # Debug: Building-Level distribution
        print("🔍 Building-Level distribution:")
        building_level_counts = df_integrated.groupby(['building', 'level']).size()
        for (building, level), count in building_level_counts.items():
            print(f"   {building}-{level}: {count} records")
        
        # Debug: Active vs inactive records
        active_records = len(df_integrated[df_integrated['is_active'] == True])
        total_records = len(df_integrated)
        print(f"🔍 Active records: {active_records}/{total_records} ({active_records/total_records*100:.1f}%)")
        
        # Calculate operation time per MAC using is_active data
        active_data = df_integrated[df_integrated['is_active'] == True]
        mac_operation_time = active_data.groupby('mac')['time_bin'].count().sort_values(ascending=False)
        # Convert to minutes (each time_bin is 10 minutes)
        mac_operation_time = mac_operation_time * 10
        
        # Simple color mapping like existing heatmaps (0: inactive, 1: active)
        # Create custom colormap based on Building-Level
        from matplotlib.colors import ListedColormap
        
        # Building-Level to color mapping
        BUILDING_COLORS = {
            'WWT-1F': 'green',
            'WWT-B1F': 'yellow', 
            'WWT-2F': 'orange',
            'FAB-1F': 'blue',
            'CUB-1F': 'skyblue',
            'Cluster-1F': 'purple',
            'Cluster-2F': 'red',
            'Cluster-B1F': 'pink',
            'Unknown': 'gray'
        }
        
        # Generate integrated heatmap data (similar to existing heatmap logic)
        time_bins = list(range(1, 145))  # 1~144 (24 hours * 6 ten-minute intervals)
        columns = ['MAC Address', 'Building-Level', 'Operation Time (min)'] + [f'T{i}' for i in time_bins]
        
        final_data = []
        building_level_counts = {}
        
        for mac, operation_time in mac_operation_time.items():
            # Determine Building-Level for each MAC
            mac_data = df_integrated[df_integrated['mac'] == mac]
            if len(mac_data) > 0:
                # Find most frequent building and level for this MAC
                building = mac_data['building'].mode().iloc[0] if not mac_data['building'].mode().empty else 'Unknown'
                level = mac_data['level'].mode().iloc[0] if not mac_data['level'].mode().empty else 'Unknown'
                building_level = f"{building}-{level}"
                
                # Count building-level distribution
                building_level_counts[building_level] = building_level_counts.get(building_level, 0) + 1
                
                # Calculate activity status by time (0: inactive, 1: active)
                operation_minutes = operation_time if mac in mac_operation_time else 0
                data_row = [mac, building_level, operation_minutes]
                
                active_count = 0
                for time_bin in time_bins:
                    # Check if this MAC was active in this time bin
                    active_in_bin = mac_data[
                        (mac_data['time_bin'] == time_bin) & 
                        (mac_data['is_active'] == True)
                    ]
                    
                    if len(active_in_bin) > 0:
                        # Active in this time bin
                        data_row.append(1)
                        active_count += 1
                    else:
                        # Inactive in this time bin  
                        data_row.append(0)
                
                if active_count > 0:
                    print(f"   MAC {mac}: {building_level}, active in {active_count}/144 time bins")
                    final_data.append(data_row)
                else:
                    # Skip T-Wards with no activity
                    continue
                final_data.append(data_row)
        
        # Debug: Building-Level statistics
        print("🔍 Building-Level distribution in heatmap:")
        for building_level, count in building_level_counts.items():
            print(f"   {building_level}: {count} T-Wards")
        
        heatmap_df = pd.DataFrame(final_data, columns=columns)
        
        print(f"🎯 Integrated heatmap data: {len(heatmap_df)} T-Wards")
        
        # Create separate heatmaps for each Building-Level (like existing approach)
        unique_building_levels = heatmap_df['Building-Level'].unique()
        
        for building_level in unique_building_levels:
            if building_level == 'Unknown-Unknown':
                continue
                
            # Filter data for this Building-Level
            level_df = heatmap_df[heatmap_df['Building-Level'] == building_level]
            if level_df.empty:
                continue
                
            # Sort by operation time
            level_df = level_df.sort_values('Operation Time (min)', ascending=False)
            
            # Take top 20 for each Building-Level
            display_df = level_df.head(20)
            
            time_cols = [f'T{i}' for i in range(1, 145)]
            heatmap_matrix = display_df[time_cols].values
            
            print(f"🎯 {building_level}: {len(display_df)} T-Wards")
            print(f"   Matrix shape: {heatmap_matrix.shape}")
            print(f"   Active cells: {np.sum(heatmap_matrix == 1)}/{heatmap_matrix.size}")
            
            if np.sum(heatmap_matrix) == 0:
                st.warning(f"No active data for {building_level}")
                continue
            
            # Create heatmap for this Building-Level
            fig, ax = plt.subplots(figsize=(20, max(8, len(display_df) * 0.4)))
            
            # Use Building-Level specific color: inactive (white/lightgray) vs active (building color)
            building_color = BUILDING_COLORS.get(building_level, 'gray')
            colors = ['lightgray', building_color]  # 0: inactive, 1: active
            cmap = ListedColormap(colors)
            
            # Draw heatmap
            im = ax.imshow(heatmap_matrix, cmap=cmap, aspect='auto', interpolation='nearest', vmin=0, vmax=1)
        
            # Axis settings
            ax.set_xlabel('Time (10min intervals)', fontsize=12)
            ax.set_ylabel(f'T-Ward in {building_level}', fontsize=12)
            ax.set_title(f'{building_level} - T-Ward Operation Heatmap\n(Top {len(display_df)} T-Wards by Operation Time)', 
                        fontsize=14, pad=20)
            
            # X-axis time labels (every 2 hours)
            x_ticks = list(range(0, 144, 12))
            x_labels = [f"{i*2:02d}:00" for i in range(0, 12)]
            ax.set_xticks(x_ticks)
            ax.set_xticklabels(x_labels)
            
            # Y-axis T-Ward labels
            y_ticks = list(range(len(display_df)))
            y_labels = [f"#{i+1} ({display_df.iloc[i]['Operation Time (min)']}min)" 
                       for i in range(len(display_df))]
            ax.set_yticks(y_ticks)
            ax.set_yticklabels(y_labels, fontsize=8)
            
            # Add time division lines (every 2 hours)
            for i in range(12, 144, 12):
                ax.axvline(x=i-0.5, color='black', linestyle='--', alpha=0.3, linewidth=0.8)
            
            # Add 6-hour division lines (thicker)
            for i in range(36, 144, 36):
                ax.axvline(x=i-0.5, color='black', linestyle='--', alpha=0.6, linewidth=1.2)
            
            # Add T-Ward division lines
            for i in range(1, len(display_df)):
                ax.axhline(y=i-0.5, color='gray', linestyle='-', alpha=0.2, linewidth=0.5)
            
            # Add colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label('Operation Status', fontsize=10)
            cbar.set_ticks([0, 1])
            cbar.set_ticklabels(['Inactive', 'Active'])
            
            plt.tight_layout()
            
            # Display in Streamlit
            st.pyplot(fig)
            
            # Show top 10 T-Ward data for this Building-Level
            st.markdown(f"##### Top 10 T-Wards in {building_level}")
            display_table = display_df[['MAC Address', 'Operation Time (min)']].head(10)
            st.dataframe(display_table, use_container_width=True)
        
        # Overall Statistics
        st.markdown("### 📊 Overall T-Ward Statistics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total T-Wards", f"{len(heatmap_df):,}")
        with col2:
            min_time = heatmap_df['Operation Time (min)'].min()
            st.metric("Min Operation Time", f"{min_time}min")
        with col3:
            max_time = heatmap_df['Operation Time (min)'].max()
            st.metric("Max Operation Time", f"{max_time}min")
        
        # Building-Level distribution
        st.markdown("### 🏢 T-Ward Distribution by Building-Level")
        distribution_df = heatmap_df['Building-Level'].value_counts().reset_index()
        distribution_df.columns = ['Building-Level', 'T-Ward Count']
        st.dataframe(distribution_df, use_container_width=True)
        
        # === UNIFIED HEATMAP: All T-Wards in one visualization ===
        st.markdown("---")
        st.markdown("### 🔥 Unified T-Ward Operation Heatmap")
        st.markdown("**All active T-Wards combined with Building-Level color coding**")
        
        # Sort all T-Wards by operation time
        unified_df = heatmap_df.sort_values('Operation Time (min)', ascending=False)
        
        # Take top 50 T-Wards for better visualization
        top_twards = unified_df.head(50)
        
        if len(top_twards) == 0:
            st.warning("No active T-Ward data available for unified heatmap")
        else:
            time_cols = [f'T{i}' for i in range(1, 145)]
            unified_matrix = top_twards[time_cols].values
            
            print(f"🎯 Unified heatmap: {len(top_twards)} T-Wards")
            print(f"   Matrix shape: {unified_matrix.shape}")
            print(f"   Active cells: {np.sum(unified_matrix == 1)}/{unified_matrix.size}")
            
            # Create Building-Level color mapping for Y-axis labels
            building_level_colors = {
                'WWT-1F': '#2E8B57',      # Sea Green
                'WWT-B1F': '#FFD700',     # Gold
                'WWT-2F': '#FF8C00',      # Dark Orange
                'FAB-1F': '#4169E1',      # Royal Blue
                'CUB-1F': '#87CEEB',      # Sky Blue
                'Cluster-1F': '#9370DB',  # Medium Purple
                'Cluster-2F': '#DC143C',  # Crimson
                'Cluster-B1F': '#FF69B4', # Hot Pink
            }
            
            # Create unified heatmap with Building-Level color coding
            fig, ax = plt.subplots(figsize=(24, max(12, len(top_twards) * 0.3)))
            
            # Create color-coded matrix based on Building-Level
            colored_matrix = np.zeros_like(unified_matrix, dtype=float)
            
            # Building-Level to numeric mapping for colormap
            building_level_mapping = {
                'WWT-1F': 1,
                'WWT-B1F': 2, 
                'WWT-2F': 3,
                'FAB-1F': 4,
                'CUB-1F': 5,
                'Cluster-1F': 6,
                'Cluster-2F': 7,
                'Cluster-B1F': 8,
            }
            
            # Apply Building-Level colors to active cells
            for i in range(len(top_twards)):
                building_level = top_twards.iloc[i]['Building-Level']
                color_value = building_level_mapping.get(building_level, 0)
                
                # For each time bin, if it's active (1), use building color; if inactive (0), stay 0
                for j in range(144):
                    if unified_matrix[i, j] == 1:  # If active
                        colored_matrix[i, j] = color_value
                    else:  # If inactive
                        colored_matrix[i, j] = 0
            
            # Create custom colormap
            from matplotlib.colors import ListedColormap
            colors = ['white',        # 0: inactive
                     '#2E8B57',      # 1: WWT-1F (Sea Green)
                     '#FFD700',      # 2: WWT-B1F (Gold)  
                     '#FF8C00',      # 3: WWT-2F (Dark Orange)
                     '#4169E1',      # 4: FAB-1F (Royal Blue)
                     '#87CEEB',      # 5: CUB-1F (Sky Blue)
                     '#9370DB',      # 6: Cluster-1F (Medium Purple)
                     '#DC143C',      # 7: Cluster-2F (Crimson)
                     '#FF69B4']      # 8: Cluster-B1F (Hot Pink)
            
            custom_cmap = ListedColormap(colors)
            
            # Draw the color-coded heatmap
            im = ax.imshow(colored_matrix, cmap=custom_cmap, aspect='auto', interpolation='nearest', 
                          vmin=0, vmax=8)
            
            # Axis settings
            ax.set_xlabel('Time (10min intervals)', fontsize=12)
            ax.set_ylabel('T-Ward (Ranked by Operation Time)', fontsize=12)
            ax.set_title('Unified T-Ward Operation Heatmap - All Building Levels\n(Sorted by Operation Time)', 
                        fontsize=16, pad=20)
            
            # X-axis time labels (every 2 hours)
            x_ticks = list(range(0, 144, 12))
            x_labels = [f"{i*2:02d}:00" for i in range(0, 12)]
            ax.set_xticks(x_ticks)
            ax.set_xticklabels(x_labels)
            
            # Y-axis T-Ward labels with Building-Level color coding
            y_ticks = list(range(len(top_twards)))
            y_labels = []
            
            for i in range(len(top_twards)):
                building_level = top_twards.iloc[i]['Building-Level']
                operation_time = top_twards.iloc[i]['Operation Time (min)']
                label = f"#{i+1} {building_level} ({operation_time}min)"
                y_labels.append(label)
            
            ax.set_yticks(y_ticks)
            ax.set_yticklabels(y_labels, fontsize=8)
            
            # Color-code the Y-axis labels by Building-Level
            for i, (tick, label) in enumerate(zip(y_ticks, y_labels)):
                building_level = top_twards.iloc[i]['Building-Level']
                color = building_level_colors.get(building_level, 'black')
                ax.get_yticklabels()[i].set_color(color)
                ax.get_yticklabels()[i].set_weight('bold')
            
            # Add time division lines (every 2 hours)
            for i in range(12, 144, 12):
                ax.axvline(x=i-0.5, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)
            
            # Add 6-hour division lines (thicker)
            for i in range(36, 144, 36):
                ax.axvline(x=i-0.5, color='gray', linestyle='--', alpha=0.6, linewidth=1.2)
            
            # Add T-Ward division lines
            for i in range(1, len(top_twards)):
                ax.axhline(y=i-0.5, color='lightgray', linestyle='-', alpha=0.2, linewidth=0.5)
            
            # Add colorbar for the matrix
            cbar = plt.colorbar(im, ax=ax, shrink=0.8)
            cbar.set_label('Building-Level Activity', fontsize=10)
            cbar.set_ticks([0, 1, 2, 3, 4, 5, 6, 7, 8])
            cbar.set_ticklabels(['Inactive', 'WWT-1F', 'WWT-B1F', 'WWT-2F', 'FAB-1F', 
                               'CUB-1F', 'Cluster-1F', 'Cluster-2F', 'Cluster-B1F'])
            
            plt.tight_layout()
            
            # Display in Streamlit
            st.pyplot(fig)
            
            # Legend for Building-Level colors in heatmap
            st.markdown("**🎨 Building-Level Color Legend (Heatmap Colors):**")
            legend_col1, legend_col2 = st.columns(2)
            
            with legend_col1:
                st.markdown("- <span style='color: #2E8B57; font-weight: bold'>■ WWT-1F (Sea Green)</span>", unsafe_allow_html=True)
                st.markdown("- <span style='color: #FFD700; font-weight: bold'>■ WWT-B1F (Gold)</span>", unsafe_allow_html=True)
                st.markdown("- <span style='color: #FF8C00; font-weight: bold'>■ WWT-2F (Orange)</span>", unsafe_allow_html=True)
                st.markdown("- <span style='color: #4169E1; font-weight: bold'>■ FAB-1F (Royal Blue)</span>", unsafe_allow_html=True)
            
            with legend_col2:
                st.markdown("- <span style='color: #87CEEB; font-weight: bold'>■ CUB-1F (Sky Blue)</span>", unsafe_allow_html=True)
                st.markdown("- <span style='color: #9370DB; font-weight: bold'>■ Cluster-1F (Purple)</span>", unsafe_allow_html=True)
                st.markdown("- <span style='color: #DC143C; font-weight: bold'>■ Cluster-2F (Crimson)</span>", unsafe_allow_html=True)
                st.markdown("- <span style='color: #FF69B4; font-weight: bold'>■ Cluster-B1F (Hot Pink)</span>", unsafe_allow_html=True)
            
            st.markdown("- **White**: Inactive (No T-Ward activity in that time slot)")
            
            # Top 10 most active T-Wards summary
            st.markdown("### 🏆 Top 10 Most Active T-Wards (All Buildings)")
            top_10_summary = top_twards[['MAC Address', 'Building-Level', 'Operation Time (min)']].head(10)
            st.dataframe(top_10_summary, use_container_width=True)
        
        print("✅ Integrated heatmap generation completed")
        
    except Exception as e:
        st.error(f"❌ Error generating integrated heatmap: {str(e)}")
        print(f"❌ Integrated heatmap error: {e}")
        import traceback
        traceback.print_exc()
    
    # --- PDF Export 기능 추가 ---
    st.markdown("---")
    
    # 분석 완료 메시지
    st.success("✅ Operation Analysis completed! Check the Report Generation tab to download PDF report.")
    # Debugging: Check if 'level' column exists after merging
    if 'level' not in df.columns:
        print("Debug: 'level' column is missing after merging with sward_config.")
        print("Available columns:", df.columns)
        print("Sample data:", df.head())
    # Debugging: Check df after merging and before groupby
    print("Debug: df sample data after merging:", df.head())
    print("Debug: df columns after merging:", df.columns)

    # Debugging: Check groupby target columns
    if 'mac' not in df.columns or 'level' not in df.columns:
        print("Debug: 'mac' or 'level' column is missing before groupby.")
    
    # Debugging: Check if 'level' column exists in groupby target
    if 'level' not in df.columns:
        print("Debug: 'level' column is missing in df before groupby.")
        print("Debug: df columns:", df.columns)
        print("Debug: df sample data:", df.head())
    else:
        print("Debug: 'level' column exists in df before groupby.")

    # Estimate 'level' if missing after merging
    if 'level' not in df.columns:
        print("Debug: 'level' column is missing. Estimating 'level' based on RSSI.")
        # Assuming 'sward_id' and 'rssi' exist in df
        df = df.merge(sward_config[['sward_id', 'level']], on='sward_id', how='left')
        df['level'] = df.groupby('mac')['rssi'].transform(lambda x: x.idxmax())
        print("Debug: 'level' column estimated.")


def render_operation_heatmap(location_data, summary_stats):
    """
    T-Ward Operation Heatmap을 생성하여 각 T-Ward의 10분 단위 가동 현황을 시각화
    
    Args:
        location_data: T-Ward 위치 및 활성화 데이터
        summary_stats: Building/Level별 요약 통계
    """
    import streamlit as st
    
    # 각 Building/Level 조합에 대해 히트맵 생성
    locations = [(row['building'], row['level']) for _, row in summary_stats.iterrows() 
                if row['level'] != '(All)']  # Building 전체는 제외
    
    # WWT 전체에 대한 히트맵도 추가
    buildings = summary_stats['building'].unique()
    for building in buildings:
        locations.append((building, '(All)'))
    
    for building, level in locations:
        st.markdown(f"#### Operation Heatmap - {building}" + (f"-{level}" if level != '(All)' else ""))
        
        # 해당 Building/Level의 데이터 필터링
        if level == '(All)':
            # Building 전체 데이터
            filtered_data = location_data[location_data['building'] == building]
        else:
            # 특정 Level 데이터
            filtered_data = location_data[
                (location_data['building'] == building) & 
                (location_data['level'] == level)
            ]
        
        if filtered_data.empty:
            st.warning(f"No data found for {building}-{level}")
            continue
            
        # T-Ward별 가동 시간 계산 (분 단위)
        tward_operation_time = filtered_data[filtered_data['is_active'] == True].groupby('mac')['time_bin'].count().reset_index()
        tward_operation_time.columns = ['mac', 'operation_minutes']
        tward_operation_time['operation_minutes'] = tward_operation_time['operation_minutes'] * 10  # 10분 단위
        
        # 모든 T-Ward 목록 (가동되지 않은 것도 포함)
        all_twards = filtered_data['mac'].unique()
        tward_list = []
        for mac in all_twards:
            op_time = tward_operation_time[tward_operation_time['mac'] == mac]['operation_minutes']
            op_time = op_time.values[0] if len(op_time) > 0 else 0
            tward_list.append({'mac': mac, 'operation_minutes': op_time})
        
        tward_summary = pd.DataFrame(tward_list)
        tward_summary = tward_summary.sort_values('operation_minutes', ascending=False)
        
        if tward_summary.empty:
            st.warning(f"No T-Ward data found for {building}-{level}")
            continue
        
        # 히트맵 데이터 생성 (T-Ward x Time Bin)
        heatmap_data = []
        
        for _, tward_row in tward_summary.iterrows():
            mac = tward_row['mac']
            row_data = [mac, int(tward_row['operation_minutes'])]  # MAC주소와 총 가동시간
            
            # 144개 time bin에 대한 가동 상태
            for time_bin in range(1, 145):
                active = filtered_data[
                    (filtered_data['mac'] == mac) & 
                    (filtered_data['time_bin'] == time_bin) & 
                    (filtered_data['is_active'] == True)
                ]
                row_data.append(1 if not active.empty else 0)  # 1: 가동, 0: 비가동
            
            heatmap_data.append(row_data)
        
        # DataFrame 생성 (Time Bin은 10분 단위: T1=00:00-00:10, T2=00:10-00:20, ...)
        columns = ['MAC Address', 'Operation Time (min)'] + [f"T{i}" for i in range(1, 145)]
        heatmap_df = pd.DataFrame(heatmap_data, columns=columns)
        
        # 히트맵 시각화
        fig, ax = plt.subplots(figsize=(20, max(8, len(heatmap_df) * 0.3)))
        
        # 가동 상태 데이터만 추출 (3열부터)
        activity_matrix = heatmap_df.iloc[:, 2:].values
        
        # 커스텀 컬러맵 생성 (회색: 비가동, 초록색: 가동)
        from matplotlib.colors import ListedColormap
        colors = ['#D3D3D3', '#32CD32']  # 연한 회색, 라임 그린
        custom_cmap = ListedColormap(colors)
        
        # 히트맵 생성
        im = ax.imshow(activity_matrix, cmap=custom_cmap, aspect='auto', vmin=0, vmax=1)
        
        # Y축 라벨 (MAC Address + Operation Time)
        y_labels = [f"{row['MAC Address']}\n({row['Operation Time (min)']} min)" 
                   for _, row in heatmap_df.iterrows()]
        ax.set_yticks(range(len(y_labels)))
        ax.set_yticklabels(y_labels, fontsize=8)
        
        # X축 라벨 (시간) - 더 세밀하게
        time_labels = []
        tick_positions = []
        for i in range(0, 144, 6):  # 1시간마다 표시
            hour = i // 6
            time_labels.append(f"{hour:02d}:00")
            tick_positions.append(i)
        
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(time_labels, rotation=45, fontsize=9)
        ax.set_xlabel('Time (Hours)', fontsize=12)
        ax.set_ylabel('T-Ward MAC Address', fontsize=12)
        
        # 시간 구분을 위한 세로 점선 추가 (2시간마다)
        for i in range(12, 144, 12):  # 2시간마다 점선
            ax.axvline(x=i-0.5, color='black', linestyle='--', alpha=0.3, linewidth=0.8)
        
        # 6시간마다 더 굵은 점선
        for i in range(36, 144, 36):  # 6시간마다 굵은 점선
            ax.axvline(x=i-0.5, color='black', linestyle='--', alpha=0.6, linewidth=1.2)
        
        # T-Ward 구분을 위한 가로 점선 추가 (옅게)
        for i in range(1, len(heatmap_df)):
            ax.axhline(y=i-0.5, color='gray', linestyle='-', alpha=0.2, linewidth=0.5)
        
        # 제목
        ax.set_title(f'T-Ward Operation Heatmap - {building}' + 
                    (f'-{level}' if level != '(All)' else ' (All Levels)'), 
                    fontsize=14)
        
        # 컬러바
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Operation Status', fontsize=10)
        cbar.set_ticks([0, 1])
        cbar.set_ticklabels(['Inactive (Gray)', 'Active (Green)'])
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # 데이터 테이블도 표시 (처음 10개 T-Ward만)
        st.markdown(f"##### Top 10 Most Active T-Wards in {building}" + (f"-{level}" if level != '(All)' else ""))
        display_df = heatmap_df.head(10).copy()
        
        # 시간 컬럼을 6시간마다만 표시 (더 명확한 표기)
        time_cols_to_show = ['MAC Address', 'Operation Time (min)']
        for i in range(0, 144, 36):  # 6시간마다
            hour = i // 6
            time_cols_to_show.append(f"T{i+1}")
        
        # 선택된 컬럼만 표시
        display_cols = [col for col in time_cols_to_show if col in display_df.columns]
        
        # 컬럼명을 더 명확하게 변경
        display_df_renamed = display_df[display_cols].copy()
        column_mapping = {}
        for col in display_df_renamed.columns:
            if col.startswith('T') and col != 'Total T-Ward Count':
                try:
                    t_num = int(col[1:])  # T1 -> 1
                    hour = (t_num - 1) // 6
                    minute = ((t_num - 1) % 6) * 10
                    column_mapping[col] = f"T{t_num} ({hour:02d}:{minute:02d})"
                except:
                    pass
        
        display_df_renamed = display_df_renamed.rename(columns=column_mapping)
        st.dataframe(display_df_renamed, use_container_width=True)
        
        # 설명 추가
        st.caption("💡 T1, T37 등은 10분 단위 Time Bin을 의미합니다. T1=00:00-00:10, T37=06:00-06:10, T73=12:00-12:10, T109=18:00-18:10")


def _calculate_enriched_statistics(location_data, summary_stats):
    """Calculate enriched statistics for better reporting"""
    enriched_data = []
    
    for _, row in summary_stats.iterrows():
        building = row['building']
        level = row['level']
        
        if level == '(All)':
            filtered_data = location_data[location_data['building'] == building]
        else:
            filtered_data = location_data[
                (location_data['building'] == building) & 
                (location_data['level'] == level)
            ]
        
        if not filtered_data.empty:
            # Calculate T-Ward operation times
            tward_operation_time = filtered_data[filtered_data['is_active'] == True].groupby('mac')['time_bin'].count().reset_index()
            tward_operation_time['operation_minutes'] = tward_operation_time['time_bin'] * 10
            
            if not tward_operation_time.empty:
                # Find longest operating device
                max_device = tward_operation_time.loc[tward_operation_time['operation_minutes'].idxmax()]
                longest_device = max_device['mac']
                longest_time = max_device['operation_minutes']
                
                # Calculate average operation time
                avg_operation_time = tward_operation_time['operation_minutes'].mean()
                
                # Calculate median operation time
                median_operation_time = tward_operation_time['operation_minutes'].median()
                
                # Count of devices that operated
                active_devices = len(tward_operation_time)
                
            else:
                longest_device = "N/A"
                longest_time = 0
                avg_operation_time = 0
                median_operation_time = 0
                active_devices = 0
            
            enriched_data.append({
                'building': building,
                'level': level,
                'longest_device': longest_device,
                'longest_time': longest_time,
                'avg_operation_time': avg_operation_time,
                'median_operation_time': median_operation_time,
                'active_devices': active_devices
            })
    
    return pd.DataFrame(enriched_data)

@st.cache_data(ttl=300)  # 5분 캐시
def generate_cached_pdf_report(summary_stats, op_rate_df, location_data):
    """
    Generate PDF report with flexible layout and English text
    """
    from datetime import datetime
    import io
    
    try:
        # Data collection date extraction
        data_collection_date = "2025-08-22"  # Default
        building_name = "WWT Building"  # Default
        
        # Extract actual date from location_data
        if not location_data.empty and 'time' in location_data.columns:
            try:
                first_time = pd.to_datetime(location_data['time'].iloc[0])
                data_collection_date = first_time.strftime("%Y-%m-%d")
            except:
                pass
        
        # Extract building info
        if not summary_stats.empty:
            building_name = f"{summary_stats['building'].iloc[0]} Building"
        
        # Calculate enriched statistics
        enriched_stats = _calculate_enriched_statistics(location_data, summary_stats)
        
        # Create PDF buffer with flexible size
        pdf_buffer = io.BytesIO()
        
        with PdfPages(pdf_buffer) as pdf:
            # Page 1: Professional Cover + Summary Statistics (optimized layout)
            fig_cover = plt.figure(figsize=(11, 14))  # Taller for better spacing
            
            # Professional header section with enhanced styling
            header_bg = plt.Rectangle((0.05, 0.88), 0.9, 0.1, 
                                    facecolor='#2E4057', alpha=0.9, transform=fig_cover.transFigure)
            fig_cover.patches.append(header_bg)
            
            # Main title with professional styling
            fig_cover.text(0.5, 0.93, 'TableLift(T/L) Operation Analysis Report', 
                         fontsize=24, fontweight='bold', ha='center', color='white')
            
            # Subtitle
            fig_cover.text(0.5, 0.90, 'Comprehensive Device Utilization & Performance Analysis', 
                         fontsize=14, ha='center', color='white', style='italic')
            
            # Professional report information section with enhanced design
            building_levels = ', '.join(summary_stats[summary_stats['level'] != '(All)']['level'].unique())
            
            # Information box with proper sizing to contain text
            info_bg = plt.Rectangle((0.08, 0.70), 0.84, 0.16, 
                                  facecolor='#F8F9FA', edgecolor='#DEE2E6', 
                                  linewidth=1.5, transform=fig_cover.transFigure)
            fig_cover.patches.append(info_bg)
            
            # Report information with structured layout
            info_lines = [
                (f"Target Building:", f"{building_name.replace(' Building', '')} Building"),
                (f"Analysis Levels:", f"{building_levels}"),
                (f"Analysis Date:", f"August 22, 2025 (24-Hour Period)"),
                (f"System:", f"Hy-con & IRFM by TJLABS"),
                (f"Data Source:", f"T-Ward Type 31 Sensors on TableLift")
            ]
            
            # Position info with two-column layout
            info_start_y = 0.83
            for i, (label, value) in enumerate(info_lines):
                y_pos = info_start_y - i * 0.025
                fig_cover.text(0.12, y_pos, label, fontsize=12, fontweight='bold', ha='left')
                fig_cover.text(0.32, y_pos, value, fontsize=12, ha='left')
            
            # Summary Statistics section with professional header (moved down 10%)
            stats_header_y = 0.58  # Moved from 0.64 to 0.58 (10% down)
            stats_bg = plt.Rectangle((0.05, stats_header_y - 0.03), 0.9, 0.05, 
                                   facecolor='#495057', alpha=0.8, transform=fig_cover.transFigure)
            fig_cover.patches.append(stats_bg)
            
            fig_cover.text(0.5, stats_header_y, 'Summary Statistics', 
                         fontsize=18, fontweight='bold', ha='center', color='white')
            
            # Enhanced table data preparation
            table_data = []
            headers = ['Building/Level', 'Total\nT-Wards', 'Active\nCount', 'Operation\nRate (%)', 
                      'Longest Device\n(MAC)', 'Max Operation\nTime (min)', 'Avg Operation\nTime (min)']
            
            for _, row in summary_stats.iterrows():
                location = f"{row['building']}-{row['level']}" if row['level'] != '(All)' else f"{row['building']} (All)"
                operation_rate = row.get('Operation Rate (%)', row.get('Average Operation Rate (%)', 0))
                total_count = row.get('Total T-Ward Count', 0)
                
                # Find corresponding enriched data
                enriched_row = enriched_stats[
                    (enriched_stats['building'] == row['building']) & 
                    (enriched_stats['level'] == row['level'])
                ]
                
                if not enriched_row.empty:
                    longest_device = enriched_row.iloc[0]['longest_device']
                    longest_time = enriched_row.iloc[0]['longest_time']
                    avg_time = enriched_row.iloc[0]['avg_operation_time']
                    active_count = enriched_row.iloc[0]['active_devices']  # Use enriched data instead
                    
                    # Truncate MAC address for display
                    display_mac = longest_device if longest_device == "N/A" else f"...{longest_device[-8:]}"
                else:
                    display_mac = "N/A"
                    longest_time = 0
                    avg_time = 0
                    active_count = 0
                
                table_data.append([
                    location, 
                    f"{total_count}", 
                    f"{int(active_count)}",
                    f"{operation_rate:.1f}%",
                    display_mac,
                    f"{int(longest_time)}",
                    f"{avg_time:.1f}"
                ])
            
            # Create table with optimal positioning and spacing (adjusted for moved header)
            ax_table = fig_cover.add_axes([0.05, 0.26, 0.9, 0.30])  # Repositioned below moved stats header
            ax_table.axis('off')
            
            # Create enhanced table with better cell spacing
            table = ax_table.table(cellText=table_data,
                                 colLabels=headers,
                                 cellLoc='center',
                                 loc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1.1, 2.2)  # Increased vertical spacing for better cell padding
            
            # Enhanced table styling
            for i in range(len(headers)):
                table[(0, i)].set_facecolor('#E6E6FA')
                table[(0, i)].set_text_props(weight='bold', fontsize=10)
            
            # Add subtle row alternating colors for better readability
            for i in range(1, len(table_data) + 1):
                for j in range(len(headers)):
                    if i % 2 == 0:
                        table[(i, j)].set_facecolor('#F8F8FF')
            
            # Explanation positioned below table with professional spacing
            ax_explanation = fig_cover.add_axes([0.05, 0.02, 0.9, 0.28])  # Positioned at bottom
            ax_explanation.axis('off')
            
            # Professional explanation with enhanced formatting
            explanation_bg = plt.Rectangle((0.0, 0.0), 1.0, 1.0, 
                                         facecolor='#F8F9FA', edgecolor='#DEE2E6', 
                                         linewidth=1, transform=ax_explanation.transAxes)
            ax_explanation.add_patch(explanation_bg)
            
            # Column explanations header
            ax_explanation.text(0.02, 0.95, 'Data Dictionary & Analysis Methodology', 
                              fontsize=12, fontweight='bold', transform=ax_explanation.transAxes)
            
            # Column explanations in structured format
            explanations = [
                ("Building/Level:", "Hierarchical location identifier for T-Ward device groupings"),
                ("Total T-Wards:", "Complete inventory count of registered devices per location"),
                ("Active Count:", "Number of devices with recorded operational activity (24-hour period)"),
                ("Operation Rate:", "Utilization efficiency percentage (Active Devices ÷ Total Devices × 100%)"),
                ("Longest Device:", "Most active device identifier (MAC address - last 8 characters)"),
                ("Max Operation Time:", "Peak individual device operation duration (minutes)"),
                ("Avg Operation Time:", "Mean operation duration across all active devices (minutes)")
            ]
            
            # Display explanations with professional formatting
            y_start = 0.85
            for i, (term, definition) in enumerate(explanations):
                y_pos = y_start - i * 0.11
                ax_explanation.text(0.05, y_pos, term, fontsize=10, fontweight='bold', 
                                  transform=ax_explanation.transAxes)
                ax_explanation.text(0.05, y_pos - 0.04, definition, fontsize=9, 
                                  transform=ax_explanation.transAxes, alpha=0.8)
            
            # Analysis note at bottom
            ax_explanation.text(0.02, 0.08, 
                              'Note: This analysis enables comprehensive operational efficiency assessment and strategic device utilization optimization.',
                              fontsize=9, style='italic', transform=ax_explanation.transAxes, alpha=0.7)
            
            pdf.savefig(fig_cover, bbox_inches='tight', pad_inches=0.5)
            plt.close(fig_cover)
            
            # Page 2: Time-Series Analysis (Operation Rate + Active Count) 
            if not op_rate_df.empty:
                fig_combined = plt.figure(figsize=(12, 10))  # Optimized size
                
                # Create clean subplot layout
                ax_rate = plt.subplot2grid((12, 1), (0, 0), rowspan=4, fig=fig_combined)
                ax_count = plt.subplot2grid((12, 1), (5, 0), rowspan=4, fig=fig_combined)
                ax_explanation = plt.subplot2grid((12, 1), (10, 0), rowspan=2, fig=fig_combined)
                ax_explanation.axis('off')
                
                # Operation Rate graph (top)
                op_rate_arr = {}
                for (bldg, lvl), group in op_rate_df.groupby(['building', 'level']):
                    key = f"{bldg}-{lvl}"
                    y_values = [0.0] * 144
                    for _, row in group.iterrows():
                        time_bin = int(row['time_bin'])
                        if 1 <= time_bin <= 144:
                            y_values[time_bin - 1] = float(row['Operation Rate (%)'])
                    op_rate_arr[key] = y_values
                
                x_indices = list(range(144))
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
                color_idx = 0
                
                for key, y_values in op_rate_arr.items():
                    # Include all data (All, 1F, B1F) to match dashboard
                    ax_rate.plot(x_indices, y_values, marker='o', markersize=1.0, 
                               linewidth=2, label=key, color=colors[color_idx % len(colors)])
                    color_idx += 1
                
                ax_rate.set_title(f'Operation Rate (%) per 10 Minutes - {building_name} ({data_collection_date})', 
                                fontsize=14, fontweight='bold')
                ax_rate.set_ylabel('Operation Rate (%)', fontsize=12)
                ax_rate.legend(fontsize=11, loc='upper right')
                ax_rate.grid(True, alpha=0.3)
                
                # Active Count graph (bottom)
                count_arr = {}
                for (bldg, lvl), group in op_rate_df.groupby(['building', 'level']):
                    key = f"{bldg}-{lvl}"
                    y_values = [0] * 144
                    for _, row in group.iterrows():
                        time_bin = int(row['time_bin'])
                        if 1 <= time_bin <= 144:
                            y_values[time_bin - 1] = int(row['Active T-Ward Count'])
                    count_arr[key] = y_values
                
                color_idx = 0
                for key, y_values in count_arr.items():
                    # Include all data (All, 1F, B1F) to match dashboard
                    ax_count.plot(x_indices, y_values, marker='o', markersize=1.0, 
                                linewidth=2, label=key, color=colors[color_idx % len(colors)])
                    color_idx += 1
                
                ax_count.set_title(f'Active T-Ward Count per 10 Minutes - {building_name} ({data_collection_date})', 
                                 fontsize=14, fontweight='bold')
                ax_count.set_xlabel('Time (10-min bins)', fontsize=12)
                ax_count.set_ylabel('Active T-Ward Count', fontsize=12)
                ax_count.legend(fontsize=11, loc='upper right')
                ax_count.grid(True, alpha=0.3)
                
                # X-axis time labels (every 3 hours)
                tick_indices = list(range(0, 144, 18))
                time_labels = [f"{i//6:02d}:00" for i in tick_indices]
                ax_rate.set_xticks(tick_indices)
                ax_rate.set_xticklabels(time_labels, fontsize=10)
                ax_count.set_xticks(tick_indices)
                ax_count.set_xticklabels(time_labels, fontsize=10)
                
                # Concise explanation
                explanation_text = """Time-Series Analysis:

Top: Operation Rate (%) - Percentage of active devices per 10-minute interval
Bottom: Active Count - Absolute number of operating devices per interval

Key Features: 144 intervals (10-min bins), peak identification, multi-level comparison"""
                
                ax_explanation.text(0.0, 0.8, explanation_text, fontsize=11, alpha=0.8,
                                  verticalalignment='top', transform=ax_explanation.transAxes,
                                  bbox=dict(boxstyle="round,pad=0.8", facecolor="lightcyan", alpha=0.3))
                
                plt.tight_layout()
                pdf.savefig(fig_combined, bbox_inches='tight', pad_inches=0.5)
                plt.close(fig_combined)
            
            # Page 3-N: Operation Heatmap for each level (flexible size)
            locations = [(row['building'], row['level']) for _, row in summary_stats.iterrows()]
            
            for building, level in locations:
                if level == '(All)':
                    # 전체 빌딩 데이터
                    filtered_data = location_data[location_data['building'] == building]
                    title_suffix = f"{building} (All Levels)"
                else:
                    # 특정 레벨 데이터
                    filtered_data = location_data[
                        (location_data['building'] == building) & 
                        (location_data['level'] == level)
                    ]
                    title_suffix = f"{building}-{level}"
                
                if not filtered_data.empty:
                    # T-Ward별 가동 시간 계산
                    tward_operation_time = filtered_data[filtered_data['is_active'] == True].groupby('mac')['time_bin'].count().reset_index()
                    tward_operation_time.columns = ['mac', 'operation_minutes']
                    tward_operation_time['operation_minutes'] = tward_operation_time['operation_minutes'] * 10
                    
                    all_twards = filtered_data['mac'].unique()
                    tward_list = []
                    for mac in all_twards:
                        op_time = tward_operation_time[tward_operation_time['mac'] == mac]['operation_minutes']
                        op_time = op_time.values[0] if len(op_time) > 0 else 0
                        tward_list.append({'mac': mac, 'operation_minutes': op_time})
                    
                    tward_summary = pd.DataFrame(tward_list)
                    tward_summary = tward_summary.sort_values('operation_minutes', ascending=False)
                    
                    if not tward_summary.empty:
                        # 모든 T-Ward를 한 페이지에 표시 (가독성 향상)
                        _create_heatmap_page(pdf, filtered_data, tward_summary, 
                                           f'Operation Heatmap - {title_suffix}', 
                                           data_collection_date)
            
            # T-Ward Location Page: Add T-Ward location images before Time Bin Reference Guide
            _create_tward_location_page(pdf, building_name, data_collection_date)
            
            # Final page: Reference Guide (simplified)
            fig_summary = plt.figure(figsize=(10, 6))  # Compact size
            ax_summary = fig_summary.add_subplot(111)
            ax_summary.axis('off')
            
            summary_text = f"""Time Bin Reference Guide

144 bins × 10-minute intervals (T1-T144)
Key References: T1=00:00, T37=06:00, T73=12:00, T109=18:00

Report Summary: {building_name} | {data_collection_date} | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
Analysis System: Hy-con & IRFM by TJLABS"""
            
            ax_summary.text(0.05, 0.95, summary_text, fontsize=10, verticalalignment='top',
                          bbox=dict(boxstyle="round,pad=0.8", facecolor="lightgray", alpha=0.1))
            
            plt.tight_layout()
            pdf.savefig(fig_summary, bbox_inches='tight')
            plt.close(fig_summary)
        
        # PDF 버퍼에서 데이터 가져하기
        pdf_buffer.seek(0)
        pdf_data = pdf_buffer.getvalue()
        
        current_date = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"TableLift_TL_Operation_Analysis_Report_{data_collection_date}_{current_date}.pdf"
        
        return pdf_data, filename
        
    except Exception as e:
        print(f"PDF generation error: {str(e)}")
        return None, None

def _create_heatmap_page(pdf, filtered_data, tward_summary, title, data_collection_date):
    """Create heatmap page with natural proportions and flexible sizing"""
    try:
        # Generate heatmap data (same logic as current dashboard)
        heatmap_data = []
        for _, tward_row in tward_summary.iterrows():
            mac = tward_row['mac']
            row_data = []
            # Operation status for 144 time bins
            for time_bin in range(1, 145):
                active = filtered_data[
                    (filtered_data['mac'] == mac) & 
                    (filtered_data['time_bin'] == time_bin) & 
                    (filtered_data['is_active'] == True)
                ]
                row_data.append(1 if not active.empty else 0)  # 1: active, 0: inactive
            heatmap_data.append(row_data)
        
        if heatmap_data:
            # Dynamic size adjustment - natural proportions based on T-Ward count
            num_twards = len(tward_summary)
            
            # Optimized sizing for better proportions
            if num_twards <= 10:
                height = max(8, num_twards * 0.6 + 3)
                fig_width = 12
            else:
                height = max(10, min(18, num_twards * 0.4 + 3))
                fig_width = 14
            
            # Create figure with better subplot proportions
            fig = plt.figure(figsize=(fig_width, height))
            
            # Main heatmap subplot (adjusted for better spacing)
            ax = plt.subplot2grid((14, 1), (0, 0), rowspan=9, fig=fig)
            
            # Increased space between heatmap and explanation (2 rows gap)
            # Explanation area subplot (bottom 3 rows with better separation)
            ax_explanation = plt.subplot2grid((14, 1), (11, 0), rowspan=3, fig=fig)
            ax_explanation.axis('off')
            
            activity_matrix = np.array(heatmap_data)
            
            # Custom colormap (same as dashboard)
            from matplotlib.colors import ListedColormap
            colors = ['#D3D3D3', '#32CD32']  # Light gray, lime green
            custom_cmap = ListedColormap(colors)
            
            # Create heatmap
            im = ax.imshow(activity_matrix, cmap=custom_cmap, aspect='auto', vmin=0, vmax=1)
            
            # Y-axis labels (MAC Address + Operation Time)
            y_labels = [f"{row['mac']} ({row['operation_minutes']} min)" 
                       for _, row in tward_summary.iterrows()]
            ax.set_yticks(range(len(y_labels)))
            ax.set_yticklabels(y_labels, fontsize=max(8, min(12, 150/num_twards)))  # Dynamic font size
            
            # X-axis labels (time)
            time_labels = []
            tick_positions = []
            for i in range(0, 144, 6):  # Every hour
                hour = i // 6
                time_labels.append(f"{hour:02d}:00")
                tick_positions.append(i)
            
            ax.set_xticks(tick_positions)
            ax.set_xticklabels(time_labels, rotation=45, fontsize=11)
            ax.set_xlabel('Time (Hours)', fontsize=14)
            ax.set_ylabel('T-Ward MAC Address', fontsize=14)
            
            # Vertical grid lines (every 2 hours)
            for i in range(12, 144, 12):  # Every 2 hours
                ax.axvline(x=i-0.5, color='black', linestyle='--', alpha=0.3, linewidth=0.8)
            
            # Thicker grid lines (every 6 hours)
            for i in range(36, 144, 36):  # Every 6 hours
                ax.axvline(x=i-0.5, color='black', linestyle='--', alpha=0.6, linewidth=1.2)
            
            # Horizontal grid lines for T-Ward separation
            for i in range(1, len(tward_summary)):
                ax.axhline(y=i-0.5, color='gray', linestyle='-', alpha=0.2, linewidth=0.5)
            
            # Title
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            
            # Colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label('Operation Status', fontsize=12)
            cbar.set_ticks([0, 1])
            cbar.set_ticklabels(['Inactive (Gray)', 'Active (Green)'])
            
            # Concise heatmap explanation
            explanation_text = f"""Operation Heatmap - {title} ({num_twards} devices):

Y-axis: MAC addresses (ranked by operation time) | X-axis: Time (hourly intervals)
Colors: Green = Active | Gray = Inactive | Grid: 2hr/6hr reference lines
Analysis: Horizontal patterns = device operation, Vertical patterns = simultaneous usage"""
            
            ax_explanation.text(0.0, 0.8, explanation_text, fontsize=11, alpha=0.8,
                              verticalalignment='top', transform=ax_explanation.transAxes,
                              bbox=dict(boxstyle="round,pad=0.8", facecolor="lightgreen", alpha=0.2))
            
            pdf.savefig(fig, bbox_inches='tight', pad_inches=0.5)
            plt.close(fig)
        
    except Exception as e:
        print(f"Error creating heatmap page: {str(e)}")
        pass


def _create_tward_location_page(pdf, building_name, data_collection_date):
    """Create T-Ward Location page with average position images"""
    import os
    import glob
    from PIL import Image
    
    try:
        # Find the most recent T-Ward average position images
        image_patterns = [
            "tward_avg_positions_WWT_1F_*.png",
            "tward_avg_positions_WWT_B1F_*.png"
        ]
        
        found_images = []
        current_dir = os.getcwd()
        
        for pattern in image_patterns:
            matching_files = glob.glob(os.path.join(current_dir, pattern))
            if matching_files:
                # Get the most recent file
                latest_file = max(matching_files, key=os.path.getctime)
                found_images.append(latest_file)
        
        if not found_images:
            print("No T-Ward location images found for PDF report")
            return
        
        # Create figure for T-Ward location page with more space
        fig = plt.figure(figsize=(12, 20))  # Much taller to avoid overlapping
        
        # Add professional header with adjusted position
        header_bg = plt.Rectangle((0.05, 0.95), 0.9, 0.04, 
                                facecolor='#2E4057', alpha=0.9, transform=fig.transFigure)
        fig.patches.append(header_bg)
        
        fig.text(0.5, 0.975, 'T/L(T-Ward, type 31) Location on WWT-1F & B1F', 
                 fontsize=18, fontweight='bold', ha='center', color='white')
        
        fig.text(0.5, 0.955, f'Average Position Analysis - {data_collection_date}', 
                 fontsize=11, ha='center', color='white', style='italic')
        
        # Sort images to ensure proper order (1F first, then B1F)
        # 1F 파일이 먼저 오도록 정렬
        found_images.sort(key=lambda x: (0 if "1F" in x else 1, x))
        
        # Add images with proper spacing and better layout
        if len(found_images) >= 2:
            # First image (WWT-1F) - positioned in upper half
            try:
                img1 = Image.open(found_images[0])
                ax1 = fig.add_axes([0.1, 0.55, 0.8, 0.35])  # [left, bottom, width, height]
                ax1.imshow(img1)
                ax1.axis('off')
                
                # Ensure correct title for first image
                filename1 = os.path.basename(found_images[0])
                if "1F" in filename1:
                    title1 = "WWT-1F (First Floor)"
                else:
                    title1 = "WWT-1F (First Floor)"  # Force 1F for first image
                
                ax1.set_title(f'T-Ward Average Positions - {title1}', 
                            fontsize=14, fontweight='bold', pad=15)
                
            except Exception as img_error:
                print(f"Error loading first image: {str(img_error)}")
            
            # Second image (WWT-B1F) - positioned in lower half
            try:
                img2 = Image.open(found_images[1])
                ax2 = fig.add_axes([0.1, 0.15, 0.8, 0.35])  # [left, bottom, width, height]
                ax2.imshow(img2)
                ax2.axis('off')
                
                # Ensure correct title for second image
                filename2 = os.path.basename(found_images[1])
                if "B1F" in filename2:
                    title2 = "WWT-B1F (Basement Floor)"
                else:
                    title2 = "WWT-B1F (Basement Floor)"  # Force B1F for second image
                
                ax2.set_title(f'T-Ward Average Positions - {title2}', 
                            fontsize=14, fontweight='bold', pad=15)
                
            except Exception as img_error:
                print(f"Error loading second image: {str(img_error)}")
        
        elif len(found_images) == 1:
            # Single image - centered
            try:
                img = Image.open(found_images[0])
                ax = fig.add_axes([0.1, 0.35, 0.8, 0.45])
                ax.imshow(img)
                ax.axis('off')
                
                filename = os.path.basename(found_images[0])
                if "1F" in filename:
                    level_title = "WWT-1F (First Floor)"
                elif "B1F" in filename:
                    level_title = "WWT-B1F (Basement Floor)"
                else:
                    level_title = "WWT Level"
                
                ax.set_title(f'T-Ward Average Positions - {level_title}', 
                           fontsize=14, fontweight='bold', pad=15)
                
            except Exception as img_error:
                print(f"Error loading single image: {str(img_error)}")
        
        # Add explanation at the bottom with proper spacing
        explanation_text = """Position Analysis Legend:

• Blue Circles with MAC: T-Ward average positions during analysis period
• Yellow Squares: S-Ward (sensor) locations providing positioning reference

Analysis Period: 24-hour operational data (144 × 10-minute intervals)
Coordinate System: Building-specific positioning grid (meters)
Positioning Method: RSSI-based trilateration with smoothing (α=0.99)"""
        
        # Add explanation box at bottom with better positioning
        ax_explanation = fig.add_axes([0.08, 0.02, 0.84, 0.11])
        ax_explanation.axis('off')
        
        explanation_bg = plt.Rectangle((0.0, 0.0), 1.0, 1.0, 
                                     facecolor='#F8F9FA', edgecolor='#DEE2E6', 
                                     linewidth=1, transform=ax_explanation.transAxes)
        ax_explanation.add_patch(explanation_bg)
        
        ax_explanation.text(0.03, 0.92, explanation_text, fontsize=10, 
                          verticalalignment='top', transform=ax_explanation.transAxes)
        pdf.savefig(fig, bbox_inches='tight', pad_inches=0.5)
        plt.close(fig)
        
        print("T-Ward location page added to PDF report successfully")
        
    except Exception as e:
        print(f"Error creating T-Ward location page: {str(e)}")
        pass


def generate_operation_pdf_report(summary_stats, op_rate_df, location_data, st):
    """
    Operation Analysis 페이지의 모든 그래프와 테이블을 PDF로 생성
    """
    import streamlit as st
    from datetime import datetime
    
    try:
        # 컬럼명 확인 및 디버깅
        st.write("Debug - Summary Stats Columns:", summary_stats.columns.tolist())
        st.write("Debug - Summary Stats Sample:", summary_stats.head())
        
        # PDF 파일 생성
        pdf_buffer = io.BytesIO()
        
        with PdfPages(pdf_buffer) as pdf:
            # 페이지 1: 요약 통계
            fig1, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            fig1.suptitle('T-Ward Operation Analysis Report', fontsize=20, fontweight='bold')
            
            # 서브플롯 1: Building/Level별 통계 테이블
            ax1.axis('tight')
            ax1.axis('off')
            ax1.set_title('Building/Level Operation Summary', fontsize=14, fontweight='bold', pad=20)
            
            # 테이블 데이터 준비
            table_data = []
            for _, row in summary_stats.iterrows():
                # 안전하게 컬럼 접근
                operation_rate = row.get('Operation Rate (%)', row.get('Average Operation Rate (%)', 0))
                table_data.append([
                    f"{row['building']}-{row['level']}", 
                    f"{row['Total T-Ward Count']}", 
                    f"{operation_rate:.1f}%"
                ])
            
            table = ax1.table(cellText=table_data,
                            colLabels=['Location', 'Total T-Wards', 'Avg Operation Rate'],
                            cellLoc='center',
                            loc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1.2, 1.8)
            
            # 서브플롯 2: 시간별 가동률 그래프
            if not op_rate_df.empty:
                # 시간별 그래프용 데이터 생성
                op_rate_arr = {}
                for (bldg, lvl), group in op_rate_df.groupby(['building', 'level']):
                    key = f"{bldg}-{lvl}"
                    y_values = [0.0] * 144
                    for _, row in group.iterrows():
                        time_bin = int(row['time_bin'])
                        if 1 <= time_bin <= 144:
                            y_values[time_bin - 1] = float(row['Operation Rate (%)'])
                    op_rate_arr[key] = y_values
                
                x_indices = list(range(144))
                for key, y_values in op_rate_arr.items():
                    if key != 'WWT-(All)':  # All 제외하고 표시
                        ax2.plot(x_indices, y_values, marker='o', markersize=1, linewidth=1, label=key)
                
                ax2.set_title('Operation Rate per 10 Minutes', fontsize=12, fontweight='bold')
                ax2.set_xlabel('Time (10-min bins)')
                ax2.set_ylabel('Operation Rate (%)')
                ax2.legend(fontsize=8)
                ax2.grid(True, alpha=0.3)
                
                # X축 시간 라벨
                tick_indices = list(range(0, 144, 36))
                time_labels = [f"{i//6:02d}:00" for i in tick_indices]
                ax2.set_xticks(tick_indices)
                ax2.set_xticklabels(time_labels)
            
            # 서브플롯 3: T-Ward 분포 파이차트
            level_counts = summary_stats[summary_stats['level'] != '(All)']['Total T-Ward Count'].values
            level_labels = [f"{row['building']}-{row['level']}" for _, row in summary_stats[summary_stats['level'] != '(All)'].iterrows()]
            
            if len(level_counts) > 0:
                ax3.pie(level_counts, labels=level_labels, autopct='%1.1f%%', startangle=90)
                ax3.set_title('T-Ward Distribution by Level', fontsize=12, fontweight='bold')
            
            # 서브플롯 4: 가동률 히스토그램
            if not op_rate_df.empty:
                all_rates = []
                for (bldg, lvl), group in op_rate_df.groupby(['building', 'level']):
                    if lvl != '(All)':
                        rates = group['Operation Rate (%)'].values
                        all_rates.extend(rates[rates > 0])  # 0이 아닌 값만
                
                if all_rates:
                    ax4.hist(all_rates, bins=20, alpha=0.7, edgecolor='black')
                    ax4.set_title('Operation Rate Distribution', fontsize=12, fontweight='bold')
                    ax4.set_xlabel('Operation Rate (%)')
                    ax4.set_ylabel('Frequency')
                    ax4.grid(True, alpha=0.3)
            
            # 날짜/시간 정보 추가
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fig1.text(0.02, 0.02, f'Generated: {current_time}', fontsize=8, alpha=0.7)
            
            plt.tight_layout()
            pdf.savefig(fig1, bbox_inches='tight')
            plt.close(fig1)
            
            # 페이지 2: Operation Heatmap들
            # Building/Level별 히트맵 생성
            locations = [(row['building'], row['level']) for _, row in summary_stats.iterrows() 
                        if row['level'] != '(All)']
            
            for building, level in locations:
                if level == '(All)':
                    filtered_data = location_data[location_data['building'] == building]
                else:
                    filtered_data = location_data[
                        (location_data['building'] == building) & 
                        (location_data['level'] == level)
                    ]
                
                if filtered_data.empty:
                    continue
                
                # T-Ward별 가동 시간 계산
                tward_operation_time = filtered_data[filtered_data['is_active'] == True].groupby('mac')['time_bin'].count().reset_index()
                tward_operation_time.columns = ['mac', 'operation_minutes']
                tward_operation_time['operation_minutes'] = tward_operation_time['operation_minutes'] * 10
                
                all_twards = filtered_data['mac'].unique()
                tward_list = []
                for mac in all_twards:
                    op_time = tward_operation_time[tward_operation_time['mac'] == mac]['operation_minutes']
                    op_time = op_time.values[0] if len(op_time) > 0 else 0
                    tward_list.append({'mac': mac, 'operation_minutes': op_time})
                
                tward_summary = pd.DataFrame(tward_list)
                tward_summary = tward_summary.sort_values('operation_minutes', ascending=False)
                
                if tward_summary.empty:
                    continue
                
                # 상위 20개 T-Ward만 표시 (PDF에서는 크기 제한)
                tward_summary = tward_summary.head(20)
                
                # 히트맵 데이터 생성
                heatmap_data = []
                for _, tward_row in tward_summary.iterrows():
                    mac = tward_row['mac']
                    row_data = []
                    for time_bin in range(1, 145):
                        active = filtered_data[
                            (filtered_data['mac'] == mac) & 
                            (filtered_data['time_bin'] == time_bin) & 
                            (filtered_data['is_active'] == True)
                        ]
                        row_data.append(1 if not active.empty else 0)
                    heatmap_data.append(row_data)
                
                if not heatmap_data:
                    continue
                
                # 히트맵 그리기
                fig, ax = plt.subplots(figsize=(16, max(8, len(tward_summary) * 0.4)))
                
                activity_matrix = np.array(heatmap_data)
                
                from matplotlib.colors import ListedColormap
                colors = ['#D3D3D3', '#32CD32']
                custom_cmap = ListedColormap(colors)
                
                im = ax.imshow(activity_matrix, cmap=custom_cmap, aspect='auto', vmin=0, vmax=1)
                
                # Y축 라벨
                y_labels = [f"{row['mac']}\n({row['operation_minutes']} min)" 
                           for _, row in tward_summary.iterrows()]
                ax.set_yticks(range(len(y_labels)))
                ax.set_yticklabels(y_labels, fontsize=8)
                
                # X축 라벨
                time_labels = []
                tick_positions = []
                for i in range(0, 144, 12):  # 2시간마다
                    hour = i // 6
                    time_labels.append(f"{hour:02d}:00")
                    tick_positions.append(i)
                
                ax.set_xticks(tick_positions)
                ax.set_xticklabels(time_labels, rotation=45, fontsize=9)
                ax.set_xlabel('Time (Hours)', fontsize=12)
                ax.set_ylabel('T-Ward MAC Address', fontsize=12)
                
                # Grid lines
                for i in range(12, 144, 12):
                    ax.axvline(x=i-0.5, color='black', linestyle='--', alpha=0.3, linewidth=0.8)
                for i in range(1, len(tward_summary)):
                    ax.axhline(y=i-0.5, color='gray', linestyle='-', alpha=0.2, linewidth=0.5)
                
                ax.set_title(f'Operation Heatmap - {building}' + 
                            (f'-{level}' if level != '(All)' else ' (All Levels)'), 
                            fontsize=14, fontweight='bold')
                
                # 컬러바
                cbar = plt.colorbar(im, ax=ax)
                cbar.set_label('Operation Status', fontsize=10)
                cbar.set_ticks([0, 1])
                cbar.set_ticklabels(['Inactive', 'Active'])
                
                plt.tight_layout()
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
        
        # PDF 다운로드 제공
        pdf_buffer.seek(0)
        
        current_date = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"T-Ward_Operation_Analysis_Report_{current_date}.pdf"
        
        st.download_button(
            label="📥 Download PDF Report",
            data=pdf_buffer.getvalue(),
            file_name=filename,
            mime="application/pdf"
        )
        
        st.success(f"✅ PDF report generated successfully! Click the download button above.")
        
    except Exception as e:
        st.error(f"❌ Error generating PDF report: {str(e)}")
        print(f"PDF generation error: {str(e)}")

def render_report_generation_tward31(st):
    """
    Report Generation 탭 - PDF 리포트 생성 및 다운로드
    """
    st.markdown("### 📄 T-Ward Operation Analysis Report Generation")
    st.info("Generate comprehensive PDF reports based on your Operation Analysis results.")
    
    # Operation Analysis 결과 확인
    if 'tward31_analysis_results' not in st.session_state:
        st.warning("⚠️ No analysis results found. Please run Operation Analysis first.")
        st.markdown("**Steps to generate report:**")
        st.markdown("1. Go to **Operation Analysis** tab")
        st.markdown("2. Run the analysis with your T-Ward data")
        st.markdown("3. Return to this tab to generate PDF report")
        return
    
    analysis_results = st.session_state['tward31_analysis_results']
    summary_stats = analysis_results['summary_stats']
    op_rate_df = analysis_results.get('op_rate_df', pd.DataFrame())  # 안전한 접근
    location_data = analysis_results['location_data']
    
    st.success("✅ Analysis results loaded successfully!")
    
    # PDF 리포트 자동 생성
    with st.spinner("Generating PDF report..."):
        pdf_data, pdf_filename = generate_cached_pdf_report(
            summary_stats, op_rate_df, location_data
        )
        
        if pdf_data:
            st.success(f"✅ PDF report generated successfully: **{pdf_filename}**")
            
            # PDF 미리보기 (Base64 인코딩)
            import base64
            base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
            
            # PDF 뷰어 임베드
            st.markdown("### 📖 PDF Preview")
            pdf_display = f"""
            <iframe src="data:application/pdf;base64,{base64_pdf}" 
                    width="100%" height="800" type="application/pdf">
                <p>Your browser does not support PDFs. 
                   <a href="data:application/pdf;base64,{base64_pdf}">Download the PDF</a>.</p>
            </iframe>
            """
            st.markdown(pdf_display, unsafe_allow_html=True)
            
            # 다운로드 버튼
            st.markdown("### 💾 Download Report")
            st.download_button(
                label="📥 Download PDF Report",
                data=pdf_data,
                file_name=pdf_filename,
                mime="application/pdf"
            )
            
            # 리포트 정보
            st.markdown("### 📋 Report Information")
            file_size = len(pdf_data) / 1024  # KB
            st.info(f"""
            **File Name:** {pdf_filename}  
            **File Size:** {file_size:.1f} KB  
            **Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}  
            **Sections Included:** Summary, Charts, Heatmap Analysis
            """)
            
        else:
            st.error("❌ Failed to generate PDF report. Please try again.")
    

