# プロジェクト構造

## ディレクトリ構成
```
/workspaces/ss79test/
├── .git/                    # Gitリポジトリ
├── .serena/                 # Serenaメモリ
├── .claude/                 # Claude設定
├── README.md                # プロジェクトREADME
├── streamlit_app.py         # メインアプリケーション
├── 仕様書.md                 # 詳細な仕様書
├── requirements.txt         # 依存パッケージ
└── spots.xlsx               # スポットデータ（観光・防災）
```

## メインファイル: streamlit_app.py

### 主要な関数
- `load_spots_data()`: Excelファイルからデータ読み込み
- `calculate_distance()`: ヒュベニの公式で距離計算
- `optimize_route_tourism()`: 観光モード用最適化（待ち時間+距離）
- `optimize_route_disaster()`: 防災モード用最適化（最近傍法）
- `create_enhanced_map()`: Foliumマップ作成
- `create_google_maps_link()`: 単一目的地のGoogleマップリンク生成
- `create_google_maps_multi_link()`: 複数経由地のGoogleマップリンク生成

### セッション状態
- `mode`: 現在のモード（観光/防災）
- `current_location`: 現在地の緯度経度
- `selected_spots`: 選択されたスポット
- `optimized_route`: 最適化されたルート情報
- `gemini_api_key`: Gemini APIキー（セッション中のみ）

### UI構成
- サイドバー: モード選択、現在地設定、天気情報
- メインコンテンツ: タブによる機能切り替え
  - 観光モード: マップ、スポット一覧、最適化ルート、天気、イベント、ランキング、AIプラン
  - 防災モード: 避難所マップ、最適化ルート、ハザードマップ、防災情報
