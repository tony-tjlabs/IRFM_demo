import streamlit as st
import os
import shutil
import pandas as pd

DATA_OUTPUT_DIR = './output/'

# 파일 저장 함수
def save_uploaded_file(uploaded_file, save_dir):
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file, f)
    return file_path

def render_data_input():
    st.header("📂 Input Data Files")
    st.info("T-Ward(type 31, 41), Flow 데이터 파일을 업로드하세요. (최대 500MB까지 지원)")

    # 1. T-Ward type 31 데이터 파일
    tward31_file = st.file_uploader("T-Ward, type 31 data file 업로드", type=["csv"], key="input_tward31")
    tward31_path = None
    if tward31_file:
        tward31_path = save_uploaded_file(tward31_file, DATA_OUTPUT_DIR)
        st.session_state['tward31_path'] = tward31_path
        
        # Type 31 데이터를 세션 상태에 로드 (대용량 파일 지원)
        try:
            file_size_mb = tward31_file.size / (1024 * 1024)
            st.info(f"파일 크기: {file_size_mb:.1f}MB - 로딩 중...")
            
            # 대용량 파일인 경우 청크 단위로 처리
            if file_size_mb > 100:
                st.warning("⏳ 대용량 파일 처리 중입니다. 잠시만 기다려주세요...")
                chunks = []
                chunk_size = 50000  # 5만 행씩 처리
                for chunk in pd.read_csv(tward31_path, names=['sward_id', 'mac', 'type', 'rssi', 'time'], chunksize=chunk_size):
                    chunks.append(chunk)
                tward31_data = pd.concat(chunks, ignore_index=True)
            else:
                tward31_data = pd.read_csv(tward31_path, names=['sward_id', 'mac', 'type', 'rssi', 'time'])
            
            tward31_data['time'] = pd.to_datetime(tward31_data['time'])
            st.session_state['tward31_data'] = tward31_data
            st.success(f"✅ 업로드 완료: {tward31_file.name} ({len(tward31_data):,} records, {file_size_mb:.1f}MB)")
        except Exception as e:
            st.error(f"Type 31 데이터 로딩 오류: {str(e)}")

    # 2. T-Ward type 41 데이터 파일
    tward41_file = st.file_uploader("T-Ward, type 41 data file 업로드", type=["csv"], key="input_tward41")
    tward41_path = None
    if tward41_file:
        tward41_path = save_uploaded_file(tward41_file, DATA_OUTPUT_DIR)
        st.session_state['tward41_path'] = tward41_path
        
        # Type 41 데이터를 세션 상태에 로드 (대용량 파일 지원)
        try:
            file_size_mb = tward41_file.size / (1024 * 1024)
            st.info(f"파일 크기: {file_size_mb:.1f}MB - 로딩 중...")
            
            # 대용량 파일인 경우 청크 단위로 처리
            if file_size_mb > 100:
                st.warning("⏳ 대용량 파일 처리 중입니다. 잠시만 기다려주세요...")
                chunks = []
                chunk_size = 50000  # 5만 행씩 처리
                for chunk in pd.read_csv(tward41_path, names=['sward_id', 'mac', 'type', 'rssi', 'time'], chunksize=chunk_size):
                    chunks.append(chunk)
                tward41_data = pd.concat(chunks, ignore_index=True)
            else:
                tward41_data = pd.read_csv(tward41_path, names=['sward_id', 'mac', 'type', 'rssi', 'time'])
            
            tward41_data['time'] = pd.to_datetime(tward41_data['time'])
            st.session_state['tward41_data'] = tward41_data
            st.success(f"✅ 업로드 완료: {tward41_file.name} ({len(tward41_data):,} records, {file_size_mb:.1f}MB)")
        except Exception as e:
            st.error(f"Type 41 데이터 로딩 오류: {str(e)}")

    # 3. Flow 데이터 파일
    flow_file = st.file_uploader("Flow data file 업로드", type=["csv"], key="input_flow")
    flow_path = None
    if flow_file:
        flow_path = save_uploaded_file(flow_file, DATA_OUTPUT_DIR)
        st.session_state['flow_path'] = flow_path
        
        # Flow 데이터를 세션 상태에 로드 (대용량 파일 지원)
        try:
            file_size_mb = flow_file.size / (1024 * 1024)
            st.info(f"파일 크기: {file_size_mb:.1f}MB - 로딩 중...")
            
            # 대용량 파일인 경우 청크 단위로 처리
            if file_size_mb > 100:
                st.warning("⏳ 대용량 파일 처리 중입니다. 잠시만 기다려주세요...")
                chunks = []
                chunk_size = 50000  # 5만 행씩 처리
                for chunk in pd.read_csv(flow_path, names=['sward_id', 'mac', 'type', 'rssi', 'time'], chunksize=chunk_size):
                    chunks.append(chunk)
                flow_data = pd.concat(chunks, ignore_index=True)
            else:
                flow_data = pd.read_csv(flow_path, names=['sward_id', 'mac', 'type', 'rssi', 'time'])
            
            flow_data['time'] = pd.to_datetime(flow_data['time'])
            st.session_state['flow_data'] = flow_data
            st.success(f"✅ 업로드 완료: {flow_file.name} ({len(flow_data):,} records, {file_size_mb:.1f}MB)")
        except Exception as e:
            st.error(f"Flow 데이터 로딩 오류: {str(e)}")

    # 업로드된 파일 경로 요약
    st.markdown("**업로드된 파일 경로 요약**")
    if tward31_path:
        st.write(f"T-Ward 31: {tward31_path}")
    if tward41_path:
        st.write(f"T-Ward 41: {tward41_path}")
    if flow_path:
        st.write(f"Flow: {flow_path}")

def upload_tward_files():
    st.markdown("### 📂 Input Data Files")
    tward31_file = st.file_uploader("T-Ward type 31 data file", type=["csv"], key="tward31_file")
    tward41_file = st.file_uploader("T-Ward type 41 data file", type=["csv"], key="tward41_file")
    flow_file = st.file_uploader("Flow data file", type=["csv"], key="flow_file")
    return tward31_file, tward41_file, flow_file

def read_uploaded_csv(uploaded_file):
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file, header=None)
    return None
