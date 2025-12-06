"""
T-Ward Type 41 Location Analysis Module
실시간 위치 추적 및 시각화 동영상 생성
"""

import streamlit as st
import pandas as pd
import numpy as np
import cv2
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation
import io
import base64
import tempfile
import os
from datetime import datetime, timedelta
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go


class LocationAnalyzer:
    def __init__(self):
        self.alpha = 0.5  # Smoothing factor
        self.location_history = {}  # Track previous locations for smoothing
        
    def load_sward_configuration(self, config_path):
        """Load S-Ward configuration with coordinates"""
        try:
            sward_config = pd.read_csv(config_path)
            # Expected columns: sward_id, building, level, x, y
            return sward_config
        except Exception as e:
            st.error(f"S-Ward configuration load error: {e}")
            return None
            
    def detect_building_level(self, rssi_data):
        """
        Detect building and level based on RSSI values
        
        Building Detection: Highest RSSI S-Ward's building
        Level Detection: Most S-Wards in same level, or highest RSSI if tie
        """
        if rssi_data.empty:
            return None, None
            
        # Building detection - highest RSSI
        max_rssi_idx = rssi_data['rssi'].idxmax()
        building = rssi_data.loc[max_rssi_idx, 'building']
        
        # Level detection - most S-Wards in same level
        level_counts = rssi_data.groupby('level').agg({
            'sward_id': 'count',
            'rssi': 'max'
        }).reset_index()
        level_counts.columns = ['level', 'sward_count', 'max_rssi']
        
        # Sort by count first, then by max RSSI
        level_counts = level_counts.sort_values(['sward_count', 'max_rssi'], ascending=[False, False])
        level = level_counts.iloc[0]['level']
        
        return building, level
        
    def calculate_position_single_sward(self, sward_pos, rssi):
        """Calculate position when received by single S-Ward"""
        # RSSI to distance mapping (simplified)
        if rssi >= -60:
            radius = 10  # pixels
        elif rssi <= -80:
            radius = 20  # pixels
        else:
            # Linear interpolation between -60 and -80
            radius = 10 + ((-60 - rssi) / (-60 - (-80))) * (20 - 10)
            
        # Random position around S-Ward
        angle = np.random.uniform(0, 2 * np.pi)
        distance = np.random.uniform(0, radius)
        
        x = sward_pos['x'] + distance * np.cos(angle)
        y = sward_pos['y'] + distance * np.sin(angle)
        
        return x, y
        
    def calculate_position_two_swards(self, sward1_pos, sward2_pos, rssi1, rssi2):
        """Calculate position using two S-Wards (internal division)"""
        # Convert RSSI to weights (higher RSSI = closer = higher weight)
        weight1 = 100 + rssi1  # Convert to positive values
        weight2 = 100 + rssi2
        
        # Normalize weights
        total_weight = weight1 + weight2
        w1 = weight2 / total_weight  # Inverse relationship
        w2 = weight1 / total_weight
        
        # Internal division point
        x = w1 * sward1_pos['x'] + w2 * sward2_pos['x']
        y = w1 * sward1_pos['y'] + w2 * sward2_pos['y']
        
        # Add small random offset (10 pixel radius)
        angle = np.random.uniform(0, 2 * np.pi)
        distance = np.random.uniform(0, 10)
        
        x += distance * np.cos(angle)
        y += distance * np.sin(angle)
        
        return x, y
        
    def calculate_position_triangulation(self, sward_positions, rssi_values):
        """Calculate position using top 3 S-Wards (triangulation)"""
        # Sort by RSSI (highest first) and take top 3
        combined = list(zip(sward_positions, rssi_values))
        combined.sort(key=lambda x: x[1], reverse=True)
        top3 = combined[:3]
        
        # Extract positions and RSSI values
        positions = [item[0] for item in top3]
        rssi_vals = [item[1] for item in top3]
        
        # Convert RSSI to weights
        weights = [100 + rssi for rssi in rssi_vals]
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # Weighted average position
        x = sum(w * pos['x'] for w, pos in zip(normalized_weights, positions))
        y = sum(w * pos['y'] for w, pos in zip(normalized_weights, positions))
        
        return x, y
        
    def apply_smoothing(self, tward_mac, new_x, new_y):
        """Apply smoothing using previous position"""
        if tward_mac not in self.location_history:
            self.location_history[tward_mac] = (new_x, new_y)
            return new_x, new_y
            
        prev_x, prev_y = self.location_history[tward_mac]
        
        # Smoothing formula: current = prev * alpha + new * (1-alpha)
        smoothed_x = prev_x * self.alpha + new_x * (1 - self.alpha)
        smoothed_y = prev_y * self.alpha + new_y * (1 - self.alpha)
        
        self.location_history[tward_mac] = (smoothed_x, smoothed_y)
        return smoothed_x, smoothed_y
        
    def process_location_data(self, raw_data, sward_config):
        """Process raw T-Ward data to extract locations"""
        if raw_data.empty or sward_config is None:
            return pd.DataFrame()
            
        # Note: raw_data already has time_index from Operation module processing
        
        # Merge with S-Ward configuration to get coordinates
        data_with_coords = raw_data.merge(
            sward_config, 
            left_on='sward_id', 
            right_on='sward_id', 
            how='left'
        )
        
        location_results = []
        
        # Group by T-Ward MAC and time_index  
        for (tward_mac, time_idx), group in data_with_coords.groupby(['mac', 'time_index']):
            if group.empty:
                continue
                
            # Detect building and level
            building, level = self.detect_building_level(group)
            
            if building is None or level is None:
                continue
                
            # Filter data for detected level only
            level_data = group[group['level'] == level].copy()
            
            if level_data.empty:
                continue
                
            # Calculate position based on number of receiving S-Wards
            sward_count = len(level_data)
            
            if sward_count == 1:
                # Single S-Ward
                sward_pos = level_data.iloc[0]
                rssi = level_data.iloc[0]['rssi']
                x, y = self.calculate_position_single_sward(sward_pos, rssi)
                
            elif sward_count == 2:
                # Two S-Wards
                sward1_pos = level_data.iloc[0]
                sward2_pos = level_data.iloc[1]
                rssi1 = level_data.iloc[0]['rssi']
                rssi2 = level_data.iloc[1]['rssi']
                x, y = self.calculate_position_two_swards(sward1_pos, sward2_pos, rssi1, rssi2)
                
            else:
                # Three or more S-Wards (triangulation)
                sward_positions = level_data[['x', 'y']].to_dict('records')
                rssi_values = level_data['rssi'].tolist()
                x, y = self.calculate_position_triangulation(sward_positions, rssi_values)
            
            # Apply smoothing
            smoothed_x, smoothed_y = self.apply_smoothing(tward_mac, x, y)
            
            # Store result
            location_results.append({
                'tward_mac': tward_mac,
                'time_index': time_idx,
                'timestamp': group.iloc[0]['time'],  # Use 'time' column from operation module
                'building': building,
                'level': level,
                'x_position': smoothed_x,
                'y_position': smoothed_y,
                'sward_count': sward_count,
                'max_rssi': group['rssi'].max()
            })
            
        return pd.DataFrame(location_results)


def create_location_animation(location_data, map_image_path, building, level):
    """Create animation video showing T-Ward movements on map"""
    try:
        # Load map image
        map_img = cv2.imread(map_image_path)
        if map_img is None:
            st.error(f"Cannot load map image: {map_image_path}")
            return None
            
        height, width = map_img.shape[:2]
        
        # Filter data for specific building and level
        filtered_data = location_data[
            (location_data['building'] == building) & 
            (location_data['level'] == level)
        ].copy()
        
        if filtered_data.empty:
            st.warning(f"No location data for {building} - {level}")
            return None
            
        # Sort by time_index
        filtered_data = filtered_data.sort_values('time_index')
        
        # Get unique time indices
        time_indices = sorted(filtered_data['time_index'].unique())
        
        # Create temporary video file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            video_path = tmp_file.name
            
        # Video settings
        fps = 10  # 10 frames per second (1 frame per second of real time)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
        
        for time_idx in time_indices:
            # Create frame
            frame = map_img.copy()
            
            # Get T-Ward positions at this time
            current_positions = filtered_data[filtered_data['time_index'] == time_idx]
            
            # Draw T-Ward positions as red circles
            for _, row in current_positions.iterrows():
                x, y = int(row['x_position']), int(row['y_position'])
                
                # Ensure coordinates are within image bounds
                if 0 <= x < width and 0 <= y < height:
                    cv2.circle(frame, (x, y), 8, (0, 0, 255), -1)  # Red filled circle
                    cv2.circle(frame, (x, y), 12, (255, 255, 255), 2)  # White border
            
            # Add timestamp text
            timestamp = filtered_data[filtered_data['time_index'] == time_idx].iloc[0]['timestamp']
            time_text = timestamp.strftime('%H:%M:%S')
            cv2.putText(frame, time_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
            
            # Add T-Ward count
            tward_count = len(current_positions)
            count_text = f'T-Ward Count: {tward_count}'
            cv2.putText(frame, count_text, (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            video_writer.write(frame)
            
        video_writer.release()
        
        # Read video file as bytes
        with open(video_path, 'rb') as f:
            video_bytes = f.read()
            
        # Clean up temporary file
        os.unlink(video_path)
        
        return video_bytes
        
    except Exception as e:
        st.error(f"Animation creation error: {e}")
        return None


def load_tward41_data():
    """Load T-Ward Type 41 data from session state (same pattern as other analysis modules)"""
    try:
        # 세션 상태에서 T-Ward Type 41 데이터 확인
        if 'tward41_data' in st.session_state and st.session_state['tward41_data'] is not None:
            data = st.session_state['tward41_data'].copy()
            
            # 기본 컬럼 확인
            required_columns = ['sward_id', 'mac', 'type', 'rssi', 'time']
            if not all(col in data.columns for col in required_columns):
                st.error(f"T-Ward Type 41 data missing required columns: {required_columns}")
                return None
            
            # Type 41 데이터만 필터링
            data = data[data['type'] == 41].copy()
            
            if data.empty:
                st.warning("No Type 41 data found in the uploaded file.")
                return None
            
            # 시간 컬럼 처리
            if not pd.api.types.is_datetime64_any_dtype(data['time']):
                data['time'] = pd.to_datetime(data['time'])
            
            # time_index 생성 (10초 단위)
            data['time_index'] = ((data['time'] - data['time'].dt.normalize()) / pd.Timedelta(seconds=10)).astype(int) + 1
            
            return data
        else:
            st.warning("No T-Ward Type 41 data found. Please upload data in 'Input data files' tab.")
            return None
            
    except Exception as e:
        st.error(f"Error loading T-Ward Type 41 data: {str(e)}")
        return None


def load_sward_configuration():
    """Load S-Ward configuration using building_setup module (same as other analysis modules)"""
    try:
        from src.building_setup import load_sward_config
        config = load_sward_config()
        
        if config.empty:
            st.warning("No S-Ward configuration found. Please set up S-Ward configuration in 'Building/Level Setup' tab.")
            return None
            
        return config
    except Exception as e:
        st.error(f"Error loading S-Ward configuration: {str(e)}")
        return None


def display_location_analysis():
    """Main Location Analysis interface"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 2rem; margin: 2rem 0; border-radius: 15px; 
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
        <h1 style="color: white; margin: 0; text-align: center;">
            🎯 T-Ward Type 41 Location Analysis
        </h1>
        <p style="color: white; text-align: center; margin-top: 1rem; font-size: 1.1rem;">
            Real-time Position Tracking & Video Visualization
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Load data from session state
    try:
        location_data = load_tward41_data()
        sward_config = load_sward_configuration()
        
        if location_data is None or sward_config is None:
            st.error("Required data not available. Please upload data in 'Input data files' tab.")
            return
            
        # Apply filtering if enabled (same as other analysis modules)
        filter_enabled = st.session_state.get('tward41_filter_enabled', False)
        min_dwell_time = st.session_state.get('tward41_min_dwell_time', 0)
        
        if filter_enabled and min_dwell_time > 0:
            # Apply dwell time filtering (same logic as other modules)
            from src.tward_type41_operation import apply_dwell_time_filter
            original_count = len(location_data)
            location_data = apply_dwell_time_filter(location_data, min_dwell_time)
            filtered_count = len(location_data)
            
            st.info(f"🔍 Filtering applied: {original_count:,} → {filtered_count:,} records (≥{min_dwell_time}min)")
            st.session_state['tward41_filtering_applied'] = True
        else:
            st.success(f"✅ Loaded {len(location_data):,} T-Ward Type 41 data records (No filtering)")
        
        # Display data info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("T-Ward Type 41 Records", f"{len(location_data):,}")
        with col2:
            st.metric("Unique T-Wards", f"{location_data['mac'].nunique():,}")
        with col3:
            st.metric("S-Ward Configuration", f"{len(sward_config):,}")
                
    except Exception as e:
        st.error(f"Data loading error: {e}")
        return
    
    # Analysis section
    st.subheader("📊 Location Processing")
    
    # Run analysis automatically when data is available
    with st.spinner("Processing location data..."):
        
        # Initialize location analyzer
        analyzer = LocationAnalyzer()
        
        # Process locations using filtered data
        location_results = analyzer.process_location_data(location_data, sward_config)
        
        if location_results.empty:
            st.error("No location data could be processed")
            return
            
        st.success(f"✅ Location processing complete! {len(location_results):,} positions calculated")
    
    # Display results summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Positions", f"{len(location_results):,}")
    with col2:
        st.metric("Buildings", f"{location_results['building'].nunique()}")
    with col3:
        st.metric("Levels", f"{location_results['level'].nunique()}")
    with col4:
        st.metric("Time Span", f"{location_results['time_index'].nunique():,} intervals")
    
    # Show sample data
    st.subheader("📋 Location Data Sample")
    st.dataframe(location_results.head(10), use_container_width=True)
    
    # Map visualization options
    st.subheader("🎬 Video Generation")
    
    available_combinations = location_results.groupby(['building', 'level']).size().reset_index()
    available_combinations.columns = ['building', 'level', 'count']
    
    col1, col2 = st.columns(2)
    with col1:
        selected_building = st.selectbox(
            "Select Building",
            options=available_combinations['building'].unique()
        )
    
    with col2:
        building_levels = available_combinations[
            available_combinations['building'] == selected_building
        ]['level'].unique()
        selected_level = st.selectbox(
            "Select Level",
            options=building_levels
        )
    
    # Auto-load map from Setup configuration
    try:
        from .building_setup import load_sward_config
    except ImportError:
        from building_setup import load_sward_config
        
    sward_config = load_sward_config()
    map_path = None
    
    if sward_config is not None and not sward_config.empty:
        # Find map for selected building and level
        building_level_data = sward_config[
            (sward_config['building'] == selected_building) & 
            (sward_config['level'] == selected_level)
        ]
        
        if not building_level_data.empty:
            map_filename = building_level_data['map_image'].iloc[0]
            if pd.notna(map_filename):
                map_path = os.path.join('./Datafile/Map_Image/', map_filename)
                if os.path.exists(map_path):
                    st.info(f"✅ Using map from Setup: {map_filename}")
                else:
                    st.error(f"❌ Map file not found: {map_filename}")
                    map_path = None
            else:
                st.warning("⚠️ No map configured for this building/level. Please set up in Setup tab.")
        else:
            st.warning("⚠️ No configuration found for this building/level. Please set up in Setup tab.")
    else:
        st.warning("⚠️ No S-Ward configuration found. Please complete Setup first.")
    
    if map_path and os.path.exists(map_path):
        with st.spinner("Generating location animation video..."):
            
            try:
                # Generate video using setup map
                video_bytes = create_location_animation(
                    location_results, 
                    map_path, 
                    selected_building, 
                    selected_level
                )
                
                if video_bytes:
                    st.success("✅ Location video generated successfully!")
                    
                    # Video preview (if possible)
                    st.video(video_bytes)
                    
                    # Download button
                    st.download_button(
                        label="📥 Download Location Video",
                        data=video_bytes,
                        file_name=f"tward_location_{selected_building}_{selected_level}.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )
                    
                else:
                    st.error("Video generation failed")
                    
            except Exception as e:
                st.error(f"Error generating location video: {str(e)}")


if __name__ == "__main__":
    display_location_analysis()