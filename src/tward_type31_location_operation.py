import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from datetime import datetime
import io
import os
from src import tward_type31_processing
from src.building_setup import load_building_config

def render_location_operation_analysis_tward31(st):
    """Location & Operation Analysis 탭 렌더링"""
    st.header("🗺️ T-Ward Type 31 Location & Operation Analysis")
    
    # 분석 수행
    analysis_results = None
    if 'tward31_analysis_results' in st.session_state:
        analysis_results = st.session_state['tward31_analysis_results']
    
    if analysis_results is None:
        with st.spinner("Loading and analyzing data..."):
            try:
                # 데이터 로드 및 분석
                analysis_results = tward_type31_processing.perform_tward31_analysis()
                if analysis_results is None:
                    st.error("No data available for analysis.")
                    return
                    
            except Exception as e:
                st.error(f"Error occurred during data loading: {str(e)}")
                return
        
        # 결과 캐시
        st.session_state['tward31_analysis_results'] = analysis_results
    
    # Location & Operation Analysis용 raw 데이터 사용
    location_data = analysis_results.get('raw_location_data', analysis_results['location_data'])
    
    # S-Ward 설정 로드
    sward_config = tward_type31_processing.load_sward_config()
    
    # 건물 설정 로드
    building_config = load_building_config()
    
    # 위치 계산 수행
    try:
        position_results = calculate_tward_positions(location_data, sward_config)
        
        if position_results is not None and not position_results.empty:
            st.success(f"✅ Position calculation completed! Generated {len(position_results)} position data points.")
            
            # 기본 정보 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Positions", len(position_results))
            with col2:
                active_positions = len(position_results[position_results['is_active'] == True])
                st.metric("Active Positions", active_positions)
            with col3:
                unique_macs = position_results['mac'].nunique()
                st.metric("Unique T-Wards", unique_macs)
            
            # 위치 데이터 표시
            st.subheader("📊 계산된 T-Ward 위치 데이터")
            
            # 데이터 필터링 옵션
            col1, col2 = st.columns(2)
            with col1:
                buildings = list(position_results['building'].unique()) if 'building' in position_results.columns else ['WWT']
                selected_building = st.selectbox("Building 선택", options=['All'] + buildings)
            with col2:
                levels = list(position_results['level'].unique()) if 'level' in position_results.columns else ['1F']
                selected_level = st.selectbox("Level 선택", options=['All'] + levels)
            
            # 필터링된 데이터
            filtered_data = position_results.copy()
            if selected_building != 'All' and 'building' in filtered_data.columns:
                filtered_data = filtered_data[filtered_data['building'] == selected_building]
            if selected_level != 'All' and 'level' in filtered_data.columns:
                filtered_data = filtered_data[filtered_data['level'] == selected_level]
            
            # 데이터 테이블 표시
            available_columns = filtered_data.columns.tolist()
            display_columns = []
            for col in ['time_bin', 'mac', 'building', 'level', 'calculated_x', 'calculated_y', 'is_active', 'sward_count']:
                if col in available_columns:
                    display_columns.append(col)
            
            if 'smoothed_x' in available_columns:
                display_columns.extend(['smoothed_x', 'smoothed_y'])
            
            st.dataframe(filtered_data[display_columns], use_container_width=True)
            
            # 지도 표시 옵션
            if selected_building != 'All' and selected_level != 'All':
                st.subheader("🗺️ T-Ward 위치 지도")
                
                # 시간 범위 선택
                time_bins = sorted(filtered_data['time_bin'].unique())
                if len(time_bins) > 0:
                    selected_time_bin = st.selectbox(
                        "시간대 선택 (10분 단위)", 
                        options=time_bins,
                        format_func=lambda x: f"Time Bin {x} ({(x-1)*10//60:02d}:{(x-1)*10%60:02d})"
                    )
                    
                    # 선택된 시간대의 위치 표시
                    display_tward_positions_on_map(
                        filtered_data, 
                        selected_building, 
                        selected_level, 
                        sward_config,
                        time_bin=selected_time_bin
                    )
            
            # Auto-generate videos and images section
            st.subheader("🎬 Auto-Generate Videos and Images")
            
            # Auto-generate by level
            generated_files = auto_generate_videos_and_images(position_results, sward_config, building_config)
            
            if generated_files:
                st.success(f"✅ {len(generated_files)} files have been automatically generated!")
                
                # 생성된 파일들을 Level별로 그룹화
                videos = [f for f in generated_files if f['type'] == 'video']
                images = [f for f in generated_files if f['type'] == 'image']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 📹 T-Ward Location Timelapse Videos")
                    for video_info in videos:
                        with open(video_info['path'], 'rb') as video_file:
                            st.download_button(
                                label=f"📹 Download {video_info['building']} {video_info['level']} Video",
                                data=video_file.read(),
                                file_name=video_info['filename'],
                                mime="video/mp4",
                                key=f"download_video_{video_info['building']}_{video_info['level']}"
                            )
                
                with col2:
                    st.markdown("### 🗺️ T-Ward Average Position Images")
                    for image_info in images:
                        # Image preview
                        st.image(image_info['path'], caption=f"{image_info['building']} {image_info['level']}", use_column_width=True)
                        with open(image_info['path'], 'rb') as img_file:
                            st.download_button(
                                label=f"🗺️ Download {image_info['building']} {image_info['level']} Image",
                                data=img_file.read(),
                                file_name=image_info['filename'],
                                mime="image/png",
                                key=f"download_image_{image_info['building']}_{image_info['level']}"
                            )
            else:
                st.warning("No valid position data available for generation.")
            
            # CSV 다운로드
            st.subheader("📥 데이터 다운로드")
            csv_data = position_results.to_csv(index=False)
            st.download_button(
                label="위치 데이터 CSV 다운로드",
                data=csv_data,
                file_name=f"tward_positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
        else:
            st.warning("Unable to calculate position data.")
            
    except Exception as e:
        st.error(f"An error occurred during position calculation: {str(e)}")
        st.exception(e)

def calculate_tward_positions(location_data, sward_config):
    """T-Ward 위치 계산 - Raw 데이터 직접 처리"""
    
    st.write("### T-Ward Position Calculation Started")
    
    # Input data verification
    st.write(f"**DEBUG: Input Data Structure**")
    st.write(f"- location_data shape: {location_data.shape}")
    st.write(f"- location_data columns: {list(location_data.columns)}")
    st.write(f"- sward_config shape: {sward_config.shape}")
    
    # Check first few rows
    st.write("**DEBUG: location_data Sample**")
    st.dataframe(location_data.head())
    
    try:
        # Direct raw data processing (skip Building/Level determination)
        st.write("**DEBUG: Direct Raw Data Processing Started**")
        
        # Calculate positions by time bin
        position_results = calculate_positions_by_timebin(location_data, sward_config)
        
        if position_results is None or position_results.empty:
            st.error("Position calculation failed")
            return None
        
        st.write(f"**DEBUG: Position Calculation Completed**")
        st.write(f"- Result shape: {position_results.shape}")
        
        # Check non-None position count
        valid_positions = position_results[
            (position_results['calculated_x'].notna()) & 
            (position_results['calculated_y'].notna())
        ]
        st.write(f"- Valid positions: {len(valid_positions)}/{len(position_results)}")
        
        if len(valid_positions) > 0:
            st.write("**DEBUG: Valid Position Sample**")
            st.dataframe(valid_positions.head())
        
        return position_results
        
    except Exception as e:
        st.error(f"Error during position calculation: {str(e)}")
        st.write(f"오류 상세: {type(e).__name__}")
        import traceback
        st.code(traceback.format_exc())
        return None

def determine_building_level(location_data, sward_config):
    """Building과 Level 결정"""
    
    # S-Ward 정보를 딕셔너리로 변환
    sward_dict = {}
    for _, sward in sward_config.iterrows():
        sward_id = str(int(sward['sward_id']))
        sward_dict[sward_id] = {
            'building': sward['building'],
            'level': sward['level'],
            'x': sward['x'],
            'y': sward['y']
        }
    
    # 복사본 생성
    result_data = location_data.copy()
    
    # Building과 Level 컬럼 초기화
    result_data['building'] = 'WWT'  # 기본값
    result_data['level'] = '1F'      # 기본값
    
    # RSSI 컬럼들을 찾아서 가장 강한 신호를 기반으로 building/level 결정
    for idx, row in result_data.iterrows():
        rssi_cols = [col for col in result_data.columns if col.startswith('27')]
        valid_rssi = {}
        
        for col in rssi_cols:
            rssi_val = row[col]
            if pd.notna(rssi_val) and rssi_val < 0:  # 유효한 RSSI 값
                if col in sward_dict:
                    valid_rssi[col] = rssi_val
        
        if valid_rssi:
            # 가장 강한 신호의 S-Ward 선택 (RSSI는 음수이므로 max가 가장 강한 신호)
            strongest_sward = max(valid_rssi, key=valid_rssi.get)
            result_data.at[idx, 'building'] = sward_dict[strongest_sward]['building']
            result_data.at[idx, 'level'] = sward_dict[strongest_sward]['level']
    
    # Type 31의 경우 하루 단위로 Level 고정
    if 'type' in result_data.columns:
        type31_macs = result_data[result_data['type'] == 31]['mac'].unique()
        
        for mac in type31_macs:
            mac_data = result_data[result_data['mac'] == mac]
            
            # 각 Level별 출현 빈도 계산
            level_counts = mac_data.groupby(['building', 'level']).size()
            if not level_counts.empty:
                # 가장 많이 나온 Building/Level 조합
                dominant_building, dominant_level = level_counts.idxmax()
                
                # 해당 MAC의 모든 데이터를 고정된 Building/Level로 설정
                mask = result_data['mac'] == mac
                result_data.loc[mask, 'building'] = dominant_building
                result_data.loc[mask, 'level'] = dominant_level
    
    return result_data

def calculate_positions_by_timebin(location_data, sward_config):
    """Calculate positions by time bin - For raw data processing"""
    
    position_results = []
    
    # Convert S-Ward info to dictionary
    sward_dict = {}
    for _, sward in sward_config.iterrows():
        sward_id = int(sward['sward_id'])  # Convert to int
        sward_dict[sward_id] = {
            'x': sward['x'],
            'y': sward['y'],
            'building': sward['building'],
            'level': sward['level']
        }
    
    st.write(f"**DEBUG: S-Ward Dictionary**")
    st.write(f"- S-Ward count: {len(sward_dict)}")
    st.write(f"- S-Ward ID sample: {list(sward_dict.keys())[:5]}")
    
    # Generate time_bin from raw data (use existing if available)
    if 'time_bin' not in location_data.columns:
        # Generate 10-second unit time_index based on 0:00:00
        location_data['time_index'] = ((location_data['time'] - location_data['time'].dt.normalize()) / pd.Timedelta(seconds=10)).astype(int) + 1
        location_data['time_bin'] = ((location_data['time_index'] - 1) // 60) + 1  # 10-minute bin index (1~144)
    
    # Process by MAC
    unique_macs = location_data['mac'].unique()
    st.write(f"- MACs to process: {len(unique_macs)}")
    
    processed_positions = 0
    valid_positions = 0
    
    for mac_idx, mac in enumerate(unique_macs):
        mac_data = location_data[location_data['mac'] == mac]
        
        if not mac_data.empty:
            # Building/Level 결정 (각 MAC별로)
            mac_sward_counts = mac_data.groupby('sward_id').size()
            most_common_sward = mac_sward_counts.idxmax()
            
            if most_common_sward in sward_dict:
                fixed_building = sward_dict[most_common_sward]['building']
                fixed_level = sward_dict[most_common_sward]['level']
            else:
                fixed_building = 'WWT'
                fixed_level = '1F'
            
            # 첫 번째 MAC에 대해서만 상세 디버깅
            if mac_idx == 0:
                st.write(f"**DEBUG: 첫 번째 MAC ({mac}) 처리**")
                st.write(f"- MAC 데이터 개수: {len(mac_data)}")
                st.write(f"- Fixed building/level: {fixed_building}/{fixed_level}")
                st.write(f"- Available S-Ward IDs: {sorted(mac_data['sward_id'].unique())}")
                st.write(f"- Time bin range: {mac_data['time_bin'].min()}-{mac_data['time_bin'].max()}")
            
            # Step 1: 신호가 있는 time index에서만 위치 계산
            calculated_positions = {}  # {time_bin: (x, y)}
            
            for time_bin in range(1, 145):
                time_data = mac_data[mac_data['time_bin'] == time_bin]
                
                if not time_data.empty:
                    # 해당 시간대의 모든 S-Ward RSSI 데이터 수집
                    sward_data_list = []
                    
                    # time_bin 내에서 S-Ward별 평균 RSSI 계산
                    for sward_id, sward_group in time_data.groupby('sward_id'):
                        if sward_id in sward_dict:
                            avg_rssi = sward_group['rssi'].mean()
                            if avg_rssi < 0:  # 유효한 RSSI 값
                                sward_data_list.append({
                                    'sward_id': sward_id,
                                    'rssi': avg_rssi,
                                    'x': sward_dict[sward_id]['x'],
                                    'y': sward_dict[sward_id]['y']
                                })
                    
                    if sward_data_list:
                        # DataFrame으로 변환하여 위치 계산
                        sward_data = pd.DataFrame(sward_data_list)
                        x_pos, y_pos = calculate_position_by_algorithm(sward_data)
                        
                        if x_pos is not None and y_pos is not None:
                            calculated_positions[time_bin] = (x_pos, y_pos)
                            processed_positions += 1
                            valid_positions += 1
            
            # Step 2: 모든 time index (1~144)에 대해 데이터 생성
            # 신호 없는 구간은 가장 가까운 위치로 채움
            all_positions = {}
            
            # 계산된 위치의 time_bin 리스트
            calculated_time_bins = sorted(calculated_positions.keys())
            
            if calculated_time_bins:  # 위치가 하나라도 계산된 경우
                for time_bin in range(1, 145):
                    if time_bin in calculated_positions:
                        # 신호가 있는 경우: 계산된 위치 사용
                        all_positions[time_bin] = calculated_positions[time_bin]
                    else:
                        # 신호가 없는 경우: 가장 가까운 이전/이후 위치 사용
                        # 이전 위치 찾기
                        prev_time_bins = [t for t in calculated_time_bins if t < time_bin]
                        next_time_bins = [t for t in calculated_time_bins if t > time_bin]
                        
                        if prev_time_bins:
                            # 가장 가까운 이전 위치 사용
                            closest_prev = max(prev_time_bins)
                            all_positions[time_bin] = calculated_positions[closest_prev]
                        elif next_time_bins:
                            # 이전 위치가 없으면 가장 가까운 이후 위치 사용
                            closest_next = min(next_time_bins)
                            all_positions[time_bin] = calculated_positions[closest_next]
            
            # Step 3: 위치 smoothing (새로운 위치 = 이전 위치 * 0.99 + 새로운 위치 * 0.01)
            smoothed_positions = {}
            prev_x, prev_y = None, None
            
            for time_bin in range(1, 145):
                if time_bin in all_positions:
                    current_x, current_y = all_positions[time_bin]
                    
                    if prev_x is not None and prev_y is not None:
                        # Smoothing 적용
                        smoothed_x = prev_x * 0.99 + current_x * 0.01
                        smoothed_y = prev_y * 0.99 + current_y * 0.01
                    else:
                        # 첫 번째 위치는 그대로 사용
                        smoothed_x, smoothed_y = current_x, current_y
                    
                    smoothed_positions[time_bin] = (smoothed_x, smoothed_y)
                    prev_x, prev_y = smoothed_x, smoothed_y
            
            # Step 4: 최종 결과 생성
            for time_bin in range(1, 145):
                is_active = time_bin in calculated_positions
                
                if time_bin in smoothed_positions:
                    x_pos, y_pos = smoothed_positions[time_bin]
                else:
                    x_pos, y_pos = None, None
                
                position_results.append({
                    'mac': mac,
                    'time_bin': time_bin,
                    'building': fixed_building,
                    'level': fixed_level,
                    'calculated_x': x_pos,
                    'calculated_y': y_pos,
                    'is_active': is_active,
                    'sward_count': len(calculated_positions) if is_active else 0
                })
            
            # 첫 번째 MAC에 대해서만 디버깅 정보 출력
            if mac_idx == 0:
                st.write(f"**DEBUG: 첫 번째 MAC ({mac}) 처리 완료**")
                st.write(f"- 신호가 있는 time_bin 개수: {len(calculated_positions)}")
                st.write(f"- 전체 생성된 위치: {len(smoothed_positions)}")
                if calculated_time_bins:
                    st.write(f"- 신호 범위: {min(calculated_time_bins)} ~ {max(calculated_time_bins)}")
                    first_pos = smoothed_positions.get(1, (None, None))
                    st.write(f"- 첫 번째 time_bin 위치: ({first_pos[0]:.1f}, {first_pos[1]:.1f})" if first_pos[0] else "- 첫 번째 time_bin 위치: None")
    
    st.write(f"**DEBUG: 위치 계산 결과**")
    st.write(f"- 처리된 위치: {processed_positions}")
    st.write(f"- 유효한 위치: {valid_positions}")
    
    return pd.DataFrame(position_results)

def calculate_position_by_algorithm(sward_data):
    """S-Ward 수에 따른 위치 계산 알고리즘"""
    
    sward_count = len(sward_data)
    
    if sward_count == 0:
        return None, None
    elif sward_count == 1:
        return calculate_single_sward_position(sward_data)
    elif sward_count == 2:
        return calculate_dual_sward_position(sward_data)
    else:
        return calculate_multi_sward_position(sward_data)

def calculate_single_sward_position(sward_data):
    """1개 S-Ward: 반경 내 랜덤 위치"""
    sward = sward_data.iloc[0]
    center_x, center_y = sward['x'], sward['y']
    
    # RSSI를 거리로 변환 (간단한 모델)
    rssi = sward['rssi']
    radius = max(10, min(100, abs(rssi) * 2))  # 10-100 픽셀 범위
    
    # 원 내부의 랜덤한 점 생성
    angle = np.random.uniform(0, 2 * np.pi)
    r = radius * np.sqrt(np.random.uniform(0, 1))
    
    x_pos = center_x + r * np.cos(angle)
    y_pos = center_y + r * np.sin(angle)
    
    return x_pos, y_pos

def calculate_dual_sward_position(sward_data):
    """2개 S-Ward: 내분점 공식"""
    sward_data = sward_data.sort_values('rssi', ascending=False)  # 강한 신호 순
    
    s1, s2 = sward_data.iloc[0], sward_data.iloc[1]
    x1, y1 = s1['x'], s1['y']
    x2, y2 = s2['x'], s2['y']
    
    # RSSI를 거리로 변환
    d1 = abs(s1['rssi'])
    d2 = abs(s2['rssi'])
    
    # 내분점 공식: 더 강한 신호에 가깝게
    total_weight = d1 + d2
    if total_weight == 0:
        return (x1 + x2) / 2, (y1 + y2) / 2
    
    # 역가중 (강한 신호가 더 가까움)
    w1 = d2 / total_weight
    w2 = d1 / total_weight
    
    x_pos = w1 * x1 + w2 * x2
    y_pos = w1 * y1 + w2 * y2
    
    return x_pos, y_pos

def calculate_multi_sward_position(sward_data):
    """3개 이상 S-Ward: 가중평균"""
    # 상위 3개 신호 선택
    sward_data = sward_data.nlargest(3, 'rssi')
    
    # 가중치 계산 (RSSI의 역수)
    weights = 1.0 / (abs(sward_data['rssi']) + 1e-6)
    weights = weights / weights.sum()
    
    x_pos = np.sum(sward_data['x'] * weights)
    y_pos = np.sum(sward_data['y'] * weights)
    
    return x_pos, y_pos

def fill_missing_positions(position_data):
    """결측 위치 선형 보간"""
    if position_data.empty:
        return position_data
    
    result_data = position_data.copy()
    
    for mac in result_data['mac'].unique():
        mask = result_data['mac'] == mac
        mac_data = result_data[mask].copy().sort_values('time_bin')
        
        if len(mac_data) > 0:
            # x, y 좌표 보간
            mac_data['calculated_x'] = mac_data['calculated_x'].interpolate(method='linear')
            mac_data['calculated_y'] = mac_data['calculated_y'].interpolate(method='linear')
            
            # 원본 데이터 업데이트
            result_data.loc[mask, 'calculated_x'] = mac_data['calculated_x'].values
            result_data.loc[mask, 'calculated_y'] = mac_data['calculated_y'].values
    
    return result_data

def smooth_positions_advanced(position_data, alpha=0.95):
    """위치 스무딩 (지수 평활법)"""
    if position_data.empty:
        return position_data
    
    result_data = position_data.copy()
    result_data['smoothed_x'] = result_data['calculated_x'].copy()
    result_data['smoothed_y'] = result_data['calculated_y'].copy()
    
    for mac in result_data['mac'].unique():
        mask = result_data['mac'] == mac
        mac_data = result_data[mask].copy().sort_values('time_bin')
        
        if len(mac_data) > 1:
            smoothed_x = [mac_data.iloc[0]['calculated_x']]
            smoothed_y = [mac_data.iloc[0]['calculated_y']]
            
            for i in range(1, len(mac_data)):
                if pd.notna(mac_data.iloc[i]['calculated_x']):
                    # 지수 평활
                    new_x = alpha * smoothed_x[-1] + (1 - alpha) * mac_data.iloc[i]['calculated_x']
                    new_y = alpha * smoothed_y[-1] + (1 - alpha) * mac_data.iloc[i]['calculated_y']
                else:
                    # 이전 값 유지
                    new_x = smoothed_x[-1] if smoothed_x else mac_data.iloc[i]['calculated_x']
                    new_y = smoothed_y[-1] if smoothed_y else mac_data.iloc[i]['calculated_y']
                
                smoothed_x.append(new_x)
                smoothed_y.append(new_y)
            
            # 원본 데이터 업데이트
            result_data.loc[mask, 'smoothed_x'] = smoothed_x
            result_data.loc[mask, 'smoothed_y'] = smoothed_y
    
    return result_data

def display_tward_positions_on_map(position_data, building, level, sward_config, time_bin=None):
    """지도에 T-Ward 위치 표시"""
    try:
        # 맵 이미지 로드
        map_path = f"./Datafile/Map_Image/Map_{building}_{level}.png"
        if not os.path.exists(map_path):
            st.error(f"맵 이미지를 찾을 수 없습니다: {map_path}")
            return
        
        img = mpimg.imread(map_path)
        img_height, img_width = img.shape[:2]
        
        # 그래프 생성
        fig, ax = plt.subplots(figsize=(15, 10))
        
        # 원본 맵 이미지 표시
        ax.imshow(img, origin='upper')
        
        # S-Ward 위치 표시 (노란색 네모)
        sward_positions = sward_config[
            (sward_config['building'] == building) & 
            (sward_config['level'] == level)
        ]
        
        for idx, sward in sward_positions.iterrows():
            x_pixel = int(sward['x'])
            y_pixel = int(sward['y'])
            
            # 노란색 네모 박스로 표시
            ax.scatter(x_pixel, y_pixel, s=120, c='yellow', marker='s', 
                      alpha=0.8, edgecolors='orange', linewidth=1,
                      label='S-Ward' if idx == sward_positions.index[0] else "")
            # 텍스트만 간단하게 (작은 크기)
            ax.annotate(f"S-{int(sward['sward_id'])}", 
                       (x_pixel, y_pixel), 
                       xytext=(5, -12), textcoords='offset points',
                       fontsize=5, fontweight='bold', color='darkorange')
        
        # T-Ward 위치 표시
        filtered_data = position_data[
            (position_data['building'] == building) & 
            (position_data['level'] == level)
        ]
        
        if time_bin is not None:
            filtered_data = filtered_data[filtered_data['time_bin'] == time_bin]
        
        # T-Ward 표시 (활성화/비활성화 구분)
        active_labeled = False
        inactive_labeled = False
        
        for _, row in filtered_data.iterrows():
            if pd.notna(row.get('calculated_x')) and pd.notna(row.get('calculated_y')):
                # 활성화 상태에 따라 색상 결정
                if row['is_active']:
                    color = 'green'
                    edge_color = 'darkgreen'
                    alpha = 0.8
                    label = 'Active T-Ward' if not active_labeled else ""
                    active_labeled = True
                else:
                    color = 'gray'
                    edge_color = 'darkgray'
                    alpha = 0.6
                    label = 'Inactive T-Ward' if not inactive_labeled else ""
                    inactive_labeled = True
                
                # 위치 좌표 결정
                x = row.get('smoothed_x', row.get('calculated_x'))
                y = row.get('smoothed_y', row.get('calculated_y'))
                
                # 원으로 표시
                ax.scatter(x, y, s=150, c=color, marker='o', alpha=alpha, 
                          edgecolors=edge_color, linewidth=1, label=label)
                
                # MAC 주소 표시 (작은 크기)
                ax.annotate(f"{row['mac']}", (x, y),
                           xytext=(8, 8), textcoords='offset points',
                           fontsize=4.5, fontweight='bold', color=edge_color)
        
        # 축 설정
        ax.set_xlim(0, img_width)
        ax.set_ylim(img_height, 0)  # Y축 뒤집기
        ax.set_xlabel(f'X Position (pixels, max: {img_width})')
        ax.set_ylabel(f'Y Position (pixels, max: {img_height})')
        
        title = f'{building}-{level} T-Ward Positions'
        if time_bin is not None:
            title += f' - Time Bin {time_bin}'
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        st.pyplot(fig)
        plt.close(fig)
        
        # 통계 정보 표시
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total T-Wards", len(filtered_data))
        with col2:
            active_count = len(filtered_data[filtered_data['is_active'] == True])
            st.metric("Active T-Wards", active_count)
        with col3:
            if time_bin is not None:
                st.metric("Selected Time Bin", time_bin)
            else:
                avg_positions = len(filtered_data[filtered_data['is_active'] == True])
                st.metric("Avg Active Positions", avg_positions)
            
    except Exception as e:
        st.error(f"지도 표시 중 오류 발생: {str(e)}")


def create_tward_timelapse_video(position_data, sward_config, building_config, building=None, level=None):
    """T-Ward 위치 변화 동영상 생성"""
    
    try:
        import matplotlib.animation as animation
        from datetime import datetime
        import os
        
        # 데이터 필터링
        filtered_data = position_data.copy()
        if building:
            filtered_data = filtered_data[filtered_data['building'] == building]
        if level:
            filtered_data = filtered_data[filtered_data['level'] == level]
        
        # 유효한 위치 데이터만 선택
        valid_data = filtered_data[
            (filtered_data['calculated_x'].notna()) & 
            (filtered_data['calculated_y'].notna()) &
            (filtered_data['is_active'] == True)
        ].copy()
        
        if valid_data.empty:
            st.warning("No valid position data available for video generation.")
            return None
        
        # 건물/레벨 결정
        target_building = building or valid_data['building'].iloc[0]
        target_level = level or valid_data['level'].iloc[0]
        
        # 지도 이미지 로드
        map_image_path = f"Datafile/Map_Image/Map_{target_building}_{target_level}.png"
        if not os.path.exists(map_image_path):
            st.error(f"지도 이미지를 찾을 수 없습니다: {map_image_path}")
            return None
        
        import cv2
        map_image = cv2.imread(map_image_path)
        map_image = cv2.cvtColor(map_image, cv2.COLOR_BGR2RGB)
        
        # 시간대별 데이터 그룹화
        time_bins = sorted(valid_data['time_bin'].unique())
        
        # 애니메이션 설정
        fig, ax = plt.subplots(figsize=(12, 8))
        
        def animate(frame):
            ax.clear()
            time_bin = time_bins[frame]
            
            # 지도 표시
            ax.imshow(map_image, extent=[0, map_image.shape[1], map_image.shape[0], 0])
            
            # 해당 시간대 데이터 (모든 T-Ward 포함)
            all_frame_data = position_data[
                (position_data['building'] == target_building) &
                (position_data['level'] == target_level) &
                (position_data['time_bin'] == time_bin)
            ]
            
            # T-Ward 위치 표시 (활성화/비활성화 구분)
            for mac in all_frame_data['mac'].unique():
                mac_data = all_frame_data[all_frame_data['mac'] == mac]
                if not mac_data.empty:
                    for _, row in mac_data.iterrows():
                        # 위치가 계산된 경우만 표시
                        if pd.notna(row['calculated_x']) and pd.notna(row['calculated_y']):
                            # 활성화 상태에 따라 색상 결정
                            if row['is_active']:
                                color = 'green'
                                edge_color = 'darkgreen'
                                alpha = 0.8
                            else:
                                color = 'gray'
                                edge_color = 'darkgray'
                                alpha = 0.6
                            
                            # 원으로 표시
                            ax.scatter(row['calculated_x'], row['calculated_y'], 
                                     c=color, s=100, alpha=alpha, 
                                     edgecolors=edge_color, linewidth=1)
                            # MAC 주소 전체 표시 (작은 크기)
                            ax.annotate(f"{mac}", 
                                       (row['calculated_x'], row['calculated_y']),
                                       xytext=(5, 5), textcoords='offset points',
                                       fontsize=4, fontweight='bold', color=edge_color)
            
            # S-Ward 위치 표시 (노란색 네모 박스)
            building_swards = sward_config[
                (sward_config['building'] == target_building) &
                (sward_config['level'] == target_level)
            ]
            for _, sward in building_swards.iterrows():
                # 노란색 네모 박스로 표시
                ax.scatter(sward['x'], sward['y'], c='yellow', s=80, marker='s', 
                          alpha=0.8, edgecolors='orange', linewidth=1)
                # 텍스트만 간단하게 (작은 크기)
                ax.annotate(f"S-{int(sward['sward_id'])}", 
                           (sward['x'], sward['y']),
                           xytext=(5, -12), textcoords='offset points',
                           fontsize=4, color='darkorange', fontweight='bold')
            
            ax.set_title(f"T-Ward Location Tracking - Time Bin {time_bin} ({(time_bin-1)*10//60:02d}:{(time_bin-1)*10%60:02d})")
            ax.set_xlabel('X Position (pixels)')
            ax.set_ylabel('Y Position (pixels)')
            ax.grid(True, alpha=0.3)
        
        # 애니메이션 생성
        anim = animation.FuncAnimation(fig, animate, frames=len(time_bins), 
                                     interval=500, repeat=True)
        
        # 동영상 저장
        output_path = f"tward_timelapse_{target_building}_{target_level}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        # FFmpeg writer 설정
        Writer = animation.writers['ffmpeg']
        writer = Writer(fps=2, metadata=dict(artist='TJLABS'), bitrate=1800)
        
        anim.save(output_path, writer=writer)
        plt.close(fig)
        
        return output_path
        
    except Exception as e:
        st.error(f"동영상 생성 중 오류 발생: {str(e)}")
        return None


def create_tward_average_position_image(position_data, sward_config, building_config, building=None, level=None):
    """T-Ward 평균 위치 이미지 생성"""
    
    try:
        from datetime import datetime
        import os
        
        # 데이터 필터링
        filtered_data = position_data.copy()
        if building:
            filtered_data = filtered_data[filtered_data['building'] == building]
        if level:
            filtered_data = filtered_data[filtered_data['level'] == level]
        
        # 유효한 위치 데이터만 선택
        valid_data = filtered_data[
            (filtered_data['calculated_x'].notna()) & 
            (filtered_data['calculated_y'].notna()) &
            (filtered_data['is_active'] == True)
        ].copy()
        
        if valid_data.empty:
            st.warning("No valid position data available for average position image generation.")
            return None
        
        # 건물/레벨 결정
        target_building = building or valid_data['building'].iloc[0]
        target_level = level or valid_data['level'].iloc[0]
        
        # MAC별 평균 위치 계산
        avg_positions = valid_data.groupby('mac').agg({
            'calculated_x': 'mean',
            'calculated_y': 'mean',
            'building': 'first',
            'level': 'first'
        }).reset_index()
        
        # 지도 이미지 로드
        map_image_path = f"Datafile/Map_Image/Map_{target_building}_{target_level}.png"
        if not os.path.exists(map_image_path):
            st.error(f"지도 이미지를 찾을 수 없습니다: {map_image_path}")
            return None
        
        import cv2
        map_image = cv2.imread(map_image_path)
        map_image = cv2.cvtColor(map_image, cv2.COLOR_BGR2RGB)
        
        # 플롯 생성
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # 지도 표시
        ax.imshow(map_image, extent=[0, map_image.shape[1], map_image.shape[0], 0])
        
        # S-Ward 위치 표시 (노란색 네모 박스)
        building_swards = sward_config[
            (sward_config['building'] == target_building) &
            (sward_config['level'] == target_level)
        ]
        for _, sward in building_swards.iterrows():
            # 노란색 네모 박스로 표시
            ax.scatter(sward['x'], sward['y'], c='yellow', s=80, marker='s', 
                      alpha=0.8, edgecolors='orange', linewidth=1,
                      label='S-Ward' if _ == building_swards.index[0] else "")
            # 텍스트만 간단하게 (박스 없이, 작은 크기)
            ax.annotate(f"S-{int(sward['sward_id'])}", 
                       (sward['x'], sward['y']),
                       xytext=(5, -12), textcoords='offset points',
                       fontsize=5, color='darkorange', fontweight='bold')
        
        # T-Ward 평균 위치 표시 (파란색 원)
        for i, (_, row) in enumerate(avg_positions.iterrows()):
            # 파란색 원으로 표시
            ax.scatter(row['calculated_x'], row['calculated_y'], 
                      c='blue', s=120, alpha=0.8, 
                      edgecolors='navy', linewidth=1,
                      label='T-Ward Average' if i == 0 else "")
            # MAC 주소 전체 표시 (박스 없이, 작은 크기)
            ax.annotate(f"{row['mac']}", 
                       (row['calculated_x'], row['calculated_y']),
                       xytext=(8, 8), textcoords='offset points',
                       fontsize=4.5, fontweight='bold', color='navy')
        
        ax.set_title(f"T-Ward Average Positions - {target_building} {target_level}\n(Total {len(avg_positions)} T-Wards)")
        ax.set_xlabel('X Position (pixels)')
        ax.set_ylabel('Y Position (pixels)')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 이미지 저장
        output_path = f"tward_avg_positions_{target_building}_{target_level}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        
        return output_path
        
    except Exception as e:
        st.error(f"Error occurred during average position image generation: {str(e)}")
        return None


def auto_generate_videos_and_images(position_data, sward_config, building_config):
    """Level별로 자동으로 동영상과 이미지 생성"""
    
    generated_files = []
    
    try:
        # 유효한 위치 데이터만 선택
        valid_data = position_data[
            (position_data['calculated_x'].notna()) & 
            (position_data['calculated_y'].notna()) &
            (position_data['is_active'] == True)
        ].copy()
        
        if valid_data.empty:
            return []
        
        # Building/Level 조합 찾기
        building_levels = valid_data[['building', 'level']].drop_duplicates()
        
        with st.spinner(f"Auto-generating videos and images by level... ({len(building_levels)} levels)"):
            
            progress_bar = st.progress(0)
            total_tasks = len(building_levels) * 2  # 각 Level당 동영상 + 이미지
            completed_tasks = 0
            
            for _, row in building_levels.iterrows():
                building = row['building']
                level = row['level']
                
                st.write(f"📍 처리 중: {building} {level}")
                
                # 동영상 생성
                try:
                    video_path = create_tward_timelapse_video(
                        position_data, sward_config, building_config, 
                        building, level
                    )
                    if video_path and os.path.exists(video_path):
                        generated_files.append({
                            'type': 'video',
                            'path': video_path,
                            'filename': f"tward_timelapse_{building}_{level}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
                            'building': building,
                            'level': level
                        })
                        st.write(f"  ✅ 동영상 생성 완료")
                    else:
                        st.write(f"  ❌ 동영상 생성 실패")
                except Exception as e:
                    st.write(f"  ❌ 동영상 생성 오류: {str(e)}")
                
                completed_tasks += 1
                progress_bar.progress(completed_tasks / total_tasks)
                
                # 이미지 생성
                try:
                    image_path = create_tward_average_position_image(
                        position_data, sward_config, building_config,
                        building, level
                    )
                    if image_path and os.path.exists(image_path):
                        generated_files.append({
                            'type': 'image',
                            'path': image_path,
                            'filename': f"tward_avg_positions_{building}_{level}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                            'building': building,
                            'level': level
                        })
                        st.write(f"  ✅ 이미지 생성 완료")
                    else:
                        st.write(f"  ❌ 이미지 생성 실패")
                except Exception as e:
                    st.write(f"  ❌ 이미지 생성 오류: {str(e)}")
                
                completed_tasks += 1
                progress_bar.progress(completed_tasks / total_tasks)
            
            progress_bar.progress(1.0)
            
        return generated_files
        
    except Exception as e:
        st.error(f"자동 생성 중 오류 발생: {str(e)}")
        return []
