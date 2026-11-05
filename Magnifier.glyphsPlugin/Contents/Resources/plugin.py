# encoding: utf-8
# Author: Yutaka Ozawa (mojipokke)
# Date: 2026-11-03 13:55:34 JST
# Version: v3.10.0
#MenuTitle: Magnifier

from __future__ import division, print_function, unicode_literals

__doc__ = """
Magnifier v3.10.0

概要:
カーソル周辺を拡大表示するGlyphs用プラグインです。
NSTimerを用いた60fpsのリアルタイム同期と、永続ウィンドウ管理を実装しています。
和文・欧文に連動するメトリクス表示、および背景レイヤーの独立した色/塗り/線設定に対応しています。
ポイントサイズの変更や、ダークモード/ライトモードのアピアランス設定に完全対応しています。

使い方:
1. 「ウインドウ」メニューから「Magnifier」を選択し、ウィンドウを開きます。
2. 他のツール（ペンツール等）に切り替えてもウィンドウは保持され、カーソル周辺をリアルタイムに拡大します。
3. 前面・背景それぞれ独立して、カラーや塗り・線の表示を切り替えることができます。
   （指定したカラーは、ダークモード時に自動で視認性の高い明度に調整されます）
4. ポイントサイズの変更や、OS・編集タブに連動するアピアランス設定が可能です。
5. 右下の設定ボタンから「倍率連動」にチェックを入れると、編集タブのズームイン/アウトに連動して拡大率が変化します。
6. 編集タブの表示オプション（背景、メトリクス、ガイド、アンカー等）のON/OFFが拡大画面にも反映されます。
7. 編集タブをすべて閉じると安全のために自動で待機状態になり、再びグリフを開くと元の位置に復帰します。
8. UIのテキストは Glyphs の言語設定（日本語／英語）に応じて自動で切り替わります。
9. コンポーネントは、パスとは別の色（塗り＋破線の輪郭）で表示されます。
   カラー・塗り・線は「コンポーネント」の行で個別に設定できます。
10. 編集タブに複数のグリフ（複数行）が並んでいる場合、それらもすべて
    編集画面と同じ並びで拡大表示されます（ポイント等はアクティブなグリフのみ）。

Overview:
A plugin for Glyphs that shows a magnified view of the area around the cursor.
It provides real-time 60 fps updates driven by NSTimer and a persistent window.
It displays metrics that adapt to CJK and Latin glyphs, and offers separate
color / fill / stroke settings for the background layer.
Node size can be changed, and Dark Mode / Light Mode appearance is fully supported.

Usage:
1. Choose Window > Magnifier to open its window.
2. The window stays open even when you switch to another tool (Pen tool, etc.)
   and keeps magnifying the area around the cursor in real time.
3. Color, fill and stroke display can be set independently for the foreground
   and the background.
   (In Dark Mode, the chosen colors are automatically adjusted to a brightness
   that stays easy to see.)
4. You can change the node size and set the appearance to follow the system
   or the Edit tab.
5. Open Settings in the lower-right corner and check "Link Zoom" to make the
   magnification follow zooming in and out in the Edit tab.
6. Display options of the Edit tab (background, metrics, guides, anchors, etc.)
   are also reflected in the magnified view when turned on or off.
7. When all Edit tabs are closed, the tool goes into standby for safety,
   and returns to its previous position when you open a glyph again.
8. The UI text switches automatically according to the Glyphs language
   setting (Japanese / English).
9. Components are drawn in a separate color from paths (fill + dashed outline).
   Their color, fill and stroke can be set in the "Component" row.
10. When the Edit tab shows several glyphs (on one or more lines), all of them
    are magnified in the same arrangement as in the Edit tab
    (nodes, anchors and metrics are shown for the active glyph only).
"""

import objc
from GlyphsApp import Glyphs, OFFCURVE, WINDOW_MENU
from GlyphsApp.plugins import GeneralPlugin
from GlyphsApp.UI import MenuItem
from vanilla import (
    FloatingWindow, Slider, EditText, CheckBox, TextBox, ColorWell, Button,
    PopUpButton, Group
)
from Cocoa import (
    NSView, NSColor, NSBezierPath, NSAffineTransform,
    NSGraphicsContext, NSMakeRect, NSMakePoint,
    NSLayoutConstraint, NSViewController, NSPopover,
    NSPopoverBehaviorSemitransient, NSMaxYEdge,
    NSNotificationCenter, NSEvent, NSTimer, NSImage, NSImageOnly, NSApp,
    NSAppearance, NSAppearanceNameAqua, NSAppearanceNameDarkAqua
)


def _L(en, ja):
    """Glyphs の言語設定に応じて英語/日本語の文字列を返す"""
    try:
        return Glyphs.localize({'en': en, 'ja': ja})
    except Exception:
        return en


class MagnifierView(NSView):
    # NSView の指定イニシャライザは initWithFrame: のため、init ではなくこちらを
    # オーバーライドする（macOS 26 Tahoe で init 経由だと内部の
    # _trackingAreaHelper が確保されず addSubview: で例外になるため）
    def initWithFrame_(self, frame):
        self = objc.super(MagnifierView, self).initWithFrame_(frame)
        if self:
            self.mousePosition = (0, 0)
            self.zoomLevel = 4.0
            self.activeLayer = None
            self.showFill = True
            self.showNodes = True
            self.showGrid = True
            self.showStroke = True
            self.fillColor = NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.4)
            self.bgShowFill = True
            self.bgShowStroke = True
            self.bgFillColor = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.8, 0.4, 0.4, 0.4
            )
            self.nodeSizeIndex = 1
            self.compShowFill = True
            self.compShowStroke = True
            self.compFillColor = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.1, 0.55, 0.55, 0.35
            )
            # 編集タブ内の他のグリフ: [(layer, dx, dy), ...]
            # dx, dy はアクティブレイヤー原点からのオフセット（フォント単位）
            self.otherLayers = []
        return self

    @objc.python_method
    def updateComponentInfo(self, compShowFill, compShowStroke, compFillColor):
        self.compShowFill = compShowFill
        self.compShowStroke = compShowStroke
        self.compFillColor = compFillColor

    @objc.python_method
    def updateOtherLayers(self, otherLayers):
        self.otherLayers = otherLayers or []

    @objc.python_method
    def drawOtherLayers_(self, context, minX, maxX, minY, maxY):
        """
        編集タブに並んでいる他のグリフを、編集画面と同じ位置関係で描画する。
        （ポイント・アンカー・メトリクスはアクティブなグリフのみ表示）
        """
        if not self.otherLayers:
            return
        fg_c = self.getAdaptiveColor_(self.fillColor)
        margin = 2000
        for (ol, dx, dy) in self.otherLayers:
            try:
                w = ol.width or 0
                # 表示範囲外のグリフは描画しない
                if dx + w + margin < minX or dx - margin > maxX:
                    continue
                if dy + margin < minY or dy - margin > maxY:
                    continue

                context.saveGraphicsState()
                t = NSAffineTransform.transform()
                t.translateXBy_yBy_(dx, dy)
                t.concat()

                self.drawComponents_(
                    ol, self.compFillColor,
                    self.compShowFill, self.compShowStroke, True
                )

                if self.showFill and ol.bezierPath:
                    if fg_c:
                        fg_c.set()
                    ol.bezierPath.fill()

                if self.showStroke and ol.paths:
                    if fg_c:
                        fg_c.colorWithAlphaComponent_(1.0).set()
                    else:
                        NSColor.textColor().set()
                    for path in ol.paths:
                        bp = path.bezierPath
                        if bp:
                            bp.setLineWidth_(1.0 / self.zoomLevel)
                            bp.stroke()

                context.restoreGraphicsState()
            except Exception:
                try:
                    context.restoreGraphicsState()
                except Exception:
                    pass

    @objc.python_method
    def drawComponents_(self, layer, color, showFill, showStroke, dashed):
        """
        レイヤー内のコンポーネントを描画する。
        コンポーネントと分かるよう、パスとは別色で塗り、線は破線で描く。
        """
        components = getattr(layer, 'components', None)
        if not components:
            return
        c = self.getAdaptiveColor_(color)
        for comp in components:
            try:
                cbp = comp.bezierPath
            except Exception:
                cbp = None
            if not cbp:
                continue
            bp = cbp.copy()  # Glyphs 側のパスに線幅などを書き込まないようコピーする
            if showFill:
                if c:
                    c.set()
                bp.fill()
            if showStroke:
                if c:
                    c.colorWithAlphaComponent_(1.0).set()
                else:
                    NSColor.textColor().set()
                bp.setLineWidth_(1.0 / self.zoomLevel)
                if dashed:
                    dash = [4.0 / self.zoomLevel, 2.0 / self.zoomLevel]
                    bp.setLineDash_count_phase_(dash, 2, 0.0)
                bp.stroke()

    @objc.python_method
    def updateInfo(self, pos, layer, zoom, showFill, showNodes, showGrid,
                   showStroke, fillColor, bgShowFill, bgShowStroke, bgFillColor,
                   nodeSizeIndex):
        self.mousePosition = pos
        self.activeLayer = layer
        self.zoomLevel = zoom
        self.showFill = showFill
        self.showNodes = showNodes
        self.showGrid = showGrid
        self.showStroke = showStroke
        self.fillColor = fillColor
        self.bgShowFill = bgShowFill
        self.bgShowStroke = bgShowStroke
        self.bgFillColor = bgFillColor
        self.nodeSizeIndex = nodeSizeIndex
        self.setNeedsDisplay_(True)

    @objc.python_method
    def getAdaptiveColor_(self, color):
        """
        アピアランスがダークモードの場合に、指定された色の明度を反転させて視認性を確保する
        """
        if not color:
            return None
        try:
            appearance_name = ""
            if hasattr(self, 'effectiveAppearance') and self.effectiveAppearance():
                appearance_name = self.effectiveAppearance().name()

            if 'Dark' in appearance_name:
                rgb = color.colorUsingColorSpaceName_("NSCalibratedRGBColorSpace")
                if rgb:
                    h = rgb.hueComponent()
                    s = rgb.saturationComponent()
                    b = rgb.brightnessComponent()
                    a = rgb.alphaComponent()

                    # ダークモード用に明度を反転し、彩度を少し抑える
                    new_b = max(b, 1.0 - b)
                    new_s = s * 0.8
                    return NSColor.colorWithCalibratedHue_saturation_brightness_alpha_(h, new_s, new_b, a)
        except Exception:
            pass
        return color

    def drawRect_(self, rect):
        try:
            NSColor.textBackgroundColor().set()
            NSBezierPath.fillRect_(rect)

            if self.activeLayer is None:
                return

            context = NSGraphicsContext.currentContext()
            context.saveGraphicsState()

            try:
                bounds = self.bounds()
                centerX = bounds.size.width / 2.0
                centerY = bounds.size.height / 2.0
                mouseX, mouseY = self.mousePosition

                transform = NSAffineTransform.transform()
                transform.translateXBy_yBy_(centerX, centerY)
                transform.scaleBy_(self.zoomLevel)
                transform.translateXBy_yBy_(-mouseX, -mouseY)
                transform.concat()

                visible_width = bounds.size.width / self.zoomLevel
                visible_height = bounds.size.height / self.zoomLevel
                minX = mouseX - visible_width - 1000
                maxX = mouseX + visible_width + 1000
                minY_screen = mouseY - visible_height - 1000
                maxY_screen = mouseY + visible_height + 1000

                # ------ 1. 背景レイヤー ------
                show_bg = Glyphs.defaults.get("showBackground", False)
                if show_bg and self.activeLayer.background:
                    context.saveGraphicsState()
                    bg_c = self.getAdaptiveColor_(self.bgFillColor)

                    if self.bgShowFill:
                        if bg_c:
                            bg_c.set()
                        if self.activeLayer.background.bezierPath:
                            self.activeLayer.background.bezierPath.fill()

                    if self.bgShowStroke:
                        if bg_c:
                            bg_c.set()
                        for path in self.activeLayer.background.paths:
                            bp = path.bezierPath
                            if bp:
                                bp.setLineWidth_(1.0 / self.zoomLevel)
                                bp.stroke()

                    # 背景レイヤー内のコンポーネント（背景色で、線は破線）
                    self.drawComponents_(
                        self.activeLayer.background, self.bgFillColor,
                        self.bgShowFill, self.bgShowStroke, True
                    )
                    context.restoreGraphicsState()

                # ------ 2. グリッド (メトリクスの下に描画) ------
                if self.showGrid and self.activeLayer.font():
                    grid = self.activeLayer.font().gridLength
                    if grid > 0 and (grid * self.zoomLevel) >= 5.0:
                        NSColor.textColor().colorWithAlphaComponent_(0.1).set()
                        gridPath = NSBezierPath.bezierPath()
                        range_units = (
                            max(bounds.size.width, bounds.size.height) / 2.0
                        ) / self.zoomLevel
                        minX_g = int((mouseX - range_units) / grid) * grid
                        maxX_g = int((mouseX + range_units) / grid) * grid + grid
                        minY_g = int((mouseY - range_units) / grid) * grid
                        maxY_g = int((mouseY + range_units) / grid) * grid + grid
                        x = minX_g
                        while x <= maxX_g:
                            gridPath.moveToPoint_(NSMakePoint(x, minY_g))
                            gridPath.lineToPoint_(NSMakePoint(x, maxY_g))
                            x += grid
                        y = minY_g
                        while y <= maxY_g:
                            gridPath.moveToPoint_(NSMakePoint(minX_g, y))
                            gridPath.lineToPoint_(NSMakePoint(maxX_g, y))
                            y += grid
                        gridPath.setLineWidth_(1.0 / self.zoomLevel)
                        gridPath.stroke()

                # ------ 3. アライメントゾーン & メトリクス ------
                show_metrics = Glyphs.defaults.get("showMetrics", False)
                if show_metrics and self.activeLayer.master:
                    master = self.activeLayer.master

                    zones_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        0.8, 0.8, 0.8, 0.4
                    )
                    zones_color.set()
                    for zone in master.alignmentZones:
                        z_pos = zone.position
                        z_size = zone.size
                        if z_size < 0:
                            z_pos += z_size
                            z_size = abs(z_size)
                        zone_rect = NSMakeRect(minX, z_pos, maxX - minX, z_size)
                        NSBezierPath.fillRect_(zone_rect)

                    metrics_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        0.7, 0.7, 0.7, 1.0
                    )
                    metrics_color.set()
                    metricsPath = NSBezierPath.bezierPath()

                    metrics_positions = []
                    if hasattr(self.activeLayer, 'metrics') and len(self.activeLayer.metrics) > 0:
                        for metric in self.activeLayer.metrics:
                            metrics_positions.append(metric.position)
                    else:
                        metrics_positions = [0, master.xHeight, master.capHeight,
                                             master.ascender, master.descender]

                    for y in metrics_positions:
                        metricsPath.moveToPoint_(NSMakePoint(minX, y))
                        metricsPath.lineToPoint_(NSMakePoint(maxX, y))

                    metricsPath.moveToPoint_(NSMakePoint(0, minY_screen))
                    metricsPath.lineToPoint_(NSMakePoint(0, maxY_screen))
                    metricsPath.moveToPoint_(NSMakePoint(self.activeLayer.width, minY_screen))
                    metricsPath.lineToPoint_(NSMakePoint(self.activeLayer.width, maxY_screen))

                    is_japanese = False
                    if self.activeLayer.parent and self.activeLayer.parent.script in [
                        "han", "hiragana", "katakana", "kana", "bopomofo", "hangul"
                    ]:
                        is_japanese = True

                    if is_japanese and metrics_positions:
                        max_y = max(metrics_positions)
                        min_y = min(metrics_positions)
                        center_x = self.activeLayer.width / 2.0
                        center_y = (max_y + min_y) / 2.0
                        tick = 20

                        metricsPath.moveToPoint_(NSMakePoint(center_x, max_y - tick))
                        metricsPath.lineToPoint_(NSMakePoint(center_x, max_y + tick))
                        metricsPath.moveToPoint_(NSMakePoint(center_x, min_y - tick))
                        metricsPath.lineToPoint_(NSMakePoint(center_x, min_y + tick))

                        metricsPath.moveToPoint_(NSMakePoint(0 - tick, center_y))
                        metricsPath.lineToPoint_(NSMakePoint(0 + tick, center_y))
                        metricsPath.moveToPoint_(NSMakePoint(self.activeLayer.width - tick, center_y))
                        metricsPath.lineToPoint_(NSMakePoint(self.activeLayer.width + tick, center_y))

                        metricsPath.moveToPoint_(NSMakePoint(0 - tick, 0))
                        metricsPath.lineToPoint_(NSMakePoint(0 + tick, 0))
                        metricsPath.moveToPoint_(NSMakePoint(self.activeLayer.width - tick, 0))
                        metricsPath.lineToPoint_(NSMakePoint(self.activeLayer.width + tick, 0))

                    metricsPath.setLineWidth_(1.0 / self.zoomLevel)
                    metricsPath.stroke()

                # ------ 4. ガイドライン ------
                show_guides = Glyphs.defaults.get("showGuidelines", False)
                if show_guides:
                    guide_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        0.7, 0.5, 0.8, 0.8
                    )
                    guide_color.set()
                    guides = list(self.activeLayer.guides)
                    if self.activeLayer.master:
                        guides.extend(self.activeLayer.master.guides)
                    for guide in guides:
                        context.saveGraphicsState()
                        pos = guide.position
                        angle = guide.angle
                        transform_guide = NSAffineTransform.transform()
                        transform_guide.translateXBy_yBy_(pos.x, pos.y)
                        transform_guide.rotateByDegrees_(angle)
                        transform_guide.concat()
                        line = NSBezierPath.bezierPath()
                        line.moveToPoint_(NSMakePoint(-10000, 0))
                        line.lineToPoint_(NSMakePoint(10000, 0))
                        line.setLineWidth_(1.0 / self.zoomLevel)
                        line.stroke()
                        context.restoreGraphicsState()

                # ------ 5. 編集タブ内の他のグリフ ------
                self.drawOtherLayers_(
                    context, minX, maxX, minY_screen, maxY_screen
                )

                # ------ 6. コンポーネント ------
                self.drawComponents_(
                    self.activeLayer, self.compFillColor,
                    self.compShowFill, self.compShowStroke, True
                )

                # ------ 7. メインパス (塗り) ------
                if self.showFill and self.activeLayer.bezierPath:
                    fg_c = self.getAdaptiveColor_(self.fillColor)
                    if fg_c:
                        fg_c.set()
                    self.activeLayer.bezierPath.fill()

                # ------ 8. メインパス (線) ------
                if self.showStroke and self.activeLayer.paths:
                    fg_c = self.getAdaptiveColor_(self.fillColor)
                    if fg_c:
                        fg_c.colorWithAlphaComponent_(1.0).set()
                    else:
                        NSColor.textColor().set()

                    for path in self.activeLayer.paths:
                        bp = path.bezierPath
                        if bp:
                            bp.setLineWidth_(1.0 / self.zoomLevel)
                            bp.stroke()

                # ------ 9. アンカー ------
                show_anchors = Glyphs.defaults.get("showAnchors", False)
                if show_anchors:
                    anchor_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        0.9, 0.3, 0.3, 1.0
                    )
                    anchor_color.set()
                    s = 4.0 / self.zoomLevel
                    for anchor in self.activeLayer.anchors:
                        pos = anchor.position
                        context.saveGraphicsState()
                        transform_anchor = NSAffineTransform.transform()
                        transform_anchor.translateXBy_yBy_(pos.x, pos.y)
                        transform_anchor.concat()
                        p = NSBezierPath.bezierPath()
                        p.moveToPoint_(NSMakePoint(-s, 0))
                        p.lineToPoint_(NSMakePoint(0, s))
                        p.lineToPoint_(NSMakePoint(s, 0))
                        p.lineToPoint_(NSMakePoint(0, -s))
                        p.closePath()
                        p.fill()
                        context.restoreGraphicsState()

                # ------ 10. ノード (ポイント) ------
                if self.showNodes and self.activeLayer.paths:
                    base_on = [2.0, 2.8, 4.0]
                    base_off = [1.2, 1.8, 2.5]
                    idx = getattr(self, 'nodeSizeIndex', 1)
                    if idx < 0 or idx > 2:
                        idx = 1

                    onCurveRadius = base_on[idx] / self.zoomLevel
                    offCurveRadius = base_off[idx] / self.zoomLevel
                    NSColor.lightGrayColor().set()
                    for path in self.activeLayer.paths:
                        nodes = path.nodes
                        nodeCount = len(nodes)
                        if nodeCount > 1:
                            for i in range(nodeCount):
                                node = nodes[i]
                                prevNode = nodes[i - 1]
                                if (node.type == OFFCURVE and
                                        prevNode.type != OFFCURVE) or \
                                   (node.type != OFFCURVE and
                                        prevNode.type == OFFCURVE):
                                    handlePath = NSBezierPath.bezierPath()
                                    handlePath.moveToPoint_(
                                        NSMakePoint(prevNode.x, prevNode.y)
                                    )
                                    handlePath.lineToPoint_(
                                        NSMakePoint(node.x, node.y)
                                    )
                                    handlePath.setLineWidth_(1.0 / self.zoomLevel)
                                    handlePath.stroke()
                    for path in self.activeLayer.paths:
                        for node in path.nodes:
                            if node.type == OFFCURVE:
                                rect = NSMakeRect(
                                    node.x - offCurveRadius, node.y - offCurveRadius,
                                    offCurveRadius * 2, offCurveRadius * 2
                                )
                                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                                    0.5, 0.5, 0.5, 1.0
                                ).set()
                                NSBezierPath.bezierPathWithOvalInRect_(rect).fill()
                            else:
                                rect = NSMakeRect(
                                    node.x - onCurveRadius, node.y - onCurveRadius,
                                    onCurveRadius * 2, onCurveRadius * 2
                                )
                                if node.smooth:
                                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                                        0.2, 0.6, 0.2, 1.0
                                    ).set()
                                    NSBezierPath.bezierPathWithOvalInRect_(rect).fill()
                                else:
                                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                                        0.1, 0.3, 0.8, 1.0
                                    ).set()
                                    NSBezierPath.fillRect_(rect)

            except Exception:
                pass
            finally:
                context.restoreGraphicsState()

            NSColor.redColor().set()
            crossPath = NSBezierPath.bezierPath()
            crossLen = 10
            crossPath.moveToPoint_(NSMakePoint(centerX - crossLen, centerY))
            crossPath.lineToPoint_(NSMakePoint(centerX + crossLen, centerY))
            crossPath.moveToPoint_(NSMakePoint(centerX, centerY - crossLen))
            crossPath.lineToPoint_(NSMakePoint(centerX, centerY + crossLen))
            crossPath.setLineWidth_(1.0)
            crossPath.stroke()
        except Exception:
            pass


class MagnifierPlugin(GeneralPlugin):
    @objc.python_method
    def settings(self):
        self.name = 'Magnifier'
        self._window = None
        self._settings = None
        self._settingsPopover = None
        self._lastMousePos = None
        self._timer = None
        self._auto_hidden = False

        self.pref_zoom = "com.mojipokke.MagnifierTool.zoom"
        self.pref_fill = "com.mojipokke.MagnifierTool.showFill"
        self.pref_nodes = "com.mojipokke.MagnifierTool.showNodes"
        self.pref_node_size = "com.mojipokke.MagnifierTool.nodeSize"
        self.pref_grid = "com.mojipokke.MagnifierTool.showGrid"
        self.pref_stroke = "com.mojipokke.MagnifierTool.showStroke"
        self.pref_color = "com.mojipokke.MagnifierTool.fillColor"
        self.pref_frame = "com.mojipokke.MagnifierTool.windowFrame"
        self.pref_link = "com.mojipokke.MagnifierTool.linkZoom"
        self.pref_bg_fill = "com.mojipokke.MagnifierTool.bgShowFill"
        self.pref_bg_stroke = "com.mojipokke.MagnifierTool.bgShowStroke"
        self.pref_bg_color = "com.mojipokke.MagnifierTool.bgFillColor"
        self.pref_comp_fill = "com.mojipokke.MagnifierTool.compShowFill"
        self.pref_comp_stroke = "com.mojipokke.MagnifierTool.compShowStroke"
        self.pref_comp_color = "com.mojipokke.MagnifierTool.compFillColor"
        self.pref_appearance = "com.mojipokke.MagnifierTool.appearance"

    @objc.python_method
    def start(self):
        self._menuItem = MenuItem(self.name, action=self.showWindow_, target=self)
        Glyphs.menu[WINDOW_MENU].append(self._menuItem)

    @objc.python_method
    def startTimer(self):
        if not hasattr(self, '_timer') or self._timer is None:
            self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0 / 60.0, self, "timerTick:", None, True
            )

    @objc.python_method
    def stopTimer(self):
        if hasattr(self, '_timer') and self._timer:
            self._timer.invalidate()
            self._timer = None

    def showWindow_(self, sender):
        self._auto_hidden = False
        self.openWindow()
        self._window.getNSWindow().makeKeyAndOrderFront_(self)
        self.updateMagnifierView(force=True)

    def interfaceUpdated_(self, notification):
        self.updateMagnifierView(force=True)

    @objc.python_method
    def windowShouldClose(self, sender):
        self._auto_hidden = False
        self.saveDefaults(save_frame=True)
        self.stopTimer()
        self.closeSettings()
        if self._window:
            self._window.hide()
        return False

    @objc.python_method
    def windowDidClose(self, sender):
        self.stopTimer()
        self.closeSettings()
        self._window = None
        self._settings = None
        self._settingsPopover = None

    @objc.python_method
    def windowDidMove(self, sender):
        self.saveDefaults()

    @objc.python_method
    def windowDidResize(self, sender):
        if self._window and hasattr(self, '_magnifierView'):
            self._magnifierView.setNeedsDisplay_(True)
        self.saveDefaults()

    def timerTick_(self, timer):
        try:
            self.updateMagnifierView(force=False)
        except Exception:
            pass

    @objc.python_method
    def applyAppearance(self, evc=None):
        if not hasattr(self, '_window') or not self._window:
            return
        nswindow = self._window.getNSWindow()
        idx = int(self._settings.appearancePopUp.get())

        target_appearance = None
        if idx == 0:  # OS連動
            target_appearance = None
        elif idx == 1:  # アプリ連動 (編集ビュー連動)
            if evc and hasattr(evc, 'graphicView') and evc.graphicView():
                gv = evc.graphicView()
                if hasattr(gv, 'effectiveAppearance'):
                    target_appearance = gv.effectiveAppearance()
            if target_appearance is None:
                if hasattr(NSApp, 'effectiveAppearance'):
                    target_appearance = NSApp.effectiveAppearance()
                else:
                    target_appearance = NSApp.appearance()
        elif idx == 2:  # ライト
            target_appearance = NSAppearance.appearanceNamed_(NSAppearanceNameAqua)
        elif idx == 3:  # ダーク
            target_appearance = NSAppearance.appearanceNamed_(NSAppearanceNameDarkAqua)

        if nswindow.appearance() != target_appearance:
            nswindow.setAppearance_(target_appearance)
        if self._settingsPopover.appearance() != target_appearance:
            self._settingsPopover.setAppearance_(target_appearance)

    @objc.python_method
    def appearanceCallback(self, sender):
        doc = Glyphs.currentDocument
        evc = None
        if doc and doc.windowController():
            evc = doc.windowController().activeEditViewController()
        self.applyAppearance(evc)
        self.saveDefaults()

    @objc.python_method
    def openWindow(self):
        if self._window:
            try:
                if not self._window.getNSWindow().isVisible():
                    def_frame = Glyphs.defaults.get(self.pref_frame)
                    if def_frame and isinstance(def_frame, str):
                        self._window.getNSWindow().setFrameFromString_(def_frame)
                    self._window.show()
                    if def_frame and isinstance(def_frame, str):
                        self._window.getNSWindow().setFrameFromString_(def_frame)
                self.startTimer()
                return
            except Exception:
                self._window = None

        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self, "GSUpdateInterface", None)
        nc.addObserver_selector_name_object_(
            self, "interfaceUpdated:", "GSUpdateInterface", None
        )

        self._window = FloatingWindow(
            (100, 100, 280, 300), self.name, minSize=(220, 180)
        )
        self._window.getNSWindow().setReleasedWhenClosed_(False)

        def_frame = Glyphs.defaults.get(self.pref_frame)
        if def_frame and isinstance(def_frame, str):
            self._window.getNSWindow().setFrameFromString_(def_frame)

        self._window.bind("shouldClose", self.windowShouldClose)
        self._window.bind("close", self.windowDidClose)
        self._window.bind("resize", self.windowDidResize)
        self._window.bind("move", self.windowDidMove)

        self._magnifierView = MagnifierView.alloc().initWithFrame_(NSMakeRect(0, 0, 0, 0))
        self._magnifierView.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self._window.getNSWindow().contentView().addSubview_(self._magnifierView)

        def_zoom = Glyphs.defaults.get(self.pref_zoom, 4.0)
        def_fill = Glyphs.defaults.get(self.pref_fill, True)
        def_nodes = Glyphs.defaults.get(self.pref_nodes, True)
        def_node_size = Glyphs.defaults.get(self.pref_node_size, 1)
        def_grid = Glyphs.defaults.get(self.pref_grid, True)
        def_stroke = Glyphs.defaults.get(self.pref_stroke, True)
        def_link = Glyphs.defaults.get(self.pref_link, False)
        def_color_arr = Glyphs.defaults.get(self.pref_color, [0.0, 0.0, 0.0, 0.4])

        def_bg_fill = Glyphs.defaults.get(self.pref_bg_fill, True)
        def_bg_stroke = Glyphs.defaults.get(self.pref_bg_stroke, True)
        def_bg_color_arr = Glyphs.defaults.get(
            self.pref_bg_color, [0.8, 0.4, 0.4, 0.4]
        )
        def_comp_fill = Glyphs.defaults.get(self.pref_comp_fill, True)
        def_comp_stroke = Glyphs.defaults.get(self.pref_comp_stroke, True)
        def_comp_color_arr = Glyphs.defaults.get(
            self.pref_comp_color, [0.1, 0.55, 0.55, 0.35]
        )
        def_appearance = Glyphs.defaults.get(self.pref_appearance, 0)

        try:
            default_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                def_color_arr[0], def_color_arr[1],
                def_color_arr[2], def_color_arr[3]
            )
        except Exception:
            default_color = NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.4)

        try:
            default_bg_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                def_bg_color_arr[0], def_bg_color_arr[1],
                def_bg_color_arr[2], def_bg_color_arr[3]
            )
        except Exception:
            default_bg_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.8, 0.4, 0.4, 0.4
            )

        try:
            default_comp_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                def_comp_color_arr[0], def_comp_color_arr[1],
                def_comp_color_arr[2], def_comp_color_arr[3]
            )
        except Exception:
            default_comp_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.1, 0.55, 0.55, 0.35
            )

        # The popover keeps its controls alive between presentations, so defaults,
        # callbacks and the timer use the same state even while it is closed.
        self._settings = Group((0, 0, 400, 264))
        settings = self._settings
        controller = NSViewController.alloc().init()
        controller.setView_(settings.getNSView())
        self._settingsPopover = NSPopover.alloc().init()
        self._settingsPopover.setContentViewController_(controller)
        self._settingsPopover.setContentSize_((400, 264))
        # Allow the shared color panel to stay open while editing a color well.
        self._settingsPopover.setBehavior_(NSPopoverBehaviorSemitransient)

        settings.lblForeground = TextBox("auto", _L("Foreground:", "前面:"))
        settings.colorWell = ColorWell(
            "auto", color=default_color, callback=self.uiCallback
        )
        settings.checkFill = CheckBox(
            "auto", _L("Fill", "塗り"), value=def_fill, callback=self.uiCallback
        )
        settings.checkStroke = CheckBox(
            "auto", _L("Stroke", "線"), value=def_stroke, callback=self.uiCallback
        )
        settings.lblComponent = TextBox("auto", _L("Component:", "コンポーネント:"))
        settings.compColorWell = ColorWell(
            "auto", color=default_comp_color, callback=self.uiCallback
        )
        settings.compCheckFill = CheckBox(
            "auto", _L("Fill", "塗り"), value=def_comp_fill, callback=self.uiCallback
        )
        settings.compCheckStroke = CheckBox(
            "auto", _L("Stroke", "線"), value=def_comp_stroke, callback=self.uiCallback
        )
        settings.lblBackground = TextBox("auto", _L("Background:", "背景:"))
        settings.bgColorWell = ColorWell(
            "auto", color=default_bg_color, callback=self.uiCallback
        )
        settings.bgCheckFill = CheckBox(
            "auto", _L("Fill", "塗り"), value=def_bg_fill, callback=self.uiCallback
        )
        settings.bgCheckStroke = CheckBox(
            "auto", _L("Stroke", "線"), value=def_bg_stroke, callback=self.uiCallback
        )
        settings.checkNodes = CheckBox(
            "auto", _L("Nodes", "ポイント"), value=def_nodes, callback=self.uiCallback
        )
        settings.nodeSizePopUp = PopUpButton(
            "auto", [_L("S", "小"), _L("M", "中"), _L("L", "大")],
            callback=self.uiCallback
        )
        settings.nodeSizePopUp.set(def_node_size)
        settings.checkGrid = CheckBox(
            "auto", _L("Grid", "グリッド"), value=def_grid, callback=self.uiCallback
        )
        settings.checkLink = CheckBox(
            "auto", _L("Link Zoom", "倍率連動"), value=def_link, callback=self.uiCallback
        )
        settings.checkLink.getNSButton().setToolTip_(_L(
            "Scale the magnification with the Edit view zoom",
            "編集タブのズームに連動して拡大率を変化させます"
        ))
        settings.lblAppearance = TextBox("auto", _L("Appearance:", "外観:"))
        settings.appearancePopUp = PopUpButton(
            "auto",
            [
                _L("Follow System", "OS連動"),
                _L("Follow Glyphs", "アプリ連動"),
                _L("Light", "ライト"),
                _L("Dark", "ダーク"),
            ],
            callback=self.appearanceCallback
        )
        settings.appearancePopUp.set(def_appearance)
        settings.btnReset = Button(
            "auto", _L("Reset", "リセット"), callback=self.resetCallback
        )
        settings.versionText = TextBox(
            "auto", "v3.10.0", sizeStyle='mini', alignment='right'
        )
        self.layoutSettings()

        self._window.slider = Slider(
            "auto", minValue=1.0, maxValue=50.0, value=def_zoom, callback=self.uiCallback
        )
        self._window.slider.getNSSlider().setToolTip_(_L("Zoom", "倍率"))
        self._window.zoomText = EditText(
            "auto", text=f"{def_zoom:.1f}", callback=self.textCallback, continuous=False
        )
        self._window.zoomText.getNSTextField().setToolTip_(_L("Zoom", "倍率"))
        self._window.zoomText.getNSTextField().setAccessibilityLabel_(_L("Zoom", "倍率"))
        self._window.settingsButton = Button(
            "auto", "", callback=self.settingsCallback
        )
        settingsButton = self._window.settingsButton.getNSButton()
        settingsButton.setBordered_(False)
        settingsButton.setImage_(NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "gearshape", _L("Settings", "設定")
        ))
        settingsButton.setImagePosition_(NSImageOnly)
        settingsButton.setToolTip_(_L("Settings", "設定"))
        settingsButton.setAccessibilityLabel_(_L("Settings", "設定"))
        self.layoutWindow()

        doc = Glyphs.currentDocument
        evc = None
        if doc and doc.windowController():
            evc = doc.windowController().activeEditViewController()
        self.applyAppearance(evc)
        self._window.open()

        if def_frame and isinstance(def_frame, str):
            self._window.getNSWindow().setFrameFromString_(def_frame)

        self.startTimer()

    @objc.python_method
    def layoutWindow(self):
        content = self._window.getNSWindow().contentView()
        view = self._magnifierView
        slider = self._window.slider.getNSSlider()
        zoomText = self._window.zoomText.getNSTextField()
        button = self._window.settingsButton.getNSButton()
        NSLayoutConstraint.activateConstraints_([
            view.leadingAnchor().constraintEqualToAnchor_(content.leadingAnchor()),
            view.trailingAnchor().constraintEqualToAnchor_(content.trailingAnchor()),
            view.topAnchor().constraintEqualToAnchor_(content.topAnchor()),
            view.bottomAnchor().constraintEqualToAnchor_(content.bottomAnchor()),
            button.trailingAnchor().constraintEqualToAnchor_constant_(content.trailingAnchor(), -6),
            button.bottomAnchor().constraintEqualToAnchor_constant_(content.bottomAnchor(), -6),
            button.widthAnchor().constraintEqualToConstant_(32),
            button.heightAnchor().constraintEqualToConstant_(24),
            slider.leadingAnchor().constraintEqualToAnchor_constant_(content.leadingAnchor(), 10),
            slider.trailingAnchor().constraintEqualToAnchor_constant_(zoomText.leadingAnchor(), -8),
            slider.centerYAnchor().constraintEqualToAnchor_(button.centerYAnchor()),
            zoomText.trailingAnchor().constraintEqualToAnchor_constant_(button.leadingAnchor(), -8),
            zoomText.centerYAnchor().constraintEqualToAnchor_(button.centerYAnchor()),
            zoomText.widthAnchor().constraintEqualToConstant_(50),
            zoomText.heightAnchor().constraintEqualToConstant_(22),
            #slider.heightAnchor().constraintEqualToConstant_(20),
        ])

    @objc.python_method
    def layoutSettings(self):
        settings = self._settings
        rules = [
            "V:|-16-[colorWell(26)]-8-[compColorWell(26)]-8-[bgColorWell(26)]"
            "-12-[checkNodes(24)]-8-[checkLink(24)]-8-[appearancePopUp(26)]"
            "-12-[btnReset(24)]-16-|",
            "H:|-16-[checkNodes]-[nodeSizePopUp(60)]-20-[checkGrid]-(>=16)-|",
            "H:|-16-[checkLink]-(>=16)-|",
            "H:|-16-[lblAppearance]-[appearancePopUp]-(>=16)-|",
            "H:|-16-[btnReset(>=80)]-(>=16)-[versionText]-16-|",
        ]
        # Shared column widths follow the longest localized label's intrinsic size.
        rows = [
            ('lblForeground', 'colorWell', 'checkFill', 'checkStroke'),
            ('lblComponent', 'compColorWell', 'compCheckFill', 'compCheckStroke'),
            ('lblBackground', 'bgColorWell', 'bgCheckFill', 'bgCheckStroke'),
        ]
        for label, well, fill, stroke in rows:
            labelWidth = '' if label == 'lblForeground' else '(==lblForeground)'
            fillWidth = '' if fill == 'checkFill' else '(==checkFill)'
            strokeWidth = '' if stroke == 'checkStroke' else '(==checkStroke)'
            rules.append(
                "H:|-16-[%s%s]-[%s(44)]-[%s%s]-[%s%s]-(>=16)-|"
                % (label, labelWidth, well, fill, fillWidth, stroke, strokeWidth)
            )
        alignedRows = [
            (settings.colorWell, (settings.lblForeground, settings.checkFill, settings.checkStroke)),
            (settings.compColorWell, (settings.lblComponent, settings.compCheckFill, settings.compCheckStroke)),
            (settings.bgColorWell, (settings.lblBackground, settings.bgCheckFill, settings.bgCheckStroke)),
            (settings.checkNodes, (settings.nodeSizePopUp, settings.checkGrid)),
            (settings.appearancePopUp, (settings.lblAppearance,)),
            (settings.btnReset, (settings.versionText,)),
        ]
        for reference, controls in alignedRows:
            for control in controls:
                rules.append(dict(
                    view1=control, attribute1='centerY',
                    view2=reference, attribute2='centerY'
                ))
        settings.addAutoPosSizeRules(rules)

    @objc.python_method
    def settingsCallback(self, sender):
        if self._settingsPopover.isShown():
            self.closeSettings()
        else:
            button = sender.getNSButton()
            self._settingsPopover.showRelativeToRect_ofView_preferredEdge_(
                button.bounds(), button, NSMaxYEdge
            )

    @objc.python_method
    def closeSettings(self):
        if self._settingsPopover and self._settingsPopover.isShown():
            self._settingsPopover.close()

    @objc.python_method
    def saveDefaults(self, save_frame=True):
        if not hasattr(self, '_window') or self._window is None:
            return
        if self._window.getNSWindow() is None:
            return

        try:
            Glyphs.defaults[self.pref_zoom] = float(self._window.slider.get())
            Glyphs.defaults[self.pref_fill] = bool(self._settings.checkFill.get())
            Glyphs.defaults[self.pref_nodes] = bool(self._settings.checkNodes.get())
            Glyphs.defaults[self.pref_node_size] = int(self._settings.nodeSizePopUp.get())
            Glyphs.defaults[self.pref_grid] = bool(self._settings.checkGrid.get())
            Glyphs.defaults[self.pref_stroke] = bool(self._settings.checkStroke.get())
            Glyphs.defaults[self.pref_link] = bool(self._settings.checkLink.get())
            Glyphs.defaults[self.pref_bg_fill] = bool(self._settings.bgCheckFill.get())
            Glyphs.defaults[self.pref_bg_stroke] = bool(self._settings.bgCheckStroke.get())
            Glyphs.defaults[self.pref_appearance] = int(self._settings.appearancePopUp.get())
            Glyphs.defaults[self.pref_comp_fill] = bool(self._settings.compCheckFill.get())
            Glyphs.defaults[self.pref_comp_stroke] = bool(self._settings.compCheckStroke.get())

            c = self._settings.colorWell.get()
            if c:
                c_rgb = c.colorUsingColorSpaceName_("NSCalibratedRGBColorSpace")
                if c_rgb:
                    r = c_rgb.redComponent()
                    g = c_rgb.greenComponent()
                    b = c_rgb.blueComponent()
                    a = c_rgb.alphaComponent()
                    Glyphs.defaults[self.pref_color] = [r, g, b, a]

            bc = self._settings.bgColorWell.get()
            if bc:
                bc_rgb = bc.colorUsingColorSpaceName_("NSCalibratedRGBColorSpace")
                if bc_rgb:
                    br = bc_rgb.redComponent()
                    bg = bc_rgb.greenComponent()
                    bb = bc_rgb.blueComponent()
                    ba = bc_rgb.alphaComponent()
                    Glyphs.defaults[self.pref_bg_color] = [br, bg, bb, ba]

            cc = self._settings.compColorWell.get()
            if cc:
                cc_rgb = cc.colorUsingColorSpaceName_("NSCalibratedRGBColorSpace")
                if cc_rgb:
                    Glyphs.defaults[self.pref_comp_color] = [
                        cc_rgb.redComponent(), cc_rgb.greenComponent(),
                        cc_rgb.blueComponent(), cc_rgb.alphaComponent()
                    ]
        except Exception:
            pass

        if save_frame:
            try:
                frame_str = self._window.getNSWindow().stringWithSavedFrame()
                if frame_str:
                    Glyphs.defaults[self.pref_frame] = frame_str
            except Exception:
                pass

    @objc.python_method
    def resetCallback(self, sender):
        if not hasattr(self, '_window'):
            return
        if self._window is None:
            return
        self._window.slider.set(4.0)
        self._window.zoomText.set("4.0")
        self._settings.checkFill.set(True)
        self._settings.checkNodes.set(True)
        self._settings.nodeSizePopUp.set(1)
        self._settings.checkGrid.set(True)
        self._settings.checkStroke.set(True)
        self._settings.checkLink.set(False)
        self._settings.appearancePopUp.set(0)

        default_color = NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.4)
        self._settings.colorWell.set(default_color)

        self._settings.bgCheckFill.set(True)
        self._settings.bgCheckStroke.set(True)
        default_bg_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(
            0.8, 0.4, 0.4, 0.4
        )
        self._settings.bgColorWell.set(default_bg_color)

        self._settings.compCheckFill.set(True)
        self._settings.compCheckStroke.set(True)
        self._settings.compColorWell.set(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.1, 0.55, 0.55, 0.35)
        )

        self.closeSettings()
        self._window.setPosSize((100, 100, 280, 300))
        self._window.center()

        doc = Glyphs.currentDocument
        evc = None
        if doc and doc.windowController():
            evc = doc.windowController().activeEditViewController()
        self.applyAppearance(evc)
        self.saveDefaults()
        self.updateMagnifierView(force=True)

    @objc.python_method
    def uiCallback(self, sender):
        if not hasattr(self, '_window') or not hasattr(self, '_magnifierView'):
            return
        if self._window is None:
            return
        zoom = float(self._window.slider.get())
        if sender == self._window.slider:
            self._window.zoomText.set(f"{zoom:.1f}")
        self.saveDefaults()
        self.updateMagnifierView(force=True)

    @objc.python_method
    def textCallback(self, sender):
        try:
            zoom = float(sender.get())
            zoom = max(1.0, min(50.0, zoom))
            if hasattr(self, '_window'):
                self._window.slider.set(zoom)
                sender.set(f"{zoom:.1f}")
            self.saveDefaults()
            self.updateMagnifierView(force=True)
        except ValueError:
            if hasattr(self, '_window'):
                current_zoom = self._window.slider.get()
                sender.set(f"{current_zoom:.1f}")

    @objc.python_method
    def _tabLayers(self, evc):
        """編集タブに表示されているレイヤーの一覧（改行等も含む）"""
        layers = None
        try:
            layers = list(evc.composedLayers)
        except Exception:
            layers = None
        if not layers:
            try:
                layers = list(evc.graphicView().layoutManager().cachedLayers())
            except Exception:
                layers = []
        return layers

    @objc.python_method
    def _positionScaleFactor(self, layers, positions, gv):
        """
        cachedPositionAtIndex_ の値が表示倍率込みかどうかを、
        同じ行で隣り合うグリフの間隔とグリフ幅の比から判定する。
        """
        try:
            scale = float(gv.scale())
        except Exception:
            return 1.0
        if abs(scale - 1.0) < 0.05:
            return 1.0
        for i in range(len(layers) - 1):
            try:
                w = float(getattr(layers[i], 'width', 0) or 0)
                if w < 50:
                    continue
                if abs(positions[i + 1].y - positions[i].y) > 0.5:
                    continue
                dx = positions[i + 1].x - positions[i].x
                if dx <= 0:
                    continue
                ratio = dx / w
                return scale if abs(ratio - scale) < abs(ratio - 1.0) else 1.0
            except Exception:
                continue
        return 1.0

    @objc.python_method
    def collectOtherLayers(self, evc, activeLayer, force=False):
        """
        編集タブ内のアクティブ以外のグリフと、アクティブなグリフ原点からの
        オフセットを返す。重いのでタブ内容・アクティブ位置・倍率が変わった
        ときだけ再計算する。
        """
        gv = evc.graphicView()
        activeIdx = None
        try:
            activeIdx = int(gv.activeIndex())
        except Exception:
            activeIdx = None
        try:
            scale = float(gv.scale())
        except Exception:
            scale = 1.0

        key = (evc, activeLayer, activeIdx, scale)
        if not force and getattr(self, '_otherLayersKey', None) == key:
            return self._otherLayersCache

        result = []
        try:
            layers = self._tabLayers(evc)
            if len(layers) > 1:
                if activeIdx is None or activeIdx >= len(layers) or \
                        layers[activeIdx] != activeLayer:
                    activeIdx = None
                    for i, l in enumerate(layers):
                        if l == activeLayer:
                            activeIdx = i
                            break
                if activeIdx is not None:
                    positions = [
                        gv.cachedPositionAtIndex_(i) for i in range(len(layers))
                    ]
                    factor = self._positionScaleFactor(layers, positions, gv)
                    ax = positions[activeIdx].x
                    ay = positions[activeIdx].y
                    for i, l in enumerate(layers):
                        if i == activeIdx:
                            continue
                        # 改行などの制御用レイヤー（パスもコンポーネントも無い）は除外
                        if not getattr(l, 'paths', None) and \
                                not getattr(l, 'components', None):
                            continue
                        pos = positions[i]
                        result.append(
                            (l, (pos.x - ax) / factor, (pos.y - ay) / factor)
                        )
        except Exception:
            result = []

        self._otherLayersKey = key
        self._otherLayersCache = result
        return result

    @objc.python_method
    def updateMagnifierView(self, force=False):
        if not self._window or not hasattr(self, '_magnifierView'):
            return
        try:
            doc = Glyphs.currentDocument
            evc = None
            if doc and doc.windowController():
                evc = doc.windowController().activeEditViewController()

            # 編集タブのアピアランスと動的に同期（設定が「アプリ連動(1)」の場合）
            if hasattr(self, '_window') and int(self._settings.appearancePopUp.get()) == 1:
                self.applyAppearance(evc)

            nodeSizeIndex = int(self._settings.nodeSizePopUp.get())

            if not evc or not hasattr(evc, 'graphicView') or not evc.graphicView():
                self._magnifierView.updateInfo(
                    (0, 0), None, 4.0, False, False, False, False, None,
                    True, True, None, nodeSizeIndex
                )
                if self._window.getNSWindow().isVisible():
                    self._auto_hidden = True
                    self.closeSettings()
                    self._window.hide()
                    self.stopTimer()
                return

            layer = evc.graphicView().activeLayer()
            if not layer:
                self._magnifierView.updateInfo(
                    (0, 0), None, 4.0, False, False, False, False, None,
                    True, True, None, nodeSizeIndex
                )
                if self._window.getNSWindow().isVisible():
                    self._auto_hidden = True
                    self.closeSettings()
                    self._window.hide()
                    self.stopTimer()
                return

            if getattr(self, '_auto_hidden', False):
                if not self._window.getNSWindow().isVisible():
                    def_frame = Glyphs.defaults.get(self.pref_frame)
                    if def_frame and isinstance(def_frame, str):
                        self._window.getNSWindow().setFrameFromString_(def_frame)
                    self._window.show()
                    if def_frame and isinstance(def_frame, str):
                        self._window.getNSWindow().setFrameFromString_(def_frame)
                    self.startTimer()
                self._auto_hidden = False

            window = evc.graphicView().window()
            if not window:
                return

            mouse_loc = window.mouseLocationOutsideOfEventStream()

            dummy_event = NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
                5, mouse_loc, 0, 0, window.windowNumber(), None, 0, 0, 0.0
            )

            try:
                loc = evc.graphicView().getActiveLocation_(dummy_event)
                new_pos = (loc.x, loc.y)
            except Exception:
                return

            zoom = float(self._window.slider.get())
            is_linked = self._settings.checkLink.get()
            if is_linked:
                try:
                    evc_scale = evc.graphicView().scale()
                    zoom = zoom * evc_scale
                except Exception:
                    pass

            showFill = self._settings.checkFill.get()
            showNodes = self._settings.checkNodes.get()
            showGrid = self._settings.checkGrid.get()
            showStroke = self._settings.checkStroke.get()
            fillColor = self._settings.colorWell.get()

            bgShowFill = self._settings.bgCheckFill.get()
            bgShowStroke = self._settings.bgCheckStroke.get()
            bgFillColor = self._settings.bgColorWell.get()

            compShowFill = self._settings.compCheckFill.get()
            compShowStroke = self._settings.compCheckStroke.get()
            compFillColor = self._settings.compColorWell.get()

            show_bg = Glyphs.defaults.get("showBackground", False)
            show_metrics = Glyphs.defaults.get("showMetrics", False)
            show_guides = Glyphs.defaults.get("showGuidelines", False)
            show_anchors = Glyphs.defaults.get("showAnchors", False)

            otherLayers = self.collectOtherLayers(evc, layer, force=force)

            current_state = (
                new_pos, layer, zoom, showFill, showNodes, showGrid, showStroke,
                fillColor.description() if fillColor else None,
                is_linked, show_bg, show_metrics, show_guides, show_anchors,
                bgShowFill, bgShowStroke,
                bgFillColor.description() if bgFillColor else None,
                nodeSizeIndex,
                compShowFill, compShowStroke,
                compFillColor.description() if compFillColor else None,
                len(otherLayers)
            )

            if not force and hasattr(self, '_last_drawn_state') and \
               self._last_drawn_state == current_state:
                return

            self._last_drawn_state = current_state
            self._lastMousePos = new_pos

            self._magnifierView.updateComponentInfo(
                compShowFill, compShowStroke, compFillColor
            )
            self._magnifierView.updateOtherLayers(otherLayers)
            self._magnifierView.updateInfo(
                new_pos, layer, zoom, showFill, showNodes, showGrid,
                showStroke, fillColor, bgShowFill, bgShowStroke, bgFillColor,
                nodeSizeIndex
            )
        except Exception:
            pass

    def __file__(self):
        return __file__
