# Journey Heatmap 보라색 24시간 문제 디버깅 체크리스트

## 📊 현재 상황
- **문제**: 보라색(Cluster)이 24시간 동안 유지되는 현상이 여전히 발생
- **수정 완료**: Present 상태 제외, Cluster 90% 조건, 5분 이상 조건 등 적용
- **결과**: 문제 지속

## 🔍 다음 디버깅 단계

### 1. 데이터 확인 (최우선)
```python
# 실제 데이터에 signal_count 컬럼이 있는지 확인
print("signal_count 컬럼 존재:", 'signal_count' in data.columns)

# signal_count 분포 확인
if 'signal_count' in data.columns:
    print(data['signal_count'].value_counts().sort_index())
else:
    print("⚠️ signal_count 컬럼이 없음 - 기존 activity_status 로직 사용")
```

**의심**: `signal_count` 컬럼이 없어서 기존 로직(`activity_status == 'Active'`)을 사용하고 있을 가능성 ⚠️

### 2. Cluster 데이터 상세 분석
```python
# Cluster 데이터만 추출
cluster_data = data[data['building'].str.contains('Cluster', na=False)]
print(f"전체 Cluster 데이터: {len(cluster_data):,}건")

# Activity Status 분포
print("Cluster Activity Status 분포:")
print(cluster_data['activity_status'].value_counts())

# 시간대별 분포
cluster_data['hour'] = cluster_data['minute_bin'] // 60
print("\nCluster 시간대별 분포:")
print(cluster_data.groupby('hour')['mac'].count())
```

### 3. 특정 MAC의 하루 패턴 추적
```python
# 보라색이 24시간 나타나는 특정 MAC 선택
problem_mac = "xx:xx:xx:xx:xx:xx"  # 실제 MAC 주소 입력

# 해당 MAC의 시간대별 Building-Level 분포
mac_data = data[data['mac'] == problem_mac]
for hour in range(24):
    hour_data = mac_data[(mac_data['minute_bin'] >= hour * 60) & 
                         (mac_data['minute_bin'] < (hour + 1) * 60)]
    if not hour_data.empty:
        bl_dist = hour_data.groupby(['building', 'level']).size()
        print(f"{hour:02d}시: {dict(bl_dist)}")
```

### 4. 1분 단위 색상 판정 로그 확인
현재 코드에 이미 디버깅 로그가 있으므로, 출력 내용을 확인:
```python
# tward_journey_fixed.py 316-320번째 줄
if is_cluster or (is_dawn_or_night and final_color not in [JOURNEY_COLORS['no_signal'], JOURNEY_COLORS['present_inactive']]):
    color_dist = {color_names.get(color, f"Unknown({color})"): count for color, count in color_counter.items()}
    hour = (start_minute // 60)
    minute = (start_minute % 60)
    print(f"🎯 판단 MAC {mac[:17]} bin{bin_idx:03d}({hour:02d}:{minute:02d}): {color_dist} → {final_name}({final_reason})")
```

출력에서 다음을 확인:
- 보라색이 나타나는 시간대의 `color_dist` 분포
- `final_reason`이 무엇인지 (Cluster부족 → 회색 전환이 작동하는지)

### 5. 가설별 대응 방안

#### 가설 1: signal_count 컬럼이 없음 ⚠️⚠️⚠️
**증상**: 기존 `activity_status == 'Active'` 로직 사용  
**문제**: Present 상태도 Active로 분류되어 있을 가능성  
**해결**: 
- 데이터 생성 과정에서 signal_count 컬럼 추가
- 또는 기존 로직 강화 (Present/Active 더 엄격하게 구분)

#### 가설 2: Cluster 데이터가 압도적으로 많음
**증상**: 90% 조건을 만족하는 경우가 많음  
**문제**: Cluster가 실제로 대부분인 경우  
**해결**:
- Cluster 조건을 95%로 상향
- 또는 절대적 시간 조건 추가 (예: 연속 30분 이상)

#### 가설 3: 새벽/야간 시간 특별 처리 미작동
**증상**: 새벽에도 Cluster가 활성화로 나타남  
**문제**: 새벽 시간대 조건이 제대로 작동하지 않음  
**해결**:
- 새벽(00:00-06:00), 야간(19:00-24:00) 시간대 Cluster 완전 차단
- 작업시간(07:00-19:00) 외에는 모두 회색 처리

#### 가설 4: 10분 집계 로직 오류
**증상**: 1분별로는 회색인데 10분 집계에서 보라색으로 변경  
**문제**: 집계 로직의 버그  
**해결**:
- 10분 집계 로직 재검토
- Cluster는 10분 중 **8분 이상** 조건으로 강화

## 🔧 긴급 임시 해결책

### 방법 1: Cluster 완전 차단 (테스트용)
```python
# tward_journey_fixed.py 220번째 줄 수정
if 'Cluster' in dominant_bl:
    # Cluster는 무조건 회색 처리 (테스트)
    minute_colors.append(JOURNEY_COLORS['present_inactive'])
```

### 방법 2: 새벽/야간 Cluster 차단
```python
# 10분 집계 시점에서 차단
is_work_time = 42 <= bin_idx <= 114  # 07:00-19:00
if not is_work_time and final_color == JOURNEY_COLORS['Cluster-1F']:
    final_color = JOURNEY_COLORS['present_inactive']
```

### 방법 3: Cluster 조건 극도로 강화
```python
# 1분 단위: 90% → 95%
if dominant_count >= total_count * 0.95:

# 10분 단위: 5분 → 8분
if cluster_minutes < 8:
```

## 📝 다음 세션 시작 시 확인 사항

1. [ ] `signal_count` 컬럼 존재 여부 확인
2. [ ] 디버깅 로그에서 보라색 나타나는 패턴 분석
3. [ ] 특정 MAC의 24시간 Building-Level 분포 확인
4. [ ] 1분 단위 색상 vs 10분 집계 색상 비교
5. [ ] 필요시 긴급 임시 해결책 적용하여 테스트

## 🎯 최종 목표

**사용자 요구사항**:
- 검정색: 10분 동안 데이터 없음
- 회색: 1분에 1-2회 수신
- 색상(초록/노랑/주황/하늘/파랑): 1분에 3회+ 수신
- **보라색: 1분에 3회+ 수신 & Cluster 90%+ & 엄격한 조건**

**현재 상태**: 보라색이 24시간 유지됨 (오류)

**목표**: 보라색은 작업시간 내 Cluster에서 실제 활성화된 경우**만** 나타나야 함

---

**작성일**: 2025년 10월 7일  
**상태**: 디버깅 중단 - 다음 세션에서 재개
