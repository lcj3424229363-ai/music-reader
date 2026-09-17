# Music Reader MVP

> Project owner: [lcj3424229363-ai](https://github.com/lcj3424229363-ai)
>
> Engineering assistance: OpenAI Codex

这个目录是乐谱分析工具的第一条可运行流水线：先读结构化乐谱文件，再输出结构化读谱结果。

当前支持：

- MusicXML：`.musicxml`、`.xml`、`.mxl`
- MIDI：`.mid`、`.midi`
- 图片/PDF OMR：`.png`、`.jpg`、`.jpeg`、`.tif`、`.tiff`、`.bmp`、`.pdf`

当前输出：

- 文件类型
- 推测调性
- 总声部/小节数量
- 每个声部的小节、拍号、调号、音符、休止符、和弦
- chordify 后的小节级纵向和声音响
- 基础校验警告

## 命令行使用

```powershell
python music-reader\reader.py path\to\score.musicxml --pretty
```

输出 JSON：

```powershell
python music-reader\reader.py path\to\score.musicxml
```

## 运行 smoke test

```powershell
python music-reader\smoke_test.py
```

## 启动上传 API

```powershell
python music-reader\server.py
```

然后访问：

```text
http://127.0.0.1:8765/health
```

上传接口：

```text
POST http://127.0.0.1:8765/read-score
form-data: file=<MusicXML/MIDI/图片/PDF>
```

手动和弦输入接口：

```text
POST http://127.0.0.1:8765/manual-chords
{
  "key": "C major",
  "timeSignature": "4/4",
  "progression": "C | Am | Dm G7 | C"
}
```

这个接口是 OMR 失败时的降级通道：用户手动输入小节和弦，系统先生成结构化和声草稿，后续继续进入罗马数字分析和解释答案。

手动音符定位接口：

```text
POST http://127.0.0.1:8765/manual-notes
{
  "clef": "treble",
  "measureNumber": 1,
  "notes": "C4 E4 G4 Bb4"
}
```

这个接口用于 OMR 校正阶段：用户输入某小节的具体音，系统返回标准化音高信息，前端将其载入小节制谱器。

四部和声参考答案接口：

```text
POST http://127.0.0.1:8765/four-part-answer
{
  "key": "C major",
  "timeSignature": "4/4",
  "melodyEntries": [
    {
      "kind": "note",
      "pitches": [{ "step": "C", "octave": 5, "accidental": "" }],
      "duration": "4",
      "dotted": false,
      "units": 8
    }
  ]
}
```

这个接口是“题目输入 -> 参考答案”的第一条闭环：把当前五线谱输入区或多小节文本当作旋律题，生成 Soprano、Alto、Tenor、Bass 四个声部、基础罗马数字、功能标签和文字说明。当前是规则草稿，不是严格四部和声批改器；尚未完整检查平行五八度、声部交叉、导音解决、七和弦解决、重复音禁忌和终止式质量。

## 小节制谱校正

前端使用本地固定版本的 VexFlow 5.0.0 排版五线谱，支持：

- 点击五线谱按音高录入，按当前光标顺序生成拍位。
- 支持多个小节的手动五线谱输入；可上一小节、下一小节、新增小节、删除当前小节。
- 每个小节独立保存音符、休止符、和弦和时值，生成四部和声时会优先读取所有已输入小节。
- 在“叠加当前和弦”模式下，把多个音高写入同一拍位；和弦只按所选时值占一次拍。
- 选择音符拍位后，可设置延音开始、延音结束和 fermata；同一小节内相邻同音会显示延音线。
- 选择音符拍位后，可设置 slur 连线开始/结束；当前小节内会显示连音线。
- 选择拍位后，可添加基础强弱记号：`pp`、`p`、`mp`、`mf`、`f`、`ff`。
- 当前小节可设置起始小节线和结束小节线，包括开始反复、结束反复、双线和终止线。
- 选择已有拍位后，可删除单个和弦音、删除整组、修改整组时值或撤销操作。
- 高音谱号、低音谱号和 4/4、3/4、2/4、6/8 拍号。
- 全、二分、四分、八分、十六分音符与休止符。
- 附点、升号、降号、还原号。
- 自动符干方向、连梁分组、加线和节奏间距。
- 小节容量校验、超拍拦截和浅色休止符补位。
- 撤销、清空和音名批量载入。批量输入用 `+` 叠加和弦音、用 `|` 分隔拍位，例如 `C4+E4+G4+Bb4:4 | D4+F4+A4:8`。
- 四部和声生成可以直接读取多小节文本：`|` 分拍位，`||` 分小节，`R` 表示休止，例如 `C5:4 | D5:4 | R:4 | C5:4 || F5:4 | E5:4 | D5:4 | C5:4`。

当前制谱校正器为多小节、单谱表、单声部。同一和弦内各音共享一个时值；同一时刻的独立时值与多声部交错尚未实现。延音线当前只支持同一小节内相邻同音，slur 只支持当前小节内音符之间的连线，跨小节连线尚未实现。

依赖安装：

```powershell
cd music-reader
npm install
```

小节数据后续会继续接入和弦识别；制谱器是 OMR 结果的校正界面，不改变“图片 -> OMR -> MusicXML -> 分析答案”的主流程。

## 四部和声草稿

前端“生成四部和声参考答案”按钮会读取上方五线谱输入区的当前小节，调用 `/four-part-answer`，并用 VexFlow 显示四条声部谱表。

当前支持：

- 1 到 16 小节旋律题。
- 以当前调性和拍号生成 SATB 四部草稿。
- 输出每拍的罗马数字、功能标签、置信度和简短理由。
- 桌面端直接显示，移动端谱面区域内部横向滚动。
- 文本输入的每小节时值必须刚好等于拍号容量。

当前边界：

- 暂不支持低音题和已给和弦题的专门解法。
- 暂不支持严格禁忌检查和自动改错。
- 暂不接 AI；自然语言解释来自规则模板。

## OMR 配置

图片会通过 homr 转成 MusicXML，然后再进入 `reader.py`。PDF 会先以
300 DPI 逐页渲染，再交给 homr；多页识别结果会合并成一个 MusicXML。

默认从 `PATH` 和常见的用户安装目录查找 `homr`。也可以通过环境变量指定：

```powershell
$env:HOMR_EXE='C:\path\to\homr.exe'
```

PDF 渲染优先使用 `pdftoppm`（Poppler）；未安装时自动回退到 PyMuPDF
的 `fitz` 模块。两者都不可用时，接口会返回明确的 OMR 配置错误。

OMR 当前只适合清晰印刷谱。图片/PDF 默认进入增强识谱流程：HOMR 先生成
MusicXML，Python 校验结构和置信度，Qwen 再复核有限的风险区域。复核面板会显示
谱面裁剪图、HOMR 原事件和 Qwen 建议；只有用户勾选确认后才会修改 ScoreIR。
高置信度建议也不会自动覆盖 HOMR。

这表示最小端到端链路已经可以运行，不表示真实复杂谱面的 OMR 准确率已经达标。
双谱表、交错声部、复杂节奏和拍摄畸变仍需通过带真值 MusicXML 的固定测试集继续改进。

## 下一步

当前开发重点：

```text
真实双谱表基准 -> HOMR 错误定位 -> Qwen 可视化确认 -> 人工最终稿 -> 可训练样本
```
