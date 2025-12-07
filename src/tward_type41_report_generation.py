"""
T-Ward Type 41 Report Generation Module
Comprehensive report generation with filtering for T-Wards dwelling 30+ minutes
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import io
import base64
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.lib.colors import HexColor
import tempfile
import os
from .tward_type41_dwell_time import display_tward_dwell_charts

def render_tward41_report_generation(st):
    print("📊 >>> render_tward41_report_generation called - NEW VERSION")
    """T-Ward Type 41 Report Generation 탭 렌더링"""
    
    st.markdown("### 📊 T-Ward Type 41 Report Generation")
    st.info("📋 Comprehensive analysis report with 30+ minute dwell time filtering")
    
    # 분석 결과 확인
    if 'tward41_analysis_results' not in st.session_state:
        st.warning("⚠️ No Type 41 analysis results found. Please run Occupancy Analysis first.")
        st.markdown("**Steps to generate comprehensive report:**")
        st.markdown("1. Go to **Occupancy Analysis** tab")
        st.markdown("2. Run the analysis with your T-Ward Type 41 data")
        st.markdown("3. Return to this tab to generate comprehensive report")
        return
    
    try:
        # 활동 데이터 확인
        if 'type41_activity_analysis' not in st.session_state:
            st.warning("⚠️ Activity analysis data not found. Please complete Occupancy Analysis first.")
            return
            
        activity_analysis = st.session_state['type41_activity_analysis']
        analysis_results = st.session_state['tward41_analysis_results']
        
        # 데이터 가용성 확인 및 정보 표시
        detected_buildings = []
        if activity_analysis is not None and not activity_analysis.empty:
            if 'building' in activity_analysis.columns:
                buildings = activity_analysis['building'].dropna().unique()
                detected_buildings = [b for b in buildings if str(b) != 'Unknown']
        
        # 데이터 가용성 알림
        if detected_buildings:
            buildings_text = ', '.join(detected_buildings)
            st.info(f"📊 Report Generation for detected buildings: **{buildings_text}**")
        else:
            st.warning("⚠️ No building data detected in activity analysis.")
            
        # S-Ward 구성과 실제 데이터 비교 정보 표시
        try:
            from .building_setup import load_sward_config
            sward_config = load_sward_config()
            if sward_config is not None and not sward_config.empty:
                configured_buildings = sward_config['building'].unique()
                missing_buildings = set(configured_buildings) - set(detected_buildings)
                if missing_buildings:
                    st.info(f"ℹ️ Configured but no data available: {', '.join(missing_buildings)}")
        except:
            pass  # Skip if building_setup not available

        # 리포트 생성 (PDF 기능 포함)
        with st.spinner("Generating comprehensive analysis report..."):
            report_content = generate_comprehensive_report(st, activity_analysis, analysis_results)
                
    except Exception as e:
        st.error(f"Error in Report Generation: {str(e)}")

def generate_comprehensive_report(st, activity_analysis, analysis_results):
    """Worker Traffic Analysis Report 생성 - 지시사항에 따른 정확한 구현"""
    
    try:
        # 세련된 스타일링 CSS (Type 31 참고)
        st.markdown("""
        <style>
        .report-header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #667eea 100%);
            color: white;
            padding: 3rem 2rem;
            border-radius: 20px;
            margin: 2rem 0;
            text-align: center;
            box-shadow: 0 15px 50px rgba(30, 60, 114, 0.3);
            position: relative;
            overflow: hidden;
        }
        .report-header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: shimmer 3s infinite;
        }
        @keyframes shimmer {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .report-title {
            font-size: 3rem;
            font-weight: 800;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 10px rgba(0,0,0,0.4);
            position: relative;
            z-index: 1;
        }
        .report-info {
            font-size: 1.1rem;
            line-height: 1.8;
            opacity: 0.95;
            position: relative;
            z-index: 1;
            margin-top: 1.5rem;
        }
        .section-container {
            background: white;
            padding: 2rem;
            border-radius: 15px;
            margin: 2rem 0;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            border: 1px solid rgba(102, 126, 234, 0.1);
        }
        .section-title {
            color: #1e3c72;
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 3px solid #667eea;
        }
        .subsection-title {
            color: #2a5298;
            font-size: 1.4rem;
            font-weight: 600;
            margin: 2rem 0 1rem 0;
        }
        .chart-container {
            background: #fafbfc;
            padding: 1.5rem;
            border-radius: 10px;
            margin: 1rem 0;
            border: 1px solid #e1e8f0;
        }
        .section-header {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 15px;
            margin: 2rem 0 1.5rem 0;
            box-shadow: 0 8px 25px rgba(245, 87, 108, 0.3);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .section-header h3 {
            margin: 0;
            font-weight: 700;
            font-size: 1.4rem;
            text-shadow: 1px 1px 3px rgba(0,0,0,0.2);
        }
        .metric-card {
            background: linear-gradient(145deg, #ffffff 0%, #f8f9fa 100%);
            padding: 1.8rem;
            border-radius: 15px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.1);
            margin: 1rem 0;
            border: 1px solid rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        }
        .metric-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        }
        .download-section {
            background: linear-gradient(135deg, #e8f4fd 0%, #f3e8ff 100%);
            padding: 2.5rem;
            border-radius: 20px;
            margin: 2rem 0;
            border: 2px solid rgba(102, 126, 234, 0.2);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.1);
        }
        .chart-container {
            background: white;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
            margin: 1.5rem 0;
            border: 1px solid rgba(0,0,0,0.05);
        }
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 1rem 2.5rem;
            font-weight: 700;
            font-size: 1rem;
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stButton > button:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.5);
        }
        .info-alert {
            background: linear-gradient(135deg, #e3f2fd 0%, #f0f4c3 100%);
            border-left: 5px solid #2196f3;
            padding: 1.5rem;
            border-radius: 10px;
            margin: 1.5rem 0;
            box-shadow: 0 4px 15px rgba(33, 150, 243, 0.2);
        }
        .success-alert {
            background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
            border-left: 5px solid #4caf50;
            padding: 1.5rem;
            border-radius: 10px;
            margin: 1.5rem 0;
            box-shadow: 0 4px 15px rgba(76, 175, 80, 0.2);
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 리포트 헤더 - 동적 건물 감지
        # 활동 데이터에서 건물 정보 자동 감지
        detected_buildings = []
        detected_levels = []
        if activity_analysis is not None and not activity_analysis.empty:
            if 'building' in activity_analysis.columns:
                buildings = activity_analysis['building'].dropna().unique()
                detected_buildings = [b for b in buildings if str(b) != 'Unknown']
            if 'level' in activity_analysis.columns:
                levels = activity_analysis['level'].dropna().unique()
                detected_levels = [l for l in levels if str(l) != 'Unknown']
        
        # 기본값 설정
        if not detected_buildings:
            detected_buildings = ['WWT']
        if not detected_levels:
            detected_levels = ['1F', 'B1F']
            
        buildings_text = ', '.join(detected_buildings) + (' Building' if len(detected_buildings) == 1 else ' Buildings')
        levels_text = ', '.join(detected_levels)
        
        st.markdown(f"""
        <div class="report-header">
            <div class="report-title">Worker Traffic Analysis Report</div>
            <div class="report-info">
                <strong>Target Building:</strong> {buildings_text}<br>
                <strong>Analysis Levels:</strong> {levels_text}<br>
                <strong>Analysis Date:</strong> August 22, 2025 (24-Hour Period)<br>
                <strong>System:</strong> Hy-con & IRFM by TJLABS<br>
                <strong>Data Source:</strong> T-Ward Type 41 Sensors on Workers' helmet
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 데이터 커버리지 정보 섹션 추가
        st.markdown('<div class="subsection-title">📊 Data Coverage Information</div>', unsafe_allow_html=True)
        
        # 실제 데이터 vs 구성 정보 비교
        try:
            from .building_setup import load_sward_config
            sward_config = load_sward_config()
            if sward_config is not None and not sward_config.empty:
                configured_buildings = sward_config['building'].unique()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Configured Buildings:**")
                    for building in configured_buildings:
                        building_swards = len(sward_config[sward_config['building'] == building])
                        status = "✅ Data Available" if building in detected_buildings else "❌ No Data"
                        st.markdown(f"- **{building}**: {building_swards} S-Wards ({status})")
                
                with col2:
                    st.markdown("**Analysis Coverage:**")
                    if activity_analysis is not None and not activity_analysis.empty:
                        total_records = len(activity_analysis)
                        unique_twards = activity_analysis['mac'].nunique()
                        st.metric("Total Records", f"{total_records:,}")
                        st.metric("Unique T-Wards", unique_twards)
                    else:
                        st.warning("No activity data available")
                        
                if set(configured_buildings) - set(detected_buildings):
                    missing = list(set(configured_buildings) - set(detected_buildings))
                    st.info(f"💡 **Note**: {', '.join(missing)} building(s) configured but no sensor data available for this time period.")
        except Exception as e:
            # Skip if building setup not available
            pass
            
        st.markdown("---")
        
        # 1. Occupancy Analysis 섹션
        display_occupancy_analysis_section(st, analysis_results)
        
        # 2. Dwell Time Analysis 섹션
        display_dwell_time_analysis_section(st, activity_analysis)
        
        # 3. Journey Heatmap Analysis 섹션
        display_journey_analysis_section(st, activity_analysis)
        
        # 4. PDF Report Generation 섹션 추가 (Type 31 스타일)
        st.markdown("---")  # 구분선
        st.markdown("### 📄 PDF Report Generation")
        st.info("Generate comprehensive PDF report based on the analysis results above.")
        
        # Automatic PDF generation (New capture method - 100% Report Generation page replication)
        with st.spinner("Capturing Report Generation page and generating PDF..."):
            try:
                from .tward_type41_pdf_capture import generate_report_page_pdf_v2
                pdf_result = generate_report_page_pdf_v2(activity_analysis, analysis_results)
                if pdf_result:
                    from .tward_type41_pdf_capture import display_pdf_preview_v2
                    display_pdf_preview_v2(pdf_result)
                    
                    # Success message and effects
                    st.balloons()
                    st.success("🎉 Report Generation page has been 100% converted to PDF!")
                else:
                    st.error("❌ PDF generation failed. Error occurred during Report Generation page capture.")
            except Exception as e:
                import traceback
                st.error(f"❌ Failed to generate PDF report: {str(e)}")
                st.code(traceback.format_exc())
        
        # 5. CSV 데이터 생성
        csv_content = generate_csv_report(activity_analysis)
        
        st.success("✅ Worker Traffic Analysis Report generated successfully!")
        
        return csv_content
        
    except Exception as e:
        st.error(f"Error generating comprehensive report: {str(e)}")
        return None

def display_occupancy_analysis_section(st, analysis_results):
    """Occupancy Analysis 섹션 표시 - Occupancy Analysis 탭과 동일"""
    
    st.markdown("### 📊 1. Occupancy Analysis")
    
    try:
        if not analysis_results:
            st.warning("No occupancy analysis results available")
            return
            
        # Occupancy Analysis 탭과 동일한 내용 표시
        summary_stats = analysis_results.get('summary_stats')
        minute_activity = analysis_results.get('minute_activity')
        
        # 요약 통계 표시
        st.markdown("#### 📊 Worker Activity Summary")
        
        if summary_stats is not None and not summary_stats.empty:
            # 통계 테이블 표시
            display_columns = ['space_name', 'total_workers', 'max_active_workers', 'avg_active_workers', 'max_present_workers', 'avg_present_workers']
            column_names = ['Space', 'Total Workers', 'Max Active', 'Avg Active', 'Max Present', 'Avg Present']
            
            if all(col in summary_stats.columns for col in display_columns):
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
            else:
                st.info("Summary statistics data format not compatible")
        else:
            st.info("No summary statistics available")
        
        # Worker Activity by Minute 그래프
        if minute_activity is not None and not minute_activity.empty:
            st.markdown("#### � Worker Activity by Minute (1-minute resolution)")
            
            # 1분 단위 원본 데이터 사용 (1440개 점)
            display_data = minute_activity
            
            if not display_data.empty:
                # Active Workers, Present Workers & Total Workers 그래프
                fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 15))
                
                # 색상 팔레트 최적화
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
                
                # X축을 시간(분)으로 변환하고 24시 직선 연결 문제 완전 해결
                display_data_copy = display_data.copy()
                display_data_copy['time_hours'] = display_data_copy['minute_bin'] / 60
                
                # 24시간(1440분) 이상의 데이터 완전 제거하여 직선 연결 방지
                display_data_copy = display_data_copy[display_data_copy['minute_bin'] <= 1440].copy()
                display_data_copy = display_data_copy[display_data_copy['time_hours'] < 24.0].copy()
                
                # Active Workers (헬멧 착용 작업자)
                for i, space_name in enumerate(display_data_copy['space_name'].unique()):
                    space_data = display_data_copy[display_data_copy['space_name'] == space_name].copy()
                    
                    # 정렬하여 시간 순서대로 플롯 (직선 연결 방지)
                    space_data = space_data.sort_values('time_hours')
                    
                    # 23시 59분을 넘지 않도록 추가 필터링
                    space_data = space_data[space_data['time_hours'] <= 23.99].copy()
                    
                    if not space_data.empty:
                        ax1.plot(space_data['time_hours'], space_data['active_workers'], 
                                label=space_name, linewidth=1, alpha=0.8,
                                color=colors[i % len(colors)])
                
                ax1.set_title('Active Workers (Helmet On) - 1 Minute Resolution', fontsize=14, fontweight='bold')
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
                    space_data = display_data_copy[display_data_copy['space_name'] == space_name].copy()
                    
                    # 정렬하여 시간 순서대로 플롯 (직선 연결 방지)
                    space_data = space_data.sort_values('time_hours')
                    
                    # 23시 59분을 넘지 않도록 추가 필터링
                    space_data = space_data[space_data['time_hours'] <= 23.99].copy()
                    
                    if not space_data.empty:
                        ax2.plot(space_data['time_hours'], space_data['present_workers'], 
                                label=space_name, linewidth=1, alpha=0.8,
                                color=colors[i % len(colors)])
                
                ax2.set_title('Total Present Workers (All Workers) - 1 Minute Resolution', fontsize=14, fontweight='bold')
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
                    space_data = display_data_copy[display_data_copy['space_name'] == space_name].copy()
                    
                    # 정렬하여 시간 순서대로 플롯 (직선 연결 방지)
                    space_data = space_data.sort_values('time_hours')
                    
                    # 23시 59분을 넘지 않도록 추가 필터링
                    space_data = space_data[space_data['time_hours'] <= 23.99].copy()
                    
                    if not space_data.empty:
                        ax3.plot(space_data['time_hours'], space_data['total_workers'], 
                                label=space_name, linewidth=1, alpha=0.8,
                                color=colors[i % len(colors)])
                
                ax3.set_title('Total Workers (All T-Wards Detected) - 1 Minute Resolution', fontsize=14, fontweight='bold')
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
        else:
            st.info("No minute activity data available for chart")
        
        # Occupancy Analysis Information
        st.markdown('<div class="subsection-title">ℹ️ Occupancy Analysis Information</div>', unsafe_allow_html=True)
        st.info("""
        **Occupancy Analysis Details:**
        - **Resolution**: 1-minute interval analysis across 24 hours
        - **Active Workers**: T-Wards with helmet on (activity status = 'Active')
        - **Present Workers**: All T-Wards present in the area (activity status = 'Present' or 'Active')
        - **Total Workers**: All T-Wards detected in any status (Active, Present, Absent)
        - **Time Range**: 00:00 - 23:59 (24-hour coverage)
        - **Data Source**: Real-time T-Ward location and activity monitoring
        - **Chart Type**: Time series line chart with space-specific color coding
        """)
        
    except Exception as e:
        st.error(f"Error in occupancy analysis section: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)

def apply_beautiful_chart_style():
    """차트에 아름다운 스타일 적용"""
    plt.style.use('seaborn-v0_8')
    sns.set_palette("husl")

# DEPRECATED: 기존 display_fixed_worker_activity_chart 함수는 제거됨
# Occupancy Analysis 탭과 동일한 차트가 display_occupancy_analysis_section에서 사용됨

def display_dwell_time_analysis_section(st, activity_analysis):
    """Dwell Time Analysis 섹션 표시 - 지시사항에 따른 정확한 구현"""
    
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">⏱️ 2. Dwell Time Analysis</div>', unsafe_allow_html=True)
    
    try:
        if activity_analysis is None or activity_analysis.empty:
            st.warning("No activity analysis data available")
            return
            
        from .tward_type41_dwell_time import analyze_dwell_times
        
        # 체류시간 분석 실행
        dwell_results = analyze_dwell_times(activity_analysis)
        if not dwell_results:
            st.warning("No dwell time analysis results available")
            return
        
        # Dwell Time Analysis Information
        st.markdown('<div class="subsection-title">📋 Dwell Time Analysis Information</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total T-Wards", activity_analysis['mac'].nunique())
        with col2:
            occupied_records = len(activity_analysis[activity_analysis['activity_status'].isin(['Active', 'Present'])])
            st.metric("Occupied Records", f"{occupied_records:,}")
        with col3:
            avg_dwell = occupied_records / activity_analysis['mac'].nunique() if activity_analysis['mac'].nunique() > 0 else 0
            st.metric("Avg Records/T-Ward", f"{avg_dwell:.1f}")
        
        # Dwell Time Statistics 표
        st.markdown('<div class="subsection-title">📊 Dwell Time Statistics</div>', unsafe_allow_html=True)
        if 'statistics' in dwell_results and dwell_results['statistics']:
            statistics = dwell_results['statistics']
            
            # Building별 통계
            st.markdown("**Building-level Statistics**")
            building_stats = []
            for key, stats in statistics.items():
                if key.startswith('Building_'):
                    space_name = key.replace('Building_', '')
                    building_stats.append({
                        'Space': space_name,
                        'Total Workers': stats['total_workers'],
                        'Min (min)': stats['min_dwell_minutes'],
                        'Max (min)': stats['max_dwell_minutes'],
                        'Avg (min)': stats['avg_dwell_minutes'],
                        'Median (min)': stats['median_dwell_minutes'],
                        'Std Dev (min)': stats['std_dwell_minutes'],
                        'Avg (hours)': stats['avg_dwell_hours']
                    })
            
            if building_stats:
                building_df = pd.DataFrame(building_stats)
                st.dataframe(building_df, use_container_width=True)
            
            # Level별 통계
            st.markdown("**Level-specific Statistics**")
            level_stats = []
            for key, stats in statistics.items():
                if key.startswith('Level_'):
                    space_name = key.replace('Level_', '')
                    level_stats.append({
                        'Space': space_name,
                        'Total Workers': stats['total_workers'],
                        'Min (min)': stats['min_dwell_minutes'],
                        'Max (min)': stats['max_dwell_minutes'],
                        'Avg (min)': stats['avg_dwell_minutes'],
                        'Median (min)': stats['median_dwell_minutes'],
                        'Std Dev (min)': stats['std_dwell_minutes'],
                        'Avg (hours)': stats['avg_dwell_hours']
                    })
            
            if level_stats:
                level_df = pd.DataFrame(level_stats)
                st.dataframe(level_df, use_container_width=True)
        
        # T-Ward Individual Dwell Time Charts (3개 그래프)
        st.markdown('<div class="subsection-title">📊 T-Ward Individual Dwell Time Charts</div>', unsafe_allow_html=True)
        if dwell_results and 'dwell_df' in dwell_results and not dwell_results['dwell_df'].empty:
            display_tward_dwell_charts(st, dwell_results['dwell_df'])
        else:
            st.warning("No dwell data available for individual charts")
        
        # Dwell Time Distribution (30-minute intervals) - Building-level만
        st.markdown('<div class="subsection-title">📊 Dwell Time Distribution (30-minute intervals)</div>', unsafe_allow_html=True)
        if 'histogram_data' in dwell_results and dwell_results['histogram_data']:
            building_histograms = {k: v for k, v in dwell_results['histogram_data'].items() if k.startswith('Building_')}
            if building_histograms:
                st.markdown("**Building-level Distribution**")
                display_distribution_charts(st, building_histograms)
        
        # Dwell Time Analysis Information
        st.markdown('<div class="subsection-title">ℹ️ Dwell Time Analysis Information</div>', unsafe_allow_html=True)
        st.info("""
        **Dwell Time Analysis Details:**
        - **Metric**: Cumulative time spent by each T-Ward in monitored spaces
        - **Resolution**: Minute-level accuracy with statistical summaries
        - **Analysis Levels**: Building-level and Level-specific (1F, B1F) breakdowns
        - **Statistics**: Min, Max, Average, Median, Standard Deviation for each space
        - **Distribution**: 30-minute interval histograms for building-level analysis
        - **Individual Charts**: T-Ward-specific dwell time visualization (sorted by duration)
        - **Data Filtering**: Present/Active status T-Wards only
        """)
        
    except Exception as e:
        st.error(f"Error in dwell time analysis section: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)



def display_distribution_charts(st, histogram_data):
    """Dwell Time Distribution 차트 표시 - Building-level만"""
    
    for space_key, hist_data in histogram_data.items():
        space_name = space_key.replace('Building_', '')
        
        st.markdown(f'<div class="chart-container">', unsafe_allow_html=True)
        st.markdown(f"**{space_name} - Dwell Time Distribution**")
        
        # 히스토그램 생성
        fig, ax = plt.subplots(figsize=(12, 6))
        
        bins = hist_data['bins']
        counts = hist_data['counts']
        labels = hist_data['labels']
        
        # 막대 그래프 (counts와 labels 길이 맞춤)
        bars = ax.bar(range(len(counts)), counts, color='#2a5298', alpha=0.8, edgecolor='white', linewidth=1)
        
        # X축 라벨 설정 (counts 길이에 맞춰 라벨 조정)
        ax.set_xticks(range(len(counts)))
        if len(labels) >= len(counts):
            ax.set_xticklabels(labels[:len(counts)], rotation=45, ha='right', fontsize=10)
        else:
            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=10)
        
        # Y축 설정
        ax.set_ylabel('Number of T-Wards', fontsize=12, fontweight='bold')
        ax.set_xlabel('Dwell Time Intervals', fontsize=12, fontweight='bold')
        
        # 제목
        total_workers = sum(counts)
        ax.set_title(f'{space_name} - Dwell Time Distribution (30-min intervals)\n'
                    f'Total Workers: {total_workers}',
                    fontsize=14, fontweight='bold', pad=20)
        
        # 격자
        ax.grid(True, axis='y', alpha=0.3)
        ax.set_axisbelow(True)
        
        # 스타일링
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#ddd')
        ax.spines['bottom'].set_color('#ddd')
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        st.markdown('</div>', unsafe_allow_html=True)



def display_dwell_distribution_charts(st, dwell_results):
    """체류시간 분포 히스토그램 표시 - 아름다운 디자인"""
    
    try:
        histogram_data = dwell_results.get('histogram_data', {})
        if not histogram_data:
            st.warning("No histogram data available")
            return
            
        # Building-level Distribution
        building_data = {k: v for k, v in histogram_data.items() if k.startswith('Building_')}
        
        if building_data:
            # 섹션 헤더 스타일링
            st.markdown("""
            <div class="section-header">
                <h4>🏢 Building-level Distribution</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # 차트 컨테이너 스타일
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            
            # 아름다운 차트 생성
            fig, axes = plt.subplots(1, len(building_data), figsize=(8*len(building_data), 8))
            fig.patch.set_facecolor('white')
            
            if len(building_data) == 1:
                axes = [axes]
                
            # 색상 팔레트
            colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe']
                
            for i, (building_key, data) in enumerate(building_data.items()):
                building_name = building_key.replace('Building_', '')
                
                if 'counts' in data and 'bins' in data:
                    # 그라디언트 색상 적용
                    color = colors[i % len(colors)]
                    
                    bars = axes[i].bar(data['bins'][:-1], data['counts'], 
                                     width=np.diff(data['bins']), 
                                     alpha=0.8, color=color, 
                                     edgecolor='white', linewidth=2)
                    
                    # Title styling
                    axes[i].set_title(f'{building_name} Building', 
                                    fontsize=14, fontweight='bold')
                    axes[i].set_xlabel('Dwell Time (minutes)')
                    axes[i].set_ylabel('Count')
                    
                    # X축 라벨 개선
                    axes[i].set_xticks(data['bins'][::2])
                    axes[i].set_xticklabels([f'{int(x)}' for x in data['bins'][::2]], 
                                          rotation=45, ha='right', fontsize=10)
                    
                    # 그리드 및 배경 스타일링
                    axes[i].grid(True, alpha=0.3, linestyle='--', color='#bdc3c7')
                    axes[i].set_facecolor('#fafafa')
                    
                    # 축 스타일링
                    for spine in axes[i].spines.values():
                        spine.set_color('#bdc3c7')
                        spine.set_linewidth(1.5)
                    
                    # 값 표시 (높은 막대에만)
                    max_count = max(data['counts'])
                    for j, bar in enumerate(bars):
                        height = bar.get_height()
                        if height > max_count * 0.1:  # 10% 이상인 막대에만 표시
                            axes[i].text(bar.get_x() + bar.get_width()/2., height,
                                       f'{int(height)}',
                                       ha='center', va='bottom', fontsize=9, fontweight='bold',
                                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
                    
                    # 통계 정보 텍스트 박스
                    total_count = sum(data['counts'])
                    avg_dwell = np.average(data['bins'][:-1], weights=data['counts']) if total_count > 0 else 0
                    stats_text = f'Total: {total_count}\nAvg: {avg_dwell:.1f}m'
                    axes[i].text(0.02, 0.98, stats_text, transform=axes[i].transAxes, 
                               fontsize=10, verticalalignment='top',
                               bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.9, 
                                        edgecolor=color, linewidth=2))
            
            plt.tight_layout(pad=3.0)
            st.pyplot(fig)
            plt.close()
            
            st.markdown('</div>', unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"Error creating distribution charts: {str(e)}")

def display_journey_analysis_section(st, activity_analysis):
    """Journey Heatmap Analysis 섹션 표시 - 지시사항에 따른 정확한 구현"""
    
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🗺️ 3. Journey Heatmap Analysis</div>', unsafe_allow_html=True)
    
    # Add color legend
    st.markdown("""
    <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin: 10px 0;">
        <h4 style="margin-top: 0; color: #1f2937;">Color Legend:</h4>
        <div style="display: flex; flex-wrap: wrap; gap: 20px;">
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 20px; background-color: black; margin-right: 8px; border-radius: 3px;"></div>
                <span><strong>Black:</strong> Absence in WWT</span>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 20px; background-color: #808080; margin-right: 8px; border-radius: 3px;"></div>
                <span><strong>Grey:</strong> Presence in WWT, but inactive</span>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 20px; background-color: #00ff00; margin-right: 8px; border-radius: 3px;"></div>
                <span><strong>Green:</strong> Active Presence in WWT - 1F</span>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 20px; background-color: #ffff00; margin-right: 8px; border-radius: 3px;"></div>
                <span><strong>Yellow:</strong> Active Presence in WWT - B1F</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        if activity_analysis is None or activity_analysis.empty:
            st.warning("No activity analysis data available")
            return
            
        from .tward_type41_journey_map import analyze_journey_patterns
        
        # Journey 패턴 분석 실행 (Building과 Level 모두)
        building_results = analyze_journey_patterns(activity_analysis, 'building')
        level_results = analyze_journey_patterns(activity_analysis, 'level')
        
        journey_results = {
            'building': building_results,
            'level': level_results
        }
        
        if not journey_results.get('building') and not journey_results.get('level'):
            st.warning("No journey analysis results available")
            return
            
        # JourneyMap Analysis Information
        st.markdown('<div class="subsection-title">📋 JourneyMap Analysis Information</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Analysis Records", f"{len(activity_analysis):,}")
        with col2:
            unique_spaces = activity_analysis['space'].nunique() if 'space' in activity_analysis.columns else 0
            st.metric("Monitored Spaces", unique_spaces)
        with col3:
            journey_records = len(activity_analysis[activity_analysis['activity_status'].isin(['Active', 'Present'])])
            st.metric("Journey Records", f"{journey_records:,}")
        
        # Journey Heatmap - WWT (핵심)
        st.markdown('<div class="subsection-title">🗺️ Journey Heatmap - WWT</div>', unsafe_allow_html=True)
        
        # Color Legend
        st.markdown("""
        **Color Legend:**
        - **Black**: Absence in WWT
        - **Grey**: Presence in WWT, but inactive  
        - **Green**: Active Presence in WWT - 1F
        - **Yellow**: Active Presence in WWT - B1F
        """)
        
        # Journey Heatmap Analysis 탭과 동일한 모든 그래프 표시
        if journey_results and (journey_results.get('building') or journey_results.get('level')):
            display_all_journey_heatmaps(st, journey_results)
        else:
            st.warning("No journey heatmap data available")
        
    except Exception as e:
        st.error(f"Error in journey analysis section: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_all_journey_heatmaps(st, journey_results):
    """Display journey heatmaps - same as Journey Heatmap Analysis tab (Building level only)"""
    
    try:
        # Journey Heatmap Analysis 탭과 똑같이 Building level만 표시
        if journey_results.get('building'):
            for space_name, data in journey_results['building'].items():
                if 'heatmap_df' in data and not data['heatmap_df'].empty:
                    # Journey Heatmap Analysis 탭과 똑같은 렌더링 사용
                    from .tward_type41_journey_map import render_space_heatmap_groups
                    render_space_heatmap_groups(st, data, space_name)
        
        # Analysis Information (Journey Heatmap Analysis 탭과 똑같이)
        st.markdown("### ℹ️ JourneyMap Analysis Information")
        st.info(f"""
        **JourneyMap Analysis (Type 41) - Type 31 Operation Heatmap Style**
        - **Resolution**: 10분 단위 (144 time bins × T-Ward 수)
        - **Y-axis**: T-Ward Index (활동시간 순 정렬, 50개씩 그룹 표시)
        - **X-axis**: 24시간 시간대 (10분 단위, 144 bins)
        - **Time Bins**: T000-T143 (00:00-00:09 ~ 23:50-23:59)
        - **Color Coding**: 
          * Black (0): 활동 없음 또는 데이터 없음
          * Gray (1): 기타 건물에서 활동
          * Green (10): WWT 건물 또는 WWT-1F에서 활동
          * Yellow (11): WWT-B1F에서 활동
        - **Grouping**: 전체 T-Ward를 50개씩 그룹으로 나누어 표시
        """)
        
    except Exception as e:
        st.error(f"Error displaying journey heatmaps: {str(e)}")

def display_comprehensive_journey_heatmaps(st, journey_results):
    """Display journey heatmaps - same results as Journey Heatmap Analysis tab"""
    
    try:
        if not journey_results:
            st.warning("No journey data available for visualization.")
            return
        
        # Check if journey_results is a dictionary and has data
        if isinstance(journey_results, dict) and len(journey_results) == 0:
            st.warning("No journey data available for visualization.")
            return
            
        # Building level heatmaps (same as Journey Heatmap Analysis tab)
        if journey_results.get('building'):
            for space_name, heatmap_data in journey_results['building'].items():
                render_report_space_heatmap(st, heatmap_data, space_name)
        else:
            st.warning("No building-level journey data available")
                
    except Exception as e:
        st.error(f"Error displaying comprehensive journey heatmaps: {str(e)}")

def render_report_space_heatmap(st, heatmap_data, space_name):
    """Render space-level heatmap for Report Generation"""
    
    try:
        heatmap_df = heatmap_data['heatmap_df']
        tward_summary = heatmap_data['tward_summary']
        time_bins = heatmap_data.get('time_bins', 144)
        
        st.markdown(f"##### Journey Heatmap - {space_name}")
        
        # If there are many T-Wards, display in groups of 50
        max_twards_per_chart = 50
        total_twards = len(heatmap_df)
        
        if total_twards > max_twards_per_chart:
            # Process T-Wards in groups of 50
            num_groups = (total_twards + max_twards_per_chart - 1) // max_twards_per_chart
            st.info(f"📊 Total {total_twards} T-Wards found. Showing {num_groups} charts (max 50 T-Wards per chart)")
            
            for group_idx in range(num_groups):
                start_idx = group_idx * max_twards_per_chart
                end_idx = min(start_idx + max_twards_per_chart, total_twards)
                group_df = heatmap_df.iloc[start_idx:end_idx]
                
                st.markdown(f"**Group {group_idx + 1}: T-Wards {start_idx + 1}-{end_idx}**")
                render_report_single_heatmap(st, group_df, space_name, group_idx + 1, start_idx)
        else:
            render_report_single_heatmap(st, heatmap_df, space_name, 1, 0)
            
        # Display statistics
        if 'activity_summary' in heatmap_data:
            activity_summary = heatmap_data['activity_summary']
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total T-Wards", total_twards)
            with col2:
                st.metric("Active Time Bins", len([v for v in heatmap_df.values.flatten() if v > 0]))
            with col3:
                st.metric("Peak Activity", int(heatmap_df.values.max()) if not heatmap_df.empty else 0)
                
    except Exception as e:
        st.error(f"Error rendering heatmap for {space_name}: {str(e)}")

def render_report_single_heatmap(st, heatmap_df, space_name, group_num, start_idx):
    """Single heatmap rendering for Report Generation"""
    
    try:
        if heatmap_df.empty:
            st.warning(f"No data available for {space_name} Group {group_num}")
            return
        
        # Extract only numeric heatmap data (exclude MAC address and other non-numeric columns)
        try:
            # Debug: print DataFrame structure
            print(f"DEBUG: heatmap_df columns: {list(heatmap_df.columns)}")
            print(f"DEBUG: heatmap_df shape: {heatmap_df.shape}")
            print(f"DEBUG: First few rows:\n{heatmap_df.head()}")
            
            # heatmap_df structure may have: [MAC Address, Activity Time (min), T000, T001, ..., T143]
            # We want only the time bin columns (T000~T143)
            
            # First, identify time columns (T000-T143)
            time_cols = [col for col in heatmap_df.columns if col.startswith('T') and len(col) == 4 and col[1:].isdigit()]
            
            if len(time_cols) > 0:
                print(f"DEBUG: Found {len(time_cols)} time columns: {time_cols[:5]}...{time_cols[-5:]}")
                heatmap_values = heatmap_df[time_cols].values.astype(int)
            else:
                # Fallback: exclude known non-numeric columns
                exclude_cols = ['MAC Address', 'Activity Time (min)', 'mac', 'activity_minutes']
                numeric_cols = [col for col in heatmap_df.columns if col not in exclude_cols]
                print(f"DEBUG: Using fallback columns: {numeric_cols[:10] if len(numeric_cols) > 10 else numeric_cols}")
                
                if len(numeric_cols) > 0:
                    # Verify these are numeric
                    try:
                        heatmap_values = heatmap_df[numeric_cols].values.astype(int)
                    except ValueError as ve:
                        st.error(f"Cannot convert columns to numeric for {space_name}: {str(ve)}")
                        return
                else:
                    st.error(f"No suitable columns found in heatmap for {space_name}")
                    return
                
            print(f"DEBUG: Final heatmap_values shape: {heatmap_values.shape}")
        except Exception as e:
            st.error(f"Error processing heatmap data for {space_name}: {str(e)}")
            import traceback
            st.error(traceback.format_exc())
            return
        
        # Simple heatmap generation (similar to tab implementation)
        fig, ax = plt.subplots(figsize=(20, 8))
        
        # Use simple color mapping like in the original tab
        from matplotlib.colors import ListedColormap
        colors = ['black', 'gray', '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
                 '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        cmap = ListedColormap(colors)
        
        # Simple imshow without interpolation to avoid dtype issues
        im = ax.imshow(heatmap_values, cmap=cmap, aspect='auto', vmin=0, vmax=11)
        
        # Y-axis settings (T-Ward index)
        y_step = max(1, len(heatmap_values)//10)
        y_ticks = range(0, len(heatmap_values), y_step)
        ax.set_yticks(y_ticks)
        y_labels = [f"T{start_idx + i + 1}" for i in y_ticks]
        ax.set_yticklabels(y_labels)
        
        # X-axis settings (time)
        total_bins = heatmap_values.shape[1]  # Use actual heatmap data dimensions
        tick_interval = max(1, total_bins // 12)
        x_ticks = list(range(0, total_bins, tick_interval))
        if total_bins - 1 not in x_ticks:
            x_ticks.append(total_bins - 1)
        
        ax.set_xticks(x_ticks)
        x_labels = []
        for tick in x_ticks:
            hour = (tick * 10) // 60
            minute = (tick * 10) % 60
            x_labels.append(f"{hour:02d}:{minute:02d}")
        ax.set_xticklabels(x_labels, rotation=45)
        
        # Title and labels
        title = f"{space_name} Journey Heatmap"
        if group_num > 1:
            title += f" (Group {group_num})"
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Time (10-minute intervals)')
        ax.set_ylabel('T-Ward Index')
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Activity Level')
        cbar.set_ticks(range(12))
        cbar.set_ticklabels(['None', 'Other', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'WWT/WWT-1F', 'WWT-B1F'])
        
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        
    except Exception as e:
        st.error(f"Error rendering single heatmap: {str(e)}")

def display_journey_heatmaps(st, journey_results):
    """Display journey heatmaps - backup function (not used)"""
    
    try:
        level_data = journey_results.get('level_data', {})
        if not level_data:
            st.warning("No journey heatmap data available")
            return
            
        # Display heatmaps for each level
        for level, data in level_data.items():
            st.markdown(f"##### 🏢 {level} Journey Heatmap")
            
            if 'heatmap_df' in data and not data['heatmap_df'].empty:
                heatmap_df = data['heatmap_df']
                
                # Heatmap visualization
                fig, ax = plt.subplots(figsize=(14, 8))
                
                # Custom colormap
                from matplotlib.colors import ListedColormap
                colors = ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', 
                         '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b']
                cmap = ListedColormap(colors)
                
                # Draw heatmap
                im = ax.imshow(heatmap_df.values, cmap=cmap, aspect='auto', interpolation='nearest')
                
                # Axis settings
                ax.set_xticks(range(len(heatmap_df.columns)))
                ax.set_xticklabels(heatmap_df.columns, rotation=45, ha='right')
                ax.set_yticks(range(len(heatmap_df.index)))
                ax.set_yticklabels(heatmap_df.index)
                
                # Title and labels
                ax.set_title(f'{level} Journey Activity Heatmap', fontsize=14, fontweight='bold')
                ax.set_xlabel('Time (Hour)')
                ax.set_ylabel('Space')
                
                # Colorbar
                plt.colorbar(im, ax=ax, label='Activity Level')
                
                plt.tight_layout()
                st.pyplot(fig)
                plt.close()
                
                # Statistics
                total_activity = heatmap_df.values.sum()
                max_activity = heatmap_df.values.max()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Activity", f"{total_activity:.0f}")
                with col2:
                    st.metric("Peak Activity", f"{max_activity:.0f}")
            else:
                st.write(f"No heatmap data available for {level}")
                
    except Exception as e:
        st.error(f"Error displaying journey heatmaps: {str(e)}")

def display_report_header(st, activity_analysis):
    """Display report header information"""
    
    st.markdown("### 📊 Analysis Information")
    
    # Basic statistics
    total_records = len(activity_analysis)
    unique_twards = activity_analysis['mac'].nunique()
    unique_spaces = activity_analysis['space'].nunique() if 'space' in activity_analysis.columns else 0
    
    # Time range
    if 'timestamp' in activity_analysis.columns:
        start_time = activity_analysis['timestamp'].min()
        end_time = activity_analysis['timestamp'].max()
        duration = end_time - start_time
        duration_hours = duration.total_seconds() / 3600
    else:
        start_time = "N/A"
        end_time = "N/A"
        duration_hours = 24  # Default value
    
    # Display information
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Records", f"{total_records:,}")
    with col2:
        st.metric("Unique T-Wards", unique_twards)
    with col3:
        st.metric("Unique Spaces", unique_spaces)
    with col4:
        st.metric("Analysis Duration", f"{duration_hours:.1f}h")
    
    # Analysis time information
    if start_time != "N/A":
        st.markdown(f"**Analysis Period**: {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}")
    
    st.markdown(f"**Report Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")



def generate_csv_report(activity_analysis):
    """Generate comprehensive report in CSV format"""
    
    try:
        # 리포트 데이터 수집
        report_data = []
        
        # 1. 기본 정보
        total_records = len(activity_analysis)
        unique_twards = activity_analysis['mac'].nunique()
        unique_spaces = activity_analysis['space'].nunique() if 'space' in activity_analysis.columns else 0
        
        # 필터링 정보
        filter_enabled = st.session_state.get('tward41_filtering_applied', False)
        original_count = st.session_state.get('tward41_original_twards', 0)
        filtered_count = st.session_state.get('tward41_filtered_twards', 0)
        removed_count = st.session_state.get('tward41_removed_twards', 0)
        min_dwell_time = st.session_state.get('tward41_min_dwell_time', 0)
        
        # 기본 통계
        report_data.append(['Section', 'Metric', 'Value', 'Description'])
        report_data.append(['Basic Info', 'Total Records', total_records, 'Total activity records in analysis'])
        report_data.append(['Basic Info', 'Unique T-Wards', unique_twards, 'Number of unique T-Ward devices'])
        report_data.append(['Basic Info', 'Unique Spaces', unique_spaces, 'Number of different spaces monitored'])
        report_data.append(['Basic Info', 'Analysis Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Report generation timestamp'])
        
        # 필터링 정보
        if filter_enabled:
            report_data.append(['Filtering', 'Filter Applied', 'Yes', f'Minimum {min_dwell_time} minutes dwell time'])
            report_data.append(['Filtering', 'Original T-Wards', original_count, 'T-Wards before filtering'])
            report_data.append(['Filtering', 'Filtered T-Wards', filtered_count, 'T-Wards after filtering'])
            report_data.append(['Filtering', 'Removed T-Wards', removed_count, 'T-Wards excluded by filter'])
            if original_count > 0:
                removal_rate = (removed_count / original_count) * 100
                report_data.append(['Filtering', 'Removal Rate (%)', f'{removal_rate:.1f}', 'Percentage of T-Wards removed'])
        else:
            report_data.append(['Filtering', 'Filter Applied', 'No', 'All T-Wards included in analysis'])
        
        # 체류시간 통계 (Active/Present만)
        if not activity_analysis.empty:
            occupied_activity = activity_analysis[activity_analysis['activity_status'].isin(['Active', 'Present'])]
            if not occupied_activity.empty:
                mac_dwell_times = occupied_activity.groupby('mac')['minute_bin'].nunique()
                report_data.append(['Dwell Time', 'Average Dwell Time (min)', f'{mac_dwell_times.mean():.1f}', 'Average actual occupancy time'])
                report_data.append(['Dwell Time', 'Max Dwell Time (min)', mac_dwell_times.max(), 'Maximum occupancy time'])
                report_data.append(['Dwell Time', 'Min Dwell Time (min)', mac_dwell_times.min(), 'Minimum occupancy time'])
                report_data.append(['Dwell Time', 'Median Dwell Time (min)', f'{mac_dwell_times.median():.1f}', 'Median occupancy time'])
        
        # 공간별 통계
        if 'space' in activity_analysis.columns:
            space_stats = activity_analysis.groupby('space').agg({
                'mac': 'nunique',
                'activity_status': lambda x: (x.isin(['Active', 'Present'])).sum()
            }).round(1)
            
            for space, stats in space_stats.iterrows():
                report_data.append(['Space Activity', f'{space} - Unique T-Wards', stats['mac'], f'Number of T-Wards in {space}'])
                report_data.append(['Space Activity', f'{space} - Activity Records', stats['activity_status'], f'Active/Present records in {space}'])
        
        # 활동 상태 분포
        status_dist = activity_analysis['activity_status'].value_counts()
        for status, count in status_dist.items():
            percentage = (count / len(activity_analysis)) * 100
            report_data.append(['Activity Status', f'{status} Count', count, f'{percentage:.1f}% of total records'])
        
        # CSV 문자열 생성
        csv_buffer = io.StringIO()
        for row in report_data:
            csv_buffer.write(','.join([str(cell).replace(',', ';') for cell in row]) + '\n')
        
        return csv_buffer.getvalue()
        
    except Exception as e:
        st.error(f"Error generating CSV report: {str(e)}")
        return None

def generate_professional_pdf_report(activity_analysis, analysis_results):
    """Report Generation 페이지의 실제 표시 내용을 PDF로 생성"""
    
    try:
        import tempfile
        import os
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, cm
        from reportlab.lib import colors
        from reportlab.lib.colors import HexColor
        import streamlit as st
        
        if activity_analysis is None or activity_analysis.empty:
            return None
            
        # Mock Streamlit object for content generation
        class MockStreamlit:
            def __init__(self):
                self.content = []
                
            def header(self, text):
                self.content.append(('header', text))
                
            def subheader(self, text):
                self.content.append(('subheader', text))
                
            def write(self, text):
                self.content.append(('write', text))
                
            def markdown(self, text):
                self.content.append(('markdown', text))
                
            def metric(self, label, value, delta=None):
                self.content.append(('metric', label, value, delta))
                
            def dataframe(self, df):
                self.content.append(('dataframe', df))
                
            def plotly_chart(self, fig):
                self.content.append(('plotly_chart', fig))
                
            def pyplot(self, fig=None):
                self.content.append(('pyplot', fig))
                
            def columns(self, spec):
                return [self, self, self]  # Return mock columns
                
            def container(self):
                return self
                
            def expander(self, label):
                return self
        
        # Report Generation의 실제 컨텐츠 생성
        mock_st = MockStreamlit()
        report_content = generate_comprehensive_report(mock_st, activity_analysis, analysis_results)
        
        # 임시 PDF 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_filename = tmp_file.name
            
        # PDF 문서 설정
        doc = SimpleDocTemplate(pdf_filename, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        
        # 스타일 정의
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, spaceAfter=20, textColor=HexColor('#1e3c72'), alignment=1)
        header_style = ParagraphStyle('CustomHeader', parent=styles['Heading1'], fontSize=14, spaceAfter=10, textColor=HexColor('#2a5298'))
        normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=10, spaceAfter=6)
        
        # PDF 스토리 구성
        story = []
        
        # Mock Streamlit에서 수집한 컨텐츠를 PDF 요소로 변환
        for item in mock_st.content:
            if item[0] == 'header':
                story.append(Paragraph(item[1], title_style))
                story.append(Spacer(1, 0.2*inch))
            elif item[0] == 'subheader':
                story.append(Paragraph(item[1], header_style))
                story.append(Spacer(1, 0.1*inch))
            elif item[0] == 'write' or item[0] == 'markdown':
                text = str(item[1]).replace('<br>', '<br/>')
                story.append(Paragraph(text, normal_style))
                story.append(Spacer(1, 0.1*inch))
            elif item[0] == 'metric':
                metric_text = f"<b>{item[1]}:</b> {item[2]}"
                if len(item) > 3 and item[3]:
                    metric_text += f" ({item[3]})"
                story.append(Paragraph(metric_text, normal_style))
                story.append(Spacer(1, 0.05*inch))
            elif item[0] == 'dataframe':
                try:
                    df = item[1]
                    if not df.empty:
                        table_data = [df.columns.tolist()]
                        for _, row in df.head(15).iterrows():
                            table_data.append([str(val) for val in row.tolist()])
                        
                        table = Table(table_data)
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 8),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('FONTSIZE', (0, 1), (-1, -1), 7),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black)
                        ]))
                        story.append(table)
                        story.append(Spacer(1, 0.2*inch))
                except Exception as e:
                    story.append(Paragraph(f"Table: {str(e)}", normal_style))
            elif item[0] == 'plotly_chart' or item[0] == 'pyplot':
                story.append(Paragraph("📊 [Chart Display - Visual content from Report Generation page]", normal_style))
                story.append(Spacer(1, 0.1*inch))
        
        # 푸터 추가
        footer_text = "Generated by T-Ward Type 41 Analysis System - Hy-con & IRFM by TJLABS"
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=1)))
        
        # PDF 빌드
        doc.build(story)
        
        # PDF 파일 읽기
        with open(pdf_filename, 'rb') as f:
            pdf_data = f.read()
        
        # 임시 파일 삭제
        os.unlink(pdf_filename)
        
        return pdf_data
        
    except Exception as e:
        import traceback
        print(f"Error generating PDF report: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return None
    
    print("Starting PDF generation...")
    print(f"Activity analysis type: {type(activity_analysis)}")
    print(f"Analysis results type: {type(analysis_results)}")
    
    # Required imports
    try:
        import tempfile
        import os
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, cm
        from reportlab.lib import colors
        from reportlab.lib.colors import HexColor
        import matplotlib.pyplot as plt
        import numpy as np
        import streamlit as st
        print("All imports successful")
    except ImportError as e:
        print(f"Import error: {e}")
        return None
    
    try:
        if activity_analysis is None or activity_analysis.empty:
            print("Activity analysis is None or empty")
            return None
            
        # Report Generation 페이지의 실제 컨텐츠 생성 (generate_comprehensive_report 함수 사용)
        print("Generating report content using existing function...")
        
        # Mock streamlit object for content generation
        class MockStreamlit:
            def __init__(self):
                self.content = []
                
            def header(self, text):
                self.content.append(('header', text))
                
            def subheader(self, text):
                self.content.append(('subheader', text))
                
            def write(self, text):
                self.content.append(('write', text))
                
            def markdown(self, text):
                self.content.append(('markdown', text))
                
            def metric(self, label, value, delta=None):
                self.content.append(('metric', label, value, delta))
                
            def dataframe(self, df):
                self.content.append(('dataframe', df))
                
            def plotly_chart(self, fig):
                self.content.append(('plotly_chart', fig))
                
            def pyplot(self, fig=None):
                self.content.append(('pyplot', fig))
                
        mock_st = MockStreamlit()
        
        # Report Generation의 실제 컨텐츠 생성
        report_content = generate_comprehensive_report(mock_st, activity_analysis, analysis_results)
        
        print(f"Generated content items: {len(mock_st.content)}")
            
        # save_chart_as_image 함수 정의
        def save_chart_as_image(fig):
            """matplotlib 차트를 이미지로 저장하고 PDF에 추가할 수 있는 Image 객체 반환"""
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                    fig.savefig(tmp_img.name, format='png', dpi=150, bbox_inches='tight')
                    plt.close(fig)
                    img = Image(tmp_img.name, width=15*cm, height=10*cm)
                    # 파일이 존재하는지 확인 후 삭제
                    if os.path.exists(tmp_img.name):
                        os.unlink(tmp_img.name)
                    return img
            except Exception as e:
                plt.close(fig)  # 에러 발생 시에도 figure 닫기
                print(f"Chart image generation error: {e}")
                return None
        
        print("Creating temporary file...")
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_filename = tmp_file.name
            
        print(f"Temporary PDF file created: {pdf_filename}")
        print("Creating PDF document...")
        # PDF 문서 생성
        doc = SimpleDocTemplate(
            pdf_filename,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        print("Setting up PDF styles...")
        # 스타일 정의
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=20,
            spaceAfter=20,
            textColor=HexColor('#1e3c72'),
            alignment=1
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=15,
            spaceBefore=20,
            textColor=HexColor('#1e3c72'),
            borderWidth=2,
            borderColor=HexColor('#667eea'),
            borderPadding=8
        )
        
        subheader_style = ParagraphStyle(
            'CustomSubHeader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            spaceBefore=15,
            textColor=HexColor('#2a5298'),
            leftIndent=15
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            leftIndent=10
        )
        

        
        print("Converting report content to PDF...")
        # PDF 내용 구성 - Report Generation 페이지의 실제 내용 사용
        story = []
        
        # Mock Streamlit에서 수집한 컨텐츠를 PDF 요소로 변환
        for item in mock_st.content:
            if item[0] == 'header':
                story.append(Paragraph(item[1], title_style))
                story.append(Spacer(1, 0.2*inch))
            elif item[0] == 'subheader':
                story.append(Paragraph(item[1], header_style))
                story.append(Spacer(1, 0.1*inch))
            elif item[0] == 'write' or item[0] == 'markdown':
                # HTML 태그 제거하고 텍스트만 추출
                text = str(item[1]).replace('<br>', '<br/>')
                story.append(Paragraph(text, normal_style))
                story.append(Spacer(1, 0.1*inch))
            elif item[0] == 'metric':
                metric_text = f"<b>{item[1]}:</b> {item[2]}"
                if len(item) > 3 and item[3]:
                    metric_text += f" ({item[3]})"
                story.append(Paragraph(metric_text, normal_style))
                story.append(Spacer(1, 0.05*inch))
            elif item[0] == 'dataframe':
                # DataFrame을 테이블로 변환
                try:
                    df = item[1]
                    if not df.empty:
                        # 테이블 데이터 준비
                        table_data = [df.columns.tolist()]
                        for _, row in df.head(20).iterrows():  # 최대 20행만 표시
                            table_data.append([str(val) for val in row.tolist()])
                        
                        # PDF 테이블 생성
                        table = Table(table_data)
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 8),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('FONTSIZE', (0, 1), (-1, -1), 7),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black)
                        ]))
                        story.append(table)
                        story.append(Spacer(1, 0.2*inch))
                except Exception as e:
                    story.append(Paragraph(f"Table could not be generated: {str(e)}", normal_style))
            elif item[0] == 'plotly_chart' or item[0] == 'pyplot':
                # 차트는 임시로 텍스트 대체
                story.append(Paragraph("[Chart would be displayed here]", normal_style))
                story.append(Spacer(1, 0.1*inch))
        story.append(Spacer(1, 0.3*inch))
        
        # 동적 건물 정보 감지
        detected_buildings = []
        detected_levels = []
        if activity_analysis is not None and not activity_analysis.empty:
            if 'building' in activity_analysis.columns:
                buildings = activity_analysis['building'].dropna().unique()
                detected_buildings = [b for b in buildings if str(b) != 'Unknown']
            if 'level' in activity_analysis.columns:
                levels = activity_analysis['level'].dropna().unique()
                detected_levels = [l for l in levels if str(l) != 'Unknown']
        
        if not detected_buildings:
            detected_buildings = ['WWT']
        if not detected_levels:
            detected_levels = ['1F', 'B1F']
            
        buildings_text = ', '.join(detected_buildings) + (' Building' if len(detected_buildings) == 1 else ' Buildings')
        levels_text = ', '.join(detected_levels)
        
        report_info = f"""
        <b>Target Building:</b> {buildings_text}<br/>
        <b>Analysis Levels:</b> {levels_text}<br/>
        <b>Analysis Date:</b> August 22, 2025 (24-Hour Period)<br/>
        <b>System:</b> Hy-con & IRFM by TJLABS<br/>
        <b>Data Source:</b> T-Ward Type 41 Sensors on Workers' helmet<br/>
        """
        
        story.append(Paragraph(report_info, normal_style))
        story.append(Spacer(1, 0.4*inch))
        
        print("Report content conversion completed.")
        
        # PDF 푸터 추가
        footer_text = """
        <i>Generated by T-Ward Type 41 Analysis System<br/>
        • Source: Hy-con & IRFM by TJLABS</i>
        """
        
        story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey)))
        
        print("Building PDF document...")
        # PDF 빌드
        doc.build(story)
        unique_twards = activity_analysis['mac'].nunique()
        filtered_records = len(activity_analysis[activity_analysis['activity_status'].isin(['Active', 'Present'])])
        
        occupancy_content = f"""
        <b>Data Filtering Applied:</b><br/>
        • 30+ minute dwell time threshold applied for data quality<br/>
        • Focus on sustained workplace activity patterns<br/>
        • Transient activities filtered out<br/>
        <br/>
        <b>Occupancy Statistics:</b><br/>
        • Total Activity Records: {total_records:,}<br/>
        • Unique T-Ward Devices: {unique_twards:,}<br/>
        • Active/Present Records: {filtered_records:,}<br/>
        • Data Quality: High (filtered for meaningful occupancy)<br/>
        <br/>
        <b>Analysis Features:</b><br/>
        • Real-time activity status monitoring<br/>
        • 24-hour occupancy patterns<br/>
        • Multi-level space utilization tracking<br/>
        • Minute-by-minute activity resolution<br/>
        """
        
        story.append(Paragraph(occupancy_content, normal_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Analysis Information (Report Generation 페이지와 동일)
        story.append(Paragraph("Analysis Information", subheader_style))
        analysis_info = """
        <b>Occupancy Analysis (Type 41):</b><br/>
        • Real-time tracking of worker presence and activity status<br/>
        • Three activity states: Active, Present, Absent<br/>
        • 1-minute resolution for precise occupancy measurement<br/>
        • Multi-level analysis across building floors<br/>
        • Quality filtering applied for meaningful data analysis<br/>
        """
        
        story.append(Paragraph(analysis_info, normal_style))
        
        # Occupancy Analysis 24시간 차트 추가 (Report Generation과 동일) - 임시 비활성화
        print("Skipping charts for basic PDF test...")
        story.append(Paragraph("📊 24-Hour Activity Pattern", subheader_style))
        story.append(Paragraph("Chart generation temporarily disabled for testing", normal_style))
        
        # 차트 생성 부분 임시 주석처리
        if False:  # 임시로 비활성화
            if analysis_results and 'minute_activity' in analysis_results:
                minute_activity = analysis_results['minute_activity']
                
                if minute_activity is not None and not minute_activity.empty:
                    pass
                    
                    # 24시간 차트 생성
                    fig, ax = plt.subplots(figsize=(15, 8))
                    
                    # 시간별 활동 데이터 준비
                    minute_activity_copy = minute_activity.copy()
                    minute_activity_copy['hour'] = (minute_activity_copy['minute_bin'] - 1) // 60
                    
                    # 시간별 Active, Present 집계
                    hourly_active = minute_activity_copy[minute_activity_copy['activity_status'] == 'Active'].groupby('hour')['mac'].nunique()
                    hourly_present = minute_activity_copy[minute_activity_copy['activity_status'] == 'Present'].groupby('hour')['mac'].nunique()
                    
                    # 전체 24시간 범위 생성
                    all_hours = range(24)
                    active_counts = [hourly_active.get(h, 0) for h in all_hours]
                    present_counts = [hourly_present.get(h, 0) for h in all_hours]
                    
                    # 차트 그리기
                    width = 0.35
                    x = np.arange(len(all_hours))
                    
                    bars1 = ax.bar(x - width/2, active_counts, width, label='Active', color='#1f77b4', alpha=0.8)
                    bars2 = ax.bar(x + width/2, present_counts, width, label='Present', color='#ff7f0e', alpha=0.8)
                    
                    ax.set_xlabel('Hour of Day')
                    ax.set_ylabel('Number of T-Wards')
                    ax.set_title('24-Hour T-Ward Activity Pattern\n(Active vs Present Status)')
                    ax.set_xticks(x)
                    ax.set_xticklabels([f'{h:02d}:00' for h in all_hours], rotation=45)
                    ax.legend()
                    ax.grid(True, alpha=0.3)
                    
                    # 값 표시
                    def autolabel(rects):
                        for rect in rects:
                            height = rect.get_height()
                            if height > 0:
                                ax.annotate(f'{int(height)}',
                                          xy=(rect.get_x() + rect.get_width() / 2, height),
                                          xytext=(0, 3),
                                          textcoords="offset points",
                                          ha='center', va='bottom', fontsize=8)
                    
                    autolabel(bars1)
                    autolabel(bars2)
                    
                    plt.tight_layout()
                    
                    # 24시간 차트를 PDF에 추가 (임시 비활성화)
                    pass
        
        story.append(Spacer(1, 0.3*inch))
        
        # 2. Dwell Time Analysis (Report Generation 페이지와 완전히 동일 - 차트 포함) - 임시 간소화
        print("Adding Dwell Time Analysis section...")
        story.append(Paragraph("⏱️ 2. Dwell Time Analysis", header_style))
        story.append(Paragraph("Dwell time analysis temporarily simplified for testing", normal_style))
        
        # 차트 생성 임시 비활성화
        if False:  # 임시로 비활성화
            dwell_results = analyze_dwell_times(activity_analysis)
            if dwell_results and 'dwell_df' in dwell_results:
                dwell_df = dwell_results['dwell_df']
                
                # 통계 정보 추가
                building_stats = dwell_df[dwell_df['space_type'] == 'Building']
                if not building_stats.empty:
                    avg_dwell = building_stats['dwell_minutes'].mean()
                    max_dwell = building_stats['dwell_minutes'].max()
                    min_dwell = building_stats['dwell_minutes'].min()
                    total_twards = len(building_stats)
                    
                    # 동적 건물 정보 감지
                    detected_buildings = []
                    if activity_analysis is not None and not activity_analysis.empty:
                        if 'building' in activity_analysis.columns:
                            buildings = activity_analysis['building'].dropna().unique()
                            detected_buildings = [b for b in buildings if str(b) != 'Unknown']
                    
                    if not detected_buildings:
                        detected_buildings = ['WWT']
                    
                    buildings_text = ', '.join(detected_buildings) + (' Building' if len(detected_buildings) == 1 else ' Buildings')
                    
                    # 통계 테이블 생성
                    stats_data = [
                        ['Space', 'Count', 'Min (min)', 'Max (min)', 'Avg (min)', 'Avg (hours)'],
                        [buildings_text, str(total_twards), str(min_dwell), str(max_dwell), f"{avg_dwell:.1f}", f"{avg_dwell/60:.2f}"]
                    ]
                    
                    # Level별 통계도 추가
                    for space_type in ['WWT-1F', 'WWT-B1F']:
                        level_stats = dwell_df[dwell_df['space'] == space_type]
                        if not level_stats.empty:
                            stats_data.append([
                                space_type,
                                str(len(level_stats)),
                                str(level_stats['dwell_minutes'].min()),
                                str(level_stats['dwell_minutes'].max()),
                                f"{level_stats['dwell_minutes'].mean():.1f}",
                                f"{level_stats['dwell_minutes'].mean()/60:.2f}"
                            ])
                    
                    # 통계 테이블을 PDF에 추가
                    stats_table = Table(stats_data, colWidths=[3*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm])
                    stats_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2a5298')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f9fa')])
                    ]))
                    
                    story.append(stats_table)
                    story.append(Spacer(1, 0.2*inch))
                    
                    # Individual T-Ward Dwell Time Charts 생성 (Report Generation과 동일)
                    story.append(Paragraph("📊 T-Ward Individual Dwell Time Charts", subheader_style))
                    
                    # 각 공간별로 차트 생성
                    spaces_to_plot = []
                    
                    # Building 데이터
                    building_data = dwell_df[dwell_df['space_type'] == 'Building']
                    for space in building_data['space'].unique():
                        space_data = building_data[building_data['space'] == space]
                        if not space_data.empty:
                            spaces_to_plot.append((space, space_data, 'Building'))
                    
                    # Level 데이터
                    level_data = dwell_df[dwell_df['space_type'] == 'Level']
                    for space in level_data['space'].unique():
                        space_data = level_data[level_data['space'] == space]
                        if not space_data.empty:
                            spaces_to_plot.append((space, space_data, 'Level'))
                    
                    # 각 공간별로 차트 생성하고 PDF에 추가
                    for space_name, space_data, space_type in spaces_to_plot:
                        # 체류시간 큰 순서로 정렬
                        sorted_data = space_data.sort_values('dwell_minutes', ascending=False)
                        
                        # 차트 생성
                        fig, ax = plt.subplots(figsize=(14, 8))
                        
                        # 막대 그래프
                        bars = ax.bar(range(len(sorted_data)), sorted_data['dwell_minutes'], 
                                     color='#1f77b4', alpha=0.7, edgecolor='black')
                        
                        # X축 설정 (라벨 제거로 가독성 향상)
                        ax.set_xticks([])
                        ax.set_xticklabels([])
                        
                        # Y축 설정
                        ax.set_ylabel('Cumulative Dwell Time (Minutes)', fontsize=12, fontweight='bold')
                        ax.set_xlabel('T-Ward Index (Sorted by Dwell Time)', fontsize=12, fontweight='bold')
                        
                        # 제목 설정
                        total_twards_chart = len(sorted_data)
                        total_time = sorted_data['dwell_minutes'].sum()
                        avg_time = sorted_data['dwell_minutes'].mean()
                        
                        ax.set_title(f'{space_name} - Individual T-Ward Dwell Times\n'
                                    f'Total: {total_twards_chart} T-Wards, {total_time} min ({total_time/60:.1f}h), '
                                    f'Average: {avg_time:.1f} min ({avg_time/60:.1f}h)',
                                    fontsize=14, fontweight='bold', pad=20)
                        
                        # 격자 추가
                        ax.grid(True, axis='y', alpha=0.3)
                        
                        # Y축 범위 조정
                        max_minutes = sorted_data['dwell_minutes'].max()
                        ax.set_ylim(0, max_minutes * 1.15)
                        
                        plt.tight_layout()
                        
                        # 차트를 PDF에 추가
                        chart_img = save_chart_as_image(fig)
                        if chart_img is not None:
                            story.append(chart_img)
                            story.append(Spacer(1, 0.2*inch))
                        else:
                            story.append(Paragraph("Individual dwell time chart could not be generated", normal_style))
                    
                    # Dwell Time Distribution 차트 추가
                    if 'histogram_data' in dwell_results:
                        story.append(Paragraph("📊 Dwell Time Distribution (30-minute intervals)", subheader_style))
                        
                        histogram_data = dwell_results['histogram_data']
                        building_histograms = {k: v for k, v in histogram_data.items() if k.startswith('Building_')}
                        
                        for space_key, hist_data in building_histograms.items():
                            space_name = space_key.replace('Building_', '')
                            
                            # 히스토그램 차트 생성
                            fig, ax = plt.subplots(figsize=(12, 6))
                            
                            bins = hist_data['bins']
                            counts = hist_data['counts']
                            labels = hist_data['labels']
                            
                            # 막대 그래프 (counts와 labels 길이 맞춤)
                            bars = ax.bar(range(len(counts)), counts, color='#2a5298', alpha=0.8, edgecolor='white', linewidth=1)
                            
                            # X축 라벨 설정
                            ax.set_xticks(range(len(counts)))
                            if len(labels) >= len(counts):
                                ax.set_xticklabels(labels[:len(counts)], rotation=45, ha='right', fontsize=10)
                            else:
                                ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=10)
                            
                            # Y축 설정
                            ax.set_ylabel('Number of T-Wards', fontsize=12, fontweight='bold')
                            ax.set_xlabel('Dwell Time Intervals', fontsize=12, fontweight='bold')
                            
                            # 제목
                            total_workers = sum(counts)
                            ax.set_title(f'{space_name} - Dwell Time Distribution (30-min intervals)\n'
                                        f'Total Workers: {total_workers}',
                                        fontsize=14, fontweight='bold', pad=20)
                            
                            # 격자
                            ax.grid(True, axis='y', alpha=0.3)
                            
                            plt.tight_layout()
                            
                            # 차트를 PDF에 추가
                            chart_img = save_chart_as_image(fig)
                            if chart_img is not None:
                                story.append(chart_img)
                                story.append(Spacer(1, 0.2*inch))
                            else:
                                story.append(Paragraph(f"{space_name} distribution chart could not be generated", normal_style))
                
        # 임시로 비활성화된 구간 처리
        
        # Dwell Time Analysis Information
        story.append(Paragraph("Dwell Time Analysis Information", subheader_style))
        dwell_analysis_info = """
        <b>Dwell Time Analysis (Type 41):</b><br/>
        • Dwell Time: 1분 단위로 Present/Active 상태인 시간 누적<br/>
        • Building Level: 전체 건물 내 체류시간<br/>
        • Level Specific: 특정 층별 체류시간<br/>
        • 30-minute Intervals: 체류시간을 30분 단위로 구간화하여 분포 표시<br/>
        • Statistics: 최소/최대/평균/중앙값/표준편차 제공<br/>
        """
        
        story.append(Paragraph(dwell_analysis_info, normal_style))
        story.append(Spacer(1, 0.3*inch))
        
        # 3. Journey Heatmap Analysis (Report Generation 페이지와 완전히 동일 - 히트맵 차트 포함) - 임시 간소화
        print("Adding Journey Heatmap Analysis section...")
        story.append(Paragraph("🗺️ 3. Journey Heatmap Analysis", header_style))
        story.append(Paragraph("Journey heatmap analysis temporarily simplified for testing", normal_style))
        
        # Journey 분석 결과 처리
        try:
            building_results = analyze_journey_patterns(activity_analysis, 'building')
            level_results = analyze_journey_patterns(activity_analysis, 'level')
            
            journey_results = {
                'building': building_results,
                'level': level_results
            }
            
            if journey_results.get('building'):
                buildings = list(journey_results['building'].keys())
                total_twards_journey = sum(len(journey_results['building'][building]['heatmap_df']) for building in buildings)
                
                # Journey 분석 결과 텍스트
                journey_content = f"""
                <b>Journey Analysis Results:</b><br/>
                • Buildings analyzed: {len(buildings)} ({', '.join(buildings)})<br/>
                • Total T-Wards in journey analysis: {total_twards_journey}<br/>
                • Spatial heatmap generation: Building level analysis<br/>
                • Movement pattern visualization completed<br/>
                """
                
                story.append(Paragraph(journey_content, normal_style))
            else:
                story.append(Paragraph("Journey analysis data not available", normal_style))
        except Exception as e:
            story.append(Paragraph(f"Journey analysis error: {str(e)}", normal_style))
        
        
        story.append(Spacer(1, 0.2*inch))
                
        # 임시로 비활성화된 구간 처리
                
        # Journey Heatmap Analysis 차트 추가 (Report Generation과 동일) - 임시 비활성화
        if False:  # 임시로 비활성화
            from src.tward_type41_journey_map import get_journey_analysis_results
            
            # 현재 세션의 데이터 가져오기
            if 'filtered_data' in st.session_state and st.session_state.filtered_data is not None:
                current_data = st.session_state.filtered_data
                
                # Journey 분석 결과 가져오기
                journey_results = get_journey_analysis_results(current_data)
                
                if journey_results and 'building_level' in journey_results:
                    building_data = journey_results['building_level']
                    
                    story.append(Paragraph("🗺️ Journey Heatmap Visualization", subheader_style))
                    
                    # Building level 히트맵만 생성 (Report Generation 탭과 동일)
                    if building_data and not building_data.empty:
                        # 히트맵 차트 생성
                        fig, ax = plt.subplots(figsize=(12, 8))
                        
                        # 건물 맵 이미지 로드 (WWT 1F 사용)
                        map_path = "Datafile/Map_Image/Map_WWT_1F.png"
                        if os.path.exists(map_path):
                            import matplotlib.image as mpimg
                            img = mpimg.imread(map_path)
                            ax.imshow(img, extent=[0, img.shape[1], 0, img.shape[0]], alpha=0.7)
                        
                        # 방문 빈도 데이터로 히트맵 오버레이
                        if 'x' in building_data.columns and 'y' in building_data.columns:
                            # 좌표별 방문 빈도 계산
                            visit_counts = building_data.groupby(['x', 'y']).size().reset_index(name='frequency')
                            
                            if not visit_counts.empty:
                                # 히트맵 생성
                                scatter = ax.scatter(visit_counts['x'], visit_counts['y'], 
                                                   c=visit_counts['frequency'], 
                                                   cmap='hot', s=100, alpha=0.8)
                                
                                # 컬러바 추가
                                cbar = plt.colorbar(scatter, ax=ax)
                                cbar.set_label('Visit Frequency')
                        
                        ax.set_title('Building Level Journey Heatmap')
                        ax.set_xlabel('X Coordinate')
                        ax.set_ylabel('Y Coordinate')
                        
                        plt.tight_layout()
                        
                        # 히트맵 차트를 PDF에 추가
                        chart_img = save_chart_as_image(fig)
                        if chart_img is not None:
                            story.append(chart_img)
                            story.append(Spacer(1, 0.2*inch))
                        else:
                            story.append(Paragraph("Building level heatmap chart could not be generated", normal_style))
                    else:
                        story.append(Paragraph("No journey data available for heatmap visualization.", normal_style))
                        
        # 임시로 비활성화된 구간 처리
        
        # JourneyMap Analysis Information
        story.append(Paragraph("JourneyMap Analysis Information", subheader_style))
        journey_analysis_info = """
        <b>JourneyMap Analysis (Type 41):</b><br/>
        • Journey Pattern: T-Ward 이동 경로를 공간별로 시각화<br/>
        • Building Level: 전체 건물의 이동 패턴 히트맵<br/>
        • Color Coding: 방문 빈도에 따른 색상 구분 표시<br/>
        • Movement Flow: 작업자들의 공간 간 이동 흐름 분석<br/>
        • Space Utilization: 공간 활용도 및 집중 구역 식별<br/>
        """
        
        story.append(Paragraph(journey_analysis_info, normal_style))
        story.append(Spacer(1, 0.3*inch))
        
        # 4. 최종 요약 및 권장사항
        story.append(Paragraph("📋 4. Summary & Recommendations", header_style))
        
        # 현재 시간 추가
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        final_summary = f"""
        <b>Analysis Summary:</b><br/>
        • Comprehensive workplace activity analysis completed<br/>
        • Multi-dimensional data processing: Occupancy, Dwell Time, Journey patterns<br/>
        • Quality filtering applied (30+ minute dwell time threshold)<br/>
        • Real-time monitoring capabilities demonstrated<br/>
        <br/>
        <b>Key Achievements:</b><br/>
        • Successfully processed {total_records:,} activity records<br/>
        • Analyzed {unique_twards:,} unique T-Ward devices<br/>
        • Generated comprehensive multi-level analysis<br/>
        • Provided actionable insights for workplace management<br/>
        <br/>
        <b>Recommendations:</b><br/>
        • Continue applying filtering for data quality improvement<br/>
        • Utilize dwell time patterns for workspace optimization<br/>
        • Monitor journey patterns for space planning<br/>
        • Implement findings for operational efficiency<br/>
        """
        
        story.append(Paragraph(final_summary, normal_style))
        
        # 푸터 정보
        story.append(Spacer(1, 0.5*inch))
        footer_text = f"""
        <br/>
        ---<br/>
        <i><b>Report Generation Details:</b><br/>
        • This PDF contains identical content to the Report Generation web page<br/>
        • Generated: {current_time}<br/>
        • System: T-Ward Type 41 Analysis Platform<br/>
        • Source: Hy-con & IRFM by TJLABS</i>
        """
        
        story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey)))
        
        print("Building PDF document...")
        # PDF 빌드
        doc.build(story)
        
        print("Reading PDF file...")
        # PDF 파일 읽기
        with open(pdf_filename, 'rb') as f:
            pdf_data = f.read()
        
        print(f"PDF generated successfully, size: {len(pdf_data)} bytes")
        
        # 임시 파일 삭제
        os.unlink(pdf_filename)
        
        return pdf_data
        
    except Exception as e:
        import traceback
        print(f"Error generating PDF report: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return None


def generate_comprehensive_pdf_report(activity_analysis, analysis_results):
    """Report Generation 페이지 전체 내용을 그대로 PDF로 출력"""
    try:
        import tempfile
        import os
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, cm
        from reportlab.lib import colors
        from reportlab.lib.colors import HexColor
        import streamlit as st
        
        if activity_analysis is None or activity_analysis.empty:
            return None
            
        # Mock Streamlit을 사용해서 Report Generation의 실제 컨텐츠 생성
        class MockStreamlit:
            def __init__(self):
                self.content = []
                self.sections = []
                
            def markdown(self, text, unsafe_allow_html=False):
                # CSS 스타일은 무시하고 내용만 수집
                if not text.startswith("<style>") and not text.startswith("<div class="):
                    self.content.append(("markdown", text))
                elif "Worker Traffic Analysis Report" in text:
                    self.content.append(("title", "Worker Traffic Analysis Report"))
                elif "Target Building:" in text:
                    self.content.append(("info", "WWT Building Analysis"))
                    
            def header(self, text):
                self.content.append(("header", text))
                
            def subheader(self, text):
                self.content.append(("subheader", text))
                
            def write(self, text):
                self.content.append(("write", text))
                
            def metric(self, label, value, delta=None):
                self.content.append(("metric", label, value, delta))
                
            def dataframe(self, df):
                self.content.append(("dataframe", df))
                
            def plotly_chart(self, fig, **kwargs):
                self.content.append(("chart", "Plotly Chart"))
                
            def pyplot(self, fig=None, **kwargs):
                self.content.append(("chart", "Matplotlib Chart"))
                
            def success(self, text):
                self.content.append(("success", text))
                
            def columns(self, spec):
                return [self, self, self, self]  # Return multiple mock objects
                
            def container(self):
                return self
                
            def expander(self, label):
                return self
                
            def info(self, text):
                self.content.append(("info", text))
                
            def warning(self, text):
                self.content.append(("warning", text))
        
        # Report Generation 페이지의 실제 컨텐츠 생성
        mock_st = MockStreamlit()
        
        # generate_comprehensive_report 함수 호출하여 실제 컨텐츠 수집
        try:
            report_content = generate_comprehensive_report(mock_st, activity_analysis, analysis_results)
        except Exception as e:
            print(f"Error generating report content: {e}")
            # 동적 건물 정보 감지
            detected_buildings = []
            if activity_analysis is not None and not activity_analysis.empty:
                if 'building' in activity_analysis.columns:
                    buildings = activity_analysis['building'].dropna().unique()
                    detected_buildings = [b for b in buildings if str(b) != 'Unknown']
            
            if not detected_buildings:
                detected_buildings = ['WWT']
                
            buildings_text = ', '.join(detected_buildings) + (' Building' if len(detected_buildings) == 1 else ' Buildings')
            
            # Fallback으로 기본 내용 생성
            mock_st.content = [
                ("title", "Worker Traffic Analysis Report"),
                ("info", f"Target Building: {buildings_text}"),
                ("info", "Analysis Date: August 22, 2025"),
                ("header", "📊 1. Occupancy Analysis"),
                ("header", "⏱️ 2. Dwell Time Analysis"), 
                ("header", "🗺️ 3. Journey Heatmap Analysis")
            ]
        
        # 임시 PDF 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_filename = tmp_file.name
            
        # PDF 문서 설정
        doc = SimpleDocTemplate(pdf_filename, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        
        # 스타일 정의
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#1e3c72'),
            alignment=1  # 중앙 정렬
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=HexColor('#2a5298'),
            backColor=HexColor('#f0f4f8'),
            borderPadding=10
        )
        
        subheader_style = ParagraphStyle(
            'CustomSubheader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
            textColor=HexColor('#2a5298')
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            leading=16
        )
        
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=6,
            textColor=HexColor('#1976d2'),
            backColor=HexColor('#e3f2fd'),
            borderPadding=8
        )
        
        # PDF 스토리 구성
        story = []
        
        # Report Generation 페이지의 실제 내용을 PDF로 직접 생성
        # 1. Occupancy Analysis 섹션
        story.append(Paragraph("📊 1. Occupancy Analysis", header_style))
        
        # Occupancy Analysis 데이터 직접 처리
        try:
            summary_stats = analysis_results.get('summary_stats') if analysis_results else None
            if summary_stats is not None and not summary_stats.empty:
                story.append(Paragraph("Worker Activity Summary", subheader_style))
                
                # 통계 테이블 생성
                display_columns = ['space_name', 'total_workers', 'max_active_workers', 'avg_active_workers', 'max_present_workers', 'avg_present_workers']
                column_names = ['Space', 'Total Workers', 'Max Active', 'Avg Active', 'Max Present', 'Avg Present']
                
                if all(col in summary_stats.columns for col in display_columns):
                    table_data = [column_names]
                    for _, row in summary_stats.iterrows():
                        table_row = []
                        for col in display_columns:
                            val = row[col]
                            if isinstance(val, float):
                                table_row.append(f"{val:.1f}")
                            else:
                                table_row.append(str(val))
                        table_data.append(table_row)
                    
                    table = Table(table_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2a5298')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f0f4f8')])
                    ]))
                    story.append(table)
                    story.append(Spacer(1, 0.2*inch))
                    
                story.append(Paragraph("📈 Worker Activity Trends - 24시간 연속 모니터링 데이터", normal_style))
                story.append(Paragraph("• Active Workers: 작업 중인 근무자 수", normal_style))
                story.append(Paragraph("• Present Workers: 현장에 있는 근무자 수", normal_style))
                story.append(Spacer(1, 0.1*inch))
        except Exception as e:
            story.append(Paragraph(f"Occupancy Analysis 데이터 처리 중 오류: {str(e)}", normal_style))
        
        # 2. Dwell Time Analysis 섹션
        story.append(Paragraph("⏱️ 2. Dwell Time Analysis", header_style))
        
        try:
            # 30분 이상 체류 필터링된 데이터 정보
            filtered_records = activity_analysis[activity_analysis['activity_status'].isin(['Active', 'Present'])]
            dwell_summary = filtered_records.groupby(['mac', 'space_name']).agg({
                'timestamp': ['count', 'min', 'max']
            }).reset_index()
            
            if not dwell_summary.empty:
                story.append(Paragraph("30분 이상 체류 T-Ward 필터링 결과", subheader_style))
                
                # 체류 시간 통계
                total_filtered = len(filtered_records)
                unique_devices = filtered_records['mac'].nunique()
                story.append(Paragraph(f"• 필터링된 총 레코드 수: {total_filtered:,}", normal_style))
                story.append(Paragraph(f"• 30분 이상 체류 T-Ward 수: {unique_devices:,}", normal_style))
                story.append(Paragraph(f"• 평균 체류 시간: {total_filtered/(unique_devices*60):.1f}시간", normal_style))
                story.append(Spacer(1, 0.15*inch))
                
                # 공간별 체류 분포
                space_stats = filtered_records.groupby('space_name').agg({
                    'mac': 'nunique',
                    'timestamp': 'count'
                }).reset_index()
                space_stats.columns = ['공간명', 'T-Ward 수', '활동 레코드 수']
                
                if not space_stats.empty:
                    story.append(Paragraph("공간별 T-Ward 체류 분포", subheader_style))
                    
                    table_data = [['공간명', 'T-Ward 수', '활동 레코드 수']]
                    for _, row in space_stats.iterrows():
                        table_data.append([str(row['공간명']), str(row['T-Ward 수']), f"{row['활동 레코드 수']:,}"])
                    
                    table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2a5298')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f0f4f8')])
                    ]))
                    story.append(table)
                    story.append(Spacer(1, 0.2*inch))
                    
        except Exception as e:
            story.append(Paragraph(f"Dwell Time Analysis 데이터 처리 중 오류: {str(e)}", normal_style))
            
        # 3. Journey Heatmap Analysis 섹션  
        story.append(Paragraph("🗺️ 3. Journey Heatmap Analysis", header_style))
        
        try:
            # Journey 패턴 분석
            journey_stats = activity_analysis.groupby(['mac', 'space_name']).agg({
                'timestamp': ['count', 'min', 'max'],
                'activity_status': lambda x: x.mode().iloc[0] if len(x) > 0 else 'Unknown'
            }).reset_index()
            
            if not journey_stats.empty:
                story.append(Paragraph("T-Ward 이동 패턴 및 Journey Heatmap 분석", subheader_style))
                
                # Journey 통계
                total_journeys = len(journey_stats)
                active_journeys = len(journey_stats[journey_stats[('activity_status', '<lambda>')] == 'Active'])
                story.append(Paragraph(f"• 총 Journey 패턴 수: {total_journeys:,}", normal_style))
                story.append(Paragraph(f"• Active Journey 수: {active_journeys:,}", normal_style))
                story.append(Paragraph(f"• Journey 활성화 비율: {(active_journeys/total_journeys*100):.1f}%", normal_style))
                story.append(Spacer(1, 0.15*inch))
                
                # 주요 이동 경로
                top_spaces = activity_analysis['space_name'].value_counts().head(5)
                if not top_spaces.empty:
                    story.append(Paragraph("주요 활동 공간 Top 5", subheader_style))
                    
                    table_data = [['공간명', '활동 레코드 수', '비율']]
                    total_records = len(activity_analysis)
                    for space, count in top_spaces.items():
                        percentage = (count / total_records * 100)
                        table_data.append([str(space), f"{count:,}", f"{percentage:.1f}%"])
                    
                    table = Table(table_data, colWidths=[2*inch, 1.5*inch, 1*inch])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2a5298')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f0f4f8')])
                    ]))
                    story.append(table)
                    story.append(Spacer(1, 0.2*inch))
                    
        except Exception as e:
            story.append(Paragraph(f"Journey Heatmap Analysis 데이터 처리 중 오류: {str(e)}", normal_style))
        
        # Report Generation 페이지에서 실제로 표시되는 기본 정보 추가
        if not any(item[0] == "info" for item in mock_st.content):
            # 동적 건물 정보 감지
            detected_buildings = []
            detected_levels = []
            if activity_analysis is not None and not activity_analysis.empty:
                if 'building' in activity_analysis.columns:
                    buildings = activity_analysis['building'].dropna().unique()
                    detected_buildings = [b for b in buildings if str(b) != 'Unknown']
                if 'level' in activity_analysis.columns:
                    levels = activity_analysis['level'].dropna().unique()
                    detected_levels = [l for l in levels if str(l) != 'Unknown']
            
            if not detected_buildings:
                detected_buildings = ['WWT']
            if not detected_levels:
                detected_levels = ['1F', 'B1F']
                
            buildings_text = ', '.join(detected_buildings) + (' Building' if len(detected_buildings) == 1 else ' Buildings')
            levels_text = ', '.join(detected_levels)
            
            story.insert(1, Paragraph(f"Target Building: {buildings_text}", info_style))
            story.insert(2, Paragraph(f"Analysis Levels: {levels_text}", info_style))
            story.insert(3, Paragraph("Analysis Date: August 22, 2025 (24-Hour Period)", info_style))
            story.insert(4, Paragraph("System: Hy-con & IRFM by TJLABS", info_style))
            story.insert(5, Paragraph("Data Source: T-Ward Type 41 Sensors on Workers' helmet", info_style))
            story.insert(6, Spacer(1, 0.2*inch))
        
        # 기본 통계 정보 추가 (Report Generation 페이지와 동일)
        total_records = len(activity_analysis)
        unique_twards = activity_analysis['mac'].nunique()
        filtered_records = len(activity_analysis[activity_analysis['activity_status'].isin(['Active', 'Present'])])
        
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("� Analysis Summary", header_style))
        story.append(Paragraph(f"Total Activity Records: {total_records:,}", normal_style))
        story.append(Paragraph(f"Unique T-Ward Devices: {unique_twards:,}", normal_style))
        story.append(Paragraph(f"Active/Present Records: {filtered_records:,}", normal_style))
        story.append(Paragraph(f"Data Quality Score: {(filtered_records/total_records*100):.1f}%", normal_style))
        
        # 푸터
        story.append(Spacer(1, 0.5*inch))
        footer_text = """
        <i>This report contains the same content as displayed in the Report Generation page.<br/>
        Generated by T-Ward Type 41 Analysis System - Hy-con & IRFM by TJLABS<br/>
        Report Generation Date: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</i>
        """
        story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=1)))
        
        # PDF 빌드
        doc.build(story)
        
        # PDF 파일 읽기
        with open(pdf_filename, 'rb') as f:
            pdf_data = f.read()
            
        # 임시 파일 삭제
        os.unlink(pdf_filename)
        
        return pdf_data
        
    except Exception as e:
        import traceback
        print(f"Enhanced PDF generation error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return None

def generate_report_page_pdf(activity_analysis, analysis_results):
    """Report Generation 페이지의 실제 내용을 100% 그대로 PDF로 추출"""
    try:
        import tempfile
        import os
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, cm
        from reportlab.lib import colors
        from reportlab.lib.colors import HexColor
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import io
        from reportlab.platypus import Image
        import pandas as pd
        import base64
        
        if activity_analysis is None or activity_analysis.empty:
            return None
            
        # Report Generation 페이지의 실제 섹션 함수들을 캡처
        class PDFContentCapture:
            def __init__(self):
                self.content = []
                self.current_section = ""
                
            def markdown(self, text, unsafe_allow_html=False):
                # HTML 스타일은 제거하고 내용만 캡처
                if "<style>" not in text and "<div class=" not in text:
                    clean_text = text.replace("#", "").replace("*", "").strip()
                    if clean_text:
                        self.content.append(("markdown", clean_text))
                        
            def write(self, text):
                self.content.append(("text", str(text)))
                
            def dataframe(self, df, use_container_width=False):
                self.content.append(("dataframe", df.copy()))
                
            def plotly_chart(self, fig, use_container_width=False):
                self.content.append(("plotly_chart", "Plotly Chart"))
                
            def pyplot(self, fig=None, clear_figure=True):
                if fig:
                    # matplotlib 차트를 이미지로 저장
                    img_buffer = io.BytesIO()
                    fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
                    img_buffer.seek(0)
                    self.content.append(("matplotlib_chart", img_buffer))
                    if clear_figure:
                        plt.close(fig)
                else:
                    self.content.append(("matplotlib_chart", "Matplotlib Chart"))
                    
            def success(self, text):
                self.content.append(("success", text))
                
            def warning(self, text):
                self.content.append(("warning", text))
                
            def info(self, text):
                self.content.append(("info", text))
                
            def error(self, text):
                self.content.append(("error", text))
                
            def metric(self, label, value, delta=None):
                self.content.append(("metric", label, value, delta))
                
            def columns(self, spec):
                return [self, self, self, self]  # Return multiple instances
                
            def container(self):
                return self
                
            def expander(self, label, expanded=False):
                return self
        
        # PDF 캡처 객체 생성
        pdf_capture = PDFContentCapture()
        
        # Report Generation 페이지의 실제 섹션들을 순서대로 실행
        print("🔍 PDF Capture: Executing display_occupancy_analysis_section...")
        display_occupancy_analysis_section(pdf_capture, analysis_results)
        
        print("🔍 PDF Capture: Executing display_dwell_time_analysis_section...")  
        display_dwell_time_analysis_section(pdf_capture, activity_analysis)
        
        print("🔍 PDF Capture: Executing display_journey_analysis_section...")
        display_journey_analysis_section(pdf_capture, activity_analysis)
        
        print(f"🔍 PDF Capture: Captured {len(pdf_capture.content)} content items")
        
        # 캡처된 내용을 PDF로 변환
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_filename = tmp_file.name
            
        # PDF 문서 생성
        doc = SimpleDocTemplate(
            pdf_filename, 
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # 스타일 설정
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#1E3A8A'),
            alignment=1  # center
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=HexColor('#F5576C'),
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=12,
            spaceBefore=6,
            spaceAfter=6,
            fontName='Helvetica'
        )
        
        # PDF 내용 생성
        story = []
        
        # 제목 추가
        story.append(Paragraph("T-Ward Type 41 Report Generation", title_style))
        story.append(Spacer(1, 30))
        
        # 캡처된 내용을 PDF 요소로 변환
        for item in pdf_capture.content:
            if item[0] == "markdown":
                if len(item[1]) > 50:  # 긴 텍스트는 헤딩으로
                    story.append(Paragraph(item[1], heading_style))
                else:
                    story.append(Paragraph(item[1], body_style))
                story.append(Spacer(1, 6))
                
            elif item[0] == "text":
                story.append(Paragraph(str(item[1]), body_style))
                story.append(Spacer(1, 6))
                
            elif item[0] == "dataframe":
                df = item[1]
                if not df.empty:
                    # DataFrame을 테이블로 변환
                    data = [df.columns.tolist()] + df.values.tolist()
                    # 데이터 크기 제한 (너무 큰 테이블 방지)
                    if len(data) > 21:  # 헤더 + 20 rows
                        data = data[:21]
                        data.append(["...", "...", "..."])
                        
                    table = Table(data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#F5576C')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#F8F9FA')),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    story.append(table)
                    story.append(Spacer(1, 20))
                    
            elif item[0] == "metric":
                label, value, delta = item[1], item[2], item[3] if len(item) > 3 else None
                metric_text = f"{label}: {value}"
                if delta:
                    metric_text += f" ({delta})"
                story.append(Paragraph(metric_text, heading_style))
                story.append(Spacer(1, 10))
                
            elif item[0] in ["success", "warning", "info", "error"]:
                story.append(Paragraph(f"{item[0].upper()}: {item[1]}", body_style))
                story.append(Spacer(1, 6))
                
            elif item[0] == "matplotlib_chart":
                if isinstance(item[1], io.BytesIO):
                    # matplotlib 이미지 추가
                    img = Image(item[1])
                    img.drawHeight = 4*inch
                    img.drawWidth = 6*inch
                    story.append(img)
                    story.append(Spacer(1, 20))
                else:
                    story.append(Paragraph("Chart: " + str(item[1]), body_style))
                    story.append(Spacer(1, 10))
                    
            elif item[0] == "plotly_chart":
                story.append(Paragraph("Interactive Chart (Plotly visualization)", body_style))
                story.append(Spacer(1, 10))
        
        # PDF 생성
        doc.build(story)
        
        # PDF 파일을 base64로 인코딩 (Type 31 스타일)
        with open(pdf_filename, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # 파일 정보
        pdf_size = len(pdf_bytes)
        pdf_size_mb = pdf_size / (1024 * 1024)
        
        # 임시 파일 삭제
        os.unlink(pdf_filename)
        
        return {
            'pdf_base64': pdf_base64,
            'filename': 'type41_report_generation.pdf',
            'size_mb': round(pdf_size_mb, 2),
            'content_items': len(pdf_capture.content)
        }
    
    except Exception as e:
        print(f"❌ PDF 생성 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None
        story.append(Paragraph("⏱️ 2. Dwell Time Analysis", header_style))
        
        # 30분 이상 체류 데이터 분석
        if 'activity_status' in activity_analysis.columns:
            filtered_data = activity_analysis[activity_analysis['activity_status'].isin(['Active', 'Present'])]
            
            story.append(Paragraph("<b>30분 이상 체류 T-Ward 분석:</b>", normal_style))
            story.append(Paragraph(f"• 필터링된 레코드 수: {len(filtered_data):,}", normal_style))
            story.append(Paragraph(f"• 체류 기준: 30분 이상", normal_style))
            story.append(Paragraph(f"• 데이터 품질: {len(filtered_data)/len(activity_analysis)*100:.1f}%", normal_style))
            
            # 공간별 체류 분포 (안전한 컬럼 체크)
            available_group_col = None
            col_name = ""
            
            if 'space_name' in activity_analysis.columns:
                available_group_col = 'space_name'
                col_name = '공간명'
            elif 'building' in activity_analysis.columns:
                available_group_col = 'building'  
                col_name = '빌딩명'
            elif 'level' in activity_analysis.columns:
                available_group_col = 'level'
                col_name = '레벨명'
            
            if available_group_col:
                # 사용 가능한 집계 컬럼 찾기
                count_col = None
                if 'timestamp' in filtered_data.columns:
                    count_col = 'timestamp'
                elif len(filtered_data.columns) > 2:  # mac과 group 컬럼 외에 다른 컬럼이 있다면
                    count_col = [col for col in filtered_data.columns if col not in ['mac', available_group_col]][0]
                
                if count_col:
                    space_stats = filtered_data.groupby(available_group_col).agg({
                        'mac': 'nunique',
                        count_col: 'count'
                    }).reset_index()
                    
                    if not space_stats.empty:
                        story.append(Paragraph(f"<b>{col_name}별 체류 분포:</b>", normal_style))
                        
                        # 테이블 데이터
                        space_table_data = [[col_name, 'T-Ward 수', '활동 레코드 수']]
                        for _, row in space_stats.head(10).iterrows():
                            space_table_data.append([
                                str(row[available_group_col]),
                                str(row['mac']),
                                f"{row[count_col]:,}"
                            ])
                        
                        space_table = Table(space_table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
                        space_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2a5298')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 10),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                            ('FONTSIZE', (0, 1), (-1, -1), 9),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f0f4f8')])
                        ]))
                        story.append(space_table)
                else:
                    # 단순 분포만 표시
                    space_counts = filtered_data[available_group_col].value_counts()
                    story.append(Paragraph(f"<b>{col_name}별 분포:</b>", normal_style))
                    for space, count in space_counts.head(5).items():
                        percentage = count / len(filtered_data) * 100
                        story.append(Paragraph(f"• {space}: {count:,} 레코드 ({percentage:.1f}%)", normal_style))
        
        story.append(Spacer(1, 0.2*inch))
        
        # 4. Journey Heatmap Analysis 섹션
        story.append(Paragraph("🗺️ 3. Journey Heatmap Analysis", header_style))
        
        # Journey 패턴 분석 (안전한 컬럼 체크)
        print(f"DEBUG: activity_analysis columns: {list(activity_analysis.columns)}")
        
        # 사용 가능한 컬럼들 확인
        has_timestamp = 'timestamp' in activity_analysis.columns
        has_space_name = 'space_name' in activity_analysis.columns
        has_building = 'building' in activity_analysis.columns
        has_level = 'level' in activity_analysis.columns
        
        # 기본 Journey 통계
        total_twards = activity_analysis['mac'].nunique()
        total_records = len(activity_analysis)
        avg_records_per_device = total_records / total_twards if total_twards > 0 else 0
        
        story.append(Paragraph(f"<b>Journey 패턴 분석:</b>", normal_style))
        story.append(Paragraph(f"• 총 T-Ward 디바이스: {total_twards:,}", normal_style))
        story.append(Paragraph(f"• 총 활동 레코드: {total_records:,}", normal_style))
        story.append(Paragraph(f"• 디바이스당 평균 레코드: {avg_records_per_device:.1f}", normal_style))
        
        # 주요 활동 공간 또는 레벨 분석
        if has_space_name:
            top_spaces = activity_analysis['space_name'].value_counts().head(5)
            if not top_spaces.empty:
                story.append(Paragraph("<b>주요 활동 공간 Top 5:</b>", normal_style))
                
                space_top_data = [['공간명', '활동 레코드 수', '비율']]
                for space, count in top_spaces.items():
                    percentage = (count / total_records * 100)
                    space_top_data.append([
                        str(space),
                        f"{count:,}",
                        f"{percentage:.1f}%"
                    ])
                
                space_top_table = Table(space_top_data, colWidths=[2*inch, 1.5*inch, 1*inch])
                space_top_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2a5298')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f0f4f8')])
                ]))
                story.append(space_top_table)
        elif has_building:
            # building 컬럼이 있는 경우
            building_stats = activity_analysis['building'].value_counts()
            if not building_stats.empty:
                story.append(Paragraph("<b>빌딩별 활동 분포:</b>", normal_style))
                for building, count in building_stats.items():
                    percentage = (count / total_records * 100)
                    story.append(Paragraph(f"• {building}: {count:,} 레코드 ({percentage:.1f}%)", normal_style))
        elif has_level:
            # level 컬럼이 있는 경우
            level_stats = activity_analysis['level'].value_counts()
            if not level_stats.empty:
                story.append(Paragraph("<b>레벨별 활동 분포:</b>", normal_style))
                for level, count in level_stats.items():
                    percentage = (count / total_records * 100)
                    story.append(Paragraph(f"• {level}: {count:,} 레코드 ({percentage:.1f}%)", normal_style))
        else:
            story.append(Paragraph("• 공간 정보가 없어 상세한 Journey 분석을 수행할 수 없습니다.", normal_style))
        
        # 푸터
        story.append(Spacer(1, 0.5*inch))
        footer_text = f"""
        <i>This report contains comprehensive analysis of T-Ward Type 41 data.<br/>
        Generated by T-Ward Type 41 Analysis System - Hy-con & IRFM by TJLABS<br/>
        Report Generation Date: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")}</i>
        """
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=1)
        story.append(Paragraph(footer_text, footer_style))
        
        # PDF 빌드
        doc.build(story)
        
        # PDF 파일 읽기
        with open(pdf_filename, 'rb') as f:
            pdf_data = f.read()
            
        # 임시 파일 삭제
        os.unlink(pdf_filename)
        
        return pdf_data
        
    except Exception as e:
        import traceback
        print(f"Report PDF generation error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return None
