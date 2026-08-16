"""Remove EXAMPLE_PRESETS + loadExamplePreset + hash preset hooks from app.js.

Run once after editing — leaves the rest of app.js intact.
"""
from pathlib import Path

P = Path(r"C:\Users\Administrator\Documents\try\music-reader\web\app.js")
src = P.read_text(encoding="utf-8")

# ----- 1) Remove EXAMPLE_PRESETS data + loadExamplePreset function -----
# start:  "Sposobin 课本例题预置"
# end:    "}\n\nfunction loadParsedMeasuresIntoEditor"
# We anchor on the unique first comment line and the next top-level function.
start_marker = "// Sposobin 课本例题预置"
end_marker = "function loadParsedMeasuresIntoEditor"

i = src.find(start_marker)
j = src.find(end_marker, i)
assert i != -1 and j != -1, f"markers not found: {i=} {j=}"
# j is the start of "function loadParsedMeasuresIntoEditor"
# step back to find the last } before the next top-level declaration
# Find last "}" before j
k = src.rfind("}", i, j)
# Move past the closing } and any whitespace
end_pos = k + 1
# Skip trailing whitespace
while end_pos < len(src) and src[end_pos] in " \t\r\n":
    end_pos += 1

replacement = (
    "// (P2.7+ 集成 2026-08-15: 课本例题 EXAMPLE_PRESETS 数据 + loadExamplePreset\n"
    "//  函数已删除, 改成 \"导入 MusicXML\" 按钮走 /parse-score (server reader.py +\n"
    "//  reader_to_editor.py) 把任意 XML 谱例直接转化到制谱页面. 五线谱只显示\n"
    "//  用户输入 (melody + bass), 不显示 alto/tenor/gold 4 voice 答案.\n"
    "//  P0-P7 solver 规则 (frozen_v1_6/solver.py) 不动.)\n\n\n"
)
new_src = src[:i] + replacement + src[end_pos:]
print(f"Removed {end_pos - i} chars (block 1)")

# ----- 2) Remove hash preset early hook (applyHashPresetEarly IIFE) -----
start2 = new_src.find("(function applyHashPresetEarly()")
end2 = new_src.find("\n})();", start2)
if start2 != -1 and end2 != -1:
    end2 += len("\n})();")
    # include trailing blank line
    while end2 < len(new_src) and new_src[end2] in " \t\r\n":
        end2 += 1
    new_src = new_src[:start2] + new_src[end2:]
    print(f"Removed {end2 - start2} chars (block 2: hash preset early)")

# ----- 3) Remove applyHashPreset function + hashchange listener -----
start3 = new_src.find("// 调试钩子：URL hash #preset=p0_cadence 自动加载课本例题")
end3 = new_src.find("\n\n// ", start3 + 50)
if start3 != -1 and end3 != -1:
    new_src = new_src[:start3] + new_src[end3:]
    print(f"Removed {end3 - start3} chars (block 3: applyHashPreset)")

P.write_text(new_src, encoding="utf-8")
print(f"\nNew file size: {len(new_src)} chars (was {len(src)})")
