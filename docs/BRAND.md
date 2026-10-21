# MiaoTask 图标

统一使用橙色圆角方块、白色猫头与完成勾的组合。主页、浏览器标签、Windows 托盘和 EXE 使用同一份图形；不含设备或账号信息。

## 文件与规格

源图与导出文件位于 [web/assets](../web/assets/)。

| 文件 | 用途 |
| --- | --- |
| `miaotask-master.png` | 内置生图生成的 1254 × 1254 RGBA 母版，保留透明背景 |
| `miaotask-{size}.png` | 16、20、24、32、40、48、64、128、180、256、512、1024 像素 |
| `miaotask.ico` | 包含 16、20、24、32、40、48、64、128、256 像素，供 EXE、托盘和 favicon 使用 |

首页以 40 像素显示 64/128 像素图；浏览器标签使用 16/32 像素图，Apple 图标使用 180 像素图。托盘按 Windows 系统的小图标尺寸加载 ICO。`scripts/export_icons.py` 仅缩放及转换格式，不重新绘制母版。

## 生成记录

2026-10-21 使用 Codex **内置 image_gen** 生成；没有调用外部 CLI 或 API。以下为最终提示词，透明背景开启：

```text
Use case: logo-brand. Create ONE polished minimal app icon master for MiaoTask, a local desktop task assistant. A bold, compact, friendly cat-head silhouette with two clear ears, with one elegantly integrated checkmark as its mouth/lower face to express completed tasks. Flat vector-like raster artwork, exceptionally simple geometric shapes, generous clean negative space, readable at 16px. Dominant warm tangerine orange matching an existing white/off-white dashboard with forest-green accents; solid orange rounded-square app tile, simple white cat/check cutout. Use a large central mark with balanced optical padding, no tiny whiskers, no thin lines, no separate check badge, no gradients, no shadows, no 3D. Square canvas 1024x1024, one icon only centered straight on; transparent outside the rounded square. No text, no wordmark, no letters, no mockup, no grid, no alternatives, no watermark. Original visual identity, do not copy any commerce company logo. Deliver crisp production icon artwork, not a presentation board.
```
