# 合并后声音菜单空白／错名 / Missing sound menu labels after merging

[中文方法](README.md) · [English method](README.en.md) · [实现位置](IMPLEMENTATION.md)

## 原因与修复范围

声音菜单的 AP、声音库和语言资源必须一起集成。AP 产生私有文字 ID，文件系统需要配套的 **68 个横屏／竖屏 UXC 资源**；遗漏这些记录会导致标题或子项空白、错名。

完整声音配方和资源独立配方采用相同目标文字，包括“自定义快门声”和音频导入确认。资源独立配方适合修复列明的缺资源布局，避免覆盖已有 LUT 或其他程序补丁。

`repair-resources` 只读取68个文字资源，先检查全部输入／输出哈希和文字记录，再创建新目录。每项只接受列明的缺资源基线，或已经修复的目标；未知内容拒绝，不覆盖输入。输出不含 AP、CP、`libmpr.so`、设置、用户音频或版本字段。它不生成可安装DAT，不连接设备。

## 使用方法

先从自己的最终构建提取文件系统，保留其中原始相对路径：

```text
local/merged-fs/share/app/string_english_horizontal.uxc
local/merged-fs/share/app/string_english_vertical.uxc
local/merged-fs/share/app/...  # 其余语言，合计68个文件
```

```powershell
python -m a7m4.custom_sound repair-resources --fs-root local/merged-fs --output output/sound-menu-repair
python -m a7m4.custom_sound verify-resources --fs-root output/sound-menu-repair/fs
```

输出为 `output/sound-menu-repair/fs/share/app/*.uxc` 和 `manifest.json`。按清单把**全部68项**加入自己的完整文件系统构建，保持其他文件和设置原样；重新计算完整包校验并签名。再从**最终安装包**重新提取文件系统，执行：

```powershell
python -m a7m4.custom_sound verify-resources --fs-root local/final-package-fs
```

此命令只读，要求68个目标文件哈希完全匹配，并检查标题、开关、导入提示、音量及10%～100%记录。`0200AB60`是已停用的时长说明，预期为空；其他19项私有文字必须存在。简体中文标题应为“自定义快门声”“自定义对焦声音”。不要删除原厂“静音模式设置”项目来遮盖错名。

完整参考 `apply` 同样验证这套资源合同；从配方中漏删一个方向的文字文件或AP／CP／MPR组件会被拒绝。其他地址布局／文字库需要独立适配，不通过关闭哈希检查来兼容。

## 核验范围

公开工具核对 UXC 完整哈希、索引与文本；原生 `libObj` 查找可核对记录解释方式，字形渲染仍需在机内检查。安装后的显示、声音和重启应分别验证。完整 SD 构建及机型兼容性遵循主项目要求；该方法不自动接入官方基线的 `build-fl23`。

## English

The sound AP, library and all 68 horizontal/vertical UXC banks must be integrated together. Missing private text records can leave working sound code with blank or incorrect labels. The full recipe and resource-only recipe share the current shutter title and audio-import confirmation targets.

Use the commands above on an extracted filesystem. `repair-resources` accepts only the pinned missing-label inputs or the already-correct targets, validates every bank before creating output, and emits only68 resources plus a manifest. It never replaces AP, CP, MPR, settings, sounds or version metadata. Integrate the complete output into your own package, recalculate checksums/signatures, extract that **final package**, and run `verify-resources` against it. No installer or hardware operation is provided by these commands.

Verification covers exact output hashes and 20 private text records per bank, including the intentionally empty retired caption `0200AB60`. Native `libObj` lookup can check record interpretation; neither check renders camera glyphs. Unknown baselines require a separate port and review.
