# SKEP IRFM Demo - Worker Tracking Analysis

## 📋 프로젝트 개요

SKEP(SK E&S Power) 용인 클러스터 현장의 작업자 트래킹 분석 대시보드입니다.  
S-Ward 센서와 T-Ward 태그 데이터를 기반으로 작업자 위치 및 활동 패턴을 분석합니다.

## 🚀 핵심 아키텍처: 사전 계산 + 캐시 로딩

### 설계 철학
```
Raw 데이터 (7M+ rows) → 사전 계산 (precompute.py, ~250초)
                              ↓
                     캐시 파일 (parquet/json)
                              ↓
              대시보드 로딩 (~1초) ← 빠른 사용자 경험
```

### 장점
1. **빠른 대시보드 로딩**: 수 분 → 1초 미만
2. **반복 계산 제거**: 동일한 데이터를 여러 번 처리하지 않음
3. **모듈화**: 전처리와 시각화 분리
4. **확장성**: 새로운 분석 추가 시 캐시에 추가만 하면 됨

---

## 📁 폴더 구조

```
IRFM_demo/
├── main.py                 # Streamlit 대시보드 메인
├── precompute.py           # 사전 계산 스크립트
├── requirements.txt        # Python 패키지 의존성
├── src/                    # 분석 모듈
│   ├── cached_data_loader.py
│   ├── tward_type41_journey_map.py
│   ├── colors.py
│   └── ...
├── Datafile/
│   ├── Map_Image/          # 건물 평면도 이미지
│   ├── sward_configuration.csv
│   └── Rawdata/
│       └── Yongin_Cluster_20250909/
│           ├── T31_*.csv   # 장비 데이터
│           ├── T41_*.csv   # 작업자 데이터
│           ├── TMobile_*.csv # Flow 데이터
│           └── cache/      # 사전 계산된 캐시
└── .streamlit/
    └── config.toml         # Streamlit 설정
```

---

## 🔧 설치 및 실행

### 1. 환경 설정
```bash
cd IRFM_demo
pip install -r requirements.txt
```

### 2. 사전 계산 실행 (최초 1회)
```bash
python precompute.py Datafile/Rawdata/Yongin_Cluster_20250909
```

### 3. 대시보드 실행
```bash
streamlit run main.py --server.port 8501
```

---

## 🌐 배포 방법

### 방법 1: Streamlit Community Cloud (무료, 추천)

1. **GitHub에 코드 업로드** (Public 또는 Private repo)
2. **https://share.streamlit.io 접속**
3. **New app → GitHub repo 선택 → Deploy**
4. **공유 링크 제공** (예: `https://your-app.streamlit.app`)

### 방법 2: Docker + 클라우드 서버

```dockerfile
# Dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## 📊 주요 기능

### T-Ward Type 31 (장비 트래킹)
- **Overview**: 장비별 활동 현황, 시간대별 분포
- **Location Analysis**: 건물/층별 장비 위치
- **Operation Heatmap**: 운영 시간 히트맵
- **AI Insight & Report**: AI 기반 분석 리포트

### T-Ward Type 41 (작업자 트래킹)
- **Overview**: 작업자 활동 현황, 밀집도 분석
- **Location Analysis**: 위치 히트맵 (추후 제공)
- **Journey Heatmap**: 작업자별 이동 경로 히트맵
- **AI Insight & Report**: AI 기반 분석 리포트

### Dashboard Mode
- 사전 계산된 캐시 데이터 기반 빠른 로딩
- 모든 분석 결과 즉시 확인

---

## 🏗️ 건물 구성

| Building | Level | 설명 |
|----------|-------|------|
| WWT | 1F, B1F | 폐수처리시설 |
| FAB | 1F | 제조동 |
| CUB | 1F, B1F | 중앙유틸리티동 |
| Cluster | 1F | 클러스터동 |

---

## 📝 버전 정보

- **v1.0** (2024-12): 초기 배포
  - T31/T41 분석 대시보드
  - 사전 계산 시스템
  - Journey Heatmap
  - AI Insights

---

## 👥 Contact

- **TJLABS** - Indoor Positioning & Analytics
