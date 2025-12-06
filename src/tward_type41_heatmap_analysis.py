"""
T-Ward Type 41 Heatmap Analysis Module
위치 데이터 기반 히트맵 생성 및 동영상 시각화
"""

import streamlit as st
import pandas as pd
import numpy as np
import cv2
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation
import seaborn as sns
from scipy.ndimage import gaussian_filter
import io
import base64
import tempfile
import os
from datetime import datetime, timedelta
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
try:
    from .tward_type41_location_analysis import LocationAnalyzer
except ImportError:
    from tward_type41_location_analysis import LocationAnalyzer


class HeatmapAnalyzer:
    def __init__(self, grid_size=50, smoothing_sigma=2.0):
        self.grid_size = grid_size  # Grid resolution for heatmap
        self.smoothing_sigma = smoothing_sigma  # Gaussian smoothing parameter
        
    def create_spatial_grid(self, location_data, map_width, map_height):
        """Create spatial grid for heatmap accumulation"""
        # Define grid boundaries
        x_min, x_max = 0, map_width
        y_min, y_max = 0, map_height
        
        # Create grid coordinates
        x_edges = np.linspace(x_min, x_max, self.grid_size + 1)
        y_edges = np.linspace(y_min, y_max, self.grid_size + 1)
        
        return x_edges, y_edges
        
    def accumulate_heatmap_data(self, location_data, x_edges, y_edges, time_window=None):
        """Accumulate position data into heatmap grid"""
        if time_window:
            start_time, end_time = time_window
            filtered_data = location_data[
                (location_data['time_index'] >= start_time) & 
                (location_data['time_index'] <= end_time)
            ]
        else:
            filtered_data = location_data
            
        if filtered_data.empty:
            return np.zeros((len(y_edges)-1, len(x_edges)-1))
            
        # Create 2D histogram (heatmap)
        heatmap, _, _ = np.histogram2d(
            filtered_data['y_position'], 
            filtered_data['x_position'],
            bins=[y_edges, x_edges]
        )
        
        # Apply Gaussian smoothing for better visualization
        if self.smoothing_sigma > 0:
            heatmap = gaussian_filter(heatmap, sigma=self.smoothing_sigma)
            
        return heatmap
        
    def create_cumulative_heatmap(self, location_data, map_image_path, building, level, time_window_minutes=60):
        """Create cumulative heatmap showing movement patterns over time"""
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
            
            # Create spatial grid
            x_edges, y_edges = self.create_spatial_grid(filtered_data, width, height)
            
            # Calculate time windows (in 10-second intervals)
            time_indices = filtered_data['time_index'].unique()
            window_size = time_window_minutes * 6  # 60 minutes * 6 (10-second intervals per minute)
            
            # Create heatmap frames
            heatmap_frames = []
            time_labels = []
            
            for i in range(0, len(time_indices), window_size // 4):  # Overlap windows
                start_idx = time_indices[i]
                end_idx = min(start_idx + window_size, time_indices[-1])
                
                # Accumulate heatmap for this time window
                heatmap = self.accumulate_heatmap_data(
                    filtered_data, x_edges, y_edges, (start_idx, end_idx)
                )
                
                heatmap_frames.append(heatmap)
                
                # Get timestamp for this window
                window_data = filtered_data[
                    (filtered_data['time_index'] >= start_idx) & 
                    (filtered_data['time_index'] <= end_idx)
                ]
                if not window_data.empty:
                    timestamp = window_data.iloc[0]['timestamp']
                    time_labels.append(timestamp.strftime('%H:%M:%S'))
                else:
                    time_labels.append(f"Time {i}")
            
            return heatmap_frames, time_labels, (x_edges, y_edges), map_img
            
        except Exception as e:
            st.error(f"Cumulative heatmap creation error: {e}")
            return None
            
    def create_real_time_heatmap(self, location_data, map_image_path, building, level, accumulation_minutes=10):
        """Create real-time heatmap showing recent activity"""
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
            
            # Create spatial grid
            x_edges, y_edges = self.create_spatial_grid(filtered_data, width, height)
            
            # Calculate accumulation window (in 10-second intervals)
            time_indices = filtered_data['time_index'].unique()
            accumulation_window = accumulation_minutes * 6  # minutes * 6 intervals per minute
            
            # Create real-time heatmap frames
            heatmap_frames = []
            time_labels = []
            
            for current_time in time_indices[::6]:  # Every minute (6 intervals)
                # Define accumulation window (recent activity)
                start_time = max(current_time - accumulation_window, time_indices[0])
                end_time = current_time
                
                # Accumulate heatmap for recent activity
                heatmap = self.accumulate_heatmap_data(
                    filtered_data, x_edges, y_edges, (start_time, end_time)
                )
                
                heatmap_frames.append(heatmap)
                
                # Get timestamp
                current_data = filtered_data[filtered_data['time_index'] == current_time]
                if not current_data.empty:
                    timestamp = current_data.iloc[0]['timestamp']
                    time_labels.append(timestamp.strftime('%H:%M:%S'))
                else:
                    time_labels.append(f"Time {current_time}")
            
            return heatmap_frames, time_labels, (x_edges, y_edges), map_img
            
        except Exception as e:
            st.error(f"Real-time heatmap creation error: {e}")
            return None


def create_heatmap_video(heatmap_frames, time_labels, grid_coords, map_img, video_type="cumulative"):
    """Create heatmap animation video"""
    try:
        x_edges, y_edges = grid_coords
        height, width = map_img.shape[:2]
        
        # Create temporary video file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            video_path = tmp_file.name
            
        # Video settings
        fps = 2  # 2 frames per second for heatmap animation
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
        
        # Find global max for consistent color scale
        global_max = max([np.max(heatmap) for heatmap in heatmap_frames if heatmap.size > 0])
        if global_max == 0:
            global_max = 1
            
        for i, (heatmap, time_label) in enumerate(zip(heatmap_frames, time_labels)):
            # Create frame
            frame = map_img.copy()
            
            if heatmap.size > 0 and np.max(heatmap) > 0:
                # Normalize heatmap
                normalized_heatmap = heatmap / global_max
                
                # Create color overlay
                # Use colormap: blue (low) -> green -> yellow -> red (high)
                colored_heatmap = plt.cm.jet(normalized_heatmap)
                colored_heatmap = (colored_heatmap[:, :, :3] * 255).astype(np.uint8)
                
                # Resize to match image dimensions
                resized_heatmap = cv2.resize(colored_heatmap, (width, height))
                
                # Apply transparency for overlay
                alpha = 0.6
                overlay = cv2.addWeighted(frame, 1-alpha, resized_heatmap, alpha, 0)
                frame = overlay
            
            # Add title and timestamp
            title_text = f"{video_type.title()} Heatmap"
            cv2.putText(frame, title_text, (50, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            cv2.putText(frame, title_text, (50, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
            
            cv2.putText(frame, time_label, (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)
            cv2.putText(frame, time_label, (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Add frame counter
            frame_text = f"Frame: {i+1}/{len(heatmap_frames)}"
            cv2.putText(frame, frame_text, (width-200, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            video_writer.write(frame)
            
        video_writer.release()
        
        # Read video file as bytes
        with open(video_path, 'rb') as f:
            video_bytes = f.read()
            
        # Clean up temporary file
        os.unlink(video_path)
        
        return video_bytes
        
    except Exception as e:
        st.error(f"Heatmap video creation error: {e}")
        return None


def create_static_heatmap_visualization(location_data, building, level):
    """Create static heatmap visualization using Plotly"""
    try:
        # Filter data
        filtered_data = location_data[
            (location_data['building'] == building) & 
            (location_data['level'] == level)
        ].copy()
        
        if filtered_data.empty:
            return None
            
        # Create 2D density plot
        fig = go.Figure()
        
        # Add heatmap
        fig.add_trace(go.Histogram2d(
            x=filtered_data['x_position'],
            y=filtered_data['y_position'],
            nbinsx=50,
            nbinsy=50,
            colorscale='Hot',
            showscale=True,
            colorbar=dict(title="Activity Density")
        ))
        
        # Add scatter points for individual positions
        fig.add_trace(go.Scatter(
            x=filtered_data['x_position'],
            y=filtered_data['y_position'],
            mode='markers',
            marker=dict(
                size=3,
                color='white',
                opacity=0.3
            ),
            name='T-Ward Positions',
            showlegend=False
        ))
        
        fig.update_layout(
            title=f"T-Ward Activity Heatmap - {building} {level}",
            xaxis_title="X Position (pixels)",
            yaxis_title="Y Position (pixels)",
            width=800,
            height=600
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Static heatmap creation error: {e}")
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


def display_heatmap_analysis():
    """Main Heatmap Analysis interface"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #FF6B6B 0%, #4ECDC4 100%); 
                padding: 2rem; margin: 2rem 0; border-radius: 15px; 
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);">
        <h1 style="color: white; margin: 0; text-align: center;">
            🔥 T-Ward Type 41 Heatmap Analysis
        </h1>
        <p style="color: white; text-align: center; margin-top: 1rem; font-size: 1.1rem;">
            Movement Pattern & Congestion Analysis
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Load data from session state
    location_data = None
    
    try:
        # Load data from session state (same pattern as other analysis modules)
        raw_data = load_tward41_data()
        sward_config = load_sward_configuration()
        
        if raw_data is None or sward_config is None:
            st.error("Required data not available. Please upload data in 'Input data files' tab.")
            return
        
        # Apply filtering if enabled
        filter_enabled = st.session_state.get('tward41_filter_enabled', False)
        min_dwell_time = st.session_state.get('tward41_min_dwell_time', 0)
        
        if filter_enabled and min_dwell_time > 0:
            from src.tward_type41_operation import apply_dwell_time_filter
            original_count = len(raw_data)
            raw_data = apply_dwell_time_filter(raw_data, min_dwell_time)
            filtered_count = len(raw_data)
            
            st.info(f"🔍 Filtering applied: {original_count:,} → {filtered_count:,} records (≥{min_dwell_time}min)")
        else:
            st.success(f"✅ Loaded {len(raw_data):,} T-Ward Type 41 data records (No filtering)")
        
        # Check if location data is already processed in session
        if 'tward41_location_results' in st.session_state:
            location_data = st.session_state['tward41_location_results']
            st.success("✅ Using previously processed location data!")
        else:
            st.info("📍 Processing location data for heatmap analysis...")
            
            with st.spinner("Processing location data for heatmap..."):
                analyzer = LocationAnalyzer()
                location_data = analyzer.process_location_data(raw_data, sward_config)
                
                if not location_data.empty:
                    # Save for reuse
                    st.session_state['tward41_location_results'] = location_data
                    st.success("✅ Location data processed successfully!")
                else:
                    st.error("Location data processing failed")
                    return
            
        if location_data is not None and not location_data.empty:
            # Display location data info
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Location Records", f"{len(location_data):,}")
            with col2:
                st.metric("Unique T-Wards", f"{location_data['tward_mac'].nunique():,}")
            with col3:
                st.metric("Time Span", f"{location_data['time_index'].nunique():,} intervals")
                        
    except Exception as e:
        st.error(f"Data processing error: {e}")
        return
    
    # Heatmap analysis
    if location_data is not None and not location_data.empty:
        st.subheader("🔥 Heatmap Generation")
        
        # Analysis options
        col1, col2 = st.columns(2)
        
        with col1:
            # Building/Level selection
            available_combinations = location_data.groupby(['building', 'level']).size().reset_index()
            available_combinations.columns = ['building', 'level', 'count']
            
            selected_building = st.selectbox(
                "Select Building",
                options=available_combinations['building'].unique(),
                key="heatmap_building_select"
            )
            
            building_levels = available_combinations[
                available_combinations['building'] == selected_building
            ]['level'].unique()
            selected_level = st.selectbox(
                "Select Level", 
                options=building_levels,
                key="heatmap_level_select"
            )
        
        with col2:
            # Heatmap parameters
            st.markdown("**Heatmap Parameters:**")
            grid_size = st.slider("Grid Resolution", 20, 100, 50, key="heatmap_grid_size")
            smoothing_sigma = st.slider("Smoothing Factor", 0.5, 5.0, 2.0, key="heatmap_smoothing")
        
        # Static heatmap visualization
        st.subheader("📊 Static Heatmap Visualization")
        
        with st.spinner("Creating static heatmap..."):
            fig = create_static_heatmap_visualization(location_data, selected_building, selected_level)
            
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Static heatmap generation failed")
        
        # Video heatmap generation
        st.subheader("🎬 Heatmap Video Generation")
        
        # Video type selection
        video_type = st.radio(
            "Select Heatmap Type",
            ["Cumulative Heatmap", "Real-time Heatmap"],
            key="heatmap_video_type",
            help="Cumulative: Shows total activity accumulation over time. Real-time: Shows recent activity in sliding window."
        )
        
        # Additional parameters
        col1, col2 = st.columns(2)
        with col1:
            if video_type == "Cumulative Heatmap":
                time_window = st.slider("Time Window (minutes)", 30, 240, 60, key="heatmap_time_window")
            else:
                accumulation_window = st.slider("Activity Window (minutes)", 5, 30, 10, key="heatmap_activity_window")
        
        with col2:
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
            with st.spinner(f"Generating {video_type.lower()} video..."):
                
                try:
                    # Initialize heatmap analyzer
                    heatmap_analyzer = HeatmapAnalyzer(grid_size=grid_size, smoothing_sigma=smoothing_sigma)
                    
                    # Generate heatmap frames
                    if video_type == "Cumulative Heatmap":
                        result = heatmap_analyzer.create_cumulative_heatmap(
                            location_data, map_path, selected_building, selected_level, time_window
                        )
                    else:
                        result = heatmap_analyzer.create_real_time_heatmap(
                            location_data, map_path, selected_building, selected_level, accumulation_window
                        )
                    
                    if result:
                        heatmap_frames, time_labels, grid_coords, map_img = result
                        
                        # Create video
                        video_bytes = create_heatmap_video(
                            heatmap_frames, time_labels, grid_coords, map_img, 
                            video_type.split()[0].lower()
                        )
                        
                        if video_bytes:
                            st.success("✅ Heatmap video generated successfully!")
                            
                            # Video preview
                            st.video(video_bytes)
                            
                            # Download button
                            filename = f"tward_heatmap_{video_type.replace(' ', '_').lower()}_{selected_building}_{selected_level}.mp4"
                            st.download_button(
                                label="📥 Download Heatmap Video",
                                data=video_bytes,
                                file_name=filename,
                                mime="video/mp4",
                                use_container_width=True
                            )
                        else:
                            st.error("Heatmap video generation failed")
                    else:
                        st.error("Heatmap data generation failed")
                        
                except Exception as e:
                    st.error(f"Heatmap video generation error: {e}")


if __name__ == "__main__":
    display_heatmap_analysis()