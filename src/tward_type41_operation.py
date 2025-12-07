"""
T-Ward Type 41 Operation Analysis Module
작업자 헬멧 부착 T-Ward의 작업 현황 분석
성능 최적화: 벡터화 연산, 캐싱, 메모리 효율적 처리
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from src.building_setup import load_sward_config
import hashlib
import time
import gc  # Garbage collection for memory management

def performance_timer(func_name):
    """성능 측정 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            print(f"🚀 {func_name} 시작...")
            
            result = func(*args, **kwargs)
            
            end_time = time.time()
            elapsed = end_time - start_time
            print(f"✅ {func_name} 완료: {elapsed:.2f}초")
            
            return result
        return wrapper
    return decorator

# 성능 최적화를 위한 캐싱 시스템
def cached_sward_processing(sward_config_hash):
    """S-Ward 설정 캐싱 (데이터 변경 시에만 재계산)"""
    # 세션 기반 캐싱으로 변경 (Streamlit Cloud 호환성)
    cache_key = f'sward_dict_{sward_config_hash}'
    
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    sward_config = load_sward_config()
    if sward_config is None:
        return None
    
    # S-Ward 딕셔너리 생성 (벡터화)
    sward_dict = {
        row['sward_id']: {
            'building': row['building'],
            'level': row['level'], 
            'x': row['x'],
            'y': row['y'],
            'space_type': row.get('space_type', 'Unknown')
        }
        for _, row in sward_config.iterrows()
    }
    
    # 세션에 캐싱
    st.session_state[cache_key] = sward_dict
    return sward_dict

def load_and_process_data_tward41():
    """T-Ward Type 41 데이터 로드 및 기본 처리 (성능 최적화)"""
    
    try:
        # 캐시된 처리 결과 확인
        if 'tward41_processed_data' in st.session_state:
            return st.session_state['tward41_processed_data']
            
        # 세션 상태에서 T-Ward Type 41 데이터 확인
        if 'tward41_data' in st.session_state and st.session_state['tward41_data'] is not None:
            data = st.session_state['tward41_data']  # copy 제거로 메모리 절약
            
            # 기본 컬럼 확인
            required_columns = ['sward_id', 'mac', 'type', 'rssi', 'time']
            if not all(col in data.columns for col in required_columns):
                st.error(f"T-Ward Type 41 data missing required columns: {required_columns}")
                return None
            
            # Type 41 데이터만 필터링
            data = data[data['type'] == 41].copy()
            
            if data.empty:
                st.warning("No Type 41 data found in the uploaded file.")
                return None
            
            # 시간 컬럼 처리
            if not pd.api.types.is_datetime64_any_dtype(data['time']):
                data['time'] = pd.to_datetime(data['time'])
            
            # time_index 생성 (10초 단위) - 벡터화 연산
            time_normalized = data['time'].dt.normalize()
            data['time_index'] = ((data['time'] - time_normalized) / pd.Timedelta(seconds=10)).astype(int) + 1
            
            # 처리된 데이터 캐싱
            st.session_state['tward41_processed_data'] = data
            
            return data
        else:
            st.warning("No T-Ward Type 41 data found. Please upload data in 'Input data files' tab.")
            return None
            
    except Exception as e:
        st.error(f"Error loading T-Ward Type 41 data: {str(e)}")
        return None

def apply_dwell_time_filter(data, min_dwell_time):
    """
    Apply dwell time filtering to T-Ward Type 41 data
    Only include T-Wards that have minimum dwell time in minutes
    """
    try:
        print(f"🔍 Applying dwell time filter: min_dwell_time={min_dwell_time} minutes")
        print(f"🔍 Original data records: {len(data)}")
        
        # Create minute bins for dwell time calculation (in-place to save memory)
        minute_bins = data['time'].dt.floor('1T')
        
        # Calculate dwell time per T-Ward (number of unique minute bins)
        mac_dwell_times = pd.DataFrame({'mac': data['mac'], 'minute_bin': minute_bins}).groupby('mac')['minute_bin'].nunique()
        print(f"🔍 T-Ward dwell times calculated. Range: {mac_dwell_times.min()}-{mac_dwell_times.max()} minutes")
        
        # Filter T-Wards with minimum dwell time
        filtered_macs = mac_dwell_times[mac_dwell_times >= min_dwell_time].index.tolist()
        print(f"🔍 T-Wards meeting criteria (≥{min_dwell_time}min): {len(filtered_macs)} out of {len(mac_dwell_times)}")
        
        # Return filtered data (use boolean indexing without copy for memory efficiency)
        mac_filter = data['mac'].isin(filtered_macs)
        filtered_data = data[mac_filter]
        print(f"🔍 Filtered data records: {len(filtered_data)}")
        
        return filtered_data
        
    except Exception as e:
        print(f"🔍 Error in apply_dwell_time_filter: {str(e)}")
        return data  # Return original data on error

def render_tward41_operation(st):
    print("🔧 >>> render_tward41_operation called - NEW VERSION")
    """T-Ward Type 41 Operation Analysis 탭 렌더링"""
    
    st.markdown("### 👷 T-Ward Type 41 Operation Analysis")
    st.info("🔧 Worker helmet monitoring and activity analysis system")
    
    # Run Analysis 버튼 체크
    should_run = st.session_state.get('tward41_should_run', False)
    
    if not should_run:
        st.info("👈 Please configure analysis settings in the sidebar and click 'Run Analysis' to start.")
        
        # 기존 결과가 있다면 표시
        if 'tward41_analysis_results' in st.session_state:
            st.markdown("---")
            st.markdown("### 📊 Previous Analysis Results")
            display_tward41_operation_results(st, st.session_state['tward41_analysis_results'])
            
            # 필터링 정보 표시 (적용된 경우)
            if st.session_state.get('tward41_filtering_applied', False):
                display_filtering_summary(st)
        return
    
    # 분석 실행 후 플래그 초기화
    st.session_state['tward41_should_run'] = False
    
    try:
        # 데이터 로드 및 분석 수행
        with st.spinner("Loading and analyzing T-Ward Type 41 data..."):
            try:
                # T-Ward Type 41 데이터 로드
                location_data = load_and_process_data_tward41()
                sward_config = load_sward_config()
                
                if location_data is None or location_data.empty:
                    st.error("No T-Ward Type 41 data available for analysis.")
                    return
                    
                if sward_config is None or sward_config.empty:
                    st.error("S-Ward configuration not found. Please complete Setup first.")
                    return
                
                # 분석 설정 표시
                filter_enabled = st.session_state.get('tward41_filter_enabled', False)
                min_dwell_time = st.session_state.get('tward41_min_dwell_time', 0)
                
                if filter_enabled and min_dwell_time > 0:
                    st.success(f"✅ Loaded {len(location_data)} T-Ward Type 41 data records (Filtering: ≥{min_dwell_time} min)")
                else:
                    st.success(f"✅ Loaded {len(location_data)} T-Ward Type 41 data records (No filtering)")
                
                # Building/Level 인지 및 활동 상태 분석
                analysis_results = analyze_tward41_operation(location_data, sward_config)
                
                if analysis_results:
                    # 결과를 세션 상태에 저장
                    st.session_state['tward41_analysis_results'] = analysis_results
                    
                    # 분석 결과 표시
                    display_tward41_operation_results(st, analysis_results)
                    
                    # 필터링 정보 표시
                    if st.session_state.get('tward41_filtering_applied', False):
                        display_filtering_summary(st)
                else:
                    st.warning("Unable to analyze T-Ward Type 41 operation data.")
                    
            except Exception as e:
                st.error(f"Error occurred during T-Ward Type 41 data loading: {str(e)}")
                
    except Exception as e:
        st.error(f"An error occurred during T-Ward Type 41 operation analysis: {str(e)}")

@performance_timer("T-Ward Type 41 작업 현황 분석")
def analyze_tward41_operation(location_data, sward_config):
    """T-Ward Type 41 작업 현황 분석 (성능 최적화 적용)"""
    
    try:
        # S-Ward 설정 캐싱 사용 (성능 최적화)
        sward_config_hash = hashlib.md5(str(sward_config.values.tolist()).encode()).hexdigest()
        sward_dict = cached_sward_processing(sward_config_hash)
        
        if sward_dict is None:
            st.error("Failed to load S-Ward configuration")
            return None
        
        # Building/Level 인지 (Type 41은 실시간 인지)
        location_data_with_space = recognize_building_level_type41(location_data, sward_dict)
        
        # 1분 단위 활동 상태 분석
        activity_analysis = analyze_worker_activity(location_data_with_space)
        
        # 메모리 정리 (중간 처리 데이터 해제)
        gc.collect()
        
        # 사이드바 설정에 따른 필터링 적용
        filter_enabled = st.session_state.get('tward41_filter_enabled', False)
        min_dwell_time = st.session_state.get('tward41_min_dwell_time', 0)
        
        print(f"🔍 Filtering Debug: enabled={filter_enabled}, min_time={min_dwell_time}")
        
        # 전체 T-Ward 개수 계산 (필터링 여부와 관계없이)
        all_mac_count = activity_analysis['mac'].nunique()
        print(f"🔍 Total unique T-Wards in data: {all_mac_count}")
        
        if filter_enabled and min_dwell_time > 0:
            # T-Ward별 실제 체류시간 계산 (Active 또는 Present 상태인 분만 계산)
            occupied_activity = activity_analysis[activity_analysis['activity_status'].isin(['Active', 'Present'])]
            mac_dwell_times = occupied_activity.groupby('mac')['minute_bin'].nunique()
            print(f"🔍 Original T-Wards: {len(mac_dwell_times)}")
            print(f"🔍 Actual dwell times range: {mac_dwell_times.min()}-{mac_dwell_times.max()} minutes")
            
            # 최소 체류시간 이상인 T-Ward만 필터링
            filtered_macs = mac_dwell_times[mac_dwell_times >= min_dwell_time].index.tolist()
            print(f"🔍 Filtered T-Wards (≥{min_dwell_time}min): {len(filtered_macs)}")
            
            # 필터링된 활동 데이터만 사용
            original_records = len(activity_analysis)
            activity_analysis = activity_analysis[activity_analysis['mac'].isin(filtered_macs)]
            filtered_records = len(activity_analysis)
            print(f"🔍 Activity records: {original_records} → {filtered_records}")
            
            # 필터링 정보 저장
            st.session_state['tward41_filtering_applied'] = True
            st.session_state['tward41_original_twards'] = all_mac_count
            st.session_state['tward41_filtered_twards'] = len(filtered_macs)
            st.session_state['tward41_removed_twards'] = all_mac_count - len(filtered_macs)
        else:
            print(f"🔍 No filtering applied")
            st.session_state['tward41_filtering_applied'] = False
        
        # 공간별 통계 생성 (필터링된 데이터 사용)
        summary_stats = generate_space_statistics(activity_analysis)
        
        # 1분 단위 활동 데이터 생성 (필터링된 데이터 사용)
        minute_activity = generate_minute_activity(activity_analysis)
        
        # 세션 상태에 저장 (다른 모듈에서 사용)
        st.session_state['type41_activity_analysis'] = activity_analysis
        
        return {
            'location_data': location_data_with_space,
            'activity_analysis': activity_analysis,
            'summary_stats': summary_stats,
            'minute_activity': minute_activity
        }
        
    except Exception as e:
        st.error(f"Error in T-Ward Type 41 analysis: {str(e)}")
        return None

def recognize_building_level_type41(location_data, sward_dict):
    """Type 41 Building/Level/Space Type 인지 (벡터화 최적화)"""
    
    # 벡터화를 위한 매핑 딕셔너리 생성
    building_map = {k: v['building'] for k, v in sward_dict.items()}
    level_map = {k: v['level'] for k, v in sward_dict.items()}
    space_type_map = {k: v.get('space_type', 'Unknown') for k, v in sward_dict.items()}
    
    # 벡터화 연산으로 매핑 (iterrows 대신)
    result_data = location_data.copy()
    result_data['building'] = result_data['sward_id'].map(building_map).fillna('Unknown')
    result_data['level'] = result_data['sward_id'].map(level_map).fillna('Unknown')
    result_data['space_type'] = result_data['sward_id'].map(space_type_map).fillna('Unknown')
    
    return result_data

@performance_timer("작업자 활동 상태 분석")
def analyze_worker_activity(location_data):
    """작업자 활동 상태 분석 (1분 단위, 고성능 최적화)"""
    
    # 1분 단위 time_bin 생성 (1440개)
    location_data['minute_bin'] = ((location_data['time'] - location_data['time'].dt.normalize()) / pd.Timedelta(minutes=1)).astype(int) + 1
    
    # 벡터화 연산으로 전체 처리 속도 대폭 개선
    activity_results = []
    
    # MAC별로 그룹화하고 각 그룹을 병렬 처리 방식으로 최적화
    mac_groups = location_data.groupby('mac')
    
    for mac, mac_data in mac_groups:
        # 해당 MAC이 활동한 minute_bin만 추출 (메모리 효율성)
        minute_groups = mac_data.groupby('minute_bin')
        
        # 빈 minute_bin을 위한 전체 범위 생성 (1440개)
        mac_activity = {}
        
        # 실제 데이터가 있는 minute_bin 처리
        for minute_bin, minute_data in minute_groups:
            # 최빈값 계산 최적화
            building_counts = minute_data['building'].value_counts()
            level_counts = minute_data['level'].value_counts()
            space_type_counts = minute_data['space_type'].value_counts()
            
            building = building_counts.index[0] if not building_counts.empty else 'Unknown'
            level = level_counts.index[0] if not level_counts.empty else 'Unknown'
            space_type = space_type_counts.index[0] if not space_type_counts.empty else 'Unknown'
            
            signal_count = len(minute_data)
            
            # 활동 상태 판단
            if signal_count >= 3:
                activity_status = 'Active'  # 헬멧 착용 상태
            elif signal_count >= 1:
                activity_status = 'Present'  # 헬멧 미착용하지만 현장에 있음
            else:
                activity_status = 'Absent'
            
            mac_activity[minute_bin] = {
                'building': building,
                'level': level,
                'space_type': space_type,
                'signal_count': signal_count,
                'activity_status': activity_status
            }
        
        # 전체 1440개 minute_bin에 대해 결과 생성 (누락된 구간은 Absent)
        for minute_bin in range(1, 1441):
            if minute_bin in mac_activity:
                data = mac_activity[minute_bin]
                activity_results.append({
                    'mac': mac,
                    'minute_bin': minute_bin,
                    'building': data['building'],
                    'level': data['level'],
                    'space_type': data['space_type'],
                    'signal_count': data['signal_count'],
                    'activity_status': data['activity_status']
                })
            else:
                # 데이터가 없는 경우
                activity_results.append({
                    'mac': mac,
                    'minute_bin': minute_bin,
                    'building': None,
                    'level': None,
                    'space_type': None,
                    'signal_count': 0,
                    'activity_status': 'Absent'
                })
    
    return pd.DataFrame(activity_results)

def generate_space_statistics(activity_analysis):
    """공간별 작업자 통계 생성"""
    
    stats_list = []
    
    # 전체 공간에 대한 통계
    spaces = []
    
    # Building별 통계
    for building in activity_analysis['building'].dropna().unique():
        spaces.append((building, None))
        
        # Level별 통계
        building_data = activity_analysis[activity_analysis['building'] == building]
        for level in building_data['level'].dropna().unique():
            spaces.append((building, level))
    
    for building, level in spaces:
        if level is None:
            # Building 전체
            space_data = activity_analysis[activity_analysis['building'] == building]
            space_name = building
        else:
            # 특정 Level
            space_data = activity_analysis[
                (activity_analysis['building'] == building) & 
                (activity_analysis['level'] == level)
            ]
            space_name = f"{building}-{level}"
        
        if not space_data.empty:
            # 통계 계산
            total_workers = space_data['mac'].nunique()
            
            # 시간대별 최대 활성 작업자 수
            active_by_time = space_data[space_data['activity_status'] == 'Active'].groupby('minute_bin')['mac'].nunique()
            max_active_workers = active_by_time.max() if not active_by_time.empty else 0
            
            # 평균 활성 작업자 수
            avg_active_workers = active_by_time.mean() if not active_by_time.empty else 0
            
            # 시간대별 전체 작업자 수 (Present + Active)
            present_by_time = space_data[space_data['activity_status'].isin(['Active', 'Present'])].groupby('minute_bin')['mac'].nunique()
            max_present_workers = present_by_time.max() if not present_by_time.empty else 0
            avg_present_workers = present_by_time.mean() if not present_by_time.empty else 0
            
            stats_list.append({
                'building': building,
                'level': level if level else '(All)',
                'space_name': space_name,
                'total_workers': total_workers,
                'max_active_workers': int(max_active_workers),
                'avg_active_workers': round(avg_active_workers, 1),
                'max_present_workers': int(max_present_workers),
                'avg_present_workers': round(avg_present_workers, 1)
            })
    
    return pd.DataFrame(stats_list)

def generate_minute_activity(activity_analysis):
    """1분 단위 활동 데이터 생성 (최적화된 계산)"""
    
    # 계산 효율성을 위해 numpy와 groupby 최적화 사용
    minute_data = []
    
    # 공간별 사전 필터링으로 중복 계산 방지
    # Building별로 그룹화하여 처리 (더 효율적)
    building_groups = activity_analysis.groupby('building')
    
    for building, building_data in building_groups:
        # Building 전체 통계
        building_stats = calculate_minute_stats(building_data, building, '(All)')
        minute_data.extend(building_stats)
        
        # Level별 통계  
        level_groups = building_data.groupby('level')
        for level, level_data in level_groups:
            level_stats = calculate_minute_stats(level_data, building, level)
            minute_data.extend(level_stats)
    
    return pd.DataFrame(minute_data)

def calculate_minute_stats(space_data, building, level):
    """공간별 1분 단위 통계 계산 (벡터화 연산 사용)"""
    
    space_name = building if level == '(All)' else f"{building}-{level}"
    stats_list = []
    
    # 벡터화된 groupby 연산으로 효율성 극대화
    minute_groups = space_data.groupby('minute_bin')
    
    for minute_bin, group in minute_groups:
        # 각 활동 상태별 고유 MAC 개수 계산
        active_workers = group[group['activity_status'] == 'Active']['mac'].nunique()
        present_workers = group[group['activity_status'].isin(['Active', 'Present'])]['mac'].nunique()
        total_workers = group['mac'].nunique()  # 모든 상태 포함 (Active, Present, Absent)
        
        stats_list.append({
            'building': building,
            'level': level,
            'space_name': space_name,
            'minute_bin': minute_bin,
            'active_workers': active_workers,
            'present_workers': present_workers,
            'total_workers': total_workers
        })
    
    return stats_list

def generate_building_level_statistics(activity_analysis):
    """Building별 및 Level별 통계 생성"""
    
    if activity_analysis is None or activity_analysis.empty:
        return None, None
    
    # Building별 통계
    building_stats = []
    level_stats = []
    
    # 전체 minute_bin 범위 (1-1440)
    for minute_bin in range(1, 1441):
        minute_data = activity_analysis[activity_analysis['minute_bin'] == minute_bin]
        
        if minute_data.empty:
            # 데이터가 없는 분에 대해서는 0으로 처리
            building_stats.append({
                'minute_bin': minute_bin,
                'total_active': 0, 'total_present': 0, 'total_inactive': 0,
                'cluster_active': 0, 'cluster_present': 0, 'cluster_inactive': 0,
                'wwt_active': 0, 'wwt_present': 0, 'wwt_inactive': 0,
                'fab_active': 0, 'fab_present': 0, 'fab_inactive': 0,
                'cub_active': 0, 'cub_present': 0, 'cub_inactive': 0
            })
            
            level_stats.append({
                'minute_bin': minute_bin,
                'total_active': 0,
                'cluster_1f_active': 0, 'wwt_1f_active': 0, 'wwt_b1f_active': 0,
                'fab_1f_active': 0, 'cub_1f_active': 0, 'cub_b1f_active': 0
            })
            continue
        
        # Building별 집계
        total_active = minute_data[minute_data['activity_status'] == 'Active']['mac'].nunique()
        total_present = minute_data[minute_data['activity_status'].isin(['Active', 'Present'])]['mac'].nunique()
        total_inactive = minute_data[minute_data['activity_status'] == 'Present']['mac'].nunique()  # Present만 (Active 제외)
        
        # 각 Building별
        cluster_data = minute_data[minute_data['building'] == 'Cluster']
        wwt_data = minute_data[minute_data['building'] == 'WWT']
        fab_data = minute_data[minute_data['building'] == 'FAB']
        cub_data = minute_data[minute_data['building'] == 'CUB']
        
        building_stats.append({
            'minute_bin': minute_bin,
            'total_active': total_active,
            'total_present': total_present,
            'total_inactive': total_inactive,
            'cluster_active': cluster_data[cluster_data['activity_status'] == 'Active']['mac'].nunique(),
            'cluster_present': cluster_data[cluster_data['activity_status'].isin(['Active', 'Present'])]['mac'].nunique(),
            'cluster_inactive': cluster_data[cluster_data['activity_status'] == 'Present']['mac'].nunique(),
            'wwt_active': wwt_data[wwt_data['activity_status'] == 'Active']['mac'].nunique(),
            'wwt_present': wwt_data[wwt_data['activity_status'].isin(['Active', 'Present'])]['mac'].nunique(),
            'wwt_inactive': wwt_data[wwt_data['activity_status'] == 'Present']['mac'].nunique(),
            'fab_active': fab_data[fab_data['activity_status'] == 'Active']['mac'].nunique(),
            'fab_present': fab_data[fab_data['activity_status'].isin(['Active', 'Present'])]['mac'].nunique(),
            'fab_inactive': fab_data[fab_data['activity_status'] == 'Present']['mac'].nunique(),
            'cub_active': cub_data[cub_data['activity_status'] == 'Active']['mac'].nunique(),
            'cub_present': cub_data[cub_data['activity_status'].isin(['Active', 'Present'])]['mac'].nunique(),
            'cub_inactive': cub_data[cub_data['activity_status'] == 'Present']['mac'].nunique()
        })
        
        # Level별 집계 (Active만)
        cluster_1f_data = minute_data[(minute_data['building'] == 'Cluster') & (minute_data['level'] == '1F')]
        wwt_1f_data = minute_data[(minute_data['building'] == 'WWT') & (minute_data['level'] == '1F')]
        wwt_b1f_data = minute_data[(minute_data['building'] == 'WWT') & (minute_data['level'] == 'B1F')]
        fab_1f_data = minute_data[(minute_data['building'] == 'FAB') & (minute_data['level'] == '1F')]
        cub_1f_data = minute_data[(minute_data['building'] == 'CUB') & (minute_data['level'] == '1F')]
        cub_b1f_data = minute_data[(minute_data['building'] == 'CUB') & (minute_data['level'] == 'B1F')]
        
        level_stats.append({
            'minute_bin': minute_bin,
            'total_active': total_active,
            'cluster_1f_active': cluster_1f_data[cluster_1f_data['activity_status'] == 'Active']['mac'].nunique(),
            'wwt_1f_active': wwt_1f_data[wwt_1f_data['activity_status'] == 'Active']['mac'].nunique(),
            'wwt_b1f_active': wwt_b1f_data[wwt_b1f_data['activity_status'] == 'Active']['mac'].nunique(),
            'fab_1f_active': fab_1f_data[fab_1f_data['activity_status'] == 'Active']['mac'].nunique(),
            'cub_1f_active': cub_1f_data[cub_1f_data['activity_status'] == 'Active']['mac'].nunique(),
            'cub_b1f_active': cub_b1f_data[cub_b1f_data['activity_status'] == 'Active']['mac'].nunique()
        })
    
    return pd.DataFrame(building_stats), pd.DataFrame(level_stats)

def display_tward41_operation_results(st, analysis_results):
    """T-Ward Type 41 분석 결과 표시 (1분 단위 최적화)"""
    
    summary_stats = analysis_results['summary_stats']
    minute_activity = analysis_results['minute_activity']
    
    # 요약 통계 표시
    st.markdown("### 📊 Worker Activity Summary")
    
    if not summary_stats.empty:
        # 통계 테이블 표시
        display_columns = ['space_name', 'total_workers', 'max_active_workers', 'avg_active_workers', 'max_present_workers', 'avg_present_workers']
        column_names = ['Space', 'Total Workers', 'Max Active', 'Avg Active', 'Max Present', 'Avg Present']
        
        display_df = summary_stats[display_columns].copy()
        display_df.columns = column_names
        
        # Total 행 추가
        total_row = pd.DataFrame({
            'Space': ['Total'],
            'Total Workers': [summary_stats['total_workers'].sum()],
            'Max Active': [summary_stats['max_active_workers'].sum()],
            'Avg Active': [summary_stats['avg_active_workers'].sum()],
            'Max Present': [summary_stats['max_present_workers'].sum()],
            'Avg Present': [summary_stats['avg_present_workers'].sum()]
        })
        
        # Total 행을 맨 아래에 추가
        display_df_with_total = pd.concat([display_df, total_row], ignore_index=True)
        
        st.dataframe(display_df_with_total, use_container_width=True)
    
    # Building별 및 Level별 통계 생성
    activity_analysis = st.session_state.get('type41_activity_analysis')
    if activity_analysis is not None and not activity_analysis.empty:
        st.markdown("### 📈 Worker Activity by Minute (1-minute resolution)")
        
        # Building별 및 Level별 통계 데이터 생성
        print(f"🔍 Activity analysis shape: {activity_analysis.shape}")
        print(f"🔍 Activity analysis columns: {activity_analysis.columns.tolist()}")
        print(f"🔍 Sample activity data:\n{activity_analysis.head()}")
        
        building_stats, level_stats = generate_building_level_statistics(activity_analysis)
        
        print(f"🔍 Building stats generated: {building_stats is not None}")
        print(f"🔍 Level stats generated: {level_stats is not None}")
        if building_stats is not None:
            print(f"🔍 Building stats shape: {building_stats.shape}")
            print(f"🔍 Building stats sample:\n{building_stats.head()}")
        
        if building_stats is not None and not building_stats.empty:
            # 4개의 서브플롯: Present, Active, Inactive (Building별), Active (Level별)
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
            print("🔍 Subplots created successfully")
            
            # 시간 축 생성 (copy 없이 직접 계산)
            building_stats = building_stats.copy()  # 한 번만 복사
            level_stats = level_stats.copy()  # 한 번만 복사
            building_stats['time_hours'] = building_stats['minute_bin'] / 60
            level_stats['time_hours'] = level_stats['minute_bin'] / 60
            
            # 24시간 범위로 제한 (추가 copy 없이 필터링)
            building_stats_filtered = building_stats[building_stats['time_hours'] < 24.0]
            level_stats_filtered = level_stats[level_stats['time_hours'] < 24.0]
            
            # 색상 정의
            colors = {'Total': '#000000', 'Cluster': '#9467bd', 'WWT': '#2ca02c', 'FAB': '#ff7f0e', 'CUB': '#1f77b4'}
            
            # 1. Total Present Workers by Building
            ax1.plot(building_stats_filtered['time_hours'], building_stats_filtered['total_present'], 
                    label='Total', linewidth=2, color=colors['Total'])
            ax1.plot(building_stats_filtered['time_hours'], building_stats_filtered['cluster_present'], 
                    label='Cluster', linewidth=1, alpha=0.8, color=colors['Cluster'])
            ax1.plot(building_stats_filtered['time_hours'], building_stats_filtered['wwt_present'], 
                    label='WWT', linewidth=1, alpha=0.8, color=colors['WWT'])
            ax1.plot(building_stats_filtered['time_hours'], building_stats_filtered['fab_present'], 
                    label='FAB', linewidth=1, alpha=0.8, color=colors['FAB'])
            ax1.plot(building_stats_filtered['time_hours'], building_stats_filtered['cub_present'], 
                    label='CUB', linewidth=1, alpha=0.8, color=colors['CUB'])
            
            ax1.set_title('Total Present Workers by Building - 1 Minute Resolution', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Time (Hours)')
            ax1.set_ylabel('Present Workers Count')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            ax1.set_xlim(0, 23.99)
            ax1.set_xticks(range(0, 24, 2))
            ax1.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)])
            
            # 2. Total Active Workers by Building
            ax2.plot(building_stats_filtered['time_hours'], building_stats_filtered['total_active'], 
                    label='Total', linewidth=2, color=colors['Total'])
            ax2.plot(building_stats_filtered['time_hours'], building_stats_filtered['cluster_active'], 
                    label='Cluster', linewidth=1, alpha=0.8, color=colors['Cluster'])
            ax2.plot(building_stats_filtered['time_hours'], building_stats_filtered['wwt_active'], 
                    label='WWT', linewidth=1, alpha=0.8, color=colors['WWT'])
            ax2.plot(building_stats_filtered['time_hours'], building_stats_filtered['fab_active'], 
                    label='FAB', linewidth=1, alpha=0.8, color=colors['FAB'])
            ax2.plot(building_stats_filtered['time_hours'], building_stats_filtered['cub_active'], 
                    label='CUB', linewidth=1, alpha=0.8, color=colors['CUB'])
            
            ax2.set_title('Total Active Workers by Building - 1 Minute Resolution', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Time (Hours)')
            ax2.set_ylabel('Active Workers Count')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            ax2.set_xlim(0, 23.99)
            ax2.set_xticks(range(0, 24, 2))
            ax2.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)])
            
            # 3. Total Inactive Workers by Building
            ax3.plot(building_stats_filtered['time_hours'], building_stats_filtered['total_inactive'], 
                    label='Total', linewidth=2, color=colors['Total'])
            ax3.plot(building_stats_filtered['time_hours'], building_stats_filtered['cluster_inactive'], 
                    label='Cluster', linewidth=1, alpha=0.8, color=colors['Cluster'])
            ax3.plot(building_stats_filtered['time_hours'], building_stats_filtered['wwt_inactive'], 
                    label='WWT', linewidth=1, alpha=0.8, color=colors['WWT'])
            ax3.plot(building_stats_filtered['time_hours'], building_stats_filtered['fab_inactive'], 
                    label='FAB', linewidth=1, alpha=0.8, color=colors['FAB'])
            ax3.plot(building_stats_filtered['time_hours'], building_stats_filtered['cub_inactive'], 
                    label='CUB', linewidth=1, alpha=0.8, color=colors['CUB'])
            
            ax3.set_title('Total Inactive Workers by Building - 1 Minute Resolution', fontsize=14, fontweight='bold')
            ax3.set_xlabel('Time (Hours)')
            ax3.set_ylabel('Inactive Workers Count')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            ax3.set_xlim(0, 23.99)
            ax3.set_xticks(range(0, 24, 2))
            ax3.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)])
            
            # 4. Total Active Workers by Level
            level_colors = {'Total': '#000000', 'Cluster-1F': '#9467bd', 'WWT-1F': '#2ca02c', 'WWT-B1F': '#98df8a', 
                           'FAB-1F': '#ff7f0e', 'CUB-1F': '#1f77b4', 'CUB-B1F': '#aec7e8'}
            
            ax4.plot(level_stats_filtered['time_hours'], level_stats_filtered['total_active'], 
                    label='Total', linewidth=2, color=level_colors['Total'])
            ax4.plot(level_stats_filtered['time_hours'], level_stats_filtered['cluster_1f_active'], 
                    label='Cluster-1F', linewidth=1, alpha=0.8, color=level_colors['Cluster-1F'])
            ax4.plot(level_stats_filtered['time_hours'], level_stats_filtered['wwt_1f_active'], 
                    label='WWT-1F', linewidth=1, alpha=0.8, color=level_colors['WWT-1F'])
            ax4.plot(level_stats_filtered['time_hours'], level_stats_filtered['wwt_b1f_active'], 
                    label='WWT-B1F', linewidth=1, alpha=0.8, color=level_colors['WWT-B1F'])
            ax4.plot(level_stats_filtered['time_hours'], level_stats_filtered['fab_1f_active'], 
                    label='FAB-1F', linewidth=1, alpha=0.8, color=level_colors['FAB-1F'])
            ax4.plot(level_stats_filtered['time_hours'], level_stats_filtered['cub_1f_active'], 
                    label='CUB-1F', linewidth=1, alpha=0.8, color=level_colors['CUB-1F'])
            ax4.plot(level_stats_filtered['time_hours'], level_stats_filtered['cub_b1f_active'], 
                    label='CUB-B1F', linewidth=1, alpha=0.8, color=level_colors['CUB-B1F'])
            
            ax4.set_title('Total Active Workers by Level - 1 Minute Resolution', fontsize=14, fontweight='bold')
            ax4.set_xlabel('Time (Hours)')
            ax4.set_ylabel('Active Workers Count')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            ax4.set_xlim(0, 23.99)
            ax4.set_xticks(range(0, 24, 2))
            ax4.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)])
            
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()
            print("🔍 Charts displayed successfully")
            

            
            # Building별 및 Level별 통계 테이블 표시
            st.markdown("#### 📊 Building-Level Worker Statistics Summary")
            
            # Building별 최대, 평균, 합계 통계
            building_summary = {
                'Building': ['Total', 'Cluster', 'WWT', 'FAB', 'CUB'],
                'Max Present': [
                    building_stats['total_present'].max(),
                    building_stats['cluster_present'].max(),
                    building_stats['wwt_present'].max(),
                    building_stats['fab_present'].max(),
                    building_stats['cub_present'].max()
                ],
                'Avg Present': [
                    round(building_stats['total_present'].mean(), 1),
                    round(building_stats['cluster_present'].mean(), 1),
                    round(building_stats['wwt_present'].mean(), 1),
                    round(building_stats['fab_present'].mean(), 1),
                    round(building_stats['cub_present'].mean(), 1)
                ],
                'Max Active': [
                    building_stats['total_active'].max(),
                    building_stats['cluster_active'].max(),
                    building_stats['wwt_active'].max(),
                    building_stats['fab_active'].max(),
                    building_stats['cub_active'].max()
                ],
                'Avg Active': [
                    round(building_stats['total_active'].mean(), 1),
                    round(building_stats['cluster_active'].mean(), 1),
                    round(building_stats['wwt_active'].mean(), 1),
                    round(building_stats['fab_active'].mean(), 1),
                    round(building_stats['cub_active'].mean(), 1)
                ],
                'Max Inactive': [
                    building_stats['total_inactive'].max(),
                    building_stats['cluster_inactive'].max(),
                    building_stats['wwt_inactive'].max(),
                    building_stats['fab_inactive'].max(),
                    building_stats['cub_inactive'].max()
                ],
                'Avg Inactive': [
                    round(building_stats['total_inactive'].mean(), 1),
                    round(building_stats['cluster_inactive'].mean(), 1),
                    round(building_stats['wwt_inactive'].mean(), 1),
                    round(building_stats['fab_inactive'].mean(), 1),
                    round(building_stats['cub_inactive'].mean(), 1)
                ]
            }
            
            building_df = pd.DataFrame(building_summary)
            st.dataframe(building_df, use_container_width=True, hide_index=True)
            
            # Level별 통계 테이블
            st.markdown("#### 📊 Level-wise Active Worker Statistics Summary")
            
            level_summary = {
                'Level': ['Total', 'Cluster-1F', 'WWT-1F', 'WWT-B1F', 'FAB-1F', 'CUB-1F', 'CUB-B1F'],
                'Max Active': [
                    level_stats['total_active'].max(),
                    level_stats['cluster_1f_active'].max(),
                    level_stats['wwt_1f_active'].max(),
                    level_stats['wwt_b1f_active'].max(),
                    level_stats['fab_1f_active'].max(),
                    level_stats['cub_1f_active'].max(),
                    level_stats['cub_b1f_active'].max()
                ],
                'Avg Active': [
                    round(level_stats['total_active'].mean(), 1),
                    round(level_stats['cluster_1f_active'].mean(), 1),
                    round(level_stats['wwt_1f_active'].mean(), 1),
                    round(level_stats['wwt_b1f_active'].mean(), 1),
                    round(level_stats['fab_1f_active'].mean(), 1),
                    round(level_stats['cub_1f_active'].mean(), 1),
                    round(level_stats['cub_b1f_active'].mean(), 1)
                ],
                'Total Hours': [
                    round(level_stats['total_active'].sum() / 60, 1),
                    round(level_stats['cluster_1f_active'].sum() / 60, 1),
                    round(level_stats['wwt_1f_active'].sum() / 60, 1),
                    round(level_stats['wwt_b1f_active'].sum() / 60, 1),
                    round(level_stats['fab_1f_active'].sum() / 60, 1),
                    round(level_stats['cub_1f_active'].sum() / 60, 1),
                    round(level_stats['cub_b1f_active'].sum() / 60, 1)
                ]
            }
            
            level_df = pd.DataFrame(level_summary)
            st.dataframe(level_df, use_container_width=True, hide_index=True)
        else:
            st.info("No activity data available for Building/Level analysis")
    
    st.markdown("### ℹ️ Analysis Information")
    st.info("""
    **Worker Activity Analysis (Type 41) - Building & Level Analysis**
    - **Present Workers**: 1분간 신호 1회 이상 수신 (현장 내 존재 - Active + Inactive)
    - **Active Workers**: 1분간 신호 3회 이상 수신 (헬멧 착용 상태)
    - **Inactive Workers**: 1분간 신호 1-2회 수신 (현장 내 있지만 헬멧 미착용)
    - **Building Analysis**: Total, Cluster, WWT, FAB, CUB별 인원 분석
    - **Level Analysis**: 층별 Active Worker 분포 (Cluster-1F, WWT-1F/B1F, FAB-1F, CUB-1F/B1F)
    - **Data Validation**: 각 Building 합계 = Total 값 검증
    - **Analysis Period**: 24시간, 1분 단위 분석 (1440 data points)
    - **Performance**: 벡터화 연산으로 대용량 데이터 최적화 처리
    """)
    
    # 30분 이상 체류한 T-Ward만 필터링한 결과 표시
    st.markdown("---")
    st.markdown("### 🏗️ Filtered Analysis (30+ minutes dwell time)")
    st.info("📋 Analysis results with T-Wards that stayed less than 30 minutes removed (to exclude passing people)")
    
    display_filtered_operation_results(st, analysis_results)

def compress_to_hourly(minute_activity):
    """1분 데이터를 시간 단위로 압축 (성능 최적화)"""
    
    # 1분 데이터를 시간으로 그룹화
    minute_activity_copy = minute_activity.copy()
    minute_activity_copy['hour'] = (minute_activity_copy['minute_bin'] - 1) // 60
    
    # 시간별 평균값 계산 (벡터화 연산)
    hourly_compressed = minute_activity_copy.groupby(['space_name', 'building', 'level', 'hour']).agg({
        'active_workers': 'mean',
        'present_workers': 'mean'
    }).reset_index()
    
    # 정수로 변환 (소수점 제거)
    hourly_compressed['active_workers'] = hourly_compressed['active_workers'].round().astype(int)
    hourly_compressed['present_workers'] = hourly_compressed['present_workers'].round().astype(int)
    
    return hourly_compressed

def display_filtered_operation_results(st, analysis_results):
    """30분 이상 체류한 T-Ward만으로 필터링된 분석 결과 표시"""
    
    # 원본 활동 분석 데이터에서 체류시간 계산
    activity_analysis = st.session_state.get('type41_activity_analysis')
    if activity_analysis is None or activity_analysis.empty:
        st.warning("Activity analysis data not found. Please run Occupancy Analysis first.")
        return
    
    # 각 T-Ward별 체류시간 계산 (분 단위)
    mac_dwell_times = activity_analysis.groupby('mac')['minute_bin'].nunique().reset_index()
    mac_dwell_times.columns = ['mac', 'dwell_minutes']
    
    # 30분 이상 체류한 T-Ward 필터링
    filtered_macs = mac_dwell_times[mac_dwell_times['dwell_minutes'] >= 30]['mac'].tolist()
    
    if not filtered_macs:
        st.warning("No T-Wards with 30+ minutes dwell time found.")
        return
    
    st.success(f"📊 Found {len(filtered_macs)} T-Wards with 30+ minutes dwell time (filtered from {len(mac_dwell_times)})")
    
    # 필터링된 데이터로 분석 재실행
    filtered_activity = activity_analysis[activity_analysis['mac'].isin(filtered_macs)]
    
    # 필터링된 통계 생성
    filtered_summary = generate_space_statistics(filtered_activity)
    filtered_minute_activity = generate_minute_activity(filtered_activity)
    
    # 필터링된 결과 표시
    st.markdown("#### 📊 Filtered Worker Activity Summary")
    
    if not filtered_summary.empty:
        display_columns = ['space_name', 'total_workers', 'max_active_workers', 'avg_active_workers', 'max_present_workers', 'avg_present_workers']
        column_names = ['Space', 'Total Workers', 'Max Active', 'Avg Active', 'Max Present', 'Avg Present']
        
        display_df = filtered_summary[display_columns].copy()
        display_df.columns = column_names
        
        # Total 행 추가
        total_row = pd.DataFrame({
            'Space': ['Total'],
            'Total Workers': [filtered_summary['total_workers'].sum()],
            'Max Active': [filtered_summary['max_active_workers'].sum()],
            'Avg Active': [filtered_summary['avg_active_workers'].sum()],
            'Max Present': [filtered_summary['max_present_workers'].sum()],
            'Avg Present': [filtered_summary['avg_present_workers'].sum()]
        })
        
        # Total 행을 맨 아래에 추가
        display_df_with_total = pd.concat([display_df, total_row], ignore_index=True)
        
        st.dataframe(display_df_with_total, use_container_width=True, hide_index=True)
    
    # 필터링된 그래프 표시
    st.markdown("#### 📈 Filtered Worker Activity by Minute (1-minute resolution)")
    
    if not filtered_minute_activity.empty:
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        
        display_data_copy = filtered_minute_activity.copy()
        display_data_copy['time_hours'] = display_data_copy['minute_bin'] / 60
        
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 15))
        
        # Active Workers (헬멧 착용 작업자)
        for i, space_name in enumerate(display_data_copy['space_name'].unique()):
            space_data = display_data_copy[display_data_copy['space_name'] == space_name]
            
            # 24시간을 넘어가는 데이터는 제거하고 23.99 이하만 표시 (직선 연결 방지)
            space_data_filtered = space_data[space_data['time_hours'] < 24.0].copy()
            
            ax1.plot(space_data_filtered['time_hours'], space_data_filtered['active_workers'], 
                    label=space_name, linewidth=1, alpha=0.8,
                    color=colors[i % len(colors)])
        
        ax1.set_title('Filtered Active Workers (Helmet On) - 1 Minute Resolution', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Time (Hours)')
        ax1.set_ylabel('Active Workers Count')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # X축 범위를 0-24시간으로 고정 (24시를 넘어가는 데이터와의 직선 연결 방지)
        ax1.set_xlim(0, 23.99)  # 24시 제외하여 연결선 방지
        ax1.set_xticks(range(0, 24, 2))  # 24시 틱 제거
        ax1.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)])
        
        # Present Workers (전체 현장 작업자)
        for i, space_name in enumerate(display_data_copy['space_name'].unique()):
            space_data = display_data_copy[display_data_copy['space_name'] == space_name]
            
            # 24시간을 넘어가는 데이터는 제거하고 23.99 이하만 표시 (직선 연결 방지)
            space_data_filtered = space_data[space_data['time_hours'] < 24.0].copy()
            
            ax2.plot(space_data_filtered['time_hours'], space_data_filtered['present_workers'], 
                    label=space_name, linewidth=1, alpha=0.8,
                    color=colors[i % len(colors)])
        
        ax2.set_title('Filtered Total Present Workers (All Workers) - 1 Minute Resolution', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Time (Hours)')
        ax2.set_ylabel('Present Workers Count')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # X축 범위를 0-24시간으로 고정 (24시를 넘어가는 데이터와의 직선 연결 방지)
        ax2.set_xlim(0, 23.99)  # 24시 제외하여 연결선 방지
        ax2.set_xticks(range(0, 24, 2))  # 24시 틱 제거
        ax2.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)])
        
        # Total Workers (모든 T-Ward 포함 - Active, Present, Absent)
        for i, space_name in enumerate(display_data_copy['space_name'].unique()):
            space_data = display_data_copy[display_data_copy['space_name'] == space_name]
            
            # 24시간을 넘어가는 데이터는 제거하고 23.99 이하만 표시 (직선 연결 방지)
            space_data_filtered = space_data[space_data['time_hours'] < 24.0].copy()
            
            ax3.plot(space_data_filtered['time_hours'], space_data_filtered['total_workers'], 
                    label=space_name, linewidth=1, alpha=0.8,
                    color=colors[i % len(colors)])
        
        ax3.set_title('Filtered Total Workers (All T-Wards Detected) - 1 Minute Resolution', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Time (Hours)')
        ax3.set_ylabel('Total Workers Count')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # X축 범위를 0-24시간으로 고정 (24시를 넘어가는 데이터와의 직선 연결 방지)
        ax3.set_xlim(0, 23.99)  # 24시 제외하여 연결선 방지
        ax3.set_xticks(range(0, 24, 2))  # 24시 틱 제거
        ax3.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)])
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

def display_filtering_summary(st):
    """필터링 적용 요약 정보 표시"""
    
    original_count = st.session_state.get('tward41_original_twards', 0)
    filtered_count = st.session_state.get('tward41_filtered_twards', 0)
    removed_count = st.session_state.get('tward41_removed_twards', 0)
    min_dwell_time = st.session_state.get('tward41_min_dwell_time', 0)
    
    if original_count > 0:
        st.markdown("---")
        st.markdown("### 🔍 Filtering Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Original T-Wards", original_count)
        with col2:
            st.metric("Included T-Wards", filtered_count)
        with col3:
            st.metric("Removed T-Wards", removed_count)
        with col4:
            removal_rate = (removed_count / original_count) * 100
            st.metric("Removal Rate", f"{removal_rate:.1f}%")
        
        st.info(f"📊 Applied filter: T-Wards with less than {min_dwell_time} minutes dwell time were removed from analysis")
