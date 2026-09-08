# Starfield Atlas / 星图寻迹 1.2.1

## English

Fixes an import problem where the drag hint remained over the interface after
dropping a photo into the main area. One capture-phase file-drop handler now
owns the operation, clears the hint before reading files, and resets on cancel,
window focus changes, errors, or a missing drag-end event. The hint is a small
dismissible banner and does not darken the photograph or hide retry controls.

Camera JPEG files identified as MPO (multi-picture JPEG), including files named
`.jpg`, now decode their primary image. The original multi-picture file stays
unchanged; annotation exports a full-resolution standard JPEG of the primary
frame, with an explicit note. Obsolete MPF offsets are not copied into the new
single-frame output. Explicit `.mpo` file selection is also supported.

Close the older app and run the executable from
`Starfield-Atlas-Windows-x64-v1.2.1.zip` after extracting it completely.

## 简体中文

修复照片拖入主区域后，“松开即可识别”提示残留、遮挡错误信息和操作按钮的问题。
拖放由统一的捕获阶段处理，接收文件前就清除提示；取消、切换窗口、发生错误及
缺失拖放结束事件时都会复位。提示改成可关闭的小横条，不再压暗照片和整个界面。

支持被相机写成 MPO（多图 JPEG）的 `.jpg` 文件。解析主画面，原始多图文件保持
不变；标注输出为同分辨率的普通 JPEG，并明确说明主图导出。新文件不会携带失效
的 MPF 副帧索引；同时支持直接选择 `.mpo` 文件。

请关闭旧版窗口，完整解压 `Starfield-Atlas-Windows-x64-v1.2.1.zip` 后运行其中的
`星图寻迹.exe`。

## 日本語

写真を中央の領域へドロップした後に、ドラッグ案内が残って操作やエラー表示を
覆う問題を修正しました。ファイルの読み取り前に案内を消し、キャンセル、
フォーカス変更、エラー、ドラッグ終了イベントの欠落時にも状態を解除します。
案内は閉じられる小さなバーとなり、写真や画面全体を暗くしません。

拡張子が `.jpg` でも内部形式が MPO（複数画像 JPEG）のカメラ画像に対応しました。
元ファイルを変更せず、主画像を解析して同じ画素寸法の通常 JPEG に注釈を
書き出します。主画像のみの出力を明示し、無効な MPF オフセットは引き継ぎません。
`.mpo` ファイルを直接選択することもできます。

旧バージョンのウィンドウを閉じ、`Starfield-Atlas-Windows-x64-v1.2.1.zip` を
完全に展開してから `星图寻迹.exe` を実行してください。
