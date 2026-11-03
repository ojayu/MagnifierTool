# Magnifier Tool for Glyphs

[English](#english) | [日本語](#日本語)

---

## English

A tool plugin for [Glyphs](https://glyphsapp.com/) that shows a magnified view of the area around the cursor.

### Features

- Real-time 60 fps magnified view of the area around the cursor in a separate window
- The window stays open when you switch to other tools (Pen tool, etc.)
- Separate color / fill / stroke settings for the foreground and background layers
- Components are shown in their own color (fill + dashed outline), with separate color / fill / stroke settings
- All glyphs in the Edit tab (including multiple lines) are magnified in the same arrangement
- Metrics display that adapts to CJK and Latin glyphs
- Node size (S / M / L) and grid display toggles
- "Link Zoom" to follow the Edit tab zoom level
- Appearance setting (Follow System / Follow Glyphs / Light / Dark)
- Reflects Edit tab display options (background, metrics, guides, anchors, etc.)
- UI text follows the Glyphs language setting (Japanese / English)

### Installation

1. Download this repository (green "Code" button → "Download ZIP").
2. Double-click `Magnifier.glyphsTool`, or copy it into
   `~/Library/Application Support/Glyphs 3/Plugins/`
3. Restart Glyphs.

### Usage

1. Select Magnifier Tool in the toolbar to open its window.
2. The window stays open when you switch tools and keeps magnifying the area around the cursor in real time.
3. Color, fill and stroke can be set independently for the foreground and the background (colors are adjusted automatically for Dark Mode).
4. Check "Link Zoom" to make the magnification follow zooming in the Edit tab.
5. When all Edit tabs are closed, the tool goes into standby and returns to its previous position when you open a glyph again.

### Author

Yutaka Ozawa (mojipokke)

---

## 日本語

カーソル周辺を拡大表示する [Glyphs](https://glyphsapp.com/) 用ツールプラグインです。

### 主な機能

- 60fps のリアルタイム同期で、カーソル周辺を別ウィンドウに拡大表示
- 他のツール（ペンツール等）に切り替えてもウィンドウを保持
- 前面・背景レイヤーそれぞれに独立したカラー／塗り／線の設定
- コンポーネントをパスとは別の色（塗り＋破線の輪郭）で表示し、カラー／塗り／線を個別に設定可能
- 編集タブに並んだすべてのグリフ（複数行を含む）を、編集画面と同じ並びで拡大表示
- 和文・欧文に連動するメトリクス表示
- ポイントサイズ（小・中・大）、グリッド表示の切り替え
- 編集タブのズームに連動する「倍率連動」
- 外観設定（OS連動／アプリ連動／ライト／ダーク）
- 編集タブの表示オプション（背景、メトリクス、ガイド、アンカー等）を反映
- UI は Glyphs の言語設定（日本語／英語）に応じて自動で切り替え

### インストール

1. このリポジトリをダウンロードします（緑の「Code」ボタン →「Download ZIP」）。
2. `Magnifier.glyphsTool` をダブルクリックするか、次のフォルダにコピーします。
   `~/Library/Application Support/Glyphs 3/Plugins/`
3. Glyphs を再起動します。

### 使い方

1. ツールバーから Magnifier Tool を選択し、ウィンドウを開きます。
2. 他のツールに切り替えてもウィンドウは保持され、カーソル周辺をリアルタイムに拡大します。
3. 前面・背景それぞれ独立して、カラーや塗り・線の表示を切り替えられます（ダークモード時は自動で視認性の高い明度に調整）。
4. 「倍率連動」にチェックを入れると、編集タブのズームイン／アウトに連動して拡大率が変化します。
5. 編集タブをすべて閉じると自動で待機状態になり、再びグリフを開くと元の位置に復帰します。

### 作者

Yutaka Ozawa (mojipokke)
