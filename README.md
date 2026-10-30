# 海

用 CSS 做出的動態海面：晴朗的白天、遠方的積雲，波浪一道道朝鏡頭推進，浪頭碎成白沫。

沒有 JavaScript、沒有 WebGL，也不需要 build。瀏覽器只負責移動與混合幾張紋理。

**線上展示：** <https://cyclopestsai.github.io/Water/>

## 運作原理

CSS 本身做不出雜訊，所以紋理是用 `tools/bake.py` 預先算好的 WebP 圖片，動畫與畫面合成則全部由 CSS 完成。

| 效果 | 做法 |
| --- | --- |
| 波浪 | 用海洋波譜與 FFT 產生無縫紋理。每張紋理只含朝同一方向前進的波，所以平移就是正確的波動 |
| 干涉 | 四到六層不同方向的波用透明度取平均，等同線性疊加 |
| 波速 | 依深水色散關係設定，長浪比短浪快 |
| 透視 | 海面是 `rotateX(90deg)` 的 3D 平面，分成遠近兩段 |
| 海色 | 灰階代表沿視線的斜率，再用 `screen` 與 `multiply` 上色，越遠反射的天空越多 |
| 白沫 | 出現在波面折疊的位置，再用高對比切門檻，消散時是碎開而不是淡出 |
| 立體感 | 用 SVG 位移濾鏡讓波面實際變形，只在電腦版的非 Safari 瀏覽器啟用 |
| 雲 | 對雲層做體積光線步進，烘成一張圖 |

## 專案結構

```text
index.html       場景結構與位移濾鏡
style.css        鏡頭、波浪層、混合與動畫
textures/        烘焙好的紋理，網站需要這些檔案才能顯示
tools/bake.py    產生 textures/ 的程式
```

## 本機預覽

```bash
python3 -m http.server 8765
```

然後開啟 <http://localhost:8765>。

## 調整紋理

修改 `tools/bake.py` 後重新產生紋理。結果是固定的，沒有修改參數時輸出會完全相同。

```bash
pip install numpy scipy pillow
```

```bash
python3 tools/bake.py
```

也可以只產生指定的紋理：

```bash
python3 tools/bake.py clouds
```

可用的名稱有 `wave-a` 到 `wave-e`、`foam`、`patch`、`glint`、`clouds`。其中 `foam` 也會一併產生 `foam-far.webp`。

## 部署到 GitHub Pages

到 repo 的 **Settings → Pages**，選 **Deploy from a branch**，分支選 `main`、資料夾選 `/ (root)`。

所有資源都是相對路徑，放在 `/Water/` 這類子路徑底下也能正常載入。

## 效能

畫面需要 GPU 加速。`style.css` 開頭的 `--soft` 會依螢幕大小與像素密度調降紋理層的解析度，避免超過瀏覽器的圖塊預算。超過時幀率不會下降，但畫面會整塊缺失，所以修改波浪層時要同時檢查畫面與幀率。

已在 macOS 的 Chromium 測試。Safari、Firefox 與實體手機尚未測試。

系統設定了「減少動態效果」時，動畫會暫停。

## 授權

[MIT](LICENSE)
