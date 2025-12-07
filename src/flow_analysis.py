"""
Flow Data Analysis Module
Apple vs Android device analysis by time bins
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def identify_device_type_from_type_column(type_value):
    """
    type 컬럼 값으로 디바이스 타입 식별
    1: Apple
    10: Google (Android)
    """
    if pd.isna(type_value):
        return 'Unknown'
    
    type_val = int(type_value)
    
    if type_val == 1:
        return 'Apple'
    elif type_val == 10:
        return 'Android'
    else:
        return 'Unknown'

def identify_device_type(mac_address):
    """
    (Deprecated) MAC 주소로 디바이스 타입 식별
    이제 type 컬럼을 사용하므로 이 함수는 사용하지 않음
    Apple: MAC 주소 OUI (첫 6자리)가 특정 범위에 속함
    """
    if pd.isna(mac_address) or mac_address == '':
        return 'Unknown'
    
    # MAC 주소 정규화 (대문자, 콜론/하이픈 제거)
    mac_clean = str(mac_address).upper().replace(':', '').replace('-', '').replace('.', '')
    
    if len(mac_clean) < 6:
        return 'Unknown'
    
    # Apple OUI 프리픽스 (주요 범위만)
    apple_ouis = [
        '0003FF', '00050E', '000A27', '000A95', '000D93', '000F61',
        '0010FA', '001124', '0016CB', '001781', '0017F2', '0019E3',
        '001B63', '001CB3', '001E52', '001EC2', '001F5B', '001FF3',
        '0021E9', '002241', '002332', '0023DF', '002436', '002500',
        '00254B', '0025BC', '002608', '0026B0', '0026BB', '002D7E',
        '003EE1', '005A38', '0080E6', '008701', '00D0E2', '00ECFC',
        '040CCE', '041E64', '042665', '04489A', '044BED', '045453',
        '0469F8', '048D38', '04D3CF', '04DB56', '04E536', '04F13E',
        '04F7E4', '0C3021', '0C3E9F', '0C4885', '0C5101', '0C6076',
        '0C74C2', '0C77A', '101C0C', '103B59', '109ADD', '10417F',
        '1499E2', '14BD61', '14C213', '1816D8', '181EB0', '185936',
        '1CBB37', '203CAE', '2078F0', '207D74', '2C1F23', '2C3361',
        '2C5490', '2C61F6', '2C8158', '2CAC8', '3096FB', '30B4B8',
        '34159E', '34A395', '34C059', '38484C', '3866F0', '38EDAD',
        '3C0754', '3C2EF9', '3C6200', '400E8', '40448A', '40831D',
        '409C28', '40A6D9', '40B395', '40CBC0', '40D32D', '448F17',
        '4496E0', '44D884', '48437C', '48746E', '48A91C', '48E9F1',
        '4C3275', '4C569D', '4C7C5F', '4C8D79', '50EAD6', '5433CB',
        '543100', '5440AD', '549963', '54AE27', '54E43A', '54FAD4',
        '5C59D6', '5C9960', '5CA8CB', '5CF7E6', '60334B', '603A7D',
        '60692E', '60A37D', '60C547', '60FB42', '642737', '6451CA',
        '64A5C3', '64B0A6', '64E682', '64FB81', '68A86D', '68AE20',
        '68D93C', '68EF43', '68FE8B', '6C3E6D', '6C4008', '6C4D73',
        '6C70F0', '6C72E7', '6C94F8', '6CAB31', '6CC26B', '707781',
        '70700D', '70CD60', '70DEE2', '70ECE4', '70F087', '74E1B6',
        '7831C1', '7C04D0', '7C6DF8', '7CD1C3', '7CF05F', '800184',
        '80929F', '80BE05', '80E650', '80EA96', '80ED2C', '8425DB',
        '8489AD', '84788B', '84B153', '84FCAC', '84FCFE', '88071E',
        '883FD3', '8866BF', '8C006D', '8C2DAA', '8C7C92', '8C8590',
        '8C8EF2', '90840D', '90B0ED', '90B931', '90DD5D', '90FD61',
        '94BF2D', '94E96A', '94F6A3', '98B8E3', '98D6BB', '98E0D9',
        '98F0AB', '98FE94', '9C207B', '9C293F', '9C35EB', '9C84BF',
        '9CE65E', '9CFC01', 'A04EA7', 'A0999B', 'A46706', 'A4C361',
        'A4D18C', 'A4D1D2', 'A85C2C', 'A88808', 'A88E24', 'AC293A',
        'AC3C0B', 'AC61EA', 'AC7F3E', 'AC87A3', 'ACCF5C', 'B019C6',
        'B065BD', 'B0702D', 'B09FBA', 'B0CA68', 'B418D1', 'B48B19',
        'B4F0AB', 'B4F61E', 'B8098A', 'B817C2', 'B844D9', 'B853AC',
        'B8C75D', 'B8F6B1', 'BC3BAF', 'BC52B7', 'BC6778', 'BC926B',
        'BC9FEF', 'BCA920', 'BCCFCC', 'C02E25', 'C06394', 'C0847A',
        'C0B658', 'C0CECD', 'C0D012', 'C42C03', 'C46AB7', 'C48466',
        'C869CD', 'C8B5AD', 'C8BCC8', 'C8D083', 'C8E0EB', 'CC08E0',
        'CC25EF', 'CC29F5', 'CC785F', 'D023DB', 'D03311', 'D04F7E',
        'D0817A', 'D0A637', 'D0C5F3', 'D0D2B0', 'D0E140', 'D48F33',
        'D4909C', 'D493D9', 'D4A33D', 'D4DCCD', 'D4F46F', 'D8004D',
        'D81D72', 'D83062', 'D89695', 'D8A25E', 'D8BB2C', 'D8CF9C',
        'DC0C5C', '3C2EFF', 'DC2B2A', 'DC2B61', 'DC3714', 'DC415F',
        'DC56E7', 'DC86D8', 'DC9B9C', 'DCA4CA', 'DCB4C4', 'DCD3A2',
        'E06267', 'E0ACCB', 'E0B52D', 'E0C767', 'E0C97A', 'E0F5C6',
        'E0F847', 'E42B34', 'E49A79', 'E4C63D', 'E4CE8F', 'E4E4AB',
        'E80688', 'E81132', 'E88D28', 'E8B2AC', 'EC3586', 'EC852F',
        'ECADB8', 'F05A09', 'F0B479', 'F0CBA1', 'F0D1A9', 'F0DBE2',
        'F0DBF8', 'F0F61C', 'F41BA1', 'F431C3', 'F437B7', 'F45C89',
        'F4F15A', 'F4F951', 'F82793', 'F86214', 'F8E94E', 'F8F1B6',
        'FC2530', 'FC253F', 'FC8F90', 'FCE998', 'FCF136', 'FCF152'
    ]
    
    oui = mac_clean[:6]
    
    if oui in apple_ouis:
        return 'Apple'
    else:
        return 'Android'  # Android나 기타 디바이스

def analyze_flow_by_time(flow_data, time_bin_minutes=30):
    """
    시간대별 Apple vs Android 디바이스 분석
    
    Parameters:
    - flow_data: Flow DataFrame (sward_id, mac, type, rssi, time)
    - time_bin_minutes: 시간 bin 크기 (기본 30분)
    
    Returns:
    - time_analysis_df: 시간대별 분석 결과
    """
    
    if flow_data is None or flow_data.empty:
        return None
    
    # 디바이스 타입 식별 (type 컬럼 사용: 1=Apple, 10=Android)
    if 'type' in flow_data.columns:
        flow_data['device_type'] = flow_data['type'].apply(identify_device_type_from_type_column)
    else:
        # type 컬럼이 없으면 MAC 주소로 추정 (deprecated)
        flow_data['device_type'] = flow_data['mac'].apply(identify_device_type)
    
    # 날짜와 시간 추출
    flow_data['date'] = flow_data['time'].dt.date
    flow_data['hour'] = flow_data['time'].dt.hour
    flow_data['minute'] = flow_data['time'].dt.minute
    
    # 시간 bin 생성 (30분 단위)
    flow_data['time_bin'] = (flow_data['hour'] * 60 + flow_data['minute']) // time_bin_minutes
    flow_data['time_label'] = flow_data['time_bin'].apply(
        lambda x: f"{(x * time_bin_minutes) // 60:02d}:{(x * time_bin_minutes) % 60:02d}"
    )
    
    # 시간대별 unique MAC 주소 카운팅
    time_analysis = []
    
    for time_bin in sorted(flow_data['time_bin'].unique()):
        bin_data = flow_data[flow_data['time_bin'] == time_bin]
        time_label = bin_data['time_label'].iloc[0]
        
        # Unique MAC 주소별 디바이스 타입 카운팅
        apple_count = bin_data[bin_data['device_type'] == 'Apple']['mac'].nunique()
        android_count = bin_data[bin_data['device_type'] == 'Android']['mac'].nunique()
        unknown_count = bin_data[bin_data['device_type'] == 'Unknown']['mac'].nunique()
        total_count = apple_count + android_count + unknown_count
        
        time_analysis.append({
            'time_bin': time_bin,
            'time': time_label,
            'apple_count': apple_count,
            'android_count': android_count,
            'unknown_count': unknown_count,
            'total_count': total_count,
            'apple_ratio': apple_count / total_count * 100 if total_count > 0 else 0,
            'android_ratio': android_count / total_count * 100 if total_count > 0 else 0,
            'unknown_ratio': unknown_count / total_count * 100 if total_count > 0 else 0
        })
    
    return pd.DataFrame(time_analysis)

def analyze_flow_daily(flow_data):
    """
    하루 전체 Apple vs Android 디바이스 분석
    
    Returns:
    - daily_analysis: 하루 전체 통계
    """
    
    if flow_data is None or flow_data.empty:
        return None
    
    # 디바이스 타입 식별 (이미 있으면 스킵)
    if 'device_type' not in flow_data.columns:
        if 'type' in flow_data.columns:
            flow_data['device_type'] = flow_data['type'].apply(identify_device_type_from_type_column)
        else:
            flow_data['device_type'] = flow_data['mac'].apply(identify_device_type)
    
    # 하루 전체 unique MAC 주소 카운팅
    apple_macs = flow_data[flow_data['device_type'] == 'Apple']['mac'].nunique()
    android_macs = flow_data[flow_data['device_type'] == 'Android']['mac'].nunique()
    unknown_macs = flow_data[flow_data['device_type'] == 'Unknown']['mac'].nunique()
    total_macs = apple_macs + android_macs + unknown_macs
    
    daily_analysis = {
        'apple_count': apple_macs,
        'android_count': android_macs,
        'unknown_count': unknown_macs,
        'total_count': total_macs,
        'apple_ratio': apple_macs / total_macs * 100 if total_macs > 0 else 0,
        'android_ratio': android_macs / total_macs * 100 if total_macs > 0 else 0,
        'unknown_ratio': unknown_macs / total_macs * 100 if total_macs > 0 else 0
    }
    
    return daily_analysis

def render_flow_occupancy_analysis():
    """Flow Data - Occupancy Analysis 렌더링"""
    
    st.subheader("📱 Device Type Analysis: Apple vs Android")
    st.write("**Time-based device occupancy analysis (30-min bins)**")
    
    # 데이터 확인
    if 'flow_data' not in st.session_state or st.session_state.flow_data is None:
        st.error("⚠️ Flow data not loaded. Please upload flow data first.")
        return
    
    flow_data = st.session_state.flow_data.copy()
    st.success(f"✅ Flow Data Loaded: {len(flow_data):,} records")
    
    # 🔍 type 컬럼 확인 및 검증
    with st.expander("🔍 Data Validation: Check 'type' column", expanded=False):
        if 'type' in flow_data.columns:
            type_counts = flow_data['type'].value_counts().sort_index()
            st.write("**Type column values:**")
            st.write(type_counts)
            
            st.write("**Interpretation:**")
            st.write("- Type 1: Apple devices")
            st.write("- Type 10: Android devices")
            st.write("- Other values: Unknown")
            
            # 샘플 데이터 표시
            st.write("**Sample data (first 10 rows):**")
            st.dataframe(flow_data[['mac', 'type', 'rssi', 'time']].head(10))
            
            st.success("✅ Using 'type' column for device identification")
        else:
            st.warning("⚠️ 'type' column not found. Using MAC address OUI (less accurate)")
    
    # 시간 bin 크기 선택
    time_bin = st.selectbox("Select Time Bin Size:", [15, 30, 60], index=1)
    
    with st.spinner("Analyzing device types..."):
        # 시간대별 분석
        time_analysis_df = analyze_flow_by_time(flow_data, time_bin_minutes=time_bin)
        
        # 하루 전체 분석
        daily_analysis = analyze_flow_daily(flow_data)
    
    if time_analysis_df is None or daily_analysis is None:
        st.error("❌ Analysis failed.")
        return
    
    # 하루 전체 통계 표시
    st.write("---")
    st.subheader("📊 Daily Summary (Unique Devices)")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🍎 Apple Devices", f"{daily_analysis['apple_count']:,}", 
                 f"{daily_analysis['apple_ratio']:.1f}%")
    with col2:
        st.metric("🤖 Android Devices", f"{daily_analysis['android_count']:,}",
                 f"{daily_analysis['android_ratio']:.1f}%")
    with col3:
        st.metric("❓ Unknown Devices", f"{daily_analysis['unknown_count']:,}",
                 f"{daily_analysis['unknown_ratio']:.1f}%")
    with col4:
        st.metric("📱 Total Devices", f"{daily_analysis['total_count']:,}")
    
    # 파이 차트
    fig_pie, ax = plt.subplots(figsize=(10, 6))
    sizes = [daily_analysis['apple_count'], daily_analysis['android_count'], daily_analysis['unknown_count']]
    labels = [f"Apple\n{daily_analysis['apple_count']:,}", 
             f"Android\n{daily_analysis['android_count']:,}",
             f"Unknown\n{daily_analysis['unknown_count']:,}"]
    colors = ['#A2AAAD', '#3DDC84', '#CCCCCC']  # Apple 회색, Android 초록, Unknown 회색
    explode = (0.05, 0.05, 0)
    
    ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
           shadow=True, startangle=90, textprops={'fontsize': 12, 'fontweight': 'bold'})
    ax.set_title('Device Distribution (Daily Total)', fontsize=14, fontweight='bold')
    
    st.pyplot(fig_pie)
    plt.close(fig_pie)
    
    # 시간대별 분석
    st.write("---")
    st.subheader(f"⏰ Time-based Analysis ({time_bin}-min bins)")
    
    # 시간대별 디바이스 수 그래프
    fig_time, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))
    
    x = time_analysis_df['time_bin'].values
    
    # 상단: 절대 개수
    ax1.plot(x, time_analysis_df['apple_count'], color='#A2AAAD', linewidth=2, marker='o', label='Apple')
    ax1.plot(x, time_analysis_df['android_count'], color='#3DDC84', linewidth=2, marker='s', label='Android')
    ax1.plot(x, time_analysis_df['total_count'], color='black', linewidth=2, linestyle='--', label='Total')
    
    ax1.set_xlabel(f'Time Bin ({time_bin}-min intervals)', fontsize=12)
    ax1.set_ylabel('Number of Unique Devices', fontsize=12)
    ax1.set_title('Device Count by Time', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    
    # X축 시간 레이블
    x_ticks = list(range(0, len(time_analysis_df), max(1, len(time_analysis_df) // 12)))
    x_labels = [time_analysis_df.iloc[i]['time'] for i in x_ticks]
    ax1.set_xticks(x_ticks)
    ax1.set_xticklabels(x_labels, rotation=45)
    
    # 하단: 비율 (스택 영역 그래프)
    ax2.fill_between(x, 0, time_analysis_df['apple_ratio'], 
                     color='#A2AAAD', alpha=0.7, label='Apple')
    ax2.fill_between(x, time_analysis_df['apple_ratio'], 
                     time_analysis_df['apple_ratio'] + time_analysis_df['android_ratio'],
                     color='#3DDC84', alpha=0.7, label='Android')
    
    ax2.set_xlabel(f'Time Bin ({time_bin}-min intervals)', fontsize=12)
    ax2.set_ylabel('Device Ratio (%)', fontsize=12)
    ax2.set_title('Device Ratio by Time', fontsize=14, fontweight='bold')
    ax2.legend(fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 100)
    
    ax2.set_xticks(x_ticks)
    ax2.set_xticklabels(x_labels, rotation=45)
    
    plt.tight_layout()
    st.pyplot(fig_time)
    plt.close(fig_time)
    
    # 테이블 표시
    st.write("**📋 Detailed Time-based Statistics**")
    display_df = time_analysis_df[['time', 'apple_count', 'android_count', 'unknown_count', 
                                    'total_count', 'apple_ratio', 'android_ratio']].copy()
    display_df.columns = ['Time', 'Apple', 'Android', 'Unknown', 'Total', 'Apple %', 'Android %']
    display_df['Apple %'] = display_df['Apple %'].round(1)
    display_df['Android %'] = display_df['Android %'].round(1)
    
    st.dataframe(display_df, use_container_width=True)
    
    # CSV 다운로드
    csv_data = display_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Time Analysis (CSV)",
        data=csv_data,
        file_name="flow_device_analysis_time.csv",
        mime="text/csv"
    )
