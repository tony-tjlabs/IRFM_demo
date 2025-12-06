"""
SKEP DataAnalysis - Cached Data Loader
======================================

사전 처리된 캐시 데이터를 로드하는 클래스
Dashboard Mode에서 빠른 데이터 접근을 위해 사용
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd


class CachedDataLoader:
    """캐시된 분석 데이터 로더"""
    
    def __init__(self, cache_folder: str):
        self.cache_folder = Path(cache_folder)
        self._cache: Dict[str, Any] = {}
        self._metadata: Optional[Dict] = None
    
    def is_valid(self) -> bool:
        """캐시가 유효한지 확인"""
        metadata_path = self.cache_folder / "metadata.json"
        return metadata_path.exists()
    
    def get_metadata(self) -> Dict:
        """메타데이터 로드"""
        if self._metadata is None:
            metadata_path = self.cache_folder / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    self._metadata = json.load(f)
            else:
                self._metadata = {}
        return self._metadata
    
    def _load_parquet(self, filename: str) -> pd.DataFrame:
        """Parquet 파일 로드 (캐싱)"""
        if filename not in self._cache:
            path = self.cache_folder / filename
            if path.exists():
                self._cache[filename] = pd.read_parquet(path)
            else:
                self._cache[filename] = pd.DataFrame()
        return self._cache[filename]
    
    def _load_json(self, filename: str) -> Any:
        """JSON 파일 로드 (캐싱)"""
        if filename not in self._cache:
            path = self.cache_folder / filename
            if path.exists():
                with open(path, 'r') as f:
                    self._cache[filename] = json.load(f)
            else:
                self._cache[filename] = {}
        return self._cache[filename]
    
    # ========== T31 (장비) 데이터 ==========
    
    def load_t31_hourly_activity(self) -> pd.DataFrame:
        """T31 시간대별 활동"""
        return self._load_parquet("t31_results_hourly_activity.parquet")
    
    def load_t31_device_stats(self) -> pd.DataFrame:
        """T31 장비별 통계"""
        return self._load_parquet("t31_results_device_stats.parquet")
    
    def load_t31_sward_activity(self) -> pd.DataFrame:
        """T31 S-Ward별 활동"""
        return self._load_parquet("t31_results_sward_activity.parquet")
    
    def load_t31_two_min_unique(self) -> pd.DataFrame:
        """T31 2분 단위 unique MAC 카운트"""
        return self._load_parquet("t31_results_two_min_unique_mac.parquet")
    
    def load_t31_operation_heatmap(self) -> pd.DataFrame:
        """T31 Operation Heatmap 데이터 (10분 단위)"""
        return self._load_parquet("t31_results_operation_heatmap.parquet")
    
    # ========== T41 (작업자) 데이터 ==========
    
    def load_t41_occupancy(self) -> pd.DataFrame:
        """T41 시간대별 작업자 수"""
        return self._load_parquet("t41_results_occupancy.parquet")
    
    def load_t41_worker_dwell(self) -> pd.DataFrame:
        """T41 작업자별 체류시간"""
        return self._load_parquet("t41_results_worker_dwell.parquet")
    
    def load_t41_building_occupancy(self) -> pd.DataFrame:
        """T41 Building/Level별 작업자 수"""
        return self._load_parquet("t41_results_building_occupancy.parquet")
    
    def load_t41_space_type_stats(self) -> pd.DataFrame:
        """T41 공간 유형별 통계"""
        return self._load_parquet("t41_results_space_type_stats.parquet")
    
    def load_t41_journey_data(self) -> pd.DataFrame:
        """T41 작업자 이동 경로"""
        return self._load_parquet("t41_results_journey_data.parquet")
    
    def load_t41_activity_analysis(self) -> pd.DataFrame:
        """T41 1분 단위 활동 분석 (Journey Heatmap용)"""
        return self._load_parquet("t41_results_activity_analysis.parquet")
    
    def load_t41_journey_heatmap(self) -> pd.DataFrame:
        """T41 Journey Heatmap 전용 precomputed 데이터 (10분 단위)
        
        Returns:
            DataFrame with columns: mac, bin_index, building_level, building, level, signal_count, color_code
        """
        return self._load_parquet("t41_results_journey_heatmap.parquet")
    
    def load_t41_two_min_unique(self) -> pd.DataFrame:
        """T41 2분 단위 unique MAC 카운트"""
        return self._load_parquet("t41_results_two_min_unique_mac.parquet")
    
    def load_t41_hourly_avg_from_2min(self) -> pd.DataFrame:
        """T41 시간대별 평균 (2분 단위 기반)"""
        return self._load_parquet("t41_results_hourly_avg_from_2min.parquet")
    
    def get_t41_worker_counts(self) -> Dict[str, int]:
        """T41 작업자 수 (필터링 전/후)"""
        total = self._load_json("t41_results_total_worker_count.json")
        filtered = self._load_json("t41_results_filtered_worker_count.json")
        return {
            'total': total if isinstance(total, int) else 0,
            'filtered': filtered if isinstance(filtered, int) else 0
        }
    
    # ========== Flow (스마트폰) 데이터 ==========
    
    def load_flow_hourly(self) -> pd.DataFrame:
        """Flow 시간대별 유동인구"""
        return self._load_parquet("flow_results_hourly_flow.parquet")
    
    def load_flow_device_stats(self) -> pd.DataFrame:
        """Flow 디바이스별 통계"""
        return self._load_parquet("flow_results_device_stats.parquet")
    
    def load_flow_sward(self) -> pd.DataFrame:
        """Flow S-Ward별 유동인구"""
        return self._load_parquet("flow_results_sward_flow.parquet")
    
    def load_flow_two_min_unique(self) -> pd.DataFrame:
        """Flow 2분 단위 unique MAC 카운트 (핵심)"""
        return self._load_parquet("flow_results_two_min_unique_mac.parquet")
    
    def load_flow_hourly_avg_from_2min(self) -> pd.DataFrame:
        """Flow 시간대별 평균 (2분 단위 기반)"""
        return self._load_parquet("flow_results_hourly_avg_from_2min.parquet")
    
    def load_flow_ten_min_unique(self) -> pd.DataFrame:
        """Flow 10분 단위 unique MAC 카운트"""
        return self._load_parquet("flow_results_ten_min_unique.parquet")
    
    def load_flow_device_type_stats(self) -> pd.DataFrame:
        """Flow 디바이스 타입별 통계 (Apple/Android)"""
        return self._load_parquet("flow_results_device_type_stats.parquet")
    
    # ========== 통합 데이터 ==========
    
    def get_summary(self) -> Dict:
        """전체 데이터 요약"""
        return self._load_json("combined_results_summary.json")
    
    # ========== Dashboard Overview 데이터 ==========
    
    def load_t31_building_level_equipment(self) -> pd.DataFrame:
        """T31 건물/층별 장비 수 (Primary Location 기준)"""
        return self._load_parquet("dashboard_results_t31_building_level_equipment.parquet")
    
    def load_t31_mac_primary_location(self) -> pd.DataFrame:
        """T31 MAC별 Primary Location 정보"""
        return self._load_parquet("dashboard_results_t31_mac_primary_location.parquet")
    
    def load_t31_ten_min_operation_rate(self) -> pd.DataFrame:
        """T31 10분 단위 가동률"""
        return self._load_parquet("dashboard_results_t31_ten_min_operation_rate.parquet")
    
    def load_t31_hourly_operation_rate(self) -> pd.DataFrame:
        """T31 시간대별 가동률"""
        return self._load_parquet("dashboard_results_t31_hourly_operation_rate.parquet")
    
    def load_t31_building_hourly_active(self) -> pd.DataFrame:
        """T31 건물별 시간대별 활성 장비"""
        return self._load_parquet("dashboard_results_t31_building_hourly_active.parquet")
    
    def load_t31_equipment_positions(self) -> pd.DataFrame:
        """T31 장비 위치 좌표"""
        return self._load_parquet("dashboard_results_t31_equipment_positions.parquet")
    
    def load_t41_building_level_workers(self) -> pd.DataFrame:
        """T41 건물/층별 작업자 수"""
        return self._load_parquet("dashboard_results_t41_building_level_workers.parquet")
    
    def load_t41_hourly_workers(self) -> pd.DataFrame:
        """T41 시간대별 작업자 수"""
        return self._load_parquet("dashboard_results_t41_hourly_workers.parquet")
    
    def load_t41_building_hourly_workers(self) -> pd.DataFrame:
        """T41 건물별 시간대별 작업자 수"""
        return self._load_parquet("dashboard_results_t41_building_hourly_workers.parquet")
    
    def load_t41_building_level_hourly_workers(self) -> pd.DataFrame:
        """T41 건물-층별 시간대별 작업자 수"""
        return self._load_parquet("dashboard_results_t41_building_level_hourly_workers.parquet")
    
    def get_t41_busiest_location(self) -> Dict:
        """T41 가장 혼잡한 위치"""
        return self._load_json("dashboard_results_t41_busiest_location.json")
    
    def load_t41_ten_min_workers(self) -> pd.DataFrame:
        """T41 10분 단위 작업자 수"""
        return self._load_parquet("dashboard_results_t41_ten_min_workers.parquet")
    
    def load_t41_building_ten_min_workers(self) -> pd.DataFrame:
        """T41 건물별 10분 단위 작업자 수"""
        return self._load_parquet("dashboard_results_t41_building_ten_min_workers.parquet")
    
    # ========== T41 Active/Inactive Stats (10분 단위, Building/Level별) ==========
    
    def load_t41_stats_10min(self, building: str = "All", level: str = "All") -> pd.DataFrame:
        """T41 10분 단위 Active/Inactive Stats 로드
        
        Args:
            building: "All" 또는 특정 빌딩명 (예: "WWT", "FAB")
            level: "All" 또는 특정 층 (예: "1F", "B1F")
            
        Returns:
            DataFrame with columns: [bin_index, Total, Active, Inactive, time_label, filter]
        """
        if building == "All":
            return self._load_parquet("dashboard_results_t41_stats_10min_all.parquet")
        elif level == "All":
            return self._load_parquet(f"dashboard_results_t41_stats_10min_{building}.parquet")
        else:
            return self._load_parquet(f"dashboard_results_t41_stats_10min_{building}_{level}.parquet")
    
    def get_available_t41_stats_filters(self) -> List[str]:
        """사용 가능한 T41 Stats 필터 목록"""
        filters = ["All"]
        for f in self.cache_folder.glob("dashboard_results_t41_stats_10min_*.parquet"):
            name = f.stem.replace("dashboard_results_t41_stats_10min_", "")
            if name != "all":
                filters.append(name.replace("_", "-"))
        return sorted(filters)

    # ========== T-Ward vs Mobile 비교 데이터 ==========
    
    def load_tvm_comparison(self, building: str = "All", level: str = "All") -> pd.DataFrame:
        """T-Ward vs Mobile 비교 데이터 로드
        
        Args:
            building: "All" 또는 특정 빌딩명
            level: "All" 또는 특정 층
            
        Returns:
            DataFrame with columns: [bin_index, t41_count, mobile_count, time_label, ratio, filter]
        """
        if building == "All":
            return self._load_parquet("dashboard_results_tvm_comparison_all.parquet")
        elif level == "All":
            return self._load_parquet(f"dashboard_results_tvm_comparison_{building}.parquet")
        else:
            return self._load_parquet(f"dashboard_results_tvm_comparison_{building}_{level}.parquet")

    # ========== Journey Heatmap 사전 계산 데이터 ==========
    
    def load_journey_heatmap_sorted(self, sort_option: str = "ai", max_workers: int = 200) -> pd.DataFrame:
        """정렬된 Journey Heatmap 데이터 로드
        
        Args:
            sort_option: "ai", "dwell", "building", "signal"
            max_workers: 50, 100, 150, 200, 250, 300, 350, 400, 450, 500
            
        Returns:
            DataFrame with worker order and color codes
        """
        filename = f"dashboard_results_journey_heatmap_{sort_option}_{max_workers}.parquet"
        return self._load_parquet(filename)
    
    def get_available_journey_options(self) -> Dict:
        """사용 가능한 Journey Heatmap 옵션"""
        sort_options = []
        max_workers_options = []
        
        for f in self.cache_folder.glob("dashboard_results_journey_heatmap_*.parquet"):
            name = f.stem.replace("dashboard_results_journey_heatmap_", "")
            parts = name.rsplit("_", 1)
            if len(parts) == 2:
                sort_options.append(parts[0])
                max_workers_options.append(int(parts[1]))
        
        return {
            'sort_options': list(set(sort_options)),
            'max_workers': sorted(list(set(max_workers_options)))
        }

    def load_flow_hourly_devices(self) -> pd.DataFrame:
        """Flow 시간대별 유동인구"""
        return self._load_parquet("dashboard_results_flow_hourly_devices.parquet")
    
    # ========== AI Insights ==========
    
    def load_ai_insights(self, data_type: str = 't41') -> Optional[Dict]:
        """AI 인사이트 로드 (통합 인터페이스)
        
        Args:
            data_type: 't31', 't41', 'flow', 'combined'
        """
        if data_type == 't31':
            return self._load_json("ai_insights_t31_overview.json")
        elif data_type == 't41':
            return self._load_json("ai_insights_t41_overview.json")
        elif data_type == 'flow':
            return self._load_json("ai_insights_flow_overview.json")
        elif data_type == 'combined':
            return self._load_json("ai_insights_combined_overview.json")
        return None
    
    def get_t41_congestion_info(self) -> Optional[Dict]:
        """T41 혼잡도 정보"""
        insights = self._load_json("ai_insights_t41_overview.json")
        # insights가 Dict이고 congestion_score가 있는 경우에만 처리
        if isinstance(insights, dict) and 'congestion_score' in insights:
            return {
                'score': insights.get('congestion_score', 0),
                'level': insights.get('congestion_level', 'Unknown'),
                'peak_time': insights.get('peak_time', 'N/A'),
                'peak_workers': insights.get('peak_workers', 0)
            }
        return None
    
    def get_t31_ai_insight(self) -> str:
        """T31 AI 인사이트 텍스트"""
        return self._load_json("ai_insights_t31_overview.json")
    
    def get_t31_ai_summary(self) -> Dict:
        """T31 AI 요약 데이터"""
        return self._load_json("ai_insights_t31_summary.json")
    
    def get_t41_ai_insight(self) -> str:
        """T41 AI 인사이트 텍스트"""
        return self._load_json("ai_insights_t41_overview.json")
    
    def get_t41_ai_summary(self) -> Dict:
        """T41 AI 요약 데이터"""
        return self._load_json("ai_insights_t41_summary.json")
    
    def get_flow_ai_insight(self) -> str:
        """Flow AI 인사이트 텍스트"""
        return self._load_json("ai_insights_flow_overview.json")
    
    def get_combined_ai_insight(self) -> str:
        """통합 AI 인사이트"""
        return self._load_json("ai_insights_combined_overview.json")
    
    # ========== 히트맵 데이터 ==========
    
    def load_heatmap(self, building: str, level: str) -> pd.DataFrame:
        """특정 Building/Level의 히트맵 데이터"""
        filename = f"heatmap_results_heatmap_t41_{building}_{level}.parquet"
        return self._load_parquet(filename)
    
    def get_available_heatmaps(self) -> List[Dict[str, str]]:
        """사용 가능한 히트맵 목록"""
        heatmaps = []
        for f in self.cache_folder.glob("heatmap_results_heatmap_t41_*.parquet"):
            # 파일명에서 building, level 추출
            name = f.stem.replace("heatmap_results_heatmap_t41_", "")
            parts = name.rsplit("_", 1)
            if len(parts) == 2:
                heatmaps.append({
                    'building': parts[0],
                    'level': parts[1],
                    'filename': f.name
                })
        return heatmaps
    
    # ========== 원본 데이터 로드 (기존 분석 기능 사용을 위해) ==========
    
    def load_raw_t31(self) -> pd.DataFrame:
        """원본 T31 데이터 로드"""
        return self._load_parquet("raw_t31.parquet")
    
    def load_raw_t41(self) -> pd.DataFrame:
        """원본 T41 데이터 로드"""
        return self._load_parquet("raw_t41.parquet")
    
    def load_raw_flow(self) -> pd.DataFrame:
        """원본 Flow 데이터 로드"""
        return self._load_parquet("raw_flow.parquet")
    
    def load_raw_sward_config(self) -> pd.DataFrame:
        """원본 S-Ward 설정 로드"""
        return self._load_parquet("raw_sward_config.parquet")
    
    def has_raw_data(self) -> Dict[str, bool]:
        """원본 데이터 존재 여부 확인"""
        return {
            't31': (self.cache_folder / "raw_t31.parquet").exists(),
            't41': (self.cache_folder / "raw_t41.parquet").exists(),
            'flow': (self.cache_folder / "raw_flow.parquet").exists(),
            'sward_config': (self.cache_folder / "raw_sward_config.parquet").exists(),
        }
    
    def clear_cache(self):
        """메모리 캐시 초기화"""
        self._cache.clear()
        self._metadata = None


def find_available_datasets(base_folder: str = None) -> List[Dict]:
    """사용 가능한 데이터셋 (캐시 있는) 목록"""
    import os
    import streamlit as st
    datasets = []
    
    # 여러 경로 후보 시도 (Streamlit Cloud 호환)
    if base_folder is None:
        path_candidates = []
        
        # 1. 현재 파일 기준 상대 경로
        current_file = Path(__file__).resolve()
        path_candidates.append(current_file.parent.parent / "Datafile" / "Rawdata")
        
        # 2. 현재 작업 디렉토리 기준
        cwd = Path(os.getcwd())
        path_candidates.append(cwd / "Datafile" / "Rawdata")
        
        # 3. Streamlit Cloud 환경 - 여러 케이스 시도
        path_candidates.append(Path("/mount/src/irfm_demo/Datafile/Rawdata"))
        path_candidates.append(Path("/mount/src/IRFM_demo/Datafile/Rawdata"))
        path_candidates.append(Path("/mount/src/irfm-demo/Datafile/Rawdata"))
        path_candidates.append(Path("/app/Datafile/Rawdata"))
        
        # 디버그: 사이드바에 경로 정보 표시
        debug_info = []
        for i, candidate in enumerate(path_candidates):
            exists = candidate.exists()
            debug_info.append(f"{i+1}. {candidate}: {'✅' if exists else '❌'}")
        
        with st.sidebar.expander("🔍 Path Debug", expanded=False):
            st.text("\n".join(debug_info))
            st.text(f"CWD: {os.getcwd()}")
            st.text(f"__file__: {__file__}")
        
        # 유효한 경로 찾기
        base_path = None
        for candidate in path_candidates:
            if candidate.exists():
                base_path = candidate
                break
        
        if base_path is None:
            st.sidebar.warning("No valid data path found!")
            return datasets
    else:
        base_path = Path(base_folder)
        if not base_path.exists():
            return datasets
    
    for folder in base_path.iterdir():
        if folder.is_dir():
            cache_folder = folder / "cache"
            metadata_path = cache_folder / "metadata.json"
            
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                datasets.append({
                    'name': folder.name,
                    'path': str(folder),
                    'cache_path': str(cache_folder),
                    'created_at': metadata.get('created_at', 'Unknown'),
                    't31_records': metadata.get('t31_records', 0),
                    't41_records': metadata.get('t41_records', 0),
                    'flow_records': metadata.get('flow_records', 0),
                })
    
    return datasets

