
import streamlit as st
import pandas as pd
import os
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go

CONFIG_PATH = './Datafile/sward_configuration.csv'
MAP_IMAGE_DIR = './Datafile/Map_Image/'

SWARD_COLUMNS = ["building", "level", "sward_id", "x", "y", "map_image", "space_type"]

def save_sward_config(df):
    df.to_csv(CONFIG_PATH, index=False)
    # session_state에도 항상 저장
    import streamlit as st
    st.session_state['sward_config'] = df.copy()

def load_sward_config():
    if os.path.exists(CONFIG_PATH):
        return pd.read_csv(CONFIG_PATH)
    return pd.DataFrame(columns=SWARD_COLUMNS)

def load_building_config():
    """
    건물 설정 로드 (기본적으로 S-Ward 설정을 반환)
    추후 확장 가능
    """
    config = load_sward_config()
    if config.empty:
        return pd.DataFrame(columns=['building', 'level', 'map_path', 'width', 'height'])
    
    # 건물별 기본 설정 생성
    building_config = []
    for building in config['building'].unique():
        for level in config[config['building'] == building]['level'].unique():
            building_config.append({
                'building': building,
                'level': level,
                'map_path': f"./Datafile/Map_Image/Map_{building}_{level}.png",
                'width': 100,  # 기본 너비
                'height': 100  # 기본 높이
            })
    
    return pd.DataFrame(building_config)


def render_building_setup():
    st.header("🏢 Building/Level Setup")
    st.info("Set up building structure, upload a map image, and set S-Ward locations by clicking on the map.")

    # 1. Building/Level input (사이드바 선택과 동기화, 중복 방지)
    df_config = load_sward_config()
    with st.sidebar:
        st.markdown("### 🏢 Structure (Select or Add)")
        buildings = df_config['building'].unique().tolist() if not df_config.empty else []
        buildings_display = buildings + ["(Add new building)"]
        building_select = st.selectbox("Select Building", buildings_display, key="sidebar_building_main")
        if building_select == "(Add new building)":
            sidebar_building = st.text_input("New Building Name", key="sidebar_building_new")
        else:
            sidebar_building = building_select
        # Level 선택/입력
        if sidebar_building and sidebar_building in buildings:
            levels = df_config[df_config['building'] == sidebar_building]['level'].unique().tolist()
            levels_display = levels + ["(Add new level)"]
            level_select = st.radio("Select Level", levels_display, key="sidebar_level_main")
            if level_select == "(Add new level)":
                sidebar_level = st.text_input("New Level Name", key="sidebar_level_new")
            else:
                sidebar_level = level_select
        else:
            sidebar_level = st.text_input("Level Name", key="sidebar_level_fallback")
    building = sidebar_building
    level = sidebar_level

    # Level/Building이 바뀌면 관련 session_state 초기화
    state_key_prefix = f"{building}_{level}" if building and level else "default"
    if st.session_state.get("_last_state_key_prefix", None) != state_key_prefix:
        for k in list(st.session_state.keys()):
            if k.startswith("setup_sward_") or k.startswith("sward_xy_buffer_") or k.startswith("sward_img_coords_") or k.startswith("sward_select_idx_"):
                del st.session_state[k]
        st.session_state["_last_state_key_prefix"] = state_key_prefix

    # 2. Map image upload
    st.markdown("**Upload Map Image**")
    map_file = st.file_uploader("Upload map image file (PNG/JPG)", type=["png", "jpg", "jpeg"], key="setup_map")
    map_image_path = None
    map_image_name = None
    img = None
    # 자동 로딩: building/level 선택 시 기존 이미지 자동 로드
    df_config = load_sward_config()
    if map_file:
        os.makedirs(MAP_IMAGE_DIR, exist_ok=True)
        map_image_path = os.path.join(MAP_IMAGE_DIR, map_file.name)
        map_image_name = map_file.name
        with open(map_image_path, "wb") as f:
            f.write(map_file.read())
        from PIL import Image
        img_orig = Image.open(map_image_path)
        # 이미지 크기 조정 (최대 width=700px)
        max_width = 700
        if img_orig.width > max_width:
            ratio = max_width / img_orig.width
            new_size = (max_width, int(img_orig.height * ratio))
            img_disp = img_orig.resize(new_size)
        else:
            img_disp = img_orig
        # 이미지를 바이트로 변환하여 캐시 문제 해결
        import io
        img_buffer = io.BytesIO()
        img_disp.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        st.image(img_buffer, caption="Uploaded Map Image", use_column_width=False)
    elif building and level and not map_file:
        # building/level에 해당하는 map_image 자동 로딩
        row = df_config[(df_config['building'] == building) & (df_config['level'] == level)]
        if not row.empty and 'map_image' in row:
            map_image_name = row['map_image'].values[0]
            if pd.notna(map_image_name):
                map_image_path = os.path.join(MAP_IMAGE_DIR, map_image_name)
                if os.path.exists(map_image_path):
                    from PIL import Image
                    img_orig = Image.open(map_image_path)
                    # 이미지 크기 조정 (최대 width=700px)
                    max_width = 700
                    if img_orig.width > max_width:
                        ratio = max_width / img_orig.width
                        new_size = (max_width, int(img_orig.height * ratio))
                        img_disp = img_orig.resize(new_size)
                    else:
                        img_disp = img_orig
                    # 이미지를 바이트로 변환하여 캐시 문제 해결
                    import io
                    img_buffer = io.BytesIO()
                    img_disp.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    st.image(img_buffer, caption="Loaded Map Image", use_column_width=False)
    else:
        st.warning("Please upload a map image to preview.")

    # 3. S-Ward IDs input (Level/Building별로 완전히 독립)
    sward_table = []
    prev_sward_count = 1
    if building and level and not df_config.empty:
        row = df_config[(df_config['building'] == building) & (df_config['level'] == level)]
        if not row.empty:
            sward_rows = row[["sward_id", "x", "y"]].rename(columns={"sward_id": "S-Ward ID"})
            sward_table = sward_rows.to_dict(orient="records")
            prev_sward_count = len(sward_table)
    sward_count = st.number_input("Number of S-Wards in this Level", min_value=1, max_value=100, step=1, key=f"setup_sward_count_{state_key_prefix}", value=prev_sward_count)
    # sward_table 길이와 sward_count 맞추기
    if len(sward_table) < sward_count:
        for _ in range(sward_count - len(sward_table)):
            sward_table.append({"S-Ward ID": "", "x": 0, "y": 0})
    elif len(sward_table) > sward_count:
        sward_table = sward_table[:sward_count]
    st.markdown("**S-Ward Table: Enter S-Ward ID, X, Y or click on the map**")
    # 클릭 좌표 임시 저장용 세션 (Level 바뀌면 초기화)
    xy_key = f"sward_xy_buffer_{state_key_prefix}"
    if xy_key not in st.session_state or len(st.session_state[xy_key]) != int(sward_count):
        st.session_state[xy_key] = [None] * int(sward_count)
    # 지도 이미지 클릭 좌표 추출
    img_for_click = None
    orig_w, orig_h = None, None
    disp_w, disp_h = None, None
    if 'img_orig' in locals() and 'img_disp' in locals():
        img_for_click = img_disp
        orig_w, orig_h = img_orig.width, img_orig.height
        disp_w, disp_h = img_disp.width, img_disp.height

        # --- 지도 위에 S-Ward 위치 시각화 (Level 로드 시) ---
        # S-Ward 좌표가 있으면 표시
        if building and level and not df_config.empty:
            row = df_config[(df_config['building'] == building) & (df_config['level'] == level)]
            if not row.empty:
                import matplotlib.pyplot as plt
                import numpy as np
                # 원본 이미지를 numpy로 변환
                img_np = np.array(img_disp)
                fig, ax = plt.subplots(figsize=(img_disp.width/100, img_disp.height/100), dpi=100)
                ax.imshow(img_np)
                # S-Ward 위치 마커 표시
                for _, r in row.iterrows():
                    sid = r['sward_id']
                    x = r['x']
                    y = r['y']
                    if pd.notna(x) and pd.notna(y) and sid:
                        # disp_w/h 기준 좌표 변환
                        x_disp = int(x * disp_w / orig_w)
                        y_disp = int(y * disp_h / orig_h)
                        ax.scatter(x_disp, y_disp, c='red', s=80, marker='o')
                        ax.text(x_disp+5, y_disp, str(sid), color='yellow', fontsize=10, weight='bold', va='center')
                ax.axis('off')
                st.pyplot(fig)
                plt.close(fig)
    if img_for_click is not None:
        try:
            import streamlit_image_coordinates
            coords = streamlit_image_coordinates.streamlit_image_coordinates(img_for_click, key=f"sward_img_coords_{state_key_prefix}")
            st.caption("Click on the map to set X, Y for the selected S-Ward.")
        except ImportError:
            st.warning("streamlit_image_coordinates 패키지가 설치되지 않았습니다. 지도 클릭 기능을 사용하려면 설치하세요: pip install streamlit-image-coordinates")
            coords = None
    else:
        coords = None
    selected_idx = st.radio("Select S-Ward to set position by clicking the map:", list(range(int(sward_count))), format_func=lambda i: f"S-Ward #{i+1}", horizontal=True, key=f"sward_select_idx_{state_key_prefix}") if sward_count > 1 else 0
    for i in range(int(sward_count)):
        col1, col2, col3 = st.columns([2,1,1])
        prev_sid = sward_table[i]["S-Ward ID"] if i < len(sward_table) else ""
        prev_x = int(sward_table[i]["x"]) if i < len(sward_table) and pd.notna(sward_table[i]["x"]) else 0
        prev_y = int(sward_table[i]["y"]) if i < len(sward_table) and pd.notna(sward_table[i]["y"]) else 0
        if (not st.session_state[xy_key][i]) or st.session_state[xy_key][i] == (0, 0):
            st.session_state[xy_key][i] = (prev_x, prev_y)
        with col1:
            sid = st.text_input(f"S-Ward ID", key=f"setup_sward_id_{i}_{state_key_prefix}", value=prev_sid)
        if coords and selected_idx == i and coords["x"] is not None and coords["y"] is not None and disp_w and orig_w:
            x_orig = int(coords["x"] * orig_w / disp_w)
            y_orig = int(coords["y"] * orig_h / disp_h)
            st.session_state[xy_key][i] = (x_orig, y_orig)
        buf = st.session_state[xy_key][i]
        with col2:
            x = st.number_input(f"X", key=f"setup_sward_x_{i}_{state_key_prefix}", min_value=0, max_value=10000, step=1, format="%d", value=buf[0] if buf else prev_x)
        with col3:
            y = st.number_input(f"Y", key=f"setup_sward_y_{i}_{state_key_prefix}", min_value=0, max_value=10000, step=1, format="%d", value=buf[1] if buf else prev_y)
        if (x, y) != buf:
            st.session_state[xy_key][i] = (x, y)
        sward_table[i] = {"S-Ward ID": sid, "x": x, "y": y}
    st.dataframe(sward_table)

    # 4. 지도에서 S-Ward 위치 클릭 및 좌표 추출 지원
    st.info("You can set X, Y by clicking the map image above for the selected S-Ward.")

    # (구) sward_ids, sward_positions 기반 코드 완전 제거. 표(sward_table) 기반으로만 동작. 중복 UI 제거.

    # 5. Save/Load/Delete
    df = load_sward_config()
    if st.button("Add/Save Level", key=f"btn_save_level_{state_key_prefix}"):
        # Remove existing rows for this building/level
        new_rows = []
        for row in sward_table:
            sid = row["S-Ward ID"]
            x = row["x"]
            y = row["y"]
            new_rows.append({
                "building": building,
                "level": level,
                "sward_id": sid,
                "x": x,
                "y": y,
                "map_image": map_image_name
            })
        # S-Ward 정보 별도 CSV 저장
        df = df[~((df['building'] == building) & (df['level'] == level))]
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        save_sward_config(df)
        # 지도 이미지는 Datafile/Map_Image/에 파일로 저장(이미 업로드 시 저장됨)
        st.success(f"Level saved: {building} - {level}")

    # 불러오기 버튼: CSV에서 S-Ward 정보, 지도 이미지는 파일명으로 연결


    # (중복) Level delete in sidebar UI 완전 제거 (사이드바 공간 정보 UI는 한 번만)

    # --- Main panel: always show selected info and map image ---
    if not df.empty and sidebar_building and sidebar_level:
        st.markdown(f"### 🏢 Building: {sidebar_building}")
        st.markdown(f"#### • Level: {sidebar_level}")
        # Show map image
        row = df[(df['building'] == sidebar_building) & (df['level'] == sidebar_level)]
        map_image_name = row['map_image'].values[0] if not row.empty and 'map_image' in row else None
        if map_image_name and pd.notna(map_image_name):
            map_image_path = os.path.join(MAP_IMAGE_DIR, map_image_name)
            if os.path.exists(map_image_path):
                # 이미지를 PIL로 로드하여 캐시 문제 해결
                from PIL import Image
                import io
                img = Image.open(map_image_path)
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                st.image(img_buffer, caption="Saved Map Image", use_column_width=True)
        st.markdown("**S-Ward List and Locations:**")
        # NaN, 빈 값, 중복 S-Ward는 출력하지 않음
        shown = set()
        for _, r in row.iterrows():
            sid = r['sward_id']
            x = r['x']
            y = r['y']
            if pd.isna(sid) or sid == '' or sid in shown:
                continue
            shown.add(sid)
            st.write(f"- {sid}: ({x}, {y})" if pd.notna(x) and pd.notna(y) else f"- {sid}: (Not set)")
