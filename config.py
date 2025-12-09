"""
SKEP DataAnalysis - Global Configuration
========================================

전역 설정 관리 - UnitTime 기반
이 파일의 UNIT_TIME_MINUTES 값만 변경하면 전체 시스템의 시간 해상도가 변경됩니다.
"""


class AnalysisConfig:
    """데이터 분석 전역 설정
    
    Usage:
        from config import config
        
        # UnitTime 정보 가져오기
        bins_per_day = config.bins_per_day()
        time_label = config.get_time_label_from_bin(72)
    """
    
    # ========== Time Resolution Settings ==========
    UNIT_TIME_MINUTES = 5  # 🎯 핵심 설정: 기본 시간 단위 (분) - 이 값만 바꾸면 전체 시스템 변경
    
    # ========== T41 Activity Detection Settings ==========
    ACTIVE_THRESHOLD = 2  # 1분당 신호 횟수 (2회 이상 = active)
    
    # ========== Display Settings ==========
    MAX_DISPLAY_WORKERS = 500  # Journey Heatmap 최대 표시 작업자 수
    
    # ========== Derived Methods (Class Methods) ==========
    
    @classmethod
    def bins_per_day(cls) -> int:
        """하루의 bin 개수 (1440분 / unit_time_minutes)
        
        Returns:
            int: 하루의 bin 개수 (예: 5분 단위 = 288개, 10분 단위 = 144개)
        """
        return (24 * 60) // cls.UNIT_TIME_MINUTES
    
    @classmethod
    def bins_per_hour(cls) -> int:
        """시간당 bin 개수 (60분 / unit_time_minutes)
        
        Returns:
            int: 시간당 bin 개수 (예: 5분 단위 = 12개, 10분 단위 = 6개)
        """
        return 60 // cls.UNIT_TIME_MINUTES
    
    @classmethod
    def get_time_label_from_bin(cls, bin_index: int) -> str:
        """bin_index로부터 시간 라벨 생성 (HH:MM)
        
        Args:
            bin_index: 0부터 시작하는 bin 인덱스
            
        Returns:
            str: 시간 라벨 (예: "06:00", "12:05")
        """
        hour = bin_index // cls.bins_per_hour()
        minute = (bin_index % cls.bins_per_hour()) * cls.UNIT_TIME_MINUTES
        return f"{hour:02d}:{minute:02d}"
    
    @classmethod
    def get_bin_from_time(cls, hour: int, minute: int) -> int:
        """시간(hour, minute)으로부터 bin_index 계산
        
        Args:
            hour: 시간 (0-23)
            minute: 분 (0-59)
            
        Returns:
            int: bin_index
        """
        return hour * cls.bins_per_hour() + minute // cls.UNIT_TIME_MINUTES
    
    @classmethod
    def get_all_time_labels(cls) -> list:
        """모든 시간 라벨 리스트 생성
        
        Returns:
            list: ["00:00", "00:05", ..., "23:55"] (5분 단위 예시)
        """
        return [cls.get_time_label_from_bin(i) for i in range(cls.bins_per_day())]


# Singleton instance for easy access
config = AnalysisConfig()
