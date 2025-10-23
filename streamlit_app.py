import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from typing import List, Tuple

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ページ設定
st.set_page_config(
    page_title="日田市総合案内コンシェルジュ",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化
if 'mode' not in st.session_state:
    st.session_state.mode = '観光モード'
if 'current_location' not in st.session_state:
    st.session_state.current_location = [33.3219, 130.9414]
if 'selected_spots' not in st.session_state:
    st.session_state.selected_spots = []
if 'optimized_route' not in st.session_state:
    st.session_state.optimized_route = None
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = ""

# データ読み込み関数
@st.cache_data
def load_spots_data():
    """Excelファイルからスポットデータを読み込む"""
    try:
        # Excelファイルから読み込み
        tourism_df = pd.read_excel('spots.xlsx', sheet_name='観光')
        disaster_df = pd.read_excel('spots.xlsx', sheet_name='防災')
        
        # カラム名の確認と標準化
        required_cols_tourism = ['No', 'スポット名', '緯度', '経度', '説明']
        required_cols_disaster = ['No', 'スポット名', '緯度', '経度', '説明']
        
        # 必須カラムの確認
        for col in required_cols_tourism:
            if col not in tourism_df.columns:
                st.error(f"❌ 観光シートに'{col}'カラムがありません")
                return None, None
        
        for col in required_cols_disaster:
            if col not in disaster_df.columns:
                st.error(f"❌ 防災シートに'{col}'カラムがありません")
                return None, None
        
        # オプションカラムの追加（存在しない場合）
        if '所要時間（参考）' not in tourism_df.columns:
            tourism_df['所要時間（参考）'] = 60  # デフォルト60分
        if 'カテゴリ' not in tourism_df.columns:
            tourism_df['カテゴリ'] = '観光地'
        if '営業時間' not in tourism_df.columns:
            tourism_df['営業時間'] = '終日'
        if '料金' not in tourism_df.columns:
            tourism_df['料金'] = '無料'
        if '待ち時間（分）' not in tourism_df.columns:
            tourism_df['待ち時間（分）'] = 0
        if '混雑状況' not in tourism_df.columns:
            tourism_df['混雑状況'] = '空いている'
        
        if '収容人数' not in disaster_df.columns:
            disaster_df['収容人数'] = 0
        if '状態' not in disaster_df.columns:
            disaster_df['状態'] = '待機中'
        
        st.success(f"✅ Excelファイル読み込み成功: 観光{len(tourism_df)}件、避難所{len(disaster_df)}件")
        
        return tourism_df, disaster_df
        
    except FileNotFoundError:
        st.warning("⚠️ spots.xlsxが見つかりません。サンプルデータを使用します。")
        
        # サンプルデータを作成
        tourism_df = pd.DataFrame({
            'No': [1, 2, 3, 4, 5, 6],
            'スポット名': ['豆田町', '日田温泉', '咸宜園', '天ヶ瀬温泉', '小鹿田焼の里', '大山ダム'],
            '緯度': [33.3219, 33.3200, 33.3240, 33.2967, 33.3500, 33.3800],
            '経度': [130.9414, 130.9400, 130.9430, 130.9167, 130.9600, 130.9200],
            '所要時間（参考）': [60, 120, 45, 90, 75, 30],
            '説明': ['江戸時代の町並みが残る歴史的な地区', '日田の名湯・温泉施設',
                   '日本最大の私塾跡・歴史的教育施設', '自然豊かな温泉街',
                   '伝統工芸の陶器の里', '美しい景観のダム'],
            'カテゴリ': ['歴史', 'グルメ', '歴史', '自然', '体験', '自然'],
            '営業時間': ['終日', '9:00-21:00', '9:00-17:00', '終日', '9:00-17:00', '終日'],
            '料金': ['無料', '500円', '300円', '無料', '無料', '無料'],
            '待ち時間（分）': [0, 15, 0, 10, 5, 0],
            '混雑状況': ['空いている', '混雑', '普通', '空いている', '空いている', '空いている']
        })
        disaster_df = pd.DataFrame({
            'No': [1, 2, 3, 4, 5],
            'スポット名': ['日田市役所（避難所）', '中央公民館', '総合体育館', '桂林公民館', '三花公民館'],
            '緯度': [33.3219, 33.3250, 33.3180, 33.3300, 33.3100],
            '経度': [130.9414, 130.9450, 130.9380, 130.9500, 130.9350],
            '所要時間（参考）': ['-', '-', '-', '-', '-'],
            '説明': ['市役所・第一避難所', '中央地区の避難所', '大規模避難所', 
                   '桂林地区の避難所', '三花地区の避難所'],
            '収容人数': [500, 300, 800, 200, 250],
            '状態': ['開設中', '開設中', '開設中', '待機中', '待機中']
        })
        return tourism_df, disaster_df
    
    except Exception as e:
        st.error(f"❌ Excelファイルの読み込みエラー: {e}")
        return None, None

# 距離計算関数
def calculate_distance(lat1, lng1, lat2, lng2):
    """2点間の距離を計算（km）- ヒュベニの公式"""
    R = 6371  # 地球の半径（km）

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)

    a = sin(delta_lat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

# 最適化経路算出関数（観光モード：待ち時間考慮）
def optimize_route_tourism(current_loc: List[float], spots_df: pd.DataFrame, selected_indices: List[int]) -> Tuple[List[int], float, float]:
    """
    観光モード用の最適化経路算出（待ち時間と距離を考慮）
    Returns: (訪問順のインデックスリスト, 総移動距離, 総所要時間)
    """
    if not selected_indices:
        return [], 0.0, 0.0

    unvisited = selected_indices.copy()
    route = []
    current_position = current_loc
    total_distance = 0.0
    total_time = 0.0

    while unvisited:
        # 各未訪問スポットのスコアを計算
        scores = []
        distances = []
        wait_times = []

        for idx in unvisited:
            spot = spots_df.iloc[idx]
            dist = calculate_distance(
                current_position[0], current_position[1],
                spot['緯度'], spot['経度']
            )
            distances.append(dist)
            wait_time = spot.get('待ち時間（分）', 0)
            wait_times.append(wait_time)

        # 距離ランキング（近い順に1, 2, 3...）
        distance_ranks = [sorted(distances).index(d) + 1 for d in distances]

        # 待ち時間ランキング（短い順に1, 2, 3...）
        wait_time_ranks = [sorted(wait_times).index(w) + 1 for w in wait_times]

        # スコア計算: S = RD + RW（小さいほど良い）
        scores = [distance_ranks[i] + wait_time_ranks[i] for i in range(len(unvisited))]

        # 最小スコアのスポットを選択
        min_score_idx = scores.index(min(scores))
        selected_idx = unvisited[min_score_idx]

        route.append(selected_idx)
        selected_spot = spots_df.iloc[selected_idx]

        # 移動距離と時間を加算
        travel_dist = distances[min_score_idx]
        total_distance += travel_dist
        total_time += (travel_dist / 40) * 60  # 時速40kmで計算（分）
        total_time += selected_spot.get('所要時間（参考）', 60)
        total_time += selected_spot.get('待ち時間（分）', 0)

        # 現在地を更新
        current_position = [selected_spot['緯度'], selected_spot['経度']]
        unvisited.remove(selected_idx)

    return route, total_distance, total_time

# 最適化経路算出関数（防災モード：最近傍法）
def optimize_route_disaster(current_loc: List[float], spots_df: pd.DataFrame, selected_indices: List[int]) -> Tuple[List[int], float, float]:
    """
    防災モード用の最適化経路算出（距離のみ考慮）
    Returns: (訪問順のインデックスリスト, 総移動距離, 総所要時間)
    """
    if not selected_indices:
        return [], 0.0, 0.0

    unvisited = selected_indices.copy()
    route = []
    current_position = current_loc
    total_distance = 0.0
    total_time = 0.0

    while unvisited:
        # 最も近いスポットを選択
        min_dist = float('inf')
        nearest_idx = None

        for idx in unvisited:
            spot = spots_df.iloc[idx]
            dist = calculate_distance(
                current_position[0], current_position[1],
                spot['緯度'], spot['経度']
            )
            if dist < min_dist:
                min_dist = dist
                nearest_idx = idx

        route.append(nearest_idx)
        selected_spot = spots_df.iloc[nearest_idx]

        # 移動距離と時間を加算
        total_distance += min_dist
        total_time += (min_dist / 4) * 60  # 徒歩時速4kmで計算（分）

        # 現在地を更新
        current_position = [selected_spot['緯度'], selected_spot['経度']]
        unvisited.remove(nearest_idx)

    return route, total_distance, total_time

# 地図作成関数（改良版）
def create_enhanced_map(spots_df, center_location, selected_spot=None, show_route=False):
    """Foliumマップを作成"""
    m = folium.Map(
        location=center_location,
        zoom_start=13,
        tiles='OpenStreetMap'
    )
    
    # 現在地マーカー（赤・大きめ）
    folium.Marker(
        center_location,
        popup=folium.Popup("📍 <b>現在地</b>", max_width=200),
        tooltip="現在地",
        icon=folium.Icon(color='red', icon='home', prefix='fa')
    ).add_to(m)
    
    # スポットマーカー
    for idx, row in spots_df.iterrows():
        # 距離計算
        distance = calculate_distance(
            center_location[0], center_location[1],
            row['緯度'], row['経度']
        )
        
        # ポップアップHTML
        popup_html = f"""
        <div style="width: 250px; font-family: sans-serif;">
            <h4 style="margin: 0 0 10px 0; color: #1f77b4;">{row['スポット名']}</h4>
            <p style="margin: 5px 0;"><b>📝 説明:</b><br>{row['説明']}</p>
            <p style="margin: 5px 0;"><b>📏 現在地から:</b> {distance:.2f} km</p>
        """
        
        # カテゴリー情報（観光モード）
        if 'カテゴリー' in row:
            popup_html += f'<p style="margin: 5px 0;"><b>🏷️ カテゴリー:</b> {row["カテゴリー"]}</p>'
        if '営業時間' in row:
            popup_html += f'<p style="margin: 5px 0;"><b>🕐 営業時間:</b> {row["営業時間"]}</p>'
        if '料金' in row:
            popup_html += f'<p style="margin: 5px 0;"><b>💰 料金:</b> {row["料金"]}</p>'
        
        # 収容人数情報（防災モード）
        if '収容人数' in row:
            popup_html += f'<p style="margin: 5px 0;"><b>👥 収容人数:</b> {row["収容人数"]}名</p>'
        if '状態' in row:
            status_color = 'green' if row['状態'] == '開設中' else 'orange'
            popup_html += f'<p style="margin: 5px 0;"><b>🚨 状態:</b> <span style="color: {status_color};">{row["状態"]}</span></p>'
        
        popup_html += "</div>"
        
        # マーカーの色を選択されたスポットで変更
        marker_color = 'green' if selected_spot == row['スポット名'] else 'blue'
        
        folium.Marker(
            [row['緯度'], row['経度']],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row['スポット名'],
            icon=folium.Icon(color=marker_color, icon='info-sign')
        ).add_to(m)
        
        # 選択されたスポットへのルート（直線）を表示
        if show_route and selected_spot == row['スポット名']:
            folium.PolyLine(
                locations=[center_location, [row['緯度'], row['経度']]],
                color='red',
                weight=3,
                opacity=0.7,
                popup=f"直線距離: {distance:.2f} km"
            ).add_to(m)
    
    return m

# Google Mapsリンク生成関数（単一目的地）
def create_google_maps_link(origin, destination, mode='driving'):
    """Google Mapsの外部リンクを生成（単一目的地）"""
    modes = {
        'driving': 'driving',
        'walking': 'walking',
        'bicycling': 'bicycling',
        'transit': 'transit'
    }
    base_url = "https://www.google.com/maps/dir/?api=1"
    link = f"{base_url}&origin={origin[0]},{origin[1]}&destination={destination[0]},{destination[1]}&travelmode={modes[mode]}"
    return link

# Google Mapsリンク生成関数（複数経由地）
def create_google_maps_multi_link(origin: List[float], waypoints: List[Tuple[float, float]], destination: Tuple[float, float], mode='driving') -> str:
    """
    Google Mapsの外部リンクを生成（複数経由地対応）
    Args:
        origin: 出発地 [緯度, 経度]
        waypoints: 経由地のリスト [(緯度, 経度), ...]
        destination: 最終目的地 (緯度, 経度)
        mode: 移動手段
    Returns:
        Google Maps URL
    """
    modes = {
        'driving': 'driving',
        'walking': 'walking',
        'bicycling': 'bicycling',
        'transit': 'transit'
    }

    base_url = "https://www.google.com/maps/dir/?api=1"
    url = f"{base_url}&origin={origin[0]},{origin[1]}&destination={destination[0]},{destination[1]}"

    if waypoints:
        waypoints_str = "|".join([f"{lat},{lng}" for lat, lng in waypoints])
        url += f"&waypoints={waypoints_str}"

    url += f"&travelmode={modes.get(mode, 'driving')}"

    return url

# サイドバー
with st.sidebar:
    # モード選択
    mode = st.radio(
        "モード選択",
        ["観光モード", "防災モード"],
        key='mode_selector'
    )
    st.session_state.mode = mode
    
    st.divider()
    
    # 現在地設定
    st.subheader("📍 現在地設定")
    
    # プリセット位置
    preset_locations = {
        '日田市中心部': [33.3219, 130.9414],
        '豆田町': [33.3219, 130.9414],
        '日田駅': [33.3205, 130.9407],
        '天ヶ瀬温泉': [33.2967, 130.9167]
    }
    
    preset = st.selectbox(
        "プリセット位置から選択",
        ['カスタム'] + list(preset_locations.keys())
    )
    
    if preset != 'カスタム':
        st.session_state.current_location = preset_locations[preset]
    
    col1, col2 = st.columns(2)
    with col1:
        current_lat = st.number_input(
            "緯度",
            value=st.session_state.current_location[0],
            format="%.6f",
            key='lat_input'
        )
    with col2:
        current_lng = st.number_input(
            "経度",
            value=st.session_state.current_location[1],
            format="%.6f",
            key='lng_input'
        )
    
    if st.button("📍 位置を更新", use_container_width=True):
        st.session_state.current_location = [current_lat, current_lng]
        st.success("✅ 位置を更新しました")
        st.rerun()
    
    st.divider()
    
    # 天気情報（シンプル版 - APIキー不要）
    st.subheader("🌤️ 天気情報")
    
    # 現在の日時から天気アイコンを選択（サンプル）
    hour = datetime.now().hour
    if 6 <= hour < 18:
        weather_icon = "☀️"
        weather_text = "晴れ"
    else:
        weather_icon = "🌙"
        weather_text = "夜間"
    
    st.markdown(f"### {weather_icon} {weather_text}")
    
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        st.metric("気温", "23°C")
    with col_w2:
        st.metric("湿度", "65%")
    
    # 外部天気サイトへのリンク
    with st.expander("🔗 詳細な天気情報"):
        # 気象庁
        jma_url = "https://www.jma.go.jp/bosai/forecast/#area_type=class20s&area_code=4410200"
        st.link_button(
            "📊 気象庁（日田市）",
            jma_url,
            use_container_width=True
        )
        
        # Yahoo天気
        yahoo_weather_url = "https://weather.yahoo.co.jp/weather/jp/44/4410/44204.html"
        st.link_button(
            "🌐 Yahoo!天気",
            yahoo_weather_url,
            use_container_width=True
        )
    
    st.caption(f"表示: {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    
    st.divider()
    
    # 統計情報
    if st.session_state.mode == '観光モード':
        st.metric("登録スポット数", "6箇所")
    else:
        st.metric("避難所数", "5箇所")
        st.metric("開設中", "3箇所", delta="安全")

# メインコンテンツ
# ページトップのタイトル
st.title("🗺️ 日田市総合案内コンシェルジュ")
st.caption("Ver. 2.1 - 観光と防災におけるタイムパフォーマンスを向上")
st.divider()

# データ読み込み
tourism_df, disaster_df = load_spots_data()

# 現在のモード表示
st.subheader(f"📍 {st.session_state.mode}")

# モードに応じた表示
if st.session_state.mode == '観光モード':
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🗺️ マップ",
        "📋 スポット一覧",
        "🎯 最適化ルート",
        "🌤️ 天気",
        "📅 イベント",
        "📊 ランキング",
        "🤖 AIプラン提案"
    ])
    
    with tab1:
        st.subheader("🗺️ 観光マップ")
        
        col_map, col_control = st.columns([3, 1])
        
        with col_control:
            st.markdown("### 🎯 目的地選択")
            
            # カテゴリーフィルター
            categories = ['すべて'] + sorted(tourism_df['カテゴリ'].unique().tolist())
            selected_category = st.selectbox("カテゴリー", categories)

            # フィルター適用
            if selected_category != 'すべて':
                filtered_df = tourism_df[tourism_df['カテゴリ'] == selected_category]
            else:
                filtered_df = tourism_df
            
            # 目的地選択
            destination = st.selectbox(
                "行きたい場所",
                ['選択してください'] + filtered_df['スポット名'].tolist(),
                key='destination_select'
            )
            
            if destination != '選択してください':
                dest_row = filtered_df[filtered_df['スポット名'] == destination].iloc[0]
                dest_coords = (dest_row['緯度'], dest_row['経度'])
                
                # 情報表示
                st.info(f"📍 **{destination}**")
                
                # 距離表示
                distance = calculate_distance(
                    st.session_state.current_location[0],
                    st.session_state.current_location[1],
                    dest_coords[0],
                    dest_coords[1]
                )
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("直線距離", f"{distance:.2f} km")
                with col_b:
                    # 徒歩時間の概算（時速4km）
                    walk_time = int((distance / 4) * 60)
                    st.metric("徒歩概算", f"{walk_time}分")
                
                # 詳細情報
                with st.expander("📝 詳細情報", expanded=True):
                    st.write(f"**説明:** {dest_row['説明']}")
                    st.write(f"**カテゴリー:** {dest_row['カテゴリ']}")
                    st.write(f"**営業時間:** {dest_row['営業時間']}")
                    st.write(f"**料金:** {dest_row['料金']}")
                    st.write(f"**所要時間（参考）:** {dest_row['所要時間（参考）']}分")
                    st.write(f"**待ち時間:** {dest_row['待ち時間（分）']}分")
                    st.write(f"**混雑状況:** {dest_row['混雑状況']}")
                
                st.markdown("---")
                st.markdown("### 🚗 ルート案内")
                
                # 移動手段選択
                travel_mode = st.selectbox(
                    "移動手段",
                    ["driving", "walking", "bicycling", "transit"],
                    format_func=lambda x: {
                        'driving': '🚗 車',
                        'walking': '🚶 徒歩',
                        'bicycling': '🚲 自転車',
                        'transit': '🚌 公共交通'
                    }[x]
                )
                
                # Google Mapsで開くボタン
                maps_link = create_google_maps_link(
                    st.session_state.current_location,
                    dest_coords,
                    travel_mode
                )
                
                st.link_button(
                    "🗺️ Google Mapsでルートを見る",
                    maps_link,
                    use_container_width=True,
                    type="primary"
                )
                
                # 地図上に直線ルートを表示
                show_route = st.checkbox("地図上に直線を表示", value=True)
            else:
                destination = None
                show_route = False
        
        with col_map:
            # 地図表示
            m = create_enhanced_map(
                tourism_df,
                st.session_state.current_location,
                selected_spot=destination if destination != '選択してください' else None,
                show_route=show_route
            )
            st_folium(m, width=700, height=600, key='tourism_map')
    
    with tab2:
        st.subheader("📋 スポット一覧")
        
        # 検索とフィルター
        col1, col2 = st.columns([2, 1])
        with col1:
            search = st.text_input("🔍 スポット名で検索", placeholder="例: 温泉")
        with col2:
            sort_by = st.selectbox("並び替え", ["番号順", "距離が近い順", "名前順"])
        
        # データフィルタリング
        display_df = tourism_df.copy()
        
        if search:
            display_df = display_df[
                display_df['スポット名'].str.contains(search, na=False) |
                display_df['説明'].str.contains(search, na=False)
            ]
        
        # 距離を計算
        display_df['距離'] = display_df.apply(
            lambda row: calculate_distance(
                st.session_state.current_location[0],
                st.session_state.current_location[1],
                row['緯度'],
                row['経度']
            ),
            axis=1
        )
        
        # 並び替え
        if sort_by == "距離が近い順":
            display_df = display_df.sort_values('距離')
        elif sort_by == "名前順":
            display_df = display_df.sort_values('スポット名')
        
        st.write(f"**表示件数:** {len(display_df)}件")
        
        # カード表示
        for idx, row in display_df.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"### {row['スポット名']}")
                    st.write(f"📝 {row['説明']}")
                    st.caption(f"🏷️ {row['カテゴリ']} | 🕐 {row['営業時間']} | 💰 {row['料金']}")
                
                with col2:
                    st.metric("距離", f"{row['距離']:.2f}km")
                
                with col3:
                    maps_link = create_google_maps_link(
                        st.session_state.current_location,
                        (row['緯度'], row['経度']),
                        'driving'
                    )
                    st.link_button("🗺️", maps_link, use_container_width=True)
                
                st.divider()

    with tab3:
        st.subheader("🎯 最適化ルート算出")

        st.info("複数のスポットを選択して、最適な訪問順序を自動で算出します。観光モードでは待ち時間と距離を考慮します。")

        # 複数スポット選択
        st.markdown("### 📍 訪問したいスポットを選択")

        selected_spots_names = st.multiselect(
            "複数のスポットを選択してください（2つ以上）",
            tourism_df['スポット名'].tolist(),
            default=[]
        )

        if len(selected_spots_names) >= 2:
            # 選択されたスポットのインデックスを取得
            selected_indices = []
            for spot_name in selected_spots_names:
                idx = tourism_df[tourism_df['スポット名'] == spot_name].index[0]
                selected_indices.append(idx)

            # 移動手段選択
            travel_mode_opt = st.selectbox(
                "🚗 移動手段",
                ["driving", "walking", "bicycling", "transit"],
                format_func=lambda x: {
                    'driving': '🚗 車',
                    'walking': '🚶 徒歩',
                    'bicycling': '🚲 自転車',
                    'transit': '🚌 公共交通'
                }[x],
                key='opt_travel_mode'
            )

            if st.button("🎯 最適化ルートを算出", type="primary", use_container_width=True):
                # 最適化ルート算出
                route, total_dist, total_time = optimize_route_tourism(
                    st.session_state.current_location,
                    tourism_df,
                    selected_indices
                )

                st.session_state.optimized_route = {
                    'route': route,
                    'total_distance': total_dist,
                    'total_time': total_time,
                    'mode': travel_mode_opt
                }

                st.success("✅ 最適化ルートを算出しました！")

            # 最適化ルート表示
            if st.session_state.optimized_route is not None:
                route_data = st.session_state.optimized_route
                route = route_data['route']
                total_dist = route_data['total_distance']
                total_time = route_data['total_time']

                st.markdown("---")
                st.markdown("### 📋 最適化された訪問順序")

                # 統計情報
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("総移動距離", f"{total_dist:.2f} km")
                with col2:
                    hours = int(total_time // 60)
                    minutes = int(total_time % 60)
                    st.metric("総所要時間", f"{hours}時間{minutes}分")
                with col3:
                    st.metric("訪問スポット数", f"{len(route)}箇所")

                st.markdown("---")

                # 訪問順序リスト
                for i, idx in enumerate(route, 1):
                    spot = tourism_df.iloc[idx]

                    with st.expander(f"{i}. {spot['スポット名']}", expanded=True):
                        col_a, col_b = st.columns([2, 1])
                        with col_a:
                            st.write(f"**説明:** {spot['説明']}")
                            st.write(f"**カテゴリー:** {spot['カテゴリ']}")
                            st.write(f"**営業時間:** {spot['営業時間']}")
                            st.write(f"**料金:** {spot['料金']}")
                            st.write(f"**所要時間:** {spot['所要時間（参考）']}分")
                            st.write(f"**待ち時間:** {spot['待ち時間（分）']}分")
                            st.write(f"**混雑状況:** {spot['混雑状況']}")
                        with col_b:
                            # 現在地からの距離（参考）
                            if i == 1:
                                prev_loc = st.session_state.current_location
                            else:
                                prev_spot = tourism_df.iloc[route[i-2]]
                                prev_loc = [prev_spot['緯度'], prev_spot['経度']]

                            dist_from_prev = calculate_distance(
                                prev_loc[0], prev_loc[1],
                                spot['緯度'], spot['経度']
                            )
                            st.metric("移動距離", f"{dist_from_prev:.2f} km")

                st.markdown("---")
                st.markdown("### 🗺️ Google Mapで開く")

                # Google Maps複数経由地リンク生成
                if len(route) > 0:
                    # 出発地
                    origin = st.session_state.current_location

                    # 経由地と最終目的地
                    if len(route) == 1:
                        # 1箇所のみ
                        dest_spot = tourism_df.iloc[route[0]]
                        destination = (dest_spot['緯度'], dest_spot['経度'])
                        waypoints = []
                    else:
                        # 2箇所以上
                        waypoints = []
                        for idx in route[:-1]:
                            spot = tourism_df.iloc[idx]
                            waypoints.append((spot['緯度'], spot['経度']))

                        dest_spot = tourism_df.iloc[route[-1]]
                        destination = (dest_spot['緯度'], dest_spot['経度'])

                    # リンク生成
                    maps_url = create_google_maps_multi_link(
                        origin,
                        waypoints,
                        destination,
                        route_data['mode']
                    )

                    st.link_button(
                        "🗺️ Google Mapで最適化ルートを開く",
                        maps_url,
                        use_container_width=True,
                        type="primary"
                    )

        elif len(selected_spots_names) == 1:
            st.warning("⚠️ 2つ以上のスポットを選択してください。")
        else:
            st.info("👆 訪問したいスポットを2つ以上選択してください。")

    with tab4:
        st.subheader("🌤️ 天気情報・気象情報")
        
        st.info("📊 詳細な天気情報は外部サイトをご利用ください")
        
        # 天気情報サイトへのリンク集
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏛️ 公式サイト")
            
            # 気象庁
            st.markdown("#### 気象庁")
            st.write("日本の公式気象情報")
            st.link_button(
                "📊 気象庁 日田市の天気",
                "https://www.jma.go.jp/bosai/forecast/#area_type=class20s&area_code=4410200",
                use_container_width=True
            )
            
            st.markdown("---")
            
            # 気象庁の警報・注意報
            st.markdown("#### 警報・注意報")
            st.write("気象警報や注意報を確認")
            st.link_button(
                "⚠️ 大分県の警報・注意報",
                "https://www.jma.go.jp/bosai/warning/#area_type=class20s&area_code=4410200",
                use_container_width=True
            )
        
        with col2:
            st.markdown("### 🌐 天気予報サイト")
            
            # Yahoo天気
            st.markdown("#### Yahoo!天気")
            st.write("詳細な天気予報と雨雲レーダー")
            st.link_button(
                "🌤️ Yahoo!天気 日田市",
                "https://weather.yahoo.co.jp/weather/jp/44/4410/44204.html",
                use_container_width=True
            )
            
            st.markdown("---")
            
            # tenki.jp
            st.markdown("#### tenki.jp")
            st.write("10日間天気予報")
            st.link_button(
                "📱 tenki.jp 日田市",
                "https://tenki.jp/forecast/9/44/8410/44204/",
                use_container_width=True
            )
        
        st.divider()
        
        # 簡易的な週間天気予報（サンプル）
        st.markdown("### 📅 週間天気の目安")
        st.caption("※ 実際の予報は上記の外部サイトでご確認ください")
        
        # サンプルの週間天気
        days = ['月', '火', '水', '木', '金', '土', '日']
        weather_icons = ['☀️', '⛅', '☁️', '🌧️', '☀️', '☀️', '⛅']
        temps_high = [25, 24, 22, 20, 23, 26, 25]
        temps_low = [15, 14, 13, 12, 14, 16, 15]
        
        cols = st.columns(7)
        for i, col in enumerate(cols):
            with col:
                st.markdown(f"**{days[i]}**")
                st.markdown(f"## {weather_icons[i]}")
                st.write(f"{temps_high[i]}°C")
                st.caption(f"{temps_low[i]}°C")
    
    with tab4:
        st.subheader("📅 年間イベントカレンダー")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            selected_month = st.selectbox(
                "月を選択",
                list(range(1, 13)),
                index=datetime.now().month - 1,
                format_func=lambda x: f"{x}月"
            )
        
        # サンプルイベントデータ
        events = {
            5: [("日田川開き観光祭", "5月20日-21日", "花火大会と伝統行事")],
            7: [("祇園祭", "7月20日-21日", "300年の歴史を持つ祭り")],
            10: [("日田天領まつり", "10月中旬", "時代行列と郷土芸能")],
            11: [("天ヶ瀬温泉もみじ祭り", "11月中旬", "紅葉の名所でのイベント")]
        }
        
        if selected_month in events:
            for event_name, event_date, event_desc in events[selected_month]:
                with st.container():
                    st.markdown(f"### 🎉 {event_name}")
                    st.write(f"📅 **開催日:** {event_date}")
                    st.write(f"📝 **内容:** {event_desc}")
                    st.divider()
        else:
            st.info(f"{selected_month}月には現在登録されているイベントはありません")
    
    with tab5:
        st.subheader("📅 年間イベントカレンダー")

        col1, col2 = st.columns([1, 3])
        with col1:
            selected_month = st.selectbox(
                "月を選択",
                list(range(1, 13)),
                index=datetime.now().month - 1,
                format_func=lambda x: f"{x}月",
                key='event_month'
            )

        # サンプルイベントデータ
        events = {
            5: [("日田川開き観光祭", "5月20日-21日", "花火大会と伝統行事")],
            7: [("祇園祭", "7月20日-21日", "300年の歴史を持つ祭り")],
            10: [("日田天領まつり", "10月中旬", "時代行列と郷土芸能")],
            11: [("天ヶ瀬温泉もみじ祭り", "11月中旬", "紅葉の名所でのイベント")]
        }

        if selected_month in events:
            for event_name, event_date, event_desc in events[selected_month]:
                with st.container():
                    st.markdown(f"### 🎉 {event_name}")
                    st.write(f"📅 **開催日:** {event_date}")
                    st.write(f"📝 **内容:** {event_desc}")
                    st.divider()
        else:
            st.info(f"{selected_month}月には現在登録されているイベントはありません")

    with tab6:
        st.subheader("📊 月別人気観光地ランキング")

        # 月選択
        ranking_month = st.selectbox(
            "🗓️ 月を選択",
            list(range(1, 13)),
            index=datetime.now().month - 1,
            format_func=lambda x: f"{x}月",
            key='ranking_month'
        )

        st.markdown(f"### {ranking_month}月の人気観光地トップ5")

        # サンプルランキングデータ（実際はデータベースから取得）
        rankings = {
            5: [
                ("豆田町", 1250, "🔥 大人気！"),
                ("日田温泉", 980, "人気上昇中"),
                ("咸宜園", 720, ""),
                ("天ヶ瀬温泉", 650, ""),
                ("小鹿田焼の里", 520, "")
            ],
            7: [
                ("天ヶ瀬温泉", 1450, "🔥 大人気！"),
                ("豆田町", 1100, ""),
                ("日田温泉", 890, ""),
                ("大山ダム", 680, ""),
                ("咸宜園", 550, "")
            ],
            10: [
                ("豆田町", 1580, "🔥 大人気！"),
                ("咸宜園", 920, "人気上昇中"),
                ("日田温泉", 810, ""),
                ("小鹿田焼の里", 690, ""),
                ("天ヶ瀬温泉", 620, "")
            ],
            11: [
                ("天ヶ瀬温泉", 1680, "🔥 大人気！"),
                ("大山ダム", 1120, "人気上昇中"),
                ("豆田町", 950, ""),
                ("日田温泉", 780, ""),
                ("咸宜園", 620, "")
            ]
        }

        # デフォルトランキング（指定月のデータがない場合）
        default_ranking = [
            ("豆田町", 1000, ""),
            ("日田温泉", 850, ""),
            ("咸宜園", 700, ""),
            ("天ヶ瀬温泉", 650, ""),
            ("小鹿田焼の里", 550, "")
        ]

        current_ranking = rankings.get(ranking_month, default_ranking)

        for i, (spot_name, visitors, badge) in enumerate(current_ranking, 1):
            # スポット情報を取得
            spot_df = tourism_df[tourism_df['スポット名'] == spot_name]

            if len(spot_df) > 0:
                spot = spot_df.iloc[0]

                with st.container():
                    col_rank, col_info, col_visitors = st.columns([0.5, 3, 1])

                    with col_rank:
                        if i == 1:
                            st.markdown("## 🥇")
                        elif i == 2:
                            st.markdown("## 🥈")
                        elif i == 3:
                            st.markdown("## 🥉")
                        else:
                            st.markdown(f"## {i}位")

                    with col_info:
                        st.markdown(f"### {spot_name} {badge}")
                        st.write(f"📝 {spot['説明']}")
                        st.caption(f"🏷️ {spot['カテゴリ']} | 💰 {spot['料金']}")

                    with col_visitors:
                        st.metric("訪問者数", f"{visitors}人")
                        maps_link = create_google_maps_link(
                            st.session_state.current_location,
                            (spot['緯度'], spot['経度']),
                            'driving'
                        )
                        st.link_button("🗺️", maps_link, use_container_width=True)

                    st.divider()

    with tab7:
        st.subheader("🤖 AIプラン提案（Gemini API）")

        st.info("Gemini AIがあなたの予算・時間・興味に合わせた最適な観光プランを提案します。")

        # APIキー入力
        st.markdown("### 🔑 APIキー設定")

        api_key_input = st.text_input(
            "Gemini APIキーを入力してください",
            type="password",
            value=st.session_state.gemini_api_key,
            help="APIキーはセッション中のみ保持され、サーバーには保存されません"
        )

        if api_key_input:
            st.session_state.gemini_api_key = api_key_input

        st.markdown("[🔑 Gemini APIキーを取得する →](https://aistudio.google.com/app/apikey)")

        st.divider()

        # プラン条件入力
        st.markdown("### 📝 プラン条件を入力")

        col1, col2 = st.columns(2)

        with col1:
            user_budget = st.text_input("💰 予算", placeholder="例: 5000円以内", key='ai_budget')
            user_duration = st.text_input("⏱️ 滞在時間", placeholder="例: 3時間", key='ai_duration')

        with col2:
            user_companion = st.selectbox(
                "👥 同行者",
                ["一人旅", "家族連れ", "カップル", "友人グループ"],
                key='ai_companion'
            )

        # 興味カテゴリー
        st.markdown("**🎯 興味のあるカテゴリー（複数選択可）:**")
        interest_categories = st.multiselect(
            "興味のあるカテゴリーを選択",
            ["歴史", "自然", "グルメ", "体験", "温泉", "文化"],
            default=["歴史"],
            key='ai_interests'
        )

        # プラン生成ボタン
        if st.button("🎯 AIプランを生成", type="primary", use_container_width=True):
            if not GENAI_AVAILABLE:
                st.error("❌ google-generativeai パッケージがインストールされていません。")
                st.info("以下のコマンドでインストールしてください: `pip install google-generativeai`")
            elif not st.session_state.gemini_api_key:
                st.error("❌ Gemini APIキーを入力してください")
            elif not user_budget or not user_duration:
                st.warning("⚠️ 予算と滞在時間を入力してください")
            else:
                try:
                    with st.spinner("🤖 AIがプランを生成中..."):
                        # Gemini API設定
                        genai.configure(api_key=st.session_state.gemini_api_key)
                        model = genai.GenerativeModel('gemini-2.0-flash-exp')

                        # スポットリスト作成
                        spots_context = []
                        for _, spot in tourism_df.iterrows():
                            spots_context.append(
                                f"- {spot['スポット名']}: {spot['説明']} (カテゴリ: {spot['カテゴリ']}, 料金: {spot['料金']}, 所要時間: {spot['所要時間（参考）']}分)"
                            )
                        spots_text = "\n".join(spots_context)

                        # プロンプト作成
                        system_prompt = "あなたは日田市の観光コンシェルジュです。以下の観光スポットリストとユーザーの要望に基づき、魅力的な観光プランを提案してください。"

                        user_prompt = f"""
観光スポットリスト:
{spots_text}

ユーザーの要望:
- 予算: {user_budget}
- 滞在時間: {user_duration}
- 興味: {', '.join(interest_categories)}
- 同行者: {user_companion}

上記の条件に合った日田市の観光プランを、訪問順序を含めて具体的に提案してください。
各スポットの魅力や、なぜそのスポットを選んだのかも簡潔に説明してください。
                        """

                        # API呼び出し
                        response = model.generate_content(f"{system_prompt}\n\n{user_prompt}")

                        # 結果表示
                        st.markdown("---")
                        st.markdown("### 📋 AI提案プラン")
                        st.markdown(response.text)

                        st.success("✅ プラン生成完了！")

                except Exception as e:
                    st.error(f"❌ エラーが発生しました: {str(e)}")
                    st.info("💡 APIキーが正しいか確認してください。また、Gemini APIが有効化されているか確認してください。")

else:  # 防災モード
    tab1, tab2, tab3, tab4 = st.tabs(["🏥 避難所マップ", "🎯 最適化ルート", "🗾 ハザードマップ", "📢 防災情報"])
    
    with tab1:
        st.subheader("🏥 避難所マップ")
        
        col_map, col_control = st.columns([3, 1])
        
        with col_control:
            st.markdown("### 🚨 避難所情報")
            
            # 状態フィルター
            status_filter = st.radio(
                "表示する避難所",
                ["すべて", "開設中のみ", "待機中のみ"]
            )
            
            # フィルター適用
            if status_filter == "開設中のみ":
                filtered_df = disaster_df[disaster_df['状態'] == '開設中']
            elif status_filter == "待機中のみ":
                filtered_df = disaster_df[disaster_df['状態'] == '待機中']
            else:
                filtered_df = disaster_df
            
            # 避難所選択
            shelter = st.selectbox(
                "避難所を選択",
                ['選択してください'] + filtered_df['スポット名'].tolist()
            )
            
            if shelter != '選択してください':
                shelter_row = filtered_df[filtered_df['スポット名'] == shelter].iloc[0]
                shelter_coords = (shelter_row['緯度'], shelter_row['経度'])
                
                # 情報表示
                st.warning(f"🏥 **{shelter}**")
                
                # 距離表示
                distance = calculate_distance(
                    st.session_state.current_location[0],
                    st.session_state.current_location[1],
                    shelter_coords[0],
                    shelter_coords[1]
                )
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("距離", f"{distance:.2f} km")
                with col_b:
                    walk_time = int((distance / 4) * 60)
                    st.metric("徒歩", f"{walk_time}分")
                
                # 詳細情報
                with st.expander("📊 詳細情報", expanded=True):
                    st.write(f"**収容人数:** {shelter_row['収容人数']}名")
                    st.write(f"**状態:** {shelter_row['状態']}")
                    st.write(f"**説明:** {shelter_row['説明']}")
                
                # Google Mapsで開く
                maps_link = create_google_maps_link(
                    st.session_state.current_location,
                    shelter_coords,
                    'walking'
                )
                
                st.link_button(
                    "🚶 徒歩ルートを見る（Google Maps）",
                    maps_link,
                    use_container_width=True,
                    type="primary"
                )
                
                show_route = st.checkbox("地図上に直線を表示", value=True)
            else:
                shelter = None
                show_route = False
        
        with col_map:
            # 地図表示
            m = create_enhanced_map(
                filtered_df,
                st.session_state.current_location,
                selected_spot=shelter if shelter != '選択してください' else None,
                show_route=show_route
            )
            st_folium(m, width=700, height=600, key='disaster_map')

    with tab2:
        st.subheader("🎯 最適化避難ルート算出")

        st.info("複数の避難所を選択して、最短距離での巡回順序を自動で算出します。防災モードでは距離のみを考慮します。")

        # 複数避難所選択
        st.markdown("### 🏥 訪問したい避難所を選択")

        selected_shelters_names = st.multiselect(
            "複数の避難所を選択してください（2つ以上）",
            disaster_df['スポット名'].tolist(),
            default=[]
        )

        if len(selected_shelters_names) >= 2:
            # 選択された避難所のインデックスを取得
            selected_indices = []
            for shelter_name in selected_shelters_names:
                idx = disaster_df[disaster_df['スポット名'] == shelter_name].index[0]
                selected_indices.append(idx)

            if st.button("🎯 最適化避難ルートを算出", type="primary", use_container_width=True):
                # 最適化ルート算出（防災モード：最近傍法）
                route, total_dist, total_time = optimize_route_disaster(
                    st.session_state.current_location,
                    disaster_df,
                    selected_indices
                )

                st.session_state.optimized_route = {
                    'route': route,
                    'total_distance': total_dist,
                    'total_time': total_time,
                    'mode': 'walking'
                }

                st.success("✅ 最適化避難ルートを算出しました！")

            # 最適化ルート表示
            if st.session_state.optimized_route is not None:
                route_data = st.session_state.optimized_route
                route = route_data['route']
                total_dist = route_data['total_distance']
                total_time = route_data['total_time']

                st.markdown("---")
                st.markdown("### 📋 最適化された避難順序")

                # 統計情報
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("総移動距離", f"{total_dist:.2f} km")
                with col2:
                    hours = int(total_time // 60)
                    minutes = int(total_time % 60)
                    st.metric("総所要時間（徒歩）", f"{hours}時間{minutes}分")
                with col3:
                    st.metric("避難所数", f"{len(route)}箇所")

                st.markdown("---")

                # 訪問順序リスト
                for i, idx in enumerate(route, 1):
                    shelter = disaster_df.iloc[idx]

                    with st.expander(f"{i}. {shelter['スポット名']}", expanded=True):
                        col_a, col_b = st.columns([2, 1])
                        with col_a:
                            st.write(f"**説明:** {shelter['説明']}")
                            st.write(f"**収容人数:** {shelter['収容人数']}名")
                            st.write(f"**状態:** {shelter['状態']}")
                        with col_b:
                            # 前の地点からの距離
                            if i == 1:
                                prev_loc = st.session_state.current_location
                            else:
                                prev_shelter = disaster_df.iloc[route[i-2]]
                                prev_loc = [prev_shelter['緯度'], prev_shelter['経度']]

                            dist_from_prev = calculate_distance(
                                prev_loc[0], prev_loc[1],
                                shelter['緯度'], shelter['経度']
                            )
                            st.metric("移動距離", f"{dist_from_prev:.2f} km")
                            walk_time = int((dist_from_prev / 4) * 60)
                            st.metric("徒歩時間", f"{walk_time}分")

                st.markdown("---")
                st.markdown("### 🗺️ Google Mapで開く")

                # Google Maps複数経由地リンク生成
                if len(route) > 0:
                    # 出発地
                    origin = st.session_state.current_location

                    # 経由地と最終目的地
                    if len(route) == 1:
                        # 1箇所のみ
                        dest_shelter = disaster_df.iloc[route[0]]
                        destination = (dest_shelter['緯度'], dest_shelter['経度'])
                        waypoints = []
                    else:
                        # 2箇所以上
                        waypoints = []
                        for idx in route[:-1]:
                            shelter = disaster_df.iloc[idx]
                            waypoints.append((shelter['緯度'], shelter['経度']))

                        dest_shelter = disaster_df.iloc[route[-1]]
                        destination = (dest_shelter['緯度'], dest_shelter['経度'])

                    # リンク生成
                    maps_url = create_google_maps_multi_link(
                        origin,
                        waypoints,
                        destination,
                        'walking'
                    )

                    st.link_button(
                        "🚶 徒歩で最適化ルートを開く（Google Maps）",
                        maps_url,
                        use_container_width=True,
                        type="primary"
                    )

        elif len(selected_shelters_names) == 1:
            st.warning("⚠️ 2つ以上の避難所を選択してください。")
        else:
            st.info("👆 訪問したい避難所を2つ以上選択してください。")

    with tab3:
        st.subheader("🗾 ハザードマップ")
        
        hazard_type = st.selectbox(
            "ハザードマップの種類",
            ["洪水", "土砂災害", "地震", "津波"]
        )
        
        st.info(f"📍 {hazard_type}のハザードマップ情報")
        
        # プレースホルダー
        st.warning("⚠️ ハザードマップの画像データは別途準備が必要です")
        
        st.markdown("""
        ### 📌 確認事項
        - 最寄りの避難所を事前に確認
        - 避難経路を複数確認
        - 非常持ち出し袋の準備
        - 家族との連絡方法を決めておく
        """)
        
        # ハザードマップリンク
        st.link_button(
            "🗾 日田市ハザードマップ（公式）",
            "https://www.city.hita.oita.jp/",
            use_container_width=True
        )

    with tab4:
        st.subheader("📢 防災情報")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏪 営業中の店舗")
            
            stores = [
                ("ファミリーマート日田店", "✅ 営業中", "green"),
                ("ローソン日田中央店", "✅ 営業中", "green"),
                ("セブンイレブン日田店", "⚠️ 確認中", "orange"),
                ("マックスバリュ日田店", "✅ 営業中", "green")
            ]
            
            for store_name, status, color in stores:
                st.markdown(f":{color}[{status}] {store_name}")
        
        with col2:
            st.markdown("### 🥤 近くの自動販売機")
            st.info("現在地から500m圏内: 8台")
            st.success("すべて稼働中")
        
        st.divider()
        
        st.markdown("### 🎒 予算別防災グッズ提案")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            disaster_budget = st.selectbox(
                "予算を選択",
                ["3,000円以下", "3,000～10,000円", "10,000円以上"]
            )
        
        if st.button("💡 おすすめグッズを表示", use_container_width=True):
            st.success(f"✅ {disaster_budget}のおすすめ防災グッズ")
            
            if disaster_budget == "3,000円以下":
                items = [
                    "🔦 懐中電灯（LED）- 500円",
                    "🍫 非常食（3日分）- 1,500円",
                    "💧 保存水（2L×6本）- 800円"
                ]
            elif disaster_budget == "3,000～10,000円":
                items = [
                    "🎒 防災リュックセット - 5,000円",
                    "📻 手回し充電ラジオ - 2,500円",
                    "🏕️ 簡易トイレセット - 1,500円"
                ]
            else:
                items = [
                    "🏕️ テント・寝袋セット - 15,000円",
                    "🔋 大容量ポータブル電源 - 30,000円",
                    "🚰 浄水器 - 8,000円",
                    "🍱 長期保存食セット（1ヶ月分）- 12,000円"
                ]
            
            for item in items:
                st.write(f"• {item}")
        
        st.divider()
        
        # 緊急連絡先
        st.markdown("### 📞 緊急連絡先")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.error("**🚒 消防・救急**")
            st.markdown("### 119")
        with col2:
            st.info("**🚓 警察**")
            st.markdown("### 110")
        with col3:
            st.warning("**🏛️ 日田市役所**")
            st.markdown("### 0973-22-8888")

# フッター
st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.caption("© 2025 日田市総合案内コンシェルジュ")
with col2:
    st.caption("📧 お問い合わせ")
with col3:
    st.caption("🔒 プライバシーポリシー")

# 使い方ヒント
with st.expander("💡 使い方のヒント"):
    st.markdown("""
    ### 📖 日田市総合案内コンシェルジュの使い方

    #### 観光モードでできること
    1. **地図でスポットを確認**: マップタブで日田市内の観光スポットを一覧表示
    2. **目的地を選択**: 行きたい場所を選ぶと、距離と概算時間を表示
    3. **最適化ルート**: 複数スポットを選択すると、待ち時間と距離を考慮した最適な訪問順序を算出
    4. **スポット検索**: スポット一覧タブでキーワード検索や並び替えが可能
    5. **天気情報**: 天気タブで気象情報サイトへアクセス
    6. **イベント情報**: 月別にイベントを確認できます
    7. **人気ランキング**: 月別の人気観光地ランキングを確認
    8. **AIプラン提案**: Gemini APIを使って、予算・時間・興味に合わせた最適な観光プランを自動生成

    #### 防災モードでできること
    1. **最寄り避難所の確認**: 現在地から近い避難所を表示
    2. **最適化避難ルート**: 複数の避難所を選択すると、最短距離での巡回順序を算出
    3. **避難ルート**: 徒歩での避難ルートをGoogle Mapsで確認
    4. **開設状況の確認**: 避難所の開設状況と収容人数をリアルタイム表示
    5. **営業店舗情報**: 災害時の営業中コンビニ・スーパーを確認
    6. **防災グッズ提案**: 予算に応じた防災グッズのおすすめ

    #### 最適化ルート機能について
    - **観光モード**: 待ち時間と距離を考慮したスコアリングで最適な訪問順序を算出
    - **防災モード**: 最近傍法により最短距離での避難順序を算出
    - Google Maps連携で実際のルートをナビゲーション可能

    #### AIプラン提案機能について
    - Gemini API（gemini-2.0-flash-exp）を使用
    - ユーザーが自身のAPIキーを入力（セッション中のみ保持）
    - 予算、時間、興味、同行者に基づいた具体的なプランを生成

    #### 便利な機能
    - **現在地の設定**: サイドバーから緯度・経度を入力、またはプリセット位置から選択
    - **カテゴリーフィルター**: 歴史、自然、グルメ、体験など、カテゴリー別に絞り込み
    - **距離表示**: すべてのスポットに現在地からの距離を表示
    - **直線表示**: 地図上で現在地から目的地への直線を表示可能
    - **待ち時間・混雑状況**: 飲食店や観光地の待ち時間と混雑状況を確認可能

    #### Google Maps連携について
    - 実際の道路に沿ったルート案内は、「Google Mapsでルートを見る」ボタンから外部アプリで確認できます
    - 移動手段（車・徒歩・自転車・公共交通）を選択してからボタンを押してください
    - スマートフォンではGoogle Mapsアプリが自動的に開きます
    - 最適化ルートでは複数の経由地を含むルートをGoogle Mapsで開くことができます
    """)

# デバッグ情報（開発時のみ表示）
if st.checkbox("🔧 デバッグ情報を表示", value=False):
    st.json({
        "現在地": st.session_state.current_location,
        "モード": st.session_state.mode
    })