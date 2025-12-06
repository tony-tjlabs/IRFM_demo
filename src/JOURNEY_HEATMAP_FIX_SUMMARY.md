# Journey Heatmap 색상 매핑 오류 수정 완료

## 📋 문제점 분석

### 1. **치명적 오류: Present 상태에서 Building-Level 색상 적용**
- **문제**: 기존 코드는 `Activity Status`가 'Active' 또는 'Present' **둘 다**에서 Building-Level을 추출하여 색상 매핑
- **결과**: 헬멧을 벗어놓은 상태(Present, 1-2회 수신)에서도 Cluster-1F 등의 색상이 적용되어 **보라색이 24시간 유지**되는 문제 발생
- **위치**: `tward_journey_fixed.py` 200-240번째 줄

### 2. **로직 혼란: Activity Status vs Signal Count**
- **사용자 요구사항**: "1분에 3회+ 수신 = 활성화"
- **기존 코드**: `activity_status`가 'Active'/'Present'로 이미 분류되어 있다고 가정
- **문제**: Present 상태도 Building-Level 색상 결정에 포함되어 잘못된 색상 매핑

### 3. **Cluster 조건 불충분**
- **기존**: 85% 이상일 때만 Cluster 색상 적용
- **문제**: 이미 Present 데이터도 포함되어 있어서 조건이 무의미

## ✅ 수정 내용

### 1. **signal_count 기반 활성화 판정** (핵심 수정)
```python
# 🔥 핵심 수정: signal_count 기반으로 활성화 판정
if 'signal_count' in minute_data.columns:
    # signal_count >= 3인 데이터만 활성화로 간주
    active_data_minute = minute_data[minute_data['signal_count'] >= 3]
    
    if active_data_minute.empty:
        # 1-2회 수신 또는 0회 수신 → 회색 (비활성화)
        minute_colors.append(JOURNEY_COLORS['present_inactive'])
    else:
        # 활성화 데이터(3회+)에서만 Building-Level 추정
        # ...
```

**변경 사항:**
- ✅ `signal_count >= 3`인 데이터**만** 사용하여 Building-Level 추정
- ✅ `signal_count 1-2`는 무조건 회색(비활성화)
- ✅ Present 상태는 Building-Level 색상 결정에서 완전 제외

### 2. **Cluster 색상 엄격한 조건 강화**
```python
# 🔥 Cluster 매우 엄격 조건: 90% 이상 확실해야만 보라색 적용
if 'Cluster' in dominant_bl:
    if dominant_count >= total_count * 0.9:
        minute_colors.append(JOURNEY_COLORS[dominant_bl])
    else:
        minute_colors.append(JOURNEY_COLORS['present_inactive'])  # 불확실한 Cluster는 회색
```

**변경 사항:**
- ✅ Cluster: 85% → **90%** 이상 (매우 엄격)
- ✅ 다른 Building-Level: 50% → **60%** 이상
- ✅ 10분 집계 시 Cluster는 **최소 5분 이상** 활성화되어야 색상 적용

### 3. **10분 집계 로직 개선**
```python
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
            if final_color == JOURNEY_COLORS['Cluster-1F']:
                # Cluster는 최소 5분 이상 활성화되어야 함
                if non_inactive_colors[final_color] < 5:
                    final_color = JOURNEY_COLORS['present_inactive']
        else:
            # Building-Level 색상이 없으면 회색 (비활성화)
            final_color = JOURNEY_COLORS['present_inactive']
```

**변경 사항:**
- ✅ 검정: 5분 → **7분** 이상 (더 엄격)
- ✅ Cluster는 10분 중 **최소 5분 이상** 활성화되어야 색상 적용
- ✅ 활성화 색상 우선, 없으면 회색 (검정/회색 혼합 제거)

### 4. **시간 계산 수정**
```python
# 🔧 올바른 시간 계산: 0시부터 시작 (bin 0 = 00:00~00:10)
start_minute = bin_idx * 10  # 0, 10, 20, 30, ...
end_minute = start_minute + 9  # 9, 19, 29, 39, ...
```

**변경 사항:**
- ✅ 기존: `bin_idx * 10 + 1 ~ (bin_idx + 1) * 10` (잘못된 계산)
- ✅ 수정: `bin_idx * 10 ~ bin_idx * 10 + 9` (올바른 계산)

## 🎨 수정된 Journey Heatmap 색상 범례

올바르게 적용되는 조건:

| 색상 | 조건 | 설명 |
|------|------|------|
| **검정색** | 10분 중 7분+ 신호 없음 | 신호 미수신 |
| **회색** | signal_count 1-2회 또는 활성화 조건 미달 | 비활성화 상태 (헬멧 벗어놓음) |
| **초록색** | signal_count 3회+ & WWT-1F 60%+ (Cluster 제외) | WWT-1F 활성화 |
| **노란색** | signal_count 3회+ & WWT-B1F 60%+ (Cluster 제외) | WWT-B1F 활성화 |
| **주황색** | signal_count 3회+ & FAB-1F 60%+ (Cluster 제외) | FAB-1F 활성화 |
| **하늘색** | signal_count 3회+ & CUB-1F 60%+ (Cluster 제외) | CUB-1F 활성화 |
| **파란색** | signal_count 3회+ & CUB-B1F 60%+ (Cluster 제외) | CUB-B1F 활성화 |
| **보라색** | signal_count 3회+ & Cluster-1F 90%+ & 5분+ | Cluster-1F 활성화 (매우 엄격) |

## 📂 수정된 파일

1. **`tward_journey_fixed.py`** (200-290번째 줄)
   - signal_count 기반 활성화 판정 로직 추가
   - Present 상태에서 Building-Level 색상 적용 제거
   - Cluster 조건 90%로 강화
   - 10분 집계 로직 개선

2. **`tward_type41_journey_map.py`** (163-268번째 줄, 328-428번째 줄)
   - `generate_integrated_journey_heatmap` 함수 수정
   - `generate_tward_heatmap_data` 함수 수정
   - 동일한 signal_count 기반 로직 적용

## 🔍 디버깅 로그 개선

Cluster 색상 및 새벽/야간 시간대 활성화 의심 케이스에 대한 상세 로그 추가:

```python
# Cluster 색상이거나 새벽/야간 시간대(bin 0-35 또는 bin 115-143)인 경우 로그
is_cluster = 'Cluster' in final_name
is_dawn_or_night = bin_idx <= 35 or bin_idx >= 115  # 06:00 이전 또는 19:00 이후

if is_cluster or (is_dawn_or_night and final_color not in [JOURNEY_COLORS['no_signal'], JOURNEY_COLORS['present_inactive']]):
    color_dist = {color_names.get(color, f"Unknown({color})"): count for color, count in color_counter.items()}
    hour = (start_minute // 60)
    minute = (start_minute % 60)
    print(f"🎯 판단 MAC {mac[:17]} bin{bin_idx:03d}({hour:02d}:{minute:02d}): {color_dist} → {final_name}({final_reason})")
```

## 🎯 기대 효과

1. ✅ **보라색(Cluster) 24시간 유지 문제 해결**
   - Present 상태에서 Cluster 색상 적용 완전 차단
   - Cluster는 90% 이상 + 5분 이상 조건 만족 시에만 보라색

2. ✅ **사용자 요구사항 정확히 반영**
   - 1분에 3회+ 수신 = 활성화 (Building-Level 색상)
   - 1분에 1-2회 수신 = 비활성화 (회색)
   - 10분 동안 데이터 없음 = 신호 미수신 (검정)

3. ✅ **정밀한 활성화 판정**
   - signal_count 기반으로 객관적 판정
   - Building-Level 추정 시 활성화 데이터만 사용
   - Cluster는 특히 엄격한 조건 적용

## 🚀 다음 단계

1. Streamlit 앱 실행하여 Journey Heatmap 재생성
2. 보라색(Cluster) 24시간 유지 문제 해결 확인
3. 각 색상별 분포가 올바르게 나타나는지 검증
4. 필요 시 threshold 값 미세 조정 (현재: Cluster 90%, 기타 60%)

## 📌 주의사항

- **데이터에 `signal_count` 컬럼이 없는 경우**: 기존 로직(`activity_status` 기반) 사용 (하위 호환성)
- **Cluster 색상**: 가장 엄격한 조건 적용 (90% + 5분+)
- **시간 계산**: bin 0 = 00:00~00:09 (0시부터 시작)

---

**수정 완료 일시**: 2025년 10월 6일
**수정자**: GitHub Copilot
**수정 이유**: Present 상태에서 Building-Level 색상 적용으로 인한 보라색(Cluster) 24시간 유지 문제 해결
