"""
Unified Color System for SKEP DataAnalysis
All Building-Level colors are consistent across all heatmaps
"""

# ============================================================================
# Building-Level Color Definitions (Unified across all heatmaps)
# ============================================================================

# Color values for heatmap (integer indices)
BUILDING_LEVEL_COLORS = {
    # Signal status
    'no_signal': 0,         # Black: No signal received
    'present_inactive': 1,  # Gray: Signal received but inactive (1-2 times/min)
    
    # Building-Level active colors
    'WWT-1F': 2,            # Green
    'WWT-B1F': 3,           # Yellow
    'WWT-2F': 2,            # Green (same as WWT-1F)
    'FAB-1F': 4,            # Orange
    'FAB-B1F': 4,           # Orange (same as FAB-1F)
    'FAB-2F': 4,            # Orange (same as FAB-1F)
    'CUB-1F': 5,            # Sky blue
    'CUB-B1F': 6,           # Blue
    'CUB-2F': 5,            # Sky blue (same as CUB-1F)
    'Cluster-1F': 7,        # Purple
    'Cluster-B1F': 7,       # Purple (same as Cluster-1F)
    'Cluster-2F': 7,        # Purple (same as Cluster-1F)
}

# Cluster-1F detailed space types
CLUSTER_SPACE_COLORS = {
    'Cluster-1F-Rest Area 1': 7,     # Purple (Rest Area)
    'Cluster-1F-Rest Area 2': 7,     # Purple
    'Cluster-1F-Rest Area 3': 7,     # Purple
    'Cluster-1F-Smoking Area': 8,    # Light Purple
    'Cluster-1F-Restroom': 9,        # Pale Purple
    'Cluster-1F-Center Stair': 10,   # Pink
    'Cluster-1F-Left Stair': 10,     # Pink
    'Cluster-1F-Storage Rack': 11,   # Light Gray
    'Cluster-1F-Entrance': 12,       # Magenta
    'Cluster-1F-Exit': 12,           # Magenta
}

# Actual color codes (hex)
COLOR_HEX_MAP = [
    '#000000',  # 0: Black (no signal)
    '#808080',  # 1: Gray (inactive)
    '#00FF00',  # 2: Green (WWT-1F, WWT-2F)
    '#FFFF00',  # 3: Yellow (WWT-B1F)
    '#FFA500',  # 4: Orange (FAB-1F, FAB-B1F, FAB-2F)
    '#87CEEB',  # 5: Sky blue (CUB-1F, CUB-2F)
    '#0000FF',  # 6: Blue (CUB-B1F)
    '#8A2BE2',  # 7: Purple (Cluster Rest Area)
    '#9370DB',  # 8: Medium Purple (Cluster Smoking Area)
    '#DDA0DD',  # 9: Plum (Cluster Restroom)
    '#FFB6C1',  # 10: Light Pink (Cluster Stairs)
    '#D3D3D3',  # 11: Light Gray (Cluster Storage)
    '#FF1493',  # 12: Deep Pink (Cluster Entrance/Exit)
]

# Building color mapping (for charts)
BUILDING_COLORS = {
    'WWT': '#00FF00',      # Green
    'FAB': '#FFA500',      # Orange
    'CUB': '#0000FF',      # Blue
    'Cluster': '#8A2BE2',  # Purple
}

# Building-Level hex color mapping (for line charts)
BUILDING_LEVEL_HEX_COLORS = {
    'WWT-1F': '#00FF00',    # Green
    'WWT-2F': '#00FF00',    # Green
    'WWT-B1F': '#FFFF00',   # Yellow
    'FAB-1F': '#FFA500',    # Orange
    'FAB-2F': '#FFA500',    # Orange
    'FAB-B1F': '#FFA500',   # Orange
    'CUB-1F': '#87CEEB',    # Sky blue
    'CUB-2F': '#87CEEB',    # Sky blue
    'CUB-B1F': '#0000FF',   # Blue
    'Cluster-1F': '#8A2BE2',  # Purple
    'Cluster-2F': '#8A2BE2',  # Purple
    'Cluster-B1F': '#8A2BE2', # Purple
}

# English labels for legend
COLOR_LABELS = {
    0: 'No Signal',
    1: 'Inactive (Present)',
    2: 'WWT-1F (Active)',
    3: 'WWT-B1F (Active)',
    4: 'FAB (Active)',
    5: 'CUB-1F (Active)',
    6: 'CUB-B1F (Active)',
    7: 'Cluster Rest Area',
    8: 'Cluster Smoking',
    9: 'Cluster Restroom',
    10: 'Cluster Stairs',
    11: 'Cluster Storage',
    12: 'Cluster Entrance/Exit',
}

# Building-level to color mapping (for quick lookup)
def get_color_value(building: str, level: str = None, space_type: str = None) -> int:
    """Get color value for a building-level combination
    
    Args:
        building: Building name (e.g., 'WWT', 'FAB', 'CUB', 'Cluster')
        level: Floor level (e.g., '1F', 'B1F', '2F')
        space_type: Space type for Cluster (e.g., 'Rest Area 1', 'Smoking Area')
    
    Returns:
        Integer color value for heatmap
    """
    if building is None or pd.isna(building):
        return BUILDING_LEVEL_COLORS['no_signal']
    
    # Build key
    if level:
        bl_key = f"{building}-{level}"
        
        # Check for Cluster space type
        if building == 'Cluster' and level == '1F' and space_type:
            space_key = f"{bl_key}-{space_type}"
            if space_key in CLUSTER_SPACE_COLORS:
                return CLUSTER_SPACE_COLORS[space_key]
        
        if bl_key in BUILDING_LEVEL_COLORS:
            return BUILDING_LEVEL_COLORS[bl_key]
    
    # Fallback: building only
    for key, value in BUILDING_LEVEL_COLORS.items():
        if key.startswith(f"{building}-"):
            return value
    
    return BUILDING_LEVEL_COLORS['present_inactive']


# ============================================================================
# Legend Generation
# ============================================================================

def get_legend_items():
    """Get legend items for display
    
    Returns:
        List of tuples: (color_hex, label)
    """
    legend = []
    for idx, hex_color in enumerate(COLOR_HEX_MAP):
        if idx in COLOR_LABELS:
            legend.append((hex_color, COLOR_LABELS[idx]))
    return legend


def create_legend_html():
    """Create HTML legend for Streamlit display"""
    html = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0;">'
    
    for hex_color, label in get_legend_items():
        html += f'''
        <div style="display: flex; align-items: center; margin-right: 15px;">
            <div style="width: 20px; height: 20px; background-color: {hex_color}; 
                        border: 1px solid #333; margin-right: 5px;"></div>
            <span style="font-size: 12px;">{label}</span>
        </div>
        '''
    
    html += '</div>'
    return html


# Import pandas for isna check
import pandas as pd
