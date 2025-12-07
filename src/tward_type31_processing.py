def timebin_operation_rate_indexed(df, sward_config):
    # time_bin을 index(1,2,3...)로 변환, 각 인덱스별 Operation Rate(%) 배열 반환
    df = df.merge(sward_config[['sward_id', 'building', 'level']], on='sward_id', how='left')
    if 'time_bin' not in df.columns:
        # 0시 0분 0초 기준 10초 단위 time_index 생성
        df['time_index'] = ((df['time'] - df['time'].dt.normalize()) / pd.Timedelta(seconds=10)).astype(int) + 1
        df['time_bin'] = ((df['time_index'] - 1) // 60) + 1  # 10분 bin index (1~144)
    # 각 time_bin, mac별로 가장 큰 RSSI의 S-Ward의 building/level로 인식
    idx = df.groupby(['time_bin', 'mac'])['rssi'].idxmax()
    df_max = df.loc[idx].copy()
    # 각 time_bin, building, level별로 고유 mac 개수(가동 장비 수, 스냅샷)
    active_counts = df_max.groupby(['time_bin', 'building', 'level'])['mac'].nunique().reset_index(name='Active T-Ward Count')
    # 전체 장비 수(24시간 내 한 번이라도 해당 공간에서 수신된 mac)
    total_counts = df_max.groupby(['building', 'level'])['mac'].nunique().reset_index(name='Total T-Ward Count')
    # time_bin별 operation rate(%) (누적X, 스냅샷)
    # Merge active_counts and total_counts for each (building, level, time_bin)
    op_rate_df = active_counts.merge(total_counts, on=['building', 'level'], how='left')
    op_rate_df['Operation Rate (%)'] = (op_rate_df['Active T-Ward Count'] / op_rate_df['Total T-Ward Count'] * 100).round(1)
    op_rate_df['Operation Rate (%)'] = op_rate_df['Operation Rate (%)'].fillna(0.0)
    op_rate_df['Active T-Ward Count'] = op_rate_df['Active T-Ward Count'].fillna(0).astype(int)
    op_rate_df['Total T-Ward Count'] = op_rate_df['Total T-Ward Count'].fillna(0).astype(int)
    # time_bin index별로 배열화 (누락 구간은 0)
    result = {}
    # level별
    for (bldg, lvl), sub in op_rate_df.groupby(['building', 'level']):
        arr = [0.0] * 144
        for i in range(1, 145):
            val = sub.loc[sub['time_bin'] == i, 'Operation Rate (%)']
            arr[i-1] = float(val.values[0]) if not val.empty else 0.0
        result[(bldg, lvl)] = arr
    # building 전체(합산) Operation Rate(%)
    for bldg in op_rate_df['building'].unique():
        arr = [0.0] * 144
        for i in range(1, 145):
            sub = op_rate_df[(op_rate_df['building'] == bldg) & (op_rate_df['time_bin'] == i)]
            active = sub['Active T-Ward Count'].sum()
            total = sub['Total T-Ward Count'].sum()
            rate = (active / total * 100) if total > 0 else 0.0
            arr[i-1] = round(rate, 1)
        result[(bldg, '(All)')] = arr
    # building 전체(합산) Active T-Ward Count (가동 장비 개수)
    count_result = {}
    for (bldg, lvl), sub in op_rate_df.groupby(['building', 'level']):
        arr = [0] * 144
        for i in range(1, 145):
            val = sub.loc[sub['time_bin'] == i, 'Active T-Ward Count']
            arr[i-1] = int(val.values[0]) if not val.empty else 0
        count_result[(bldg, lvl)] = arr
    for bldg in op_rate_df['building'].unique():
        arr = [0] * 144
        for i in range(1, 145):
            sub = op_rate_df[(op_rate_df['building'] == bldg) & (op_rate_df['time_bin'] == i)]
            active = sub['Active T-Ward Count'].sum()
            arr[i-1] = int(active)
        count_result[(bldg, '(All)')] = arr
    return result, count_result, op_rate_df
# 10분 단위로 building/level 인식(최대 RSSI 기준) 및 operation rate(%) 계산
def timebin_operation_rate(df, sward_config):
    # df: 컬럼명 [sward_id, mac, type, rssi, time, ...]
    # sward_config: sward_id, building, level, ...
    df = df.merge(sward_config[['sward_id', 'building', 'level']], on='sward_id', how='left')
    if 'time_bin' not in df.columns:
        df['time_bin'] = df['time'].dt.floor('10min')
    # 각 time_bin, mac별로 가장 큰 RSSI의 S-Ward의 building/level로 인식
    idx = df.groupby(['time_bin', 'mac'])['rssi'].idxmax()
    df_max = df.loc[idx].copy()
    # 각 time_bin, building, level별로 고유 mac 개수(가동 장비 수, 스냅샷)
    active_counts = df_max.groupby(['time_bin', 'building', 'level'])['mac'].nunique().reset_index(name='Active T-Ward Count')
    # 전체 장비 수(24시간 내 한 번이라도 해당 공간에서 수신된 mac)
    total_counts = df_max.groupby(['building', 'level'])['mac'].nunique().reset_index(name='Total T-Ward Count')
    # time_bin별 operation rate(%) (누적X, 스냅샷)
    op_rate_df = active_counts.merge(total_counts, on=['building', 'level'], how='left')
    op_rate_df['Operation Rate (%)'] = (op_rate_df['Active T-Ward Count'] / op_rate_df['Total T-Ward Count'] * 100).round(1)
    return op_rate_df
def hierarchical_operation_stats(df, sward_config):
    # S-Ward의 building, level 정보 merge (공간 인지)
    df = df.merge(sward_config[['sward_id', 'building', 'level']], on='sward_id', how='left')

    # time_bin 컬럼이 없으면 생성 (10분 bin)
    if 'time_bin' not in df.columns:
        df['time_bin'] = df['time'].dt.floor('10min')

    # --- 통계: 공간별 전체 장비 수, 하루 중 한 번이라도 가동된 장비 수, 가동률(%) ---
    # 전체 장비 수 (해당 공간에서 단 1회라도 수신된 mac)
    total_stats = df.groupby(['building', 'level', 'mac']).size().reset_index(name='count')
    total_stats = total_stats.groupby(['building', 'level'])['mac'].nunique().reset_index(name='Total T-Ward Count')

    # 하루 중 한 번이라도 가동된 장비(10분 bin 중 2회 이상 수신된 bin이 1개라도 있으면 가동)
    op = df.groupby(['building', 'level', 'mac', 'time_bin']).size().reset_index(name='count')
    op['active'] = op['count'] >= 2
    op_any_active = op.groupby(['building', 'level', 'mac'])['active'].any().reset_index()
    op_any_active = op_any_active[op_any_active['active']]
    active_stats = op_any_active.groupby(['building', 'level'])['mac'].nunique().reset_index(name='Active T-Ward (Any)')

    # 가동률(%)
    merged = total_stats.merge(active_stats, on=['building', 'level'], how='left').fillna(0)
    merged['Active T-Ward (Any)'] = merged['Active T-Ward (Any)'].astype(int)
    merged['Operation Rate (%)'] = (merged['Active T-Ward (Any)'] / merged['Total T-Ward Count'] * 100).round(1)

    # building 단위 집계
    b_total = merged.groupby('building')['Total T-Ward Count'].sum().reset_index()
    b_active = merged.groupby('building')['Active T-Ward (Any)'].sum().reset_index()
    b_merged = b_total.merge(b_active, on='building')
    b_merged['Operation Rate (%)'] = (b_merged['Active T-Ward (Any)'] / b_merged['Total T-Ward Count'] * 100).round(1)

    return {
        'level': active_stats,
        'level_total': total_stats,
        'building': None,
        'building_total': None,
        'site': None,
        'site_total': None,
        'operation_summary': merged,
        'operation_summary_building': b_merged
    }
    # 공간별(빌딩, 레벨, 전체) 장비 가동률/개수/그래프용 데이터 생성
    df = df.copy()
    df = df.merge(sward_config[['sward_id', 'building', 'level']], on='sward_id', how='left')
    df['time_bin'] = df['time'].dt.floor('10min')
    # 10분 bin별, mac별 2회 이상 수신시 active
    op = df.groupby(['building', 'level', 'mac', 'time_bin']).size().reset_index(name='count')
    op['active'] = op['count'] >= 2
    # 각 time_bin별로 active==True인 mac만 카운트(누적X, 스냅샷)
    active_stats = op[op['active']].groupby(['building', 'level', 'time_bin'])['mac'].nunique().reset_index(name='Active T-Ward Count')
    # 공간별 전체 mac 개수(24시간 내 단 1회라도 수신된 mac)
    present = df.groupby(['building', 'level', 'mac']).size().reset_index(name='count')
    present['present'] = True
    total_stats = present.groupby(['building', 'level'])['mac'].nunique().reset_index(name='Total T-Ward Count')
    # 빌딩 전체(빌딩 단위) 집계
    building_active = active_stats.groupby(['building', 'time_bin'])['Active T-Ward Count'].sum().reset_index()
    building_total = total_stats.groupby(['building'])['Total T-Ward Count'].sum().reset_index()
    # 전체(현장 전체) 집계
    site_active = active_stats.groupby(['time_bin'])['Active T-Ward Count'].sum().reset_index()
    site_total = pd.DataFrame({'Total T-Ward Count': [total_stats['Total T-Ward Count'].sum()]})
    return {
        'level': active_stats,
        'level_total': total_stats,
        'building': building_active,
        'building_total': building_total,
        'site': site_active,
        'site_total': site_total
    }

# --- 위치 추정 알고리즘 스텁 (구현 시작) ---
def estimate_tward_positions(df, sward_config, alpha=0.95):
    # df: type31 데이터(컬럼: sward_id, mac, type, rssi, time, ...)
    # sward_config: sward_id, x, y, building, level, ...
    # return: mac별, time_bin별 추정 위치(x, y), 가동상태(active)
    # 1. time_bin별, mac별로 수신 S-Ward 집합 추출
    # 2. S-Ward 개수에 따라 위치 추정 방식 분기
    # 3. smoothing 적용
    # (구현은 이후 단계에서 진행)
    return None
def load_sward_config():
    # Setup에서 저장한 S-Ward config 파일 경로 고정
    config_path = './Datafile/sward_configuration.csv'
    return pd.read_csv(config_path)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import numpy as np

def unified_tward31_analysis(df, sward_config):
    """
    Type 31 T-Ward 데이터에 대한 통합 분석 함수
    Operation Analysis와 Location Analysis가 동일한 결과를 도출하도록 함
    
    Returns:
    - operation_data: 가동률 분석 결과
    - location_data: 위치 분석 결과  
    - summary_stats: 요약 통계
    """
    # S-Ward 설정 merge
    df = df.merge(sward_config[['sward_id', 'building', 'level']], on='sward_id', how='left')
    
    # Time bin 생성 (10분 단위)
    if 'time_bin' not in df.columns:
        df['time_index'] = ((df['time'] - df['time'].dt.normalize()) / pd.Timedelta(seconds=10)).astype(int) + 1
        df['time_bin'] = ((df['time_index'] - 1) // 60) + 1  # 10분 bin index (1~144)
    
    # Type 31 장비 층 고정: 하루 동안 가장 빈번한 층으로 설정
    def get_most_frequent_level(x):
        """안전하게 가장 빈번한 층을 찾는 함수"""
        if len(x) == 0:
            return None
        value_counts = x.value_counts()
        if len(value_counts) == 0:
            return None
        return value_counts.idxmax()
    
    floor_fix = df.groupby('mac')['level'].agg(get_most_frequent_level).reset_index()
    floor_fix.columns = ['mac', 'fixed_level']
    
    # None 값이 있는 경우 원본 level 값을 유지
    df = df.merge(floor_fix, on='mac', how='left')
    df['level'] = df['fixed_level'].fillna(df['level'])
    df = df.drop(columns=['fixed_level'])
    
    # 가동률 판단: 10분 동안 2회 이상 수신되면 가동
    activity_check = df.groupby(['time_bin', 'mac']).size().reset_index(name='signal_count')
    activity_check['is_active'] = activity_check['signal_count'] >= 2
    
    # 각 time_bin, mac별로 가장 큰 RSSI의 S-Ward 위치 결정
    idx = df.groupby(['time_bin', 'mac'])['rssi'].idxmax()
    df_max = df.loc[idx].copy()
    
    # 가동 상태 정보 merge
    df_max = df_max.merge(activity_check[['time_bin', 'mac', 'is_active']], 
                         on=['time_bin', 'mac'], how='left')
    
    # 전체 T-Ward 수 계산 (24시간 동안 한 번이라도 수신된 장비)
    total_counts = df_max.groupby(['building', 'level'])['mac'].nunique().reset_index(name='Total T-Ward Count')
    
    # 시간별 가동 T-Ward 수 계산
    active_counts = df_max[df_max['is_active'] == True].groupby(['time_bin', 'building', 'level'])['mac'].nunique().reset_index(name='Active T-Ward Count')
    
    # Operation rate 계산
    op_rate_df = active_counts.merge(total_counts, on=['building', 'level'], how='right')
    op_rate_df['Active T-Ward Count'] = op_rate_df['Active T-Ward Count'].fillna(0).astype(int)
    op_rate_df['Operation Rate (%)'] = (op_rate_df['Active T-Ward Count'] / op_rate_df['Total T-Ward Count'] * 100).round(1)
    op_rate_df['time_bin'] = op_rate_df['time_bin'].fillna(0).astype(int)
    
    # 요약 통계 생성
    summary_stats = total_counts.copy()
    active_summary = df_max[df_max['is_active'] == True].groupby(['building', 'level'])['mac'].nunique().reset_index(name='Active T-Ward (Any)')
    summary_stats = summary_stats.merge(active_summary, on=['building', 'level'], how='left')
    summary_stats['Active T-Ward (Any)'] = summary_stats['Active T-Ward (Any)'].fillna(0).astype(int)
    summary_stats['Operation Rate (%)'] = (summary_stats['Active T-Ward (Any)'] / summary_stats['Total T-Ward Count'] * 100).round(1)
    
    # Building 전체 통계 추가
    building_rows = []
    for bldg in summary_stats['building'].unique():
        bldg_df = summary_stats[summary_stats['building'] == bldg]
        total = bldg_df['Total T-Ward Count'].sum()
        active = bldg_df['Active T-Ward (Any)'].sum()
        rate = round((active / total * 100) if total > 0 else 0, 1)
        building_rows.append({
            'building': bldg, 
            'level': '(All)', 
            'Total T-Ward Count': total, 
            'Active T-Ward (Any)': active, 
            'Operation Rate (%)': rate
        })
    summary_stats = pd.concat([summary_stats, pd.DataFrame(building_rows)], ignore_index=True)
    
    # Building 전체에 대한 시간별 데이터도 생성
    building_op_data = []
    for bldg in op_rate_df['building'].unique():
        for time_bin in range(1, 145):
            bldg_data = op_rate_df[(op_rate_df['building'] == bldg) & (op_rate_df['time_bin'] == time_bin)]
            if not bldg_data.empty:
                total_active = bldg_data['Active T-Ward Count'].sum()
                total_count = bldg_data['Total T-Ward Count'].sum()
                rate = round((total_active / total_count * 100) if total_count > 0 else 0, 1)
                building_op_data.append({
                    'time_bin': time_bin,
                    'building': bldg,
                    'level': '(All)',
                    'Active T-Ward Count': total_active,
                    'Total T-Ward Count': total_count,
                    'Operation Rate (%)': rate
                })
    
    if building_op_data:
        op_rate_df = pd.concat([op_rate_df, pd.DataFrame(building_op_data)], ignore_index=True)
    
    return {
        'operation_data': op_rate_df,
        'location_data': df_max,  # Operation Analysis용 (is_active 포함)
        'raw_location_data': df,  # Location & Operation Analysis용 (전체 RSSI 데이터)
        'summary_stats': summary_stats,
        'total_counts': total_counts
    }

def preprocess_tward31(df):
    # 컬럼명 부여
    df.columns = ["sward_id", "mac", "type", "rssi", "time"]
    # 시간 파싱
    df["time"] = pd.to_datetime(df["time"])
    return df

def get_time_index(dt):
    # 0시 0분 0초 기준 10초 단위 time_index
    base = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    delta = (dt - base).total_seconds()
    return int(delta // 10) + 1

def add_time_index(df):
    df["time_index"] = df["time"].apply(get_time_index)
    return df

def operation_stats(df):
    # 10분 단위(600초) time_bin, 2회 이상 수신시 가동
    df["time_bin"] = df["time"].dt.floor("10min")
    op = df.groupby(["mac", "time_bin"]).size().reset_index(name="count")
    op["active"] = op["count"] >= 2
    return op
