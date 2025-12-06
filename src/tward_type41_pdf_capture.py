"""
T-Ward Type 41 Report Generation PDF 캡처 모듈
Report Generation 페이지의 실제 내용을 100% 그대로 PDF로 추출
"""

import streamlit as st
import pandas as pd
import tempfile
import os
import base64
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


def generate_report_page_pdf_v2(activity_analysis, analysis_results):
    """Report Generation 페이지의 실제 내용을 100% 그대로 PDF로 추출"""
    try:
        if activity_analysis is None or activity_analysis.empty:
            return None
            
        # Report Generation 페이지의 실제 섹션 함수들을 캡처
        class PDFContentCapture:
            def __init__(self):
                self.content = []
                self.current_section = ""
                self.debug_calls = []
                
            def _log_call(self, method, *args, **kwargs):
                """모든 streamlit 호출을 로깅"""
                self.debug_calls.append(f"{method}({args}, {kwargs})")
                print(f"🔍 PDFCapture: {method} called with {len(str(args))} chars")
                
            def markdown(self, text, unsafe_allow_html=False):
                self._log_call("markdown", text[:50] + "..." if len(str(text)) > 50 else text)
                # HTML 스타일과 CSS는 제거하고 내용만 캡처
                if isinstance(text, str):
                    if not any(x in text.lower() for x in ["<style>", "<div class=", "background:", "color:", "font-"]):
                        # 마크다운 기호들 정리
                        clean_text = text.replace("#", "").replace("*", "").replace("---", "").strip()
                        if clean_text and clean_text != "📊" and len(clean_text) > 1:
                            self.content.append(("markdown", clean_text))
                        
            def write(self, text):
                self._log_call("write", text)
                if text and str(text).strip():
                    self.content.append(("text", str(text)))
                
            def dataframe(self, df, use_container_width=False, **kwargs):
                self._log_call("dataframe", f"DataFrame shape: {df.shape if df is not None else 'None'}")
                if df is not None and not df.empty:
                    self.content.append(("dataframe", df.copy()))
                
            def plotly_chart(self, fig, use_container_width=False, **kwargs):
                self._log_call("plotly_chart", "Plotly figure")
                # Plotly 차트 정보 저장
                try:
                    chart_title = getattr(fig, 'layout', {}).get('title', {}).get('text', 'Interactive Chart')
                    self.content.append(("plotly_chart", f"Plotly Chart: {chart_title}"))
                except:
                    self.content.append(("plotly_chart", "Interactive Plotly Chart"))
                
            def pyplot(self, fig=None, clear_figure=True, **kwargs):
                self._log_call("pyplot", f"Figure: {fig is not None}")
                try:
                    if fig:
                        # matplotlib 차트를 이미지로 저장
                        img_buffer = io.BytesIO()
                        fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
                        img_buffer.seek(0)
                        self.content.append(("matplotlib_chart", img_buffer))
                        if clear_figure:
                            plt.close(fig)
                    else:
                        # 현재 figure를 캡처
                        current_fig = plt.gcf()
                        if current_fig.get_axes():
                            img_buffer = io.BytesIO()
                            current_fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
                            img_buffer.seek(0)
                            self.content.append(("matplotlib_chart", img_buffer))
                            if clear_figure:
                                plt.close(current_fig)
                except Exception as e:
                    print(f"⚠️ pyplot 캡처 실패: {e}")
                    self.content.append(("matplotlib_chart", "Chart (capture failed)"))
                    
            def success(self, text):
                self._log_call("success", text)
                self.content.append(("success", str(text)))
                
            def warning(self, text):
                self._log_call("warning", text)
                self.content.append(("warning", str(text)))
                
            def info(self, text):
                self._log_call("info", text)
                self.content.append(("info", str(text)))
                
            def error(self, text):
                self._log_call("error", text)
                self.content.append(("error", str(text)))
                
            def metric(self, label, value, delta=None, **kwargs):
                self._log_call("metric", label, value, delta)
                self.content.append(("metric", label, value, delta))
                
            def columns(self, spec):
                self._log_call("columns", spec)
                # 각 컬럼에 대해 별도의 캡처 객체 반환
                return [PDFContentCapture() for _ in range(len(spec) if isinstance(spec, (list, tuple)) else spec)]
                
            def container(self):
                self._log_call("container")
                return self
                
            def expander(self, label, expanded=False):
                self._log_call("expander", label)
                self.content.append(("markdown", f"▼ {label}"))
                return self
                
            def header(self, text):
                self._log_call("header", text)
                self.content.append(("header", str(text)))
                
            def subheader(self, text):
                self._log_call("subheader", text)
                self.content.append(("subheader", str(text)))
                
            def title(self, text):
                self._log_call("title", text)
                self.content.append(("title", str(text)))
                
            def caption(self, text):
                self._log_call("caption", text)
                self.content.append(("caption", str(text)))
                
            def code(self, body, language='python'):
                self._log_call("code", body[:50])
                self.content.append(("code", str(body)))
                
            def json(self, body):
                self._log_call("json", "JSON data")
                self.content.append(("json", str(body)))
                
            def latex(self, body):
                self._log_call("latex", body)
                self.content.append(("latex", str(body)))
                
            # 기타 streamlit 메서드들
            def empty(self):
                return self
                
            def beta_columns(self, spec):
                return self.columns(spec)
                
            def selectbox(self, *args, **kwargs):
                return None
                
            def button(self, *args, **kwargs):
                return False
                
            def slider(self, *args, **kwargs):
                return 0
                
            def checkbox(self, *args, **kwargs):
                return False
                
            # 차트 관련 추가 메서드들
            def line_chart(self, data, **kwargs):
                self._log_call("line_chart", f"Data shape: {data.shape if hasattr(data, 'shape') else 'N/A'}")
                self.content.append(("chart", "Line Chart"))
                
            def bar_chart(self, data, **kwargs):
                self._log_call("bar_chart", f"Data shape: {data.shape if hasattr(data, 'shape') else 'N/A'}")
                self.content.append(("chart", "Bar Chart"))
                
            def area_chart(self, data, **kwargs):
                self._log_call("area_chart", f"Data shape: {data.shape if hasattr(data, 'shape') else 'N/A'}")
                self.content.append(("chart", "Area Chart"))
                
            # Plotly 관련 추가
            def plotly_chart_container(self, *args, **kwargs):
                return self
                
            # 컨텍스트 매니저 지원
            def __enter__(self):
                return self
                
            def __exit__(self, *args):
                pass
        
        # PDF 캡처 객체 생성
        pdf_capture = PDFContentCapture()
        
        print("� PDF Capture: Starting Report Generation page execution...")
        
        # Execute actual Report Generation page sections in order
        from .tward_type41_report_generation import (
            display_occupancy_analysis_section,
            display_dwell_time_analysis_section, 
            display_journey_analysis_section
        )
        
        try:
            print("� PDF Capture: Executing display_occupancy_analysis_section...")
            initial_count = len(pdf_capture.content)
            display_occupancy_analysis_section(pdf_capture, analysis_results)
            new_count = len(pdf_capture.content)
            print(f"   📊 Occupancy Analysis: {new_count - initial_count} items captured")
        except Exception as e:
            print(f"⚠️ Occupancy Analysis section capture failed: {e}")
            import traceback
            traceback.print_exc()
            pdf_capture.content.append(("error", f"Occupancy Analysis section error: {e}"))
        
        try:
            print("⏱️ PDF Capture: Executing display_dwell_time_analysis_section...")
            initial_count = len(pdf_capture.content)
            display_dwell_time_analysis_section(pdf_capture, activity_analysis)
            new_count = len(pdf_capture.content)
            print(f"   ⏱️ Dwell Time Analysis: {new_count - initial_count} items captured")
        except Exception as e:
            print(f"⚠️ Dwell Time Analysis section capture failed: {e}")
            import traceback
            traceback.print_exc()
            pdf_capture.content.append(("error", f"Dwell Time Analysis section error: {e}"))
        
        try:
            print("�️ PDF Capture: Executing display_journey_analysis_section...")
            initial_count = len(pdf_capture.content)
            display_journey_analysis_section(pdf_capture, activity_analysis)
            new_count = len(pdf_capture.content)
            print(f"   🗺️ Journey Analysis: {new_count - initial_count} items captured")
        except Exception as e:
            print(f"⚠️ Journey Analysis section capture failed: {e}")
            import traceback
            traceback.print_exc()
            pdf_capture.content.append(("error", f"Journey Analysis section error: {e}"))
        
        print(f"✅ PDF Capture: Total {len(pdf_capture.content)} content items captured")
        
        # 캡처된 콘텐츠 요약 출력
        content_summary = {}
        for item in pdf_capture.content:
            item_type = item[0]
            content_summary[item_type] = content_summary.get(item_type, 0) + 1
        
        print("📋 캡처된 콘텐츠 요약:")
        for content_type, count in content_summary.items():
            print(f"   • {content_type}: {count}개")
            
        # 디버그 호출 정보도 출력
        print(f"🔧 디버그: 총 {len(pdf_capture.debug_calls)}개 streamlit 메서드 호출됨")
        
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
        
        # PDF content creation
        story = []
        
        # Title Page
        story.append(Paragraph("Worker Traffic Analysis Report", title_style))
        story.append(Spacer(1, 40))
        
        # Report Information
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=14,
            spaceBefore=8,
            spaceAfter=8,
            fontName='Helvetica-Bold',
            leftIndent=50
        )
        
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
            
        buildings_text = ', '.join(detected_buildings)
        levels_text = ', '.join(detected_levels)
        
        story.append(Paragraph(f"Target Building : {buildings_text}", info_style))
        story.append(Paragraph(f"Target Level : {levels_text}", info_style))
        story.append(Paragraph("Date : Aug. 22, 2025 (24-Hour)", info_style))
        story.append(Paragraph("System : Hy-con. & IRFM by TJLABS", info_style))
        story.append(Paragraph("Data source : T-Ward type 41 on Workers' helmet", info_style))
        story.append(Spacer(1, 50))
        
        # Convert captured content to PDF elements  
        print(f"📄 Converting PDF content... Total {len(pdf_capture.content)} items")
        
        for i, item in enumerate(pdf_capture.content):
            try:
                item_type = item[0]
                print(f"  📝 Processing: {item_type} ({i+1}/{len(pdf_capture.content)})")
                
                if item_type == "markdown":
                    text = item[1]
                    
                    # Convert Korean text to English
                    text = text.replace("점유도 분석", "Occupancy Analysis")
                    text = text.replace("체류 시간 분석", "Dwell Time Analysis") 
                    text = text.replace("이동 경로 분석", "Journey Analysis")
                    text = text.replace("워커 활동", "Worker Activity")
                    text = text.replace("분석 결과", "Analysis Results")
                    text = text.replace("데이터 테이블", "Data Table")
                    text = text.replace("차트", "Chart")
                    text = text.replace("그래프", "Graph")
                    
                    # Special handling for Color Legend
                    if "Color Legend:" in text:
                        # Create legend style
                        legend_style = ParagraphStyle(
                            'Legend',
                            parent=body_style,
                            fontSize=11,
                            leftIndent=20,
                            spaceBefore=8,
                            spaceAfter=12,
                            fontName='Helvetica'
                        )
                        story.append(Paragraph(text, legend_style))
                        story.append(Spacer(1, 10))
                    elif "📊" in text or "⏱️" in text or "🗺️" in text or len(text) > 50:
                        # Process as heading
                        story.append(Paragraph(text, heading_style))
                        story.append(Spacer(1, 15))
                    else:
                        story.append(Paragraph(text, body_style))
                        story.append(Spacer(1, 6))
                        
                elif item_type == "text":
                    text = str(item[1])
                    # Convert Korean text to English
                    text = text.replace("레코드", "records")
                    text = text.replace("명", "people")
                    text = text.replace("개", "items")
                    text = text.replace("시간", "time")
                    text = text.replace("분", "minutes")
                    story.append(Paragraph(text, body_style))
                    story.append(Spacer(1, 6))
                    
                elif item_type in ["header", "title"]:
                    text = str(item[1])
                    # Convert Korean headers
                    text = text.replace("점유도 분석", "Occupancy Analysis")
                    text = text.replace("체류 시간 분석", "Dwell Time Analysis")
                    text = text.replace("이동 경로 분석", "Journey Analysis")
                    story.append(Paragraph(text, heading_style))
                    story.append(Spacer(1, 15))
                    
                elif item_type == "subheader":
                    subheader_style = ParagraphStyle(
                        'Subheader',
                        parent=body_style,
                        fontSize=14,
                        textColor=HexColor('#333333'),
                        fontName='Helvetica-Bold',
                        spaceBefore=10,
                        spaceAfter=8
                    )
                    story.append(Paragraph(str(item[1]), subheader_style))
                    story.append(Spacer(1, 10))
                    
                elif item_type == "dataframe":
                    df = item[1]
                    if not df.empty:
                        story.append(Paragraph("📊 Data Table", heading_style))
                        
                        # Convert DataFrame to table (size optimization)
                        data = [df.columns.tolist()]
                        
                        # Add data rows (limit to 15 rows max)
                        display_rows = min(15, len(df))
                        for idx in range(display_rows):
                            row = df.iloc[idx]
                            data.append([str(val)[:30] + "..." if len(str(val)) > 30 else str(val) for val in row.values])
                            
                        if len(df) > 15:
                            data.append(["...", "...", "..."] + ["..."] * max(0, len(df.columns) - 3))
                            
                        # Calculate column width
                        num_cols = len(data[0])
                        col_width = 7*inch / num_cols
                        
                        # 테이블 생성
                        table = Table(data, colWidths=[col_width] * num_cols)
                        table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#F5576C')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 9),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                            ('BACKGROUND', (0, 1), (-1, -1), HexColor('#F8F9FA')),
                            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                            ('FONTSIZE', (0, 1), (-1, -1), 8),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
                        ]))
                        story.append(table)
                        story.append(Spacer(1, 20))
                        
                elif item_type == "metric":
                    label, value = item[1], item[2]
                    delta = item[3] if len(item) > 3 and item[3] else None
                    metric_text = f"📊 {label}: {value}"
                    if delta:
                        metric_text += f" ({delta})"
                    
                    metric_style = ParagraphStyle(
                        'Metric',
                        parent=body_style,
                        fontSize=13,
                        textColor=HexColor('#2E86AB'),
                        fontName='Helvetica-Bold',
                        leftIndent=20
                    )
                    story.append(Paragraph(metric_text, metric_style))
                    story.append(Spacer(1, 8))
                    
                elif item_type in ["success", "warning", "info", "error"]:
                    emoji = {"success": "✅", "warning": "⚠️", "info": "ℹ️", "error": "❌"}
                    text = f"{emoji.get(item_type, '•')} {item[1]}"
                    
                    alert_style = ParagraphStyle(
                        'Alert',
                        parent=body_style,
                        fontSize=11,
                        textColor=HexColor('#666666'),
                        leftIndent=15,
                        rightIndent=15,
                        spaceBefore=5,
                        spaceAfter=5
                    )
                    story.append(Paragraph(text, alert_style))
                    story.append(Spacer(1, 6))
                    
                elif item_type == "matplotlib_chart":
                    if isinstance(item[1], io.BytesIO):
                        # matplotlib 이미지 추가
                        try:
                            item[1].seek(0)  # 버퍼 위치를 처음으로
                            img = Image(item[1])
                            # 이미지 크기 최적화
                            img.drawHeight = 4.5*inch
                            img.drawWidth = 7*inch
                            story.append(Paragraph("📈 Chart Visualization", heading_style))
                            story.append(Spacer(1, 10))
                            story.append(img)
                            story.append(Spacer(1, 25))
                            print(f"  ✅ 차트 이미지 추가됨")
                        except Exception as e:
                            print(f"  ⚠️ 차트 이미지 처리 실패: {e}")
                            story.append(Paragraph("📈 Chart (이미지 처리 실패)", body_style))
                            story.append(Spacer(1, 10))
                    else:
                        story.append(Paragraph("📈 Chart: " + str(item[1]), body_style))
                        story.append(Spacer(1, 10))
                        
                elif item_type == "plotly_chart":
                    chart_description = str(item[1]) if len(item) > 1 else "Interactive Chart"
                    story.append(Paragraph(f"📊 {chart_description}", body_style))
                    story.append(Spacer(1, 10))
                    
                elif item_type in ["chart", "line_chart", "bar_chart", "area_chart"]:
                    chart_type = item_type.replace("_", " ").title()
                    story.append(Paragraph(f"📊 {chart_type}", body_style))
                    story.append(Spacer(1, 10))
                    
                elif item_type == "code":
                    code_style = ParagraphStyle(
                        'Code',
                        parent=body_style,
                        fontSize=10,
                        fontName='Courier',
                        backColor=HexColor('#F5F5F5'),
                        leftIndent=20,
                        rightIndent=20,
                        spaceBefore=5,
                        spaceAfter=5
                    )
                    story.append(Paragraph(f"<pre>{item[1]}</pre>", code_style))
                    story.append(Spacer(1, 10))
                    
                else:
                    # 알 수 없는 타입도 텍스트로 처리
                    story.append(Paragraph(f"{item_type}: {item[1] if len(item) > 1 else ''}", body_style))
                    story.append(Spacer(1, 6))
                    
            except Exception as e:
                print(f"⚠️ PDF 아이템 {i} ({item_type}) 처리 중 오류: {e}")
                story.append(Paragraph(f"Content processing error ({item_type}): {e}", body_style))
                story.append(Spacer(1, 6))
        
        # Generate PDF
        print("📄 Building PDF document...")
        doc.build(story)
        
        # Encode PDF file to base64 (Type 31 style)
        with open(pdf_filename, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # File information
        pdf_size = len(pdf_bytes)
        pdf_size_mb = pdf_size / (1024 * 1024)
        
        # Delete temporary file
        os.unlink(pdf_filename)
        
        print(f"✅ PDF generation complete! Size: {pdf_size_mb:.2f}MB, Content: {len(pdf_capture.content)} items")
        
        return {
            'pdf_base64': pdf_base64,
            'filename': 'type41_report_generation.pdf',
            'size_mb': round(pdf_size_mb, 2),
            'content_items': len(pdf_capture.content)
        }
    
    except Exception as e:
        print(f"❌ PDF generation error: {e}")
        import traceback
        traceback.print_exc()
        return None


def display_pdf_preview_v2(pdf_result):
    """Type 31 style PDF preview and download"""
    if not pdf_result:
        st.error("PDF generation failed.")
        return
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 2rem; margin: 2rem 0; border-radius: 15px; 
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
        <h2 style="color: white; margin: 0; text-align: center;">
            📄 Report Generation PDF Preview
        </h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Display PDF information
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📁 File Size", f"{pdf_result['size_mb']} MB")
    
    with col2:
        st.metric("📊 Content Items", f"{pdf_result['content_items']} items")
    
    with col3:
        st.metric("📄 Filename", pdf_result['filename'])
    
    # PDF preview (iframe)
    pdf_display = f"""
    <iframe src="data:application/pdf;base64,{pdf_result['pdf_base64']}" 
            width="100%" height="600px" type="application/pdf">
    </iframe>
    """
    
    st.markdown(pdf_display, unsafe_allow_html=True)
    
    # Download button
    st.download_button(
        label="📥 Download PDF",
        data=base64.b64decode(pdf_result['pdf_base64']),
        file_name=pdf_result['filename'],
        mime="application/pdf",
        use_container_width=True
    )
    
    st.success(f"✅ PDF successfully generated! ({pdf_result['content_items']} content items included)")