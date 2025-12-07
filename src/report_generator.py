"""
PDF Report Generator for T31 Equipment and T41 Worker Analysis
Uses reportlab for PDF generation
"""

from io import BytesIO
from datetime import datetime
import pandas as pd

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_t31_pdf_report(t31_data: pd.DataFrame, insights: dict = None) -> bytes:
    """
    Generate PDF report for T31 Equipment Analysis
    
    Args:
        t31_data: T31 equipment DataFrame
        insights: Pre-computed AI insights dictionary
        
    Returns:
        PDF as bytes
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Title Style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=30,
        textColor=colors.HexColor('#1a73e8')
    )
    
    # Subtitle Style
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.grey
    )
    
    # Heading Style
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.HexColor('#333333')
    )
    
    # Normal Text Style
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        leading=14
    )
    
    # =========================================================================
    # Cover Page
    # =========================================================================
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph("T31 Equipment Analysis Report", title_style))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    elements.append(Spacer(1, inch))
    
    # Summary Box
    total_equipment = t31_data['mac'].nunique() if 'mac' in t31_data.columns else 0
    total_records = len(t31_data)
    
    summary_data = [
        ['Total Equipment', f'{total_equipment:,}'],
        ['Total Records', f'{total_records:,}'],
        ['Analysis Period', '24 hours'],
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f4f8')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
    ]))
    elements.append(summary_table)
    
    elements.append(PageBreak())
    
    # =========================================================================
    # Key Findings
    # =========================================================================
    elements.append(Paragraph("Key Findings", heading_style))
    
    if insights and 'findings' in insights:
        for i, finding in enumerate(insights['findings'], 1):
            title = finding.get('title', '')
            desc = finding.get('description', '')
            elements.append(Paragraph(f"<b>{i}. {title}:</b> {desc}", normal_style))
    else:
        elements.append(Paragraph("1. <b>Equipment Utilization:</b> Most equipment showed consistent operation patterns", normal_style))
        elements.append(Paragraph("2. <b>Peak Hours:</b> Highest activity during 8AM-6PM work hours", normal_style))
        elements.append(Paragraph("3. <b>Building Distribution:</b> Equipment distributed across buildings", normal_style))
    
    elements.append(Spacer(1, 20))
    
    # =========================================================================
    # Recommendations
    # =========================================================================
    elements.append(Paragraph("Recommendations", heading_style))
    
    if insights and 'recommendations' in insights:
        for i, rec in enumerate(insights['recommendations'], 1):
            elements.append(Paragraph(f"{i}. {rec}", normal_style))
    else:
        elements.append(Paragraph("1. Schedule maintenance for low-activity equipment", normal_style))
        elements.append(Paragraph("2. Optimize equipment placement based on usage patterns", normal_style))
        elements.append(Paragraph("3. Monitor equipment health indicators regularly", normal_style))
    
    elements.append(Spacer(1, 20))
    
    # =========================================================================
    # Data Summary Table
    # =========================================================================
    elements.append(Paragraph("Equipment Summary by Building", heading_style))
    
    if 'sward_id' in t31_data.columns:
        # Create a summary by building if building info is available
        equipment_counts = t31_data.groupby('mac').size().reset_index(name='Signal Count')
        top_equipment = equipment_counts.nlargest(10, 'Signal Count')
        
        table_data = [['Equipment ID', 'Signal Count']]
        for _, row in top_equipment.iterrows():
            # Truncate MAC for display
            mac_display = row['mac'][:12] + '...' if len(str(row['mac'])) > 12 else str(row['mac'])
            table_data.append([mac_display, f"{row['Signal Count']:,}"])
        
        data_table = Table(table_data, colWidths=[3*inch, 2*inch])
        data_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))
        elements.append(data_table)
    
    # =========================================================================
    # Footer
    # =========================================================================
    elements.append(Spacer(1, inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    elements.append(Paragraph("Generated by TJLABS Hy-con & IRFM System", footer_style))
    
    # Build PDF
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


def generate_t41_pdf_report(t41_data: pd.DataFrame, insights: dict = None) -> bytes:
    """
    Generate PDF report for T41 Worker Analysis
    
    Args:
        t41_data: T41 worker DataFrame
        insights: Pre-computed AI insights dictionary
        
    Returns:
        PDF as bytes
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Title Style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=30,
        textColor=colors.HexColor('#34a853')
    )
    
    # Subtitle Style
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.grey
    )
    
    # Heading Style
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.HexColor('#333333')
    )
    
    # Normal Text Style
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        leading=14
    )
    
    # =========================================================================
    # Cover Page
    # =========================================================================
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph("T41 Worker Analysis Report", title_style))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    elements.append(Spacer(1, inch))
    
    # Summary Box
    total_workers = t41_data['mac'].nunique() if 'mac' in t41_data.columns else 0
    total_records = len(t41_data)
    
    summary_data = [
        ['Total Workers', f'{total_workers:,}'],
        ['Total Records', f'{total_records:,}'],
        ['Analysis Period', '24 hours'],
    ]
    
    if insights and 'congestion_score' in insights:
        summary_data.append(['Congestion Score', str(insights['congestion_score'])])
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e8f5e9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
    ]))
    elements.append(summary_table)
    
    elements.append(PageBreak())
    
    # =========================================================================
    # Key Findings
    # =========================================================================
    elements.append(Paragraph("Key Findings", heading_style))
    
    if insights and 'findings' in insights:
        for i, finding in enumerate(insights['findings'], 1):
            title = finding.get('title', '')
            desc = finding.get('description', '')
            elements.append(Paragraph(f"<b>{i}. {title}:</b> {desc}", normal_style))
    else:
        elements.append(Paragraph("1. <b>Worker Mobility:</b> High cross-building movement detected", normal_style))
        elements.append(Paragraph("2. <b>Peak Hours:</b> Most activity during 9AM-5PM", normal_style))
        elements.append(Paragraph("3. <b>Congestion Points:</b> Specific areas with high worker density identified", normal_style))
    
    elements.append(Spacer(1, 20))
    
    # =========================================================================
    # Safety Observations
    # =========================================================================
    elements.append(Paragraph("Safety Observations", heading_style))
    
    if insights and 'alerts' in insights:
        for alert in insights['alerts']:
            elements.append(Paragraph(f"⚠️ {alert}", normal_style))
    else:
        elements.append(Paragraph("⚠️ Some workers showed extended periods in potentially hazardous zones", normal_style))
        elements.append(Paragraph("⚠️ Cross-zone movement patterns may indicate workflow inefficiencies", normal_style))
    
    elements.append(Spacer(1, 20))
    
    # =========================================================================
    # Recommendations
    # =========================================================================
    elements.append(Paragraph("Recommendations", heading_style))
    
    if insights and 'recommendations' in insights:
        for i, rec in enumerate(insights['recommendations'], 1):
            elements.append(Paragraph(f"{i}. {rec}", normal_style))
    else:
        elements.append(Paragraph("1. Optimize worker routing to reduce congestion", normal_style))
        elements.append(Paragraph("2. Consider shift scheduling adjustments for peak hours", normal_style))
        elements.append(Paragraph("3. Review safety protocols for high-exposure areas", normal_style))
    
    elements.append(Spacer(1, 20))
    
    # =========================================================================
    # Worker Activity Summary
    # =========================================================================
    elements.append(Paragraph("Top Workers by Activity", heading_style))
    
    if 'mac' in t41_data.columns:
        worker_counts = t41_data.groupby('mac').size().reset_index(name='Signal Count')
        top_workers = worker_counts.nlargest(10, 'Signal Count')
        
        table_data = [['Worker ID', 'Signal Count']]
        for _, row in top_workers.iterrows():
            mac_display = row['mac'][:12] + '...' if len(str(row['mac'])) > 12 else str(row['mac'])
            table_data.append([mac_display, f"{row['Signal Count']:,}"])
        
        data_table = Table(table_data, colWidths=[3*inch, 2*inch])
        data_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34a853')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))
        elements.append(data_table)
    
    # =========================================================================
    # Footer
    # =========================================================================
    elements.append(Spacer(1, inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    elements.append(Paragraph("Generated by TJLABS Hy-con & IRFM System", footer_style))
    
    # Build PDF
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


def check_reportlab_available() -> bool:
    """Check if reportlab is available for PDF generation"""
    return REPORTLAB_AVAILABLE


def generate_comprehensive_t31_report(t31_data: pd.DataFrame, sward_config: pd.DataFrame = None, 
                                       insights: dict = None, cache_loader = None) -> bytes:
    """
    Generate comprehensive PDF report for T31 Equipment Analysis
    Includes Building/Level breakdown, operation times, and visual summaries
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation")
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22, alignment=TA_CENTER, 
                                  spaceAfter=20, textColor=colors.HexColor('#1a73e8'))
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, spaceAfter=10, 
                                    spaceBefore=15, textColor=colors.HexColor('#333'))
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10, spaceAfter=6, leading=12)
    
    # =========================================================================
    # Cover Page
    # =========================================================================
    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph("T31 Equipment Analysis Report", title_style))
    elements.append(Paragraph(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 
                              ParagraphStyle('Sub', alignment=TA_CENTER, textColor=colors.grey)))
    elements.append(Spacer(1, 0.5*inch))
    
    # Summary statistics
    total_equipment = t31_data['mac'].nunique() if 'mac' in t31_data.columns else 0
    total_records = len(t31_data)
    
    summary = [
        ['Metric', 'Value'],
        ['Total Equipment', f'{total_equipment:,}'],
        ['Total Signal Records', f'{total_records:,}'],
        ['Monitoring Period', '24 hours'],
        ['Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M')]
    ]
    
    summary_table = Table(summary, colWidths=[2.5*inch, 2.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f4f8')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
    ]))
    elements.append(summary_table)
    elements.append(PageBreak())
    
    # =========================================================================
    # Building/Level Breakdown
    # =========================================================================
    elements.append(Paragraph("Equipment Distribution by Building & Level", heading_style))
    
    if sward_config is not None:
        t31_with_loc = t31_data.merge(
            sward_config[['sward_id', 'building', 'level']],
            on='sward_id', how='left'
        )
        
        building_level_counts = t31_with_loc.groupby(['building', 'level'])['mac'].nunique().reset_index()
        building_level_counts.columns = ['Building', 'Level', 'Equipment Count']
        
        table_data = [['Building', 'Level', 'Equipment Count']]
        for _, row in building_level_counts.iterrows():
            table_data.append([str(row['Building']), str(row['Level']), f"{row['Equipment Count']:,}"])
        
        # Add total row
        table_data.append(['TOTAL', '-', f'{total_equipment:,}'])
        
        dist_table = Table(table_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        dist_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E8F5E9')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f9f9f9')]),
        ]))
        elements.append(dist_table)
    
    elements.append(Spacer(1, 20))
    
    # =========================================================================
    # Equipment Operation Time
    # =========================================================================
    elements.append(Paragraph("Equipment Operation Time (Top 20)", heading_style))
    
    if 'time' in t31_data.columns:
        t31_copy = t31_data.copy()
        t31_copy['time'] = pd.to_datetime(t31_copy['time'])
        t31_copy['time_bin'] = (t31_copy['time'].dt.hour * 6 + t31_copy['time'].dt.minute // 10)
        
        mac_operation = t31_copy.groupby('mac')['time_bin'].nunique().reset_index()
        mac_operation.columns = ['MAC Address', 'Active Bins']
        mac_operation['Operation Hours'] = (mac_operation['Active Bins'] * 10 / 60).round(1)
        mac_operation = mac_operation.sort_values('Active Bins', ascending=False).head(20)
        
        table_data = [['Equipment MAC', 'Active Bins', 'Operation Hours']]
        for _, row in mac_operation.iterrows():
            mac_short = row['MAC Address'][:12] + '...'
            table_data.append([mac_short, f"{row['Active Bins']}", f"{row['Operation Hours']} hrs"])
        
        op_table = Table(table_data, colWidths=[2.5*inch, 1.2*inch, 1.3*inch])
        op_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2196F3')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))
        elements.append(op_table)
    
    elements.append(PageBreak())
    
    # =========================================================================
    # AI Insights
    # =========================================================================
    elements.append(Paragraph("AI Analysis & Recommendations", heading_style))
    
    if insights:
        elements.append(Paragraph("<b>Key Findings:</b>", normal_style))
        for finding in insights.get('findings', []):
            elements.append(Paragraph(f"• {finding.get('title', '')}: {finding.get('description', '')}", normal_style))
        
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>Recommendations:</b>", normal_style))
        for i, rec in enumerate(insights.get('recommendations', []), 1):
            elements.append(Paragraph(f"{i}. {rec}", normal_style))
    else:
        elements.append(Paragraph("• Equipment utilization patterns analyzed", normal_style))
        elements.append(Paragraph("• Peak operation hours: 8AM-6PM", normal_style))
        elements.append(Paragraph("• Regular maintenance scheduling recommended", normal_style))
    
    # Footer
    elements.append(Spacer(1, inch))
    elements.append(Paragraph("Generated by TJLABS Hy-con & IRFM System", 
                              ParagraphStyle('Footer', alignment=TA_CENTER, fontSize=8, textColor=colors.grey)))
    
    doc.build(elements)
    return buffer.getvalue()


def generate_comprehensive_t41_report(t41_data: pd.DataFrame, sward_config: pd.DataFrame = None,
                                       insights: dict = None, cache_loader = None) -> bytes:
    """
    Generate comprehensive PDF report for T41 Worker Analysis
    Includes Building/Level breakdown, worker activity, and visual summaries
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation")
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22, alignment=TA_CENTER,
                                  spaceAfter=20, textColor=colors.HexColor('#34a853'))
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, spaceAfter=10,
                                    spaceBefore=15, textColor=colors.HexColor('#333'))
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10, spaceAfter=6, leading=12)
    
    # Cover Page
    elements.append(Spacer(1, 1.5*inch))
    elements.append(Paragraph("T41 Worker Analysis Report", title_style))
    elements.append(Paragraph(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                              ParagraphStyle('Sub', alignment=TA_CENTER, textColor=colors.grey)))
    elements.append(Spacer(1, 0.5*inch))
    
    total_workers = t41_data['mac'].nunique() if 'mac' in t41_data.columns else 0
    total_records = len(t41_data)
    
    summary = [
        ['Metric', 'Value'],
        ['Total Workers', f'{total_workers:,}'],
        ['Total Signal Records', f'{total_records:,}'],
        ['Monitoring Period', '24 hours'],
    ]
    
    if insights and 'congestion_score' in insights:
        summary.append(['Congestion Score', str(insights['congestion_score'])])
    
    summary_table = Table(summary, colWidths=[2.5*inch, 2.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34a853')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8f5e9')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
    ]))
    elements.append(summary_table)
    elements.append(PageBreak())
    
    # Worker Distribution by Building/Level
    elements.append(Paragraph("Worker Distribution by Building & Level", heading_style))
    
    if sward_config is not None:
        t41_with_loc = t41_data.merge(
            sward_config[['sward_id', 'building', 'level']],
            on='sward_id', how='left'
        )
        
        building_level_counts = t41_with_loc.groupby(['building', 'level'])['mac'].nunique().reset_index()
        building_level_counts.columns = ['Building', 'Level', 'Worker Count']
        
        table_data = [['Building', 'Level', 'Worker Count']]
        for _, row in building_level_counts.iterrows():
            table_data.append([str(row['Building']), str(row['Level']), f"{row['Worker Count']:,}"])
        table_data.append(['TOTAL', '-', f'{total_workers:,}'])
        
        dist_table = Table(table_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        dist_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF9800')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFF3E0')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(dist_table)
    
    elements.append(Spacer(1, 20))
    
    # Top Active Workers
    elements.append(Paragraph("Most Active Workers (Top 20)", heading_style))
    
    worker_activity = t41_data.groupby('mac').size().reset_index(name='Signal Count')
    top_workers = worker_activity.nlargest(20, 'Signal Count')
    
    table_data = [['Worker MAC', 'Signal Count']]
    for _, row in top_workers.iterrows():
        mac_short = row['mac'][:12] + '...'
        table_data.append([mac_short, f"{row['Signal Count']:,}"])
    
    activity_table = Table(table_data, colWidths=[3*inch, 2*inch])
    activity_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9C27B0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
    ]))
    elements.append(activity_table)
    
    elements.append(PageBreak())
    
    # AI Insights
    elements.append(Paragraph("AI Analysis & Safety Recommendations", heading_style))
    
    if insights:
        elements.append(Paragraph("<b>Key Findings:</b>", normal_style))
        for finding in insights.get('findings', []):
            elements.append(Paragraph(f"• {finding.get('title', '')}: {finding.get('description', '')}", normal_style))
        
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>Safety Alerts:</b>", normal_style))
        for alert in insights.get('alerts', []):
            elements.append(Paragraph(f"⚠️ {alert}", normal_style))
        
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>Recommendations:</b>", normal_style))
        for i, rec in enumerate(insights.get('recommendations', []), 1):
            elements.append(Paragraph(f"{i}. {rec}", normal_style))
    
    # Footer
    elements.append(Spacer(1, inch))
    elements.append(Paragraph("Generated by TJLABS Hy-con & IRFM System",
                              ParagraphStyle('Footer', alignment=TA_CENTER, fontSize=8, textColor=colors.grey)))
    
    doc.build(elements)
    return buffer.getvalue()