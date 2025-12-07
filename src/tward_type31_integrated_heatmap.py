"""
T-Ward Type 31 Integrated Operation Heatmap
전체 T-Ward 통합 Operation Heatmap 생성
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 백엔드를 명시적으로 설정
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import streamlit as st
import os
from src import tward_type31_processing

# Building-Level별 색상 매핑 (사용자 지정)
OPERATION_COLORS = {
    'no_signal': 0,         # 신호 미수신: 검정색
    'inactive': 1,          # 비활성화: 회색
    'WWT-1F': 2,           # 초록색
    'WWT-B1F': 3,          # 노란색  
    'FAB-1F': 4,           # 주황색
    'CUB-1F': 5,           # 파란색
    'CUB-B1F': 6,          # 하늘색
    'Cluster-1F': 7,       # 보라색
    
    # 추가 가능한 조합들
    'WWT-2F': 2,           # WWT-1F와 같은 초록색
    'FAB-2F': 4,           # FAB-1F와 같은 주황색  
    'FAB-B1F': 4,          # FAB-1F와 같은 주황색
    'CUB-2F': 5,           # CUB-1F와 같은 파란색
    'Cluster-2F': 7,       # Cluster-1F와 같은 보라색
    'Cluster-B1F': 7       # Cluster-1F와 같은 보라색
}

# 실제 색상 코드 매핑
COLOR_MAP = [
    '#000000',  # 0: 검정색 (신호 미수신)
    '#808080',  # 1: 회색 (비활성화) 
    '#00FF00',  # 2: 초록색 (WWT-1F)
    '#FFFF00',  # 3: 노란색 (WWT-B1F)
    '#FFA500',  # 4: 주황색 (FAB-1F)
    '#0000FF',  # 5: 파란색 (CUB-1F)
    '#87CEEB',  # 6: 하늘색 (CUB-B1F)
    '#8A2BE2'   # 7: 보라색 (Cluster-1F)
]

def render_integrated_operation_heatmap():
    """전체 T-Ward 통합 Operation Heatmap 렌더링"""
    
    print("🎯 render_integrated_operation_heatmap 함수 시작")
    
    st.subheader("🔥 T-Ward Type 31 Integrated Operation Heatmap")
    st.write("**All T-Ward Operation Patterns by Building-Level (Sorted by Operation Time)**")
    
    print("🎯 제목 표시 완료")
    
    # 데이터 로드
    tward31_path = st.session_state.get('tward31_path', None)
    print(f"🎯 tward31_path: {tward31_path}")
    
    if not tward31_path:
        st.error("⚠️ T-Ward Type 31 data not loaded. Please upload data first.")
        print("❌ tward31_path가 없음")
        return
    
    # 데이터 전처리
    print("🎯 데이터 전처리 시작")
    with st.spinner("🔄 Loading and processing T-Ward Type 31 data..."):
        df = pd.read_csv(tward31_path, header=None)
        df = tward_type31_processing.preprocess_tward31(df)
        df = tward_type31_processing.add_time_index(df)
        sward_config = tward_type31_processing.load_sward_config()
        
        # 통합 분석 수행
        analysis_results = tward_type31_processing.unified_tward31_analysis(df, sward_config)
        op_rate_df = analysis_results['operation_data']
    
    print(f"🎯 데이터 로드 완료: {len(df)} records")
    st.success(f"✅ Data Loaded: {len(df):,} records, {len(op_rate_df):,} operation records")
    
    # 통합 Operation Heatmap 생성
    print("🎯 히트맵 생성 시작")
    with st.spinner("🎨 Generating Integrated Operation Heatmap..."):
        heatmap_result = generate_integrated_operation_heatmap(df, sward_config)
        
        if heatmap_result:
            print("🎯 히트맵 결과 있음, display 함수 호출")
            display_integrated_operation_heatmap(heatmap_result)
            print("🎯 display 함수 완료")
        else:
            print("❌ 히트맵 결과 없음")
            st.error("⚠️ Failed to generate operation heatmap.")

def generate_integrated_operation_heatmap(df, sward_config):
    """전체 T-Ward 통합 Operation Heatmap 데이터 생성 - 모든 T-Ward를 하나의 히트맵에 표시"""
    
    if df is None or df.empty:
        return None
    
    print(f"\n🌟 통합 Operation Heatmap 생성 시작 - 모든 T-Ward 통합")
    
    # S-Ward 설정과 DataFrame 병합하여 Building-Level 정보 추가
    df_with_location = df.merge(sward_config[['sward_id', 'building', 'level']], on='sward_id', how='left')
    
    # 각 (mac, time_index)별로 최대 RSSI를 가진 레코드만 선택 (위치 결정)
    idx = df_with_location.groupby(['mac', 'time_index'])['rssi'].idxmax()
    df_max_rssi = df_with_location.loc[idx].copy()
    
    # MAC별 가동시간 계산
    mac_operation_time = df_max_rssi.groupby('mac')['time_index'].nunique().reset_index()
    mac_operation_time.columns = ['mac', 'operation_minutes']
    
    # 가동시간 기준 내림차순 정렬
    mac_operation_time = mac_operation_time.sort_values('operation_minutes', ascending=False).reset_index(drop=True)
    
    print(f"🎯 전체 T-Ward 수: {len(mac_operation_time)}")
    print(f"   가동시간 범위: {mac_operation_time['operation_minutes'].min()}~{mac_operation_time['operation_minutes'].max()}분")
    
    if mac_operation_time.empty:
        return None
    
    # 144개 10분 bins에 대한 히트맵 데이터 생성
    heatmap_data = []
    
    for _, row in mac_operation_time.iterrows():
        mac = row['mac']
        tward_row = []
        
        # 해당 T-Ward의 위치 결정된 데이터 추출
        mac_data = df_max_rssi[df_max_rssi['mac'] == mac]
        
        # 144개 10분 bin에 대해 색상 결정
        for bin_idx in range(144):
            # 10분 구간 계산 (bin_idx * 10 + 1 ~ (bin_idx + 1) * 10)
            start_minute = bin_idx * 10 + 1
            end_minute = (bin_idx + 1) * 10
            
            # 해당 10분 구간의 데이터
            time_data = mac_data[
                (mac_data['time_index'] >= start_minute) & 
                (mac_data['time_index'] <= end_minute)
            ]
            
            if time_data.empty:
                # 10분 동안 데이터 없음 - 신호 미수신 (검정색)
                tward_row.append(OPERATION_COLORS['no_signal'])
            else:
                # 10분 구간에서 가장 많이 나타난 Building-Level 찾기
                building_level_counts = {}
                for _, data_row in time_data.iterrows():
                    building = data_row.get('building', 'Unknown')
                    level = data_row.get('level', 'Unknown')
                    bl_key = f"{building}-{level}"
                    building_level_counts[bl_key] = building_level_counts.get(bl_key, 0) + 1
                
                if building_level_counts:
                    # 가장 많이 나타난 Building-Level 선택
                    dominant_bl = max(building_level_counts, key=building_level_counts.get)
                    
                    if dominant_bl in OPERATION_COLORS:
                        color_value = OPERATION_COLORS[dominant_bl]
                    else:
                        color_value = OPERATION_COLORS['inactive']  # 미정의 공간은 회색
                        print(f"🚨 Unknown Building-Level: {dominant_bl} - using gray")
                    
                    tward_row.append(color_value)
                else:
                    # Building-Level을 결정할 수 없는 경우 - 회색
                    tward_row.append(OPERATION_COLORS['inactive'])
        
        heatmap_data.append(tward_row)
    
    # DataFrame 생성
    columns = ['MAC Address', 'Operation Time (min)'] + [f"T{i:03d}" for i in range(144)]
    
    final_data = []
    for i, (_, row) in enumerate(mac_operation_time.iterrows()):
        mac = row['mac']
        operation_minutes = int(row['operation_minutes'])
        data_row = [mac, operation_minutes] + heatmap_data[i]
        final_data.append(data_row)
    
    heatmap_df = pd.DataFrame(final_data, columns=columns)
    
    # 디버깅: 색상 분포 확인
    time_cols = [col for col in heatmap_df.columns if col.startswith('T')]
    heatmap_matrix = heatmap_df[time_cols]
    
    color_distribution = {}
    for color_name, color_value in OPERATION_COLORS.items():
        count = (heatmap_matrix == color_value).sum().sum()
        color_distribution[color_name] = count
    
    print("🎨 색상별 분포:")
    for color_name, count in color_distribution.items():
        if count > 0:
            print(f"   {color_name}: {count}개 셀")
    
    return {
        'heatmap_df': heatmap_df,
        'tward_count': len(mac_operation_time),
        'operation_time_range': (mac_operation_time['operation_minutes'].min(), mac_operation_time['operation_minutes'].max()),
        'color_distribution': color_distribution
    }

def determine_building_level_from_rssi(data_row, sward_config):
    """RSSI 데이터를 기반으로 Building-Level 결정"""
    
    # Type 31 데이터에서는 sward_id와 rssi가 직접 제공됨
    sward_id = data_row.get('sward_id', None)
    
    if not sward_id or sward_config.empty:
        return 'Unknown', 'Unknown'
    
    # S-Ward 설정에서 Building-Level 정보 조회
    sward_info = sward_config[sward_config['sward_id'] == sward_id]
    
    if not sward_info.empty:
        building = sward_info.iloc[0].get('building', 'Unknown')
        level = sward_info.iloc[0].get('level', 'Unknown')
        return building, level
    
    return 'Unknown', 'Unknown'

def display_integrated_operation_heatmap(heatmap_result):
    """통합 Operation Heatmap 시각화"""
    
    print("🎯 display_integrated_operation_heatmap 시작")
    
    heatmap_df = heatmap_result['heatmap_df']
    tward_count = heatmap_result['tward_count']
    operation_time_range = heatmap_result['operation_time_range']
    
    print(f"🎯 데이터 정보: {tward_count}개 T-Ward, 범위: {operation_time_range}")
    
    # 기본 통계 정보
    print("🎯 통계 정보 표시 시작")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total T-Ward", f"{tward_count:,}")
    with col2:
        st.metric("Min Operation Time", f"{operation_time_range[0]}min")
    with col3:
        st.metric("Max Operation Time", f"{operation_time_range[1]}min")
    
    print("🎯 통계 정보 표시 완료")
    
    # 히트맵 시각화 (50개씩 10개 그룹)
    if not heatmap_df.empty:
        
        print("🎯 히트맵 시각화 시작")
        
        time_cols = [col for col in heatmap_df.columns if col.startswith('T')]
        
        # 상위 500개 T-Ward만 선택
        max_twards = min(500, len(heatmap_df))
        top_twards_df = heatmap_df.head(max_twards)
        
        print(f"🎯 시각화 대상: {max_twards}개 T-Ward")
        
        # 테스트 그래프 먼저 표시
        print("🔍 테스트 그래프 생성")
        test_fig, test_ax = plt.subplots(figsize=(8, 4))
        test_ax.plot([1, 2, 3, 4], [1, 4, 2, 3])
        test_ax.set_title("Test Graph - If you see this, matplotlib works")
        try:
            # 버퍼에 저장 후 이미지로 표시 시도
            import io
            buf = io.BytesIO()
            test_fig.savefig(buf, format='png')
            buf.seek(0)
            st.image(buf, caption="Test Graph via st.image()", use_column_width=True)
            print("✅ 테스트 그래프 이미지로 표시 성공")
        except Exception as e:
            print(f"🚨 테스트 그래프 이미지 실패: {e}")
            # 기존 방식 시도
            try:
                st.pyplot(test_fig, clear_figure=True)
                print("✅ 테스트 그래프 pyplot으로 표시 성공")
            except Exception as e2:
                print(f"🚨 테스트 그래프 pyplot 실패: {e2}")
        finally:
            plt.close(test_fig)
        
        st.write(f"**📊 Top {max_twards} T-Ward Operation Heatmap (50 T-Wards per Group)**")
        
        # 50개씩 10개 그룹으로 분할
        for group_idx in range(10):
            start_idx = group_idx * 50
            end_idx = min((group_idx + 1) * 50, max_twards)
            
            if start_idx >= max_twards:
                break
                
            group_df = top_twards_df.iloc[start_idx:end_idx]
            group_matrix = group_df[time_cols].values
            group_size = len(group_df)
            
            print(f"🎯 그룹 {group_idx + 1} 생성 중: {start_idx + 1} ~ {end_idx}")
            print(f"🔍 그룹 매트릭스 크기: {group_matrix.shape}")
            print(f"🔍 매트릭스 값 범위: {group_matrix.min()} ~ {group_matrix.max()}")
            print(f"🔍 매트릭스 고유값: {np.unique(group_matrix)}")
            
            st.write(f"**Group {group_idx + 1}: T-Ward #{start_idx + 1} ~ #{end_idx} (Operation Time Ranking)**")
            
            # 히트맵 생성
            fig, ax = plt.subplots(figsize=(20, max(8, group_size * 0.4)))
            
            cmap = ListedColormap(COLOR_MAP)
            
            # 히트맵 그리기
            im = ax.imshow(group_matrix, cmap=cmap, aspect='auto', interpolation='nearest', vmin=0, vmax=7)
            
            # 축 설정
            ax.set_xlabel('Time (10min intervals)', fontsize=12)
            ax.set_ylabel(f'T-Ward Rank #{start_idx + 1} ~ #{end_idx}', fontsize=12)
            ax.set_title(f'T-Ward Operation Heatmap - Group {group_idx + 1}\n(Black: No Signal, Gray: Inactive, Colors: Building-Level)', fontsize=14, pad=20)
            
            # X축 시간 레이블
            x_ticks = list(range(0, 144, 12))
            x_labels = [f"{i*2:02d}:00" for i in range(0, 12)]
            ax.set_xticks(x_ticks)
            ax.set_xticklabels(x_labels)
            
            # Y축 T-Ward 레이블
            y_ticks = list(range(group_size))
            y_labels = [f"#{start_idx + i + 1} ({group_df.iloc[i]['Operation Time (min)']}min)" for i in range(group_size)]
            ax.set_yticks(y_ticks)
            ax.set_yticklabels(y_labels, fontsize=9)
            
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            
            print(f"🎯 그룹 {group_idx + 1} Streamlit에 표시 중")
            try:
                # 이미지로 저장 후 표시
                import io
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
                buf.seek(0)
                st.image(buf, caption=f"Group {group_idx + 1}: T-Ward Operation Heatmap", use_column_width=True)
                print(f"✅ 그룹 {group_idx + 1} 이미지로 표시 완료")
            except Exception as e:
                print(f"🚨 그룹 {group_idx + 1} 이미지 표시 실패: {e}")
                # 기존 방식으로 재시도
                try:
                    st.pyplot(fig, clear_figure=True)
                    print(f"✅ 그룹 {group_idx + 1} pyplot으로 표시 완료")
                except Exception as e2:
                    print(f"🚨 그룹 {group_idx + 1} pyplot 표시도 실패: {e2}")
                    st.error(f"Failed to display group {group_idx + 1}: {e}")
            finally:
                plt.close(fig)  # 메모리 정리
            
            # 그룹별 통계
            col1, col2, col3 = st.columns(3)
            with col1:
                min_time = group_df['Operation Time (min)'].min()
                st.metric(f"Group {group_idx + 1} Min", f"{min_time}min")
            with col2:
                max_time = group_df['Operation Time (min)'].max()
                st.metric(f"Group {group_idx + 1} Max", f"{max_time}min")
            with col3:
                avg_time = group_df['Operation Time (min)'].mean()
                st.metric(f"Group {group_idx + 1} Avg", f"{avg_time:.1f}min")
            
            st.write("---")
        
        print("✅ 모든 히트맵 그룹 표시 완료")
        
        # 색상 범례 (Journey Heatmap 스타일 - 흰색 박스 안에 표시)
        st.markdown("#### 🎨 Color Legend")
        legend_html = """
        <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; padding: 10px; background: #f0f0f0; border-radius: 5px;">
            <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #000000; border: 1px solid #333;"></span> <b>No Signal</b></span>
            <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #808080; border: 1px solid #333;"></span> <b>Inactive</b></span>
            <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #00FF00; border: 1px solid #333;"></span> <b>WWT-1F</b></span>
            <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #FFFF00; border: 1px solid #333;"></span> <b>WWT-B1F</b></span>
            <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #FFA500; border: 1px solid #333;"></span> <b>FAB</b></span>
            <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #0000FF; border: 1px solid #333;"></span> <b>CUB-1F</b></span>
            <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #87CEEB; border: 1px solid #333;"></span> <b>CUB-B1F</b></span>
            <span style="display: inline-flex; align-items: center; gap: 5px; color: #000;"><span style="display: inline-block; width: 16px; height: 16px; background: #8A2BE2; border: 1px solid #333;"></span> <b>Cluster</b></span>
        </div>
        """
        st.markdown(legend_html, unsafe_allow_html=True)
        
        # 데이터 다운로드
        if st.checkbox("📊 Show Detailed Data"):
            st.dataframe(heatmap_df, use_container_width=True)
            
            csv_data = heatmap_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Heatmap Data (CSV)",
                data=csv_data,
                file_name="tward31_integrated_operation_heatmap.csv",
                mime="text/csv"
            )
    else:
        print("🚨 히트맵 데이터가 비어있음")
        st.warning("No data to display.")
        
    print("🎯 display_integrated_operation_heatmap 완료")

if __name__ == "__main__":
    print("T-Ward Type 31 Integrated Operation Heatmap Module loaded")