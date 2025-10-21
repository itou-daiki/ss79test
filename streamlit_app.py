import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

# ページ設定
st.set_page_config(
    page_title="日田ナビ（Hita Navi）",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化
if 'mode' not in st.session_state:
    st.session_state.mode = '観光モード'
if 'language' not in st.session_state:
    st.session_state.language = '日本語'
if 'current_location' not in st.session_state:
    st.session_state.current_location = [33.3219, 130.9414]
if 'selected_spots' not in st.session_state:
    st.session_state.selected_spots = []

# データ読み込み関数
@st.cache_data
def load_spots_data():
    """Excelファイルからスポットデータを読み込む"""
    try:
        tourism_df = pd.read_excel('spots.xlsx', sheet_name='観光')
        disaster_df = pd.read_excel('spots.xlsx', sheet_name='防災')
        return tourism_df, disaster_df
    except FileNotFoundError:
        # サンプルデータを作成
        tourism_df = pd.DataFrame({
            '番号': [1, 2, 3, 4, 5, 6],
            'スポット名': ['豆田町', '日田温泉', '咸宜園', '天ヶ瀬温泉', '小鹿田焼の里', '大山ダム'],
            '緯度': [33.3219, 33.3200, 33.3240, 33.2967, 33.3500, 33.3800],
            '経度': [130.9414, 130.9400, 130.9430, 130.9167, 130.9600, 130.9200],
            '説明': ['江戸時代の町並みが残る歴史的な地区', '日田の名湯・温泉施設', 
                   '日本最大の私塾跡・歴史的教育施設', '自然豊かな温泉街', 
                   '伝統工芸の陶器の里', '美しい景観のダム'],
            'カテゴリー': ['観光地', '温泉', '歴史', '温泉', '観光地', '観光地'],
            '営業時間': ['終日', '9:00-21:00', '9:00-17:00', '終日', '9:00-17:00', '終日'],
            '料金': ['無料', '500円', '300円', '無料', '無料', '無料']
        })
        disaster_df = pd.DataFrame({
            '番号': [1, 2, 3, 4, 5],
            'スポット名': ['日田市役所（避難所）', '中央公民館', '総合体育館', '桂林公民館', '三花公民館'],
            '緯度': [33.3219, 33.3250, 33.3180, 33.3300, 33.3100],
            '経度': [130.9414, 130.9450, 130.9380, 130.9500, 130.9350],
            '説明': ['市役所・第一避難所', '中央地区の避難所', '大規模避難所', 
                   '桂林地区の避難所', '三花地区の避難所'],
            '収容人数': [500, 300, 800, 200, 250],
            '状態': ['開設中', '開設中', '開設中', '待機中', '待機中']
        })
        return tourism_df, disaster_df

# 距離計算関数
def calculate_distance(lat1, lng1, lat2, lng2):
    """2点間の距離を計算（km）"""
    R = 6371  # 地球の半径（km）
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)
    
    a = sin(delta_lat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

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

# Google Mapsリンク生成関数
def create_google_maps_link(origin, destination, mode='driving'):
    """Google Mapsの外部リンクを生成"""
    modes = {
        'driving': 'driving',
        'walking': 'walking',
        'bicycling': 'bicycling',
        'transit': 'transit'
    }
    base_url = "https://www.google.com/maps/dir/?api=1"
    link = f"{base_url}&origin={origin[0]},{origin[1]}&destination={destination[0]},{destination[1]}&travelmode={modes[mode]}"
    return link

# サイドバー
with st.sidebar:
    st.title("🗺️ 日田ナビ")
    st.caption("APIキー不要版")
    
    # 言語切替
    language = st.selectbox(
        "言語 / Language",
        ["日本語", "English"],
        key='language_selector'
    )
    st.session_state.language = language
    
    st.divider()
    
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
st.title(f"📍 {st.session_state.mode}")

# データ読み込み
tourism_df, disaster_df = load_spots_data()

# モードに応じた表示
if st.session_state.mode == '観光モード':
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗺️ マップ", "📋 スポット一覧", "🌤️ 天気", "📅 イベント", "💡 おすすめプラン"])
    
    with tab1:
        st.subheader("🗺️ 観光マップ")
        
        col_map, col_control = st.columns([3, 1])
        
        with col_control:
            st.markdown("### 🎯 目的地選択")
            
            # カテゴリーフィルター
            categories = ['すべて'] + sorted(tourism_df['カテゴリー'].unique().tolist())
            selected_category = st.selectbox("カテゴリー", categories)
            
            # フィルター適用
            if selected_category != 'すべて':
                filtered_df = tourism_df[tourism_df['カテゴリー'] == selected_category]
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
                    st.write(f"**カテゴリー:** {dest_row['カテゴリー']}")
                    st.write(f"**営業時間:** {dest_row['営業時間']}")
                    st.write(f"**料金:** {dest_row['料金']}")
                
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
                    st.caption(f"🏷️ {row['カテゴリー']} | 🕐 {row['営業時間']} | 💰 {row['料金']}")
                
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
        st.subheader("💡 おすすめプラン提案")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            plan_type = st.selectbox(
                "👥 プランタイプ",
                ["家族向け", "一人旅向け", "カップル向け", "グループ向け"]
            )
        with col2:
            budget = st.selectbox(
                "💰 予算",
                ["0～5,000円", "5,001～10,000円", "10,001～30,000円", "30,000円以上"]
            )
        with col3:
            duration = st.selectbox(
                "⏱️ 滞在時間",
                ["半日（3-4時間）", "1日（6-8時間）", "1泊2日", "2泊3日"]
            )
        
        if st.button("🎯 プランを提案", type="primary", use_container_width=True):
            st.success(f"✅ {plan_type} {budget} {duration}のプランを提案します")
            
            # サンプルプラン
            st.markdown("### 📋 提案されたプラン")
            
            plan_spots = tourism_df.sample(min(3, len(tourism_df)))
            
            for i, (idx, spot) in enumerate(plan_spots.iterrows(), 1):
                with st.expander(f"スポット{i}: {spot['スポット名']}", expanded=True):
                    col_a, col_b = st.columns([2, 1])
                    with col_a:
                        st.write(f"**説明:** {spot['説明']}")
                        st.write(f"**料金:** {spot['料金']}")
                        st.write(f"**おすすめ滞在時間:** 1-2時間")
                    with col_b:
                        maps_link = create_google_maps_link(
                            st.session_state.current_location,
                            (spot['緯度'], spot['経度']),
                            'driving'
                        )
                        st.link_button("🗺️ ルートを見る", maps_link, use_container_width=True)

else:  # 防災モード
    tab1, tab2, tab3 = st.tabs(["🏥 避難所マップ", "🗾 ハザードマップ", "📢 防災情報"])
    
    with tab1:
        st.subheader("🏥 避難所マップ")