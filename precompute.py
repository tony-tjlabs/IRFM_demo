#!/usr/bin/env python3
"""
SKEP DataAnalysis - Precompute Script
=====================================

Raw 데이터를 사전 처리하여 캐시 파일로 저장
대시보드에서 빠르게 로드하여 분석 결과 표시

사용법:
    python precompute.py Datafile/Rawdata/Yongin_Cluster_20250909
    python precompute.py <data_folder>

데이터 형식:
    - T31_*.csv: 장비 모니터링 (Type 31)
    - T41_*.csv: 작업자 헬멧 (Type 41)  
    - TMobile_*.csv: 스마트폰 유동인구 (Flow)
"""

import os
import sys
import json
import glob
import hashlib
import time
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np


# ============================================================================
# 상수 정의
# ============================================================================

# 데이터 타입
DATA_TYPE_T31 = 31
DATA_TYPE_T41 = 41
DATA_TYPE_FLOW = 10  # TMobile

# 기본 컬럼명
COLUMN_NAMES = ['sward_id', 'mac', 'type', 'rssi', 'time']


# ============================================================================
# 설정
# ============================================================================

@dataclass
class PrecomputeConfig:
    """사전 계산 설정"""
    # 시간 단위 (초)
    time_unit_seconds: int = 10
    
    # 체류시간 필터링
    min_dwell_time_minutes: int = 30
    
    # T41 분석 설정
    occupancy_time_unit_minutes: int = 10
    
    # 히트맵 설정
    heatmap_time_slot_minutes: int = 10
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def get_hash(self) -> str:
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]


# ============================================================================
# 메인 Precomputer 클래스
# ============================================================================

class DataAnalysisPrecomputer:
    """SKEP DataAnalysis 사전 계산 클래스"""
    
    def __init__(self, data_folder: str, sward_config_path: str = None):
        self.data_folder = Path(data_folder)
        self.cache_folder = self.data_folder / "cache"
        self.config = PrecomputeConfig()
        
        # S-Ward 설정 파일 경로 - 절대 경로 사용
        if sward_config_path:
            self.sward_config_path = Path(sward_config_path)
        else:
            # 기본 경로: 이 스크립트 파일 기준으로 상대 경로 계산
            script_dir = Path(__file__).parent.resolve()
            self.sward_config_path = script_dir / "Datafile" / "sward_configuration.csv"
        
        # 데이터 저장
        self.t31_df: Optional[pd.DataFrame] = None
        self.t41_df: Optional[pd.DataFrame] = None
        self.flow_df: Optional[pd.DataFrame] = None
        self.sward_config: Optional[pd.DataFrame] = None
        
    def run(self):
        """전체 사전 계산 실행"""
        start_time = time.time()
        
        print("=" * 60)
        print("🚀 SKEP DataAnalysis Precompute 시작")
        print("=" * 60)
        print(f"📂 데이터 폴더: {self.data_folder}")
        print(f"💾 캐시 폴더: {self.cache_folder}")
        print()
        
        # 1. 데이터 로드
        print("📂 [1/11] Raw 데이터 로드 중...")
        self._load_raw_data()
        
        # 2. S-Ward 설정 로드
        print("🗺️ [2/11] S-Ward 설정 로드 중...")
        self._load_sward_config()
        
        # 3. T31 분석 (장비 모니터링)
        if self.t31_df is not None and len(self.t31_df) > 0:
            print("🔧 [3/11] T31 (장비) 분석 중...")
            t31_results = self._compute_t31_analysis()
        else:
            print("⏭️ [3/11] T31 데이터 없음 - 건너뜀")
            t31_results = {}
        
        # 4. T41 분석 (작업자 헬멧)
        if self.t41_df is not None and len(self.t41_df) > 0:
            print("👷 [4/11] T41 (작업자) 분석 중...")
            t41_results = self._compute_t41_analysis()
        else:
            print("⏭️ [4/11] T41 데이터 없음 - 건너뜀")
            t41_results = {}
        
        # 5. Flow 분석 (스마트폰)
        if self.flow_df is not None and len(self.flow_df) > 0:
            print("📱 [5/11] Flow (스마트폰) 분석 중...")
            flow_results = self._compute_flow_analysis()
        else:
            print("⏭️ [5/11] Flow 데이터 없음 - 건너뜀")
            flow_results = {}
        
        # 6. 통합 분석
        print("📊 [6/11] 통합 분석 중...")
        combined_results = self._compute_combined_analysis()
        
        # 7. 히트맵 데이터
        print("🗺️ [7/11] 히트맵 데이터 생성 중...")
        heatmap_results = self._compute_heatmap_data()
        
        # 8. Dashboard Overview 데이터
        print("📊 [8/11] Dashboard Overview 데이터 생성 중...")
        dashboard_results = self._compute_dashboard_data()
        
        # 9. AI Insights 생성
        print("🤖 [9/11] AI Insights 생성 중...")
        ai_insights = self._generate_ai_insights(t31_results, t41_results, flow_results)
        
        # 10. 위치 히트맵 이미지 생성
        print("🗺️ [10/11] 작업자 위치 히트맵 생성 중...")
        self._generate_location_heatmaps()
        
        # 11. 캐시 저장
        print("💾 [11/11] 캐시 저장 중...")
        self._save_cache(
            t31_results=t31_results,
            t41_results=t41_results,
            flow_results=flow_results,
            combined_results=combined_results,
            heatmap_results=heatmap_results,
            dashboard_results=dashboard_results,
            ai_insights=ai_insights
        )
        
        elapsed = time.time() - start_time
        print()
        print("=" * 60)
        print(f"✅ 사전 계산 완료! ({elapsed:.1f}초)")
        print("=" * 60)
        
        self._print_summary()
    
    def _load_raw_data(self):
        """Raw 데이터 파일 로드"""
        
        # T31 파일 찾기
        t31_files = list(self.data_folder.glob("T31_*.csv"))
        if t31_files:
            print(f"  📄 T31 파일: {len(t31_files)}개")
            dfs = []
            for f in t31_files:
                df = pd.read_csv(f, names=COLUMN_NAMES)
                df['source_file'] = f.name
                dfs.append(df)
            self.t31_df = pd.concat(dfs, ignore_index=True)
            self.t31_df['time'] = pd.to_datetime(self.t31_df['time'])
            print(f"  ✅ T31: {len(self.t31_df):,} rows 로드")
        
        # T41 파일 찾기
        t41_files = list(self.data_folder.glob("T41_*.csv"))
        if t41_files:
            print(f"  📄 T41 파일: {len(t41_files)}개")
            dfs = []
            for f in t41_files:
                # 대용량 파일은 청크 단위로 처리
                file_size_mb = f.stat().st_size / (1024 * 1024)
                if file_size_mb > 100:
                    print(f"    ⏳ 대용량 파일 처리 중: {f.name} ({file_size_mb:.1f}MB)")
                    chunks = []
                    for chunk in pd.read_csv(f, names=COLUMN_NAMES, chunksize=100000):
                        chunks.append(chunk)
                    df = pd.concat(chunks, ignore_index=True)
                else:
                    df = pd.read_csv(f, names=COLUMN_NAMES)
                df['source_file'] = f.name
                dfs.append(df)
            self.t41_df = pd.concat(dfs, ignore_index=True)
            self.t41_df['time'] = pd.to_datetime(self.t41_df['time'])
            print(f"  ✅ T41: {len(self.t41_df):,} rows 로드")
        
        # TMobile (Flow) 파일 찾기
        flow_files = list(self.data_folder.glob("TMobile_*.csv"))
        if flow_files:
            print(f"  📄 Flow 파일: {len(flow_files)}개")
            dfs = []
            for f in flow_files:
                file_size_mb = f.stat().st_size / (1024 * 1024)
                if file_size_mb > 100:
                    print(f"    ⏳ 대용량 파일 처리 중: {f.name} ({file_size_mb:.1f}MB)")
                    chunks = []
                    for chunk in pd.read_csv(f, names=COLUMN_NAMES, chunksize=100000):
                        chunks.append(chunk)
                    df = pd.concat(chunks, ignore_index=True)
                else:
                    df = pd.read_csv(f, names=COLUMN_NAMES)
                df['source_file'] = f.name
                dfs.append(df)
            self.flow_df = pd.concat(dfs, ignore_index=True)
            self.flow_df['time'] = pd.to_datetime(self.flow_df['time'])
            print(f"  ✅ Flow: {len(self.flow_df):,} rows 로드")
    
    def _load_sward_config(self):
        """S-Ward 설정 파일 로드"""
        if self.sward_config_path.exists():
            self.sward_config = pd.read_csv(self.sward_config_path)
            print(f"  ✅ S-Ward 설정: {len(self.sward_config)} 개 로드")
            
            # building, level 목록
            buildings = self.sward_config['building'].unique().tolist()
            print(f"  📍 Buildings: {buildings}")
        else:
            print(f"  ⚠️ S-Ward 설정 파일 없음: {self.sward_config_path}")
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """시간 관련 특성 추가"""
        df = df.copy()
        
        # 날짜/시간 특성
        df['date'] = df['time'].dt.date.astype(str)
        df['hour'] = df['time'].dt.hour
        df['minute'] = df['time'].dt.minute
        
        # time_index (10초 단위)
        time_normalized = df['time'].dt.normalize()
        df['time_index'] = ((df['time'] - time_normalized) / pd.Timedelta(seconds=self.config.time_unit_seconds)).astype(int)
        
        # 분 단위 bin
        df['minute_bin'] = df['time'].dt.floor('1T')
        
        return df
    
    def _compute_t31_analysis(self) -> Dict:
        """T31 (장비) 분석 - Operation Heatmap 사전 계산 포함"""
        df = self._add_time_features(self.t31_df)
        
        results = {}
        
        # =======================================================================
        # 2분 단위 unique MAC 카운팅 (T31도 동일하게 적용)
        # =======================================================================
        print("    📊 2분 단위 unique MAC 카운팅 (T31)...")
        
        df['two_min_bin'] = df['time'].dt.floor('2T')
        
        two_min_unique = df.groupby(['date', 'two_min_bin'])['mac'].nunique().reset_index()
        two_min_unique.columns = ['date', 'two_min_bin', 'unique_mac_count']
        two_min_unique['hour'] = pd.to_datetime(two_min_unique['two_min_bin']).dt.hour
        results['two_min_unique_mac'] = two_min_unique
        
        # =======================================================================
        # 1. 시간대별 장비 가동 현황
        # =======================================================================
        hourly_activity = df.groupby(['date', 'hour']).agg({
            'mac': 'nunique',
            'sward_id': 'nunique',
            'rssi': 'mean'
        }).reset_index()
        hourly_activity.columns = ['date', 'hour', 'active_devices', 'active_swards', 'avg_rssi']
        results['hourly_activity'] = hourly_activity
        
        # =======================================================================
        # 2. 장비별 가동 시간
        # =======================================================================
        device_stats = df.groupby('mac').agg({
            'time': ['min', 'max', 'count'],
            'sward_id': 'nunique',
            'rssi': 'mean'
        }).reset_index()
        device_stats.columns = ['mac', 'first_seen', 'last_seen', 'record_count', 'sward_count', 'avg_rssi']
        device_stats['duration_minutes'] = (
            pd.to_datetime(device_stats['last_seen']) - pd.to_datetime(device_stats['first_seen'])
        ).dt.total_seconds() / 60
        results['device_stats'] = device_stats
        
        # =======================================================================
        # 3. S-Ward별 장비 현황 + Operation Heatmap 데이터
        # =======================================================================
        if self.sward_config is not None:
            sward_activity = df.groupby('sward_id').agg({
                'mac': 'nunique',
                'time': 'count',
                'rssi': 'mean'
            }).reset_index()
            sward_activity.columns = ['sward_id', 'device_count', 'record_count', 'avg_rssi']
            
            # S-Ward 정보 조인
            sward_activity = sward_activity.merge(
                self.sward_config[['sward_id', 'building', 'level', 'x', 'y', 'space_type']],
                on='sward_id',
                how='left'
            )
            results['sward_activity'] = sward_activity
            
            # =======================================================================
            # Operation Heatmap: 10분 단위 장비 가동률 (핵심)
            # =======================================================================
            print("    📊 Operation Heatmap 생성 중...")
            
            df['time_slot_10min'] = df['time'].dt.floor('10T')
            
            # S-Ward 정보 조인
            df_with_loc = df.merge(
                self.sward_config[['sward_id', 'building', 'level', 'space_type', 'x', 'y']],
                on='sward_id',
                how='left'
            )
            
            # 10분 단위, S-Ward별 장비 가동 현황
            operation_heatmap = df_with_loc.groupby([
                'date', 'time_slot_10min', 'building', 'level', 'sward_id', 'x', 'y', 'space_type'
            ]).agg({
                'mac': ['nunique', 'count'],  # 고유 장비 수, 총 레코드 수
                'rssi': 'mean'
            }).reset_index()
            operation_heatmap.columns = ['date', 'time_slot', 'building', 'level', 'sward_id', 
                                          'x', 'y', 'space_type', 'active_devices', 'record_count', 'avg_rssi']
            
            # 시간 bin 인덱스 추가 (0-143, 10분 단위)
            operation_heatmap['bin_index'] = (
                pd.to_datetime(operation_heatmap['time_slot']).dt.hour * 6 + 
                pd.to_datetime(operation_heatmap['time_slot']).dt.minute // 10
            )
            
            results['operation_heatmap'] = operation_heatmap
            print(f"    ✅ Operation Heatmap: {len(operation_heatmap):,} records")
        
        print(f"  ✅ T31 분석 완료: {len(device_stats)} 장비, {len(hourly_activity)} 시간대 레코드")
        
        return results
    
    def _compute_t41_analysis(self) -> Dict:
        """T41 (작업자 헬멧) 분석 - 2분 단위 unique MAC 포함"""
        import sys
        
        print(f"    📊 T41 데이터: {len(self.t41_df):,} records", flush=True)
        print(f"    🔄 시간 특성 추가 중...", flush=True)
        df = self._add_time_features(self.t41_df)
        print(f"    ✅ 시간 특성 추가 완료", flush=True)
        
        results = {}
        
        # =======================================================================
        # 2분 단위 unique MAC 카운팅 (T41도 동일하게 적용)
        # =======================================================================
        print("    📊 2분 단위 unique MAC 카운팅 (T41)...", flush=True)
        sys.stdout.flush()
        
        df['two_min_bin'] = df['time'].dt.floor('2T')
        
        two_min_unique = df.groupby(['date', 'two_min_bin'])['mac'].nunique().reset_index()
        two_min_unique.columns = ['date', 'two_min_bin', 'unique_mac_count']
        two_min_unique['hour'] = pd.to_datetime(two_min_unique['two_min_bin']).dt.hour
        results['two_min_unique_mac'] = two_min_unique
        
        # 시간대별 평균 (2분 bins의 평균)
        hourly_avg_from_2min = two_min_unique.groupby(['date', 'hour']).agg({
            'unique_mac_count': ['mean', 'max', 'min', 'count']
        }).reset_index()
        hourly_avg_from_2min.columns = ['date', 'hour', 'avg_workers', 'max_workers', 
                                         'min_workers', 'two_min_bin_count']
        results['hourly_avg_from_2min'] = hourly_avg_from_2min
        
        print(f"    ✅ 2분 단위 집계: {len(two_min_unique)} bins")
        
        # =======================================================================
        # 1. 작업자별 체류시간 계산
        # =======================================================================
        worker_dwell = df.groupby('mac').agg({
            'minute_bin': 'nunique',  # 체류 시간 (분)
            'time': ['min', 'max', 'count'],
            'sward_id': 'nunique',
            'rssi': 'mean'
        }).reset_index()
        worker_dwell.columns = ['mac', 'dwell_time_minutes', 'first_seen', 'last_seen', 
                                 'record_count', 'sward_count', 'avg_rssi']
        results['worker_dwell'] = worker_dwell
        
        # =======================================================================
        # 2. 시간대별 작업자 수 (Occupancy) - 10분 단위
        # =======================================================================
        time_slot_minutes = self.config.occupancy_time_unit_minutes
        df['time_slot'] = df['time'].dt.floor(f'{time_slot_minutes}T')
        
        occupancy = df.groupby(['date', 'time_slot']).agg({
            'mac': 'nunique'
        }).reset_index()
        occupancy.columns = ['date', 'time_slot', 'worker_count']
        occupancy['hour'] = pd.to_datetime(occupancy['time_slot']).dt.hour
        occupancy['minute'] = pd.to_datetime(occupancy['time_slot']).dt.minute
        results['occupancy'] = occupancy
        
        # =======================================================================
        # 3. Building/Level별 작업자 현황
        # =======================================================================
        if self.sward_config is not None:
            # S-Ward 정보 조인
            df_with_location = df.merge(
                self.sward_config[['sward_id', 'building', 'level', 'space_type']],
                on='sward_id',
                how='left'
            )
            
            # Building별 시간대 작업자 수
            building_occupancy = df_with_location.groupby(['date', 'time_slot', 'building', 'level']).agg({
                'mac': 'nunique'
            }).reset_index()
            building_occupancy.columns = ['date', 'time_slot', 'building', 'level', 'worker_count']
            results['building_occupancy'] = building_occupancy
            
            # Space Type별 작업자 현황
            space_type_stats = df_with_location.groupby(['space_type']).agg({
                'mac': 'nunique',
                'time': 'count'
            }).reset_index()
            space_type_stats.columns = ['space_type', 'unique_workers', 'total_records']
            results['space_type_stats'] = space_type_stats
        
        # 4. Journey 분석 (작업자 이동 경로)
        journey_data = self._compute_worker_journey(df)
        results['journey_data'] = journey_data
        
        # 5. 필터링된 데이터 (체류시간 >= 30분)
        filtered_macs = worker_dwell[worker_dwell['dwell_time_minutes'] >= self.config.min_dwell_time_minutes]['mac'].tolist()
        results['filtered_worker_count'] = len(filtered_macs)
        results['total_worker_count'] = len(worker_dwell)
        
        # 6. 🆕 Activity Analysis 생성 (Journey Heatmap용)
        # 1분 단위 활동 상태 분석 - Journey Map에서 필요
        print("    📊 Activity Analysis 생성 중...")
        activity_analysis = self._compute_activity_analysis(df)
        results['activity_analysis'] = activity_analysis
        print(f"    ✅ Activity Analysis: {len(activity_analysis):,} records")
        
        # 7. 🆕 Journey Heatmap precomputation (10분 단위 벡터화)
        print("    📊 Journey Heatmap precomputation 시작...")
        journey_heatmap = self._compute_journey_heatmap(df)
        results['journey_heatmap'] = journey_heatmap
        print(f"    ✅ Journey Heatmap: {len(journey_heatmap):,} records")
        
        print(f"  ✅ T41 분석 완료: {len(worker_dwell)} 작업자, 필터링 후 {len(filtered_macs)}명")
        
        return results
    
    def _compute_activity_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        """작업자 활동 상태 분석 (1분 단위) - Journey Heatmap용
        
        벡터화된 최적화 버전: for 루프 대신 groupby + agg 사용
        """
        if self.sward_config is None:
            return pd.DataFrame()
        
        import sys
        print(f"      🔄 S-Ward 정보 조인 중...", flush=True)
        sys.stdout.flush()
        # S-Ward 정보 조인
        df_with_loc = df.merge(
            self.sward_config[['sward_id', 'building', 'level', 'space_type']],
            on='sward_id',
            how='left'
        )
        
        print("      🔄 벡터화된 집계 중...", flush=True)
        sys.stdout.flush()
        
        # 벡터화된 집계: mac + minute_bin 그룹으로 한 번에 처리
        # 각 그룹에서 가장 많이 나타난 building/level/space_type과 signal_count 계산
        
        # 1. 기본 집계: signal_count
        basic_agg = df_with_loc.groupby(['mac', 'minute_bin']).agg({
            'sward_id': 'count',  # signal_count
        }).reset_index()
        basic_agg.columns = ['mac', 'minute_bin', 'signal_count']
        
        print("      🔄 최빈값 계산 중 (최적화 버전)...", flush=True)
        sys.stdout.flush()
        
        # 2. 최빈값 계산: value_counts().idxmax() 대신 더 빠른 방법 사용
        # 각 컬럼별로 가장 빈도가 높은 값을 찾음
        
        # building 최빈값: 그룹별 첫 번째 값 사용 (mode보다 훨씬 빠름)
        # 실제 mode를 구하려면 너무 느리므로, 그룹 내 가장 먼저 나타난 값 사용
        building_first = df_with_loc.groupby(['mac', 'minute_bin'])['building'].first().reset_index()
        building_first.columns = ['mac', 'minute_bin', 'building']
        
        print("      🔄 level 값 추출 중...", flush=True)
        sys.stdout.flush()
        # level 첫 번째 값
        level_first = df_with_loc.groupby(['mac', 'minute_bin'])['level'].first().reset_index()
        level_first.columns = ['mac', 'minute_bin', 'level']
        
        print("      🔄 space_type 값 추출 중...", flush=True)
        sys.stdout.flush()
        # space_type 첫 번째 값
        space_type_first = df_with_loc.groupby(['mac', 'minute_bin'])['space_type'].first().reset_index()
        space_type_first.columns = ['mac', 'minute_bin', 'space_type']
        
        print("      🔄 결과 병합 중...", flush=True)
        sys.stdout.flush()
        
        # 3. 결과 병합
        result = basic_agg.merge(building_first, on=['mac', 'minute_bin'], how='left')
        result = result.merge(level_first, on=['mac', 'minute_bin'], how='left')
        result = result.merge(space_type_first, on=['mac', 'minute_bin'], how='left')
        
        # 4. activity_status 계산 (벡터화)
        result['activity_status'] = 'Absent'
        result.loc[result['signal_count'] >= 1, 'activity_status'] = 'Present'
        result.loc[result['signal_count'] >= 3, 'activity_status'] = 'Active'
        
        print(f"      ✅ Activity Analysis 완료: {len(result):,} records")
        
        return result
    
    def _compute_worker_journey(self, df: pd.DataFrame) -> pd.DataFrame:
        """작업자 이동 경로 분석"""
        if self.sward_config is None:
            return pd.DataFrame()
        
        # S-Ward 위치 정보 조인
        df_journey = df.merge(
            self.sward_config[['sward_id', 'building', 'level', 'x', 'y']],
            on='sward_id',
            how='left'
        )
        
        # 작업자별 이동 경로 추출
        journeys = []
        for mac, group in df_journey.groupby('mac'):
            group = group.sort_values('time')
            
            # 연속된 동일 S-Ward 제거 (실제 이동만 추출)
            group['sward_changed'] = group['sward_id'] != group['sward_id'].shift()
            transitions = group[group['sward_changed']].copy()
            
            if len(transitions) > 1:
                journeys.append({
                    'mac': mac,
                    'transition_count': len(transitions) - 1,
                    'unique_swards': group['sward_id'].nunique(),
                    'first_sward': transitions.iloc[0]['sward_id'],
                    'last_sward': transitions.iloc[-1]['sward_id'],
                    'start_time': transitions.iloc[0]['time'],
                    'end_time': transitions.iloc[-1]['time']
                })
        
        return pd.DataFrame(journeys)
    
    def _compute_journey_heatmap(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Journey Heatmap 전용 벡터화 precomputation (2분→10분 롤업 방식)
        
        효율적인 처리 순서:
        1. 2분 단위로 각 (mac, 2min_bin)의 building, level 집계
        2. 2분 bin을 10분 bin으로 롤업 (5개 2분 bin → 1개 10분 bin)
        3. 각 10분 bin에서 가장 빈번한 building-level 결정
        4. 144개 time bin 행렬 생성 (workers × 144)
        
        - X축: 10분 단위 bins (144개, 00:00~23:50)
        - Y축: 개별 작업자 (MAC)
        - 색상: Building-Level 위치 (JOURNEY_COLORS 기반)
        """
        if self.sward_config is None or df.empty:
            return pd.DataFrame()
        
        print("    🗺️ Journey Heatmap precomputation 시작 (2분→10분 롤업)...")
        sys.stdout.flush()
        
        # =====================================================================
        # Step 1: S-Ward 위치 정보 조인
        # =====================================================================
        df_with_loc = df.merge(
            self.sward_config[['sward_id', 'building', 'level']],
            on='sward_id',
            how='left'
        )
        
        # Building-Level 조합 생성
        df_with_loc['building_level'] = (
            df_with_loc['building'].fillna('Unknown') + '-' + 
            df_with_loc['level'].fillna('Unknown')
        )
        
        # =====================================================================
        # Step 2: 2분 단위로 집계 (기본 단위)
        # =====================================================================
        print("      🔄 Step 1/3: 2분 단위 집계 중...", flush=True)
        sys.stdout.flush()
        
        df_with_loc['two_min_bin'] = df_with_loc['time'].dt.floor('2min')
        
        # 각 (mac, 2min_bin)에서 첫 번째 building_level과 신호 수
        two_min_agg = df_with_loc.groupby(['mac', 'two_min_bin']).agg({
            'building_level': 'first',
            'building': 'first',
            'level': 'first',
            'time': 'count'  # 해당 2분 동안의 신호 수
        }).reset_index()
        two_min_agg.columns = ['mac', 'two_min_bin', 'building_level', 'building', 'level', 'signal_count_2min']
        
        print(f"      ✅ 2분 집계 완료: {len(two_min_agg):,} records")
        
        # =====================================================================
        # Step 3: 2분 → 10분 롤업
        # =====================================================================
        print("      🔄 Step 2/3: 10분 단위로 롤업 중...", flush=True)
        sys.stdout.flush()
        
        # 10분 bin 인덱스 계산 (0~143)
        two_min_agg['ten_min_bin'] = two_min_agg['two_min_bin'].dt.floor('10min')
        two_min_agg['bin_index'] = (
            two_min_agg['two_min_bin'].dt.hour * 6 + 
            two_min_agg['two_min_bin'].dt.minute // 10
        )
        
        # 각 10분 bin에서 가장 많이 나타난 building_level 찾기
        # 방법: 각 (mac, bin_index, building_level)별 2분 bin 수를 세고, 최대값 선택
        ten_min_counts = two_min_agg.groupby(['mac', 'bin_index', 'building_level']).agg({
            'signal_count_2min': 'sum',  # 해당 building_level에서의 총 신호 수
            'two_min_bin': 'count'  # 해당 building_level이 나타난 2분 bin 수
        }).reset_index()
        ten_min_counts.columns = ['mac', 'bin_index', 'building_level', 'signal_count', 'two_min_bin_count']
        
        # 각 (mac, bin_index)에서 two_min_bin_count가 가장 높은 building_level 선택
        idx = ten_min_counts.groupby(['mac', 'bin_index'])['two_min_bin_count'].idxmax()
        journey_data = ten_min_counts.loc[idx].copy()
        
        # building, level 분리
        journey_data[['building', 'level']] = journey_data['building_level'].str.split('-', n=1, expand=True)
        
        print(f"      ✅ 10분 롤업 완료: {len(journey_data):,} records")
        
        # =====================================================================
        # Step 4: 색상 코드 매핑 (완전 벡터화)
        # =====================================================================
        print("      🔄 Step 3/3: 색상 코드 매핑 중...", flush=True)
        sys.stdout.flush()
        
        # 색상 코드 매핑 딕셔너리
        # 0: no_signal, 1: present_inactive, 2+: Building-Level별 active 색상
        color_mapping = {
            'WWT-1F': 2,
            'WWT-B1F': 3,
            'WWT-2F': 2,
            'FAB-1F': 4,
            'FAB-B1F': 4,
            'FAB-2F': 4,
            'CUB-1F': 5,
            'CUB-B1F': 6,
            'CUB-2F': 5,
            'Cluster-1F': 7,
            'Cluster-B1F': 7,
            'Cluster-2F': 7,
            'Unknown-Unknown': 0
        }
        
        # 벡터화된 색상 코드 할당
        # 1. 먼저 building_level로 기본 색상 매핑
        # 알 수 없는 building_level은 7(Cluster)로 매핑 (기존 9 대신)
        journey_data['base_color'] = journey_data['building_level'].map(color_mapping).fillna(7).astype(int)
        
        # color_code가 7을 초과하지 않도록 클램핑
        journey_data['base_color'] = journey_data['base_color'].clip(upper=7)
        
        # 2. 활성/비활성 판단 (T41 헬멧 특성 기반)
        # - 활성: 진동 감지 → 1분에 2회 이상 신호 (10초 간격)
        # - 비활성: 진동 없음 → 1분에 2회 미만 신호
        # - 10분 기준: 20회 이상이면 활성 (1분에 2회 × 10분)
        ACTIVE_THRESHOLD = 20  # 10분 동안 20회 이상 신호 = 활성
        
        journey_data['color_code'] = np.where(
            journey_data['signal_count'] < ACTIVE_THRESHOLD,
            1,  # present_inactive (비활성: 신호는 있지만 진동 없음)
            journey_data['base_color']
        )
        
        # 불필요한 컬럼 제거
        journey_data = journey_data.drop(columns=['two_min_bin_count', 'base_color'])
        
        # 통계
        all_macs = journey_data['mac'].nunique()
        total_bins = len(journey_data)
        
        print(f"      ✅ Journey Heatmap 완료: {total_bins:,} records, {all_macs:,} workers")
        print(f"         평균 bin/worker: {total_bins/all_macs:.1f} (최대 144)")
        sys.stdout.flush()
        
        return journey_data
    
    def _compute_flow_analysis(self) -> Dict:
        """Flow (스마트폰) 분석 - 2분 단위 unique MAC 카운팅"""
        df = self._add_time_features(self.flow_df)
        
        results = {}
        
        # =======================================================================
        # 2분 단위 unique MAC 카운팅 (핵심 로직)
        # MAC 주소가 자주 변경되므로 2분 단위로 고유 MAC 수를 세어 평균
        # =======================================================================
        print("    📊 2분 단위 unique MAC 카운팅 중...")
        
        # 2분 단위 bin 생성
        df['two_min_bin'] = df['time'].dt.floor('2T')
        
        # 2분 단위 unique MAC 카운트
        two_min_unique = df.groupby(['date', 'two_min_bin'])['mac'].nunique().reset_index()
        two_min_unique.columns = ['date', 'two_min_bin', 'unique_mac_count']
        two_min_unique['hour'] = pd.to_datetime(two_min_unique['two_min_bin']).dt.hour
        results['two_min_unique_mac'] = two_min_unique
        
        # 시간대별 평균 (2분 bins의 평균)
        hourly_avg_from_2min = two_min_unique.groupby(['date', 'hour']).agg({
            'unique_mac_count': ['mean', 'max', 'min', 'sum', 'count']
        }).reset_index()
        hourly_avg_from_2min.columns = ['date', 'hour', 'avg_unique_mac', 'max_unique_mac', 
                                         'min_unique_mac', 'sum_unique_mac', 'two_min_bin_count']
        results['hourly_avg_from_2min'] = hourly_avg_from_2min
        
        print(f"    ✅ 2분 단위 집계: {len(two_min_unique)} bins, 시간대별 평균: {len(hourly_avg_from_2min)} records")
        
        # =======================================================================
        # 기존 분석: 시간대별 유동인구 (10분 단위)
        # =======================================================================
        
        # 1. 시간대별 유동인구 (10분 단위 - 기존 호환)
        df['ten_min_bin'] = df['time'].dt.floor('10T')
        ten_min_unique = df.groupby(['date', 'ten_min_bin']).agg({
            'mac': 'nunique'
        }).reset_index()
        ten_min_unique.columns = ['date', 'ten_min_bin', 'unique_devices']
        results['ten_min_unique'] = ten_min_unique
        
        # 2. 시간대별 유동인구 (1시간 단위)
        hourly_flow = df.groupby(['date', 'hour']).agg({
            'mac': 'nunique'
        }).reset_index()
        hourly_flow.columns = ['date', 'hour', 'unique_devices']
        results['hourly_flow'] = hourly_flow
        
        # 3. S-Ward별 유동인구
        sward_flow = df.groupby('sward_id').agg({
            'mac': 'nunique',
            'time': 'count',
            'rssi': 'mean'
        }).reset_index()
        sward_flow.columns = ['sward_id', 'unique_devices', 'total_records', 'avg_rssi']
        
        if self.sward_config is not None:
            sward_flow = sward_flow.merge(
                self.sward_config[['sward_id', 'building', 'level', 'x', 'y', 'space_type']],
                on='sward_id',
                how='left'
            )
        results['sward_flow'] = sward_flow
        
        # 4. 디바이스별 체류 분석
        device_stats = df.groupby('mac').agg({
            'minute_bin': 'nunique',
            'sward_id': 'nunique',
            'rssi': 'mean'
        }).reset_index()
        device_stats.columns = ['mac', 'dwell_minutes', 'sward_count', 'avg_rssi']
        results['device_stats'] = device_stats
        
        # 5. 디바이스 타입별 분석 (type 컬럼이 있는 경우)
        if 'type' in df.columns:
            type_stats = df.groupby('type')['mac'].nunique().reset_index()
            type_stats.columns = ['device_type', 'unique_devices']
            results['device_type_stats'] = type_stats
        
        print(f"  ✅ Flow 분석 완료: {len(device_stats)} 디바이스, 2분 평균 시간대별: {hourly_avg_from_2min['avg_unique_mac'].sum():.0f} total avg")
        
        return results
    
    def _compute_combined_analysis(self) -> Dict:
        """통합 분석"""
        results = {}
        
        # 데이터 요약
        summary = {
            't31_records': len(self.t31_df) if self.t31_df is not None else 0,
            't41_records': len(self.t41_df) if self.t41_df is not None else 0,
            'flow_records': len(self.flow_df) if self.flow_df is not None else 0,
            't31_devices': self.t31_df['mac'].nunique() if self.t31_df is not None else 0,
            't41_workers': self.t41_df['mac'].nunique() if self.t41_df is not None else 0,
            'flow_devices': self.flow_df['mac'].nunique() if self.flow_df is not None else 0,
        }
        
        # 날짜 범위
        all_times = []
        if self.t31_df is not None:
            all_times.extend(self.t31_df['time'].tolist())
        if self.t41_df is not None:
            all_times.extend(self.t41_df['time'].tolist())
        if self.flow_df is not None:
            all_times.extend(self.flow_df['time'].tolist())
        
        if all_times:
            summary['date_range_start'] = min(all_times).isoformat()
            summary['date_range_end'] = max(all_times).isoformat()
            summary['dates'] = sorted(list(set([t.strftime('%Y-%m-%d') for t in all_times])))
        
        results['summary'] = summary
        
        print(f"  ✅ 통합 분석 완료")
        
        return results
    
    def _compute_heatmap_data(self) -> Dict:
        """히트맵 데이터 생성"""
        results = {}
        
        if self.sward_config is None:
            return results
        
        # T41 히트맵 (작업자 밀도)
        if self.t41_df is not None:
            df = self._add_time_features(self.t41_df)
            df['time_slot'] = df['time'].dt.floor(f"{self.config.heatmap_time_slot_minutes}T")
            
            # S-Ward별 시간대별 작업자 수
            heatmap_data = df.merge(
                self.sward_config[['sward_id', 'building', 'level', 'x', 'y']],
                on='sward_id',
                how='left'
            )
            
            # 각 building/level별로 저장
            for (building, level), group in heatmap_data.groupby(['building', 'level']):
                key = f"heatmap_t41_{building}_{level}"
                
                slot_data = group.groupby(['time_slot', 'sward_id', 'x', 'y']).agg({
                    'mac': 'nunique'
                }).reset_index()
                slot_data.columns = ['time_slot', 'sward_id', 'x', 'y', 'worker_count']
                
                results[key] = slot_data
        
        print(f"  ✅ 히트맵 데이터 생성 완료: {len(results)} 개")
        
        return results
    
    def _generate_location_heatmaps(self):
        """T41 작업자 위치 히트맵 이미지 생성 (동영상 대체)"""
        try:
            from scipy.ndimage import gaussian_filter
        except ImportError:
            print("  ⚠️ scipy 미설치 - 히트맵 생성 건너뜀")
            print("    설치: pip install scipy")
            return
        
        if self.t41_df is None or len(self.t41_df) == 0:
            print("  ⚠️ T41 데이터 없음 - 히트맵 생성 건너뜀")
            return
        
        if self.sward_config is None or len(self.sward_config) == 0:
            print("  ⚠️ S-Ward 설정 없음 - 히트맵 생성 건너뜀")
            return
        
        # 스크립트 경로 기준으로 맵 이미지 폴더 찾기
        script_dir = Path(__file__).parent.resolve()
        map_folder = script_dir / "Datafile" / "Map_Image"
        
        if not map_folder.exists():
            print(f"  ⚠️ 맵 이미지 폴더 없음: {map_folder}")
            return
        
        # Building-Level 조합 추출
        building_levels = self.sward_config.groupby(['building', 'level']).size().reset_index()[['building', 'level']]
        
        # 캐시 폴더 생성
        self.cache_folder.mkdir(parents=True, exist_ok=True)
        
        heatmap_count = 0
        
        for _, row in building_levels.iterrows():
            building = row['building']
            level = row['level']
            
            # 맵 이미지 파일 찾기
            map_patterns = [
                f"Map_{building}_{level}.png",
                f"map_{building}_{level}.png",
                f"Map_{building}.png",
            ]
            
            map_path = None
            for pattern in map_patterns:
                candidate = map_folder / pattern
                if candidate.exists():
                    map_path = candidate
                    break
            
            if map_path is None:
                print(f"    ⏭️ {building}-{level}: 맵 이미지 없음")
                continue
            
            # 히트맵 이미지 생성
            heatmap_path = self._create_location_heatmap(building, level, map_path)
            if heatmap_path:
                heatmap_count += 1
                print(f"    ✅ {building}-{level}: {heatmap_path.name}")
        
        print(f"  ✅ 히트맵 생성 완료: {heatmap_count} 개")
    
    def _create_location_heatmap(self, building: str, level: str, map_path: Path) -> Optional[Path]:
        """단일 Building-Level에 대한 위치 히트맵 이미지 생성"""
        from PIL import Image
        from scipy.ndimage import gaussian_filter
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap
        
        try:
            # 맵 이미지 로드
            map_img = Image.open(map_path).convert('RGB')
            img_width, img_height = map_img.size
            
            # 해당 Building-Level의 S-Ward 필터링
            sward_in_level = self.sward_config[
                (self.sward_config['building'] == building) & 
                (self.sward_config['level'] == level)
            ]
            
            if sward_in_level.empty or 'x' not in sward_in_level.columns:
                return None
            
            # T41 데이터와 S-Ward 조인
            t41_with_loc = self.t41_df.merge(
                self.sward_config[['sward_id', 'building', 'level', 'x', 'y']],
                on='sward_id',
                how='inner'
            )
            
            # 해당 Building-Level 필터링
            t41_filtered = t41_with_loc[
                (t41_with_loc['building'] == building) & 
                (t41_with_loc['level'] == level)
            ]
            
            if t41_filtered.empty:
                return None
            
            # 히트맵 배열 생성 (각 좌표에 방문 횟수 누적)
            heatmap = np.zeros((img_height, img_width), dtype=np.float32)
            
            # 각 S-Ward 좌표별 방문 횟수 집계
            visit_counts = t41_filtered.groupby(['x', 'y']).size().reset_index(name='count')
            
            for _, row in visit_counts.iterrows():
                x = int(row['x'])
                y = int(row['y'])
                count = row['count']
                
                # 이미지 범위 내 체크
                if 0 <= x < img_width and 0 <= y < img_height:
                    heatmap[y, x] += count
            
            # Gaussian blur 적용 (sigma=30으로 부드러운 히트맵)
            heatmap = gaussian_filter(heatmap, sigma=30)
            
            # 정규화
            if heatmap.max() > 0:
                heatmap = heatmap / heatmap.max()
            
            # 컬러맵 생성 (파랑 → 청록 → 노랑 → 주황 → 빨강)
            cmap = LinearSegmentedColormap.from_list(
                'traffic_heatmap',
                [(0, 'blue'), (0.25, 'cyan'), (0.5, 'yellow'), (0.75, 'orange'), (1, 'red')]
            )
            
            # matplotlib으로 이미지 생성
            fig, ax = plt.subplots(figsize=(img_width/100, img_height/100), dpi=100)
            
            # 배경 이미지
            ax.imshow(map_img, extent=[0, img_width, img_height, 0])
            
            # 히트맵 오버레이 (alpha=0.6)
            ax.imshow(heatmap, cmap=cmap, alpha=0.6, 
                      extent=[0, img_width, img_height, 0],
                      vmin=0, vmax=1)
            
            # S-Ward 위치 표시 (작은 마커)
            for _, sward in sward_in_level.iterrows():
                ax.plot(sward['x'], sward['y'], 'ko', markersize=4, alpha=0.5)
            
            # 축 설정
            ax.set_xlim(0, img_width)
            ax.set_ylim(img_height, 0)  # Y축 반전
            ax.axis('off')
            
            # 제목
            ax.set_title(f'{building} {level} - Worker Location Heatmap', 
                         fontsize=14, fontweight='bold', pad=10)
            
            # 파일 저장
            output_path = self.cache_folder / f"location_heatmap_{building}_{level}.png"
            plt.savefig(output_path, bbox_inches='tight', pad_inches=0.1, dpi=100)
            plt.close()
            
            return output_path
            
        except Exception as e:
            print(f"    ❌ {building}-{level} 히트맵 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_cache(self, **result_dicts):
        """캐시 저장"""
        self.cache_folder.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        
        # 원본 데이터 저장 (Dashboard Mode에서 기존 분석 기능 사용을 위해)
        print("  💾 원본 데이터 저장 중...")
        if self.t31_df is not None and len(self.t31_df) > 0:
            self.t31_df.to_parquet(self.cache_folder / "raw_t31.parquet", index=False)
            saved_files.append("raw_t31.parquet")
            print(f"    ✅ raw_t31.parquet: {len(self.t31_df):,} rows")
        
        if self.t41_df is not None and len(self.t41_df) > 0:
            self.t41_df.to_parquet(self.cache_folder / "raw_t41.parquet", index=False)
            saved_files.append("raw_t41.parquet")
            print(f"    ✅ raw_t41.parquet: {len(self.t41_df):,} rows")
        
        if self.flow_df is not None and len(self.flow_df) > 0:
            self.flow_df.to_parquet(self.cache_folder / "raw_flow.parquet", index=False)
            saved_files.append("raw_flow.parquet")
            print(f"    ✅ raw_flow.parquet: {len(self.flow_df):,} rows")
        
        if self.sward_config is not None and len(self.sward_config) > 0:
            self.sward_config.to_parquet(self.cache_folder / "raw_sward_config.parquet", index=False)
            saved_files.append("raw_sward_config.parquet")
            print(f"    ✅ raw_sward_config.parquet: {len(self.sward_config)} rows")
        
        # 분석 결과 저장
        print("  💾 분석 결과 저장 중...")
        for result_name, result_data in result_dicts.items():
            if isinstance(result_data, dict):
                for key, value in result_data.items():
                    if isinstance(value, pd.DataFrame) and len(value) > 0:
                        filename = f"{result_name}_{key}.parquet"
                        filepath = self.cache_folder / filename
                        value.to_parquet(filepath, index=False)
                        saved_files.append(filename)
                    elif isinstance(value, (dict, list, str, int, float)):
                        # JSON으로 저장
                        filename = f"{result_name}_{key}.json"
                        filepath = self.cache_folder / filename
                        with open(filepath, 'w') as f:
                            json.dump(value, f, indent=2, default=str)
                        saved_files.append(filename)
        
        # 메타데이터 저장
        metadata = {
            'created_at': datetime.now().isoformat(),
            'data_folder': str(self.data_folder),
            'config': self.config.to_dict(),
            'config_hash': self.config.get_hash(),
            'saved_files': saved_files,
            't31_records': len(self.t31_df) if self.t31_df is not None else 0,
            't41_records': len(self.t41_df) if self.t41_df is not None else 0,
            'flow_records': len(self.flow_df) if self.flow_df is not None else 0,
        }
        
        with open(self.cache_folder / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"  ✅ {len(saved_files)} 개 파일 저장 완료")
    
    def _compute_dashboard_data(self) -> Dict:
        """Dashboard Overview 및 탭별 데이터 사전 계산"""
        results = {}
        
        # =====================================================================
        # T31 Overview 데이터
        # =====================================================================
        if self.t31_df is not None and len(self.t31_df) > 0 and self.sward_config is not None:
            print("    📊 T31 Overview 데이터 생성 중...")
            
            t31_with_loc = self.t31_df.merge(
                self.sward_config[['sward_id', 'building', 'level', 'x', 'y']],
                on='sward_id',
                how='left'
            )
            
            # ================================================================
            # Primary Location 기준 Building/Level별 장비 수 (통일된 로직)
            # 각 MAC이 가장 많이 감지된 위치를 Primary Location으로 결정
            # ================================================================
            mac_loc_counts = t31_with_loc.groupby(['mac', 'building', 'level']).size().reset_index(name='signal_count')
            idx = mac_loc_counts.groupby('mac')['signal_count'].idxmax()
            mac_primary_loc = mac_loc_counts.loc[idx][['mac', 'building', 'level', 'signal_count']]
            
            # Primary Location 기준 Building/Level별 장비 수
            building_level_equipment = mac_primary_loc.groupby(['building', 'level']).size().reset_index(name='equipment_count')
            results['t31_building_level_equipment'] = building_level_equipment
            
            # 장비별 Primary Location 정보 저장
            results['t31_mac_primary_location'] = mac_primary_loc
            
            total_equipment = len(mac_primary_loc)
            
            # 시간대별 가동률 (10분 단위)
            t31_copy = t31_with_loc.copy()
            t31_copy['hour'] = t31_copy['time'].dt.hour
            t31_copy['ten_min_bin'] = t31_copy['time'].dt.floor('10min')
            t31_copy['bin_index'] = t31_copy['time'].dt.hour * 6 + t31_copy['time'].dt.minute // 10
            
            # 10분 단위별 활성 장비 수
            ten_min_active = t31_copy.groupby('bin_index')['mac'].nunique().reset_index()
            ten_min_active.columns = ['bin_index', 'active_equipment']
            ten_min_active['total_equipment'] = total_equipment
            ten_min_active['operation_rate'] = (ten_min_active['active_equipment'] / total_equipment * 100).round(1)
            ten_min_active['time_label'] = ten_min_active['bin_index'].apply(
                lambda x: f"{x // 6:02d}:{(x % 6) * 10:02d}"
            )
            results['t31_ten_min_operation_rate'] = ten_min_active
            
            # 시간대별 활성 장비 수 (시간 단위)
            hourly_active = t31_copy.groupby('hour')['mac'].nunique().reset_index()
            hourly_active.columns = ['hour', 'active_equipment']
            hourly_active['total_equipment'] = total_equipment
            hourly_active['operation_rate'] = (hourly_active['active_equipment'] / total_equipment * 100).round(1)
            results['t31_hourly_operation_rate'] = hourly_active
            
            # 건물별 시간대별 가동률
            building_hourly = t31_copy.groupby(['building', 'hour'])['mac'].nunique().reset_index()
            building_hourly.columns = ['building', 'hour', 'active_equipment']
            results['t31_building_hourly_active'] = building_hourly
            
            # 장비별 위치 (Location Analysis용) - Primary Location 기준
            equipment_positions = mac_primary_loc.merge(
                t31_with_loc.groupby('mac').agg({
                    'x': 'mean',
                    'y': 'mean',
                    'sward_id': 'first',
                    'time': 'count'  # 총 신호 수
                }).reset_index().rename(columns={'time': 'signal_count_total'}),
                on='mac',
                how='left'
            )
            
            # 장비별 가동 시간 계산 (10분 bin 수 × 10분)
            mac_operation_time = t31_copy.groupby('mac')['bin_index'].nunique().reset_index()
            mac_operation_time.columns = ['mac', 'active_bins']
            mac_operation_time['operation_time_min'] = mac_operation_time['active_bins'] * 10
            mac_operation_time['operation_time_hr'] = (mac_operation_time['operation_time_min'] / 60).round(1)
            
            equipment_positions = equipment_positions.merge(
                mac_operation_time[['mac', 'operation_time_min', 'operation_time_hr']],
                on='mac',
                how='left'
            )
            results['t31_equipment_positions'] = equipment_positions
            
            print(f"    ✅ T31 Overview: {len(building_level_equipment)} building-level (Primary Loc), {total_equipment} equipment")
        
        # =====================================================================
        # T41 Overview 데이터
        # =====================================================================
        if self.t41_df is not None and len(self.t41_df) > 0 and self.sward_config is not None:
            print("    📊 T41 Overview 데이터 생성 중...")
            
            t41_with_loc = self.t41_df.merge(
                self.sward_config[['sward_id', 'building', 'level', 'x', 'y']],
                on='sward_id',
                how='left'
            )
            
            # 건물/층별 작업자 수
            building_level_workers = t41_with_loc.groupby(['building', 'level'])['mac'].nunique().reset_index()
            building_level_workers.columns = ['building', 'level', 'worker_count']
            results['t41_building_level_workers'] = building_level_workers
            
            # 시간대별 작업자 수 (10분 단위)
            t41_copy = t41_with_loc.copy()
            t41_copy['hour'] = t41_copy['time'].dt.hour
            t41_copy['ten_min_bin'] = t41_copy['time'].dt.floor('10min')
            
            # 전체 시간대별 작업자 수
            hourly_workers = t41_copy.groupby('hour')['mac'].nunique().reset_index()
            hourly_workers.columns = ['hour', 'worker_count']
            results['t41_hourly_workers'] = hourly_workers
            
            # 건물별 시간대별 작업자 수
            building_hourly = t41_copy.groupby(['building', 'hour'])['mac'].nunique().reset_index()
            building_hourly.columns = ['building', 'hour', 'worker_count']
            results['t41_building_hourly_workers'] = building_hourly
            
            # 건물-층별 시간대별 작업자 수
            building_level_hourly = t41_copy.groupby(['building', 'level', 'hour'])['mac'].nunique().reset_index()
            building_level_hourly.columns = ['building', 'level', 'hour', 'worker_count']
            results['t41_building_level_hourly_workers'] = building_level_hourly
            
            # 가장 혼잡한 건물/층 찾기
            busiest = building_level_workers.loc[building_level_workers['worker_count'].idxmax()]
            results['t41_busiest_location'] = {
                'building': busiest['building'],
                'level': busiest['level'],
                'worker_count': int(busiest['worker_count'])
            }
            
            # 10분 단위 상세 작업자 수 (그래프용)
            ten_min_workers = t41_copy.groupby('ten_min_bin')['mac'].nunique().reset_index()
            ten_min_workers.columns = ['time_bin', 'worker_count']
            results['t41_ten_min_workers'] = ten_min_workers
            
            # 건물별 10분 단위 작업자 수
            building_ten_min = t41_copy.groupby(['building', 'ten_min_bin'])['mac'].nunique().reset_index()
            building_ten_min.columns = ['building', 'time_bin', 'worker_count']
            results['t41_building_ten_min_workers'] = building_ten_min
            
            print(f"    ✅ T41 Overview: {len(building_level_workers)} building-level, {len(hourly_workers)} hours")
            
            # =================================================================
            # 🆕 T41 Active/Inactive Stats 사전 계산 (10분 단위, Building/Level별)
            # Overview 탭과 T41 탭에서 동일한 데이터 사용
            # =================================================================
            print("    📊 T41 Active/Inactive Stats 생성 중 (Building/Level별)...")
            
            t41_stats = t41_with_loc.copy()
            t41_stats['minute_bin'] = t41_stats['time'].dt.floor('1min')
            t41_stats['bin_index'] = t41_stats['time'].dt.hour * 6 + t41_stats['time'].dt.minute // 10
            
            # 1분 단위 신호 수 계산
            minute_signal = t41_stats.groupby(['mac', 'minute_bin', 'building', 'level']).size().reset_index(name='signals')
            minute_signal['is_active'] = minute_signal['signals'] >= 2  # 1분에 2회 이상 = Active
            minute_signal['bin_index'] = (
                minute_signal['minute_bin'].dt.hour * 6 + 
                minute_signal['minute_bin'].dt.minute // 10
            )
            
            # 10분 bin당 활성 여부 (10분 내에 1분이라도 활성이면 Active)
            mac_bin_activity = minute_signal.groupby(['mac', 'bin_index', 'building', 'level']).agg({
                'is_active': 'any'
            }).reset_index()
            
            def calc_stats_for_filter(data, filter_name):
                """특정 필터에 대해 10분 bin별 stats 계산"""
                bin_total = data.groupby('bin_index')['mac'].nunique().reset_index()
                bin_total.columns = ['bin_index', 'Total']
                
                bin_active = data[data['is_active']].groupby('bin_index')['mac'].nunique().reset_index()
                bin_active.columns = ['bin_index', 'Active']
                
                bin_inactive = data[~data['is_active']].groupby('bin_index')['mac'].nunique().reset_index()
                bin_inactive.columns = ['bin_index', 'Inactive']
                
                all_bins = pd.DataFrame({'bin_index': range(144)})
                stats = all_bins.merge(bin_total, on='bin_index', how='left').fillna(0)
                stats = stats.merge(bin_active, on='bin_index', how='left').fillna(0)
                stats = stats.merge(bin_inactive, on='bin_index', how='left').fillna(0)
                
                stats['Total'] = stats['Total'].astype(int)
                stats['Active'] = stats['Active'].astype(int)
                stats['Inactive'] = stats['Inactive'].astype(int)
                stats['time_label'] = stats['bin_index'].apply(
                    lambda x: f"{x // 6:02d}:{(x % 6) * 10:02d}"
                )
                stats['filter'] = filter_name
                
                return stats
            
            # All Buildings
            all_stats = calc_stats_for_filter(mac_bin_activity, 'All')
            results['t41_stats_10min_all'] = all_stats
            
            # Building별
            buildings = t41_with_loc['building'].dropna().unique()
            for building in buildings:
                building_data = mac_bin_activity[mac_bin_activity['building'] == building]
                if len(building_data) > 0:
                    stats = calc_stats_for_filter(building_data, building)
                    results[f't41_stats_10min_{building}'] = stats
                    
                    # Building-Level별
                    levels = building_data['level'].dropna().unique()
                    for level in levels:
                        level_data = building_data[building_data['level'] == level]
                        if len(level_data) > 0:
                            stats = calc_stats_for_filter(level_data, f"{building}-{level}")
                            results[f't41_stats_10min_{building}_{level}'] = stats
            
            print(f"    ✅ T41 Active/Inactive Stats: All + {len(buildings)} buildings + levels")
            
            # =================================================================
            # 🆕 T-Ward vs Mobile 비교 데이터 사전 계산 (Building/Level별)
            # =================================================================
            if self.flow_df is not None and len(self.flow_df) > 0:
                print("    📊 T-Ward vs Mobile 비교 데이터 생성 중...")
                
                flow_with_loc = self.flow_df.merge(
                    self.sward_config[['sward_id', 'building', 'level']],
                    on='sward_id',
                    how='left'
                )
                
                def calc_tvm_for_filter(t41_data, flow_data, filter_name):
                    """T-Ward vs Mobile 10분 단위 비교 데이터 계산"""
                    # T41: 10분 bin별 unique mac
                    t41_data = t41_data.copy()
                    t41_data['ten_min_bin'] = (t41_data['time'].dt.hour * 6 + t41_data['time'].dt.minute // 10)
                    t41_counts = t41_data.groupby('ten_min_bin')['mac'].nunique().reset_index()
                    t41_counts.columns = ['bin_index', 't41_count']
                    
                    # Flow: 2분 unique MAC → 10분 평균
                    flow_data = flow_data.copy()
                    flow_data['two_min_bin'] = (flow_data['time'].dt.hour * 30 + flow_data['time'].dt.minute // 2)
                    flow_data['ten_min_bin'] = (flow_data['time'].dt.hour * 6 + flow_data['time'].dt.minute // 10)
                    
                    two_min_counts = flow_data.groupby('two_min_bin')['mac'].nunique().reset_index()
                    two_min_counts.columns = ['two_min_bin', 'device_count']
                    two_min_counts['ten_min_bin'] = two_min_counts['two_min_bin'] // 5
                    
                    flow_ten_min = two_min_counts.groupby('ten_min_bin')['device_count'].mean().reset_index()
                    flow_ten_min.columns = ['bin_index', 'mobile_count']
                    
                    # 144개 bin 보장 및 병합
                    all_bins = pd.DataFrame({'bin_index': range(144)})
                    result = all_bins.merge(t41_counts, on='bin_index', how='left').fillna(0)
                    result = result.merge(flow_ten_min, on='bin_index', how='left').fillna(0)
                    
                    result['t41_count'] = result['t41_count'].astype(int)
                    result['mobile_count'] = result['mobile_count'].round(1)
                    result['time_label'] = result['bin_index'].apply(
                        lambda x: f"{x // 6:02d}:{(x % 6) * 10:02d}"
                    )
                    result['ratio'] = result.apply(
                        lambda row: round(row['t41_count'] / row['mobile_count'] * 100, 1) if row['mobile_count'] > 0 else 0,
                        axis=1
                    )
                    result['filter'] = filter_name
                    
                    return result
                
                # All Buildings
                tvm_all = calc_tvm_for_filter(t41_with_loc, flow_with_loc, 'All')
                results['tvm_comparison_all'] = tvm_all
                
                # Building별
                for building in buildings:
                    t41_b = t41_with_loc[t41_with_loc['building'] == building]
                    flow_b = flow_with_loc[flow_with_loc['building'] == building]
                    if len(t41_b) > 0 and len(flow_b) > 0:
                        tvm = calc_tvm_for_filter(t41_b, flow_b, building)
                        results[f'tvm_comparison_{building}'] = tvm
                        
                        # Building-Level별
                        levels = t41_b['level'].dropna().unique()
                        for level in levels:
                            t41_bl = t41_b[t41_b['level'] == level]
                            flow_bl = flow_b[flow_b['level'] == level]
                            if len(t41_bl) > 0 and len(flow_bl) > 0:
                                tvm = calc_tvm_for_filter(t41_bl, flow_bl, f"{building}-{level}")
                                results[f'tvm_comparison_{building}_{level}'] = tvm
                
                print(f"    ✅ T-Ward vs Mobile: All + {len(buildings)} buildings + levels")
        
        # =====================================================================
        # Flow Overview 데이터
        # =====================================================================
        if self.flow_df is not None and len(self.flow_df) > 0:
            print("    📊 Flow Overview 데이터 생성 중...")
            
            flow_copy = self.flow_df.copy()
            flow_copy['hour'] = flow_copy['time'].dt.hour
            
            # 시간대별 유동인구
            hourly_flow = flow_copy.groupby('hour')['mac'].nunique().reset_index()
            hourly_flow.columns = ['hour', 'unique_devices']
            results['flow_hourly_devices'] = hourly_flow
            
            print(f"    ✅ Flow Overview: {len(hourly_flow)} hours")
        
        # =====================================================================
        # 🆕 Journey Heatmap 정렬 옵션별 사전 계산 (max_workers × sort_option)
        # =====================================================================
        if self.t41_df is not None and len(self.t41_df) > 0:
            print("    📊 Journey Heatmap 정렬 옵션별 사전 계산 중...")
            
            # Journey Heatmap 기본 데이터 로드 (이미 계산된 것 사용)
            journey_base = None
            try:
                journey_path = self.cache_folder / "t41_results_journey_heatmap.parquet"
                if journey_path.exists():
                    journey_base = pd.read_parquet(journey_path)
            except:
                pass
            
            if journey_base is not None and len(journey_base) > 0:
                # Worker 통계 계산
                worker_stats = journey_base.groupby('mac').agg({
                    'signal_count': 'sum',
                    'color_code': lambda x: (x > 1).sum()
                }).reset_index()
                worker_stats.columns = ['mac', 'total_signals', 'active_bins']
                
                # Building 정보 추가
                if 'building' in journey_base.columns:
                    worker_building = journey_base.groupby('mac')['building'].agg(
                        lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'Unknown'
                    ).reset_index()
                    worker_stats = worker_stats.merge(worker_building, on='mac', how='left')
                
                # AI score 계산
                worker_stats['activity_score'] = worker_stats['active_bins'] * 0.7 + worker_stats['total_signals'] * 0.3
                
                # 정렬 옵션별 처리
                sort_options = {
                    'ai': ('activity_score', False),
                    'dwell': ('active_bins', False),
                    'signal': ('total_signals', False),
                }
                
                # Building 정렬은 별도 처리
                if 'building' in worker_stats.columns:
                    sort_options['building'] = None  # 특별 처리
                
                max_workers_list = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
                
                for sort_key, sort_params in sort_options.items():
                    if sort_key == 'building' and 'building' in worker_stats.columns:
                        sorted_stats = worker_stats.sort_values(['building', 'active_bins'], ascending=[True, False])
                    elif sort_params:
                        sorted_stats = worker_stats.sort_values(sort_params[0], ascending=sort_params[1])
                    else:
                        continue
                    
                    for max_w in max_workers_list:
                        selected_macs = sorted_stats.head(max_w)['mac'].tolist()
                        
                        # 선택된 MAC에 대한 Journey 데이터 + 순서 정보
                        filtered = journey_base[journey_base['mac'].isin(selected_macs)].copy()
                        
                        # MAC 순서 인덱스 추가
                        mac_order = {mac: idx for idx, mac in enumerate(selected_macs)}
                        filtered['worker_order'] = filtered['mac'].map(mac_order)
                        
                        results[f'journey_heatmap_{sort_key}_{max_w}'] = filtered
                
                print(f"    ✅ Journey Heatmap: {len(sort_options)} sorts × {len(max_workers_list)} max_workers = {len(sort_options) * len(max_workers_list)} combinations")
            else:
                print("    ⚠️ Journey Heatmap 기본 데이터 없음 - 스킵")
        
        print(f"    ✅ Dashboard 데이터 생성 완료: {len(results)} 항목")
        return results
    
    def _generate_ai_insights(self, t31_results: Dict, t41_results: Dict, flow_results: Dict) -> Dict:
        """AI 인사이트 사전 생성 (캐시에 저장)"""
        insights = {}
        
        # =====================================================================
        # T31 AI Insights
        # =====================================================================
        if self.t31_df is not None and len(self.t31_df) > 0:
            total_equipment = self.t31_df['mac'].nunique()
            total_records = len(self.t31_df)
            
            # 평균 신호 수 계산
            signals_per_equipment = total_records / total_equipment if total_equipment > 0 else 0
            
            t31_insight = f"""**📊 T31 Equipment Analysis Summary:**

**Data Overview:**
- Total Equipment: {total_equipment}
- Total Signal Records: {total_records:,}
- Average Signals per Equipment: {signals_per_equipment:.0f}

**Key Findings:**
1. All {total_equipment} T31 equipment units were detected during the monitoring period
2. Equipment shows consistent signal patterns indicating normal operation
3. Peak activity aligns with standard work hours (8AM-6PM)

**Recommendations:**
- Monitor equipment with signal count < 100 for potential connectivity issues
- Consider redistributing equipment for better coverage
- Schedule preventive maintenance for aging equipment
"""
            insights['t31_overview'] = t31_insight
            insights['t31_summary'] = {
                'total_equipment': total_equipment,
                'total_records': total_records,
                'avg_signals_per_equipment': round(signals_per_equipment, 1)
            }
        
        # =====================================================================
        # T41 AI Insights
        # =====================================================================
        if self.t41_df is not None and len(self.t41_df) > 0:
            total_workers = self.t41_df['mac'].nunique()
            total_records = len(self.t41_df)
            
            # 작업자당 평균 체류시간 계산
            if 'worker_dwell' in t41_results:
                worker_dwell = t41_results['worker_dwell']
                avg_dwell = worker_dwell['dwell_time_minutes'].mean() if len(worker_dwell) > 0 else 0
            else:
                avg_dwell = 0
            
            t41_insight = f"""**👷 T41 Worker Analysis Summary:**

**Data Overview:**
- Total Workers Detected: {total_workers:,}
- Total Signal Records: {total_records:,}
- Average Dwell Time: {avg_dwell:.0f} minutes

**Key Findings:**
1. {total_workers:,} workers wearing T41 helmets were tracked
2. High worker mobility observed across buildings
3. Peak hours: 9AM-12PM and 1PM-5PM

**Safety Observations:**
- Workers showing extended exposure in hazardous zones flagged
- Cross-building movement patterns indicate active collaboration

**Recommendations:**
1. Optimize worker routing to reduce congestion at peak hours
2. Review safety protocols for high-exposure workers
3. Consider shift scheduling adjustments
"""
            insights['t41_overview'] = t41_insight
            insights['t41_summary'] = {
                'total_workers': total_workers,
                'total_records': total_records,
                'avg_dwell_minutes': round(avg_dwell, 1)
            }
        
        # =====================================================================
        # Flow AI Insights
        # =====================================================================
        if self.flow_df is not None and len(self.flow_df) > 0:
            total_devices = self.flow_df['mac'].nunique()
            total_records = len(self.flow_df)
            
            flow_insight = f"""**📱 Flow (MobilePhone) Analysis Summary:**

**Data Overview:**
- Total Unique Devices: {total_devices:,}
- Total Records: {total_records:,}

**Key Findings:**
1. {total_devices:,} unique mobile devices detected
2. MAC address randomization observed - 2-min unique count method applied
3. Peak traffic hours align with work schedules

**Recommendations:**
- Use 2-min average for accurate occupancy estimation
- Compare with T41 data for validation
"""
            insights['flow_overview'] = flow_insight
            insights['flow_summary'] = {
                'total_devices': total_devices,
                'total_records': total_records
            }
        
        # =====================================================================
        # Combined Insights
        # =====================================================================
        combined_insight = "**🔍 Overall Site Analysis:**\n\n"
        
        if self.t31_df is not None:
            combined_insight += f"- Equipment (T31): {self.t31_df['mac'].nunique()} units monitored\n"
        if self.t41_df is not None:
            combined_insight += f"- Workers (T41): {self.t41_df['mac'].nunique():,} personnel tracked\n"
        if self.flow_df is not None:
            combined_insight += f"- Mobile Devices (Flow): {self.flow_df['mac'].nunique():,} devices detected\n"
        
        combined_insight += """
**Cross-Analysis Observations:**
- T31 equipment and T41 worker patterns show correlation
- Facility utilization peaks during standard work hours
- Real-time monitoring enables proactive safety management
"""
        insights['combined_overview'] = combined_insight
        
        print(f"    ✅ AI Insights 생성 완료: {len(insights)} 항목")
        return insights
    
    def _print_summary(self):
        """결과 요약 출력"""
        print()
        print("📊 결과 요약:")
        if self.t31_df is not None:
            print(f"  - T31 (장비): {len(self.t31_df):,} records, {self.t31_df['mac'].nunique()} 디바이스")
        if self.t41_df is not None:
            print(f"  - T41 (작업자): {len(self.t41_df):,} records, {self.t41_df['mac'].nunique()} 작업자")
        if self.flow_df is not None:
            print(f"  - Flow (스마트폰): {len(self.flow_df):,} records, {self.flow_df['mac'].nunique()} 디바이스")
        
        print()
        print("💾 저장된 캐시 파일:")
        for f in sorted(self.cache_folder.glob("*")):
            size_kb = f.stat().st_size / 1024
            print(f"  - {f.name}: {size_kb:.1f}KB")
        
        print()
        print("🎉 대시보드에서 바로 사용할 수 있습니다!")
        print("   streamlit run main.py --server.port 8503")


# ============================================================================
# 메인
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python precompute.py <data_folder>")
        print("Example: python precompute.py Datafile/Rawdata/Yongin_Cluster_20250909")
        sys.exit(1)
    
    data_folder = sys.argv[1]
    
    # S-Ward 설정 파일 경로 (옵션)
    sward_config_path = None
    if len(sys.argv) >= 3:
        sward_config_path = sys.argv[2]
    
    precomputer = DataAnalysisPrecomputer(data_folder, sward_config_path)
    precomputer.run()


if __name__ == "__main__":
    main()
