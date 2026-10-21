# 合并后声音菜单空白／错名 / Missing sound menu labels after merging

[中文方法](README.md) · [English method](README.en.md) · [实现位置](IMPLEMENTATION.md)

## 原因与修复范围

声音功能可用、菜单标题或子项却空白／错名时，应先核对语言资源。已确认的一次合并只带入 AP 和声音库，遗漏了声音菜单需要的 **68 个横屏／竖屏 UXC 资源**。AP仍产生正确的私有文字ID，缺少配套记录导致文字异常。不能以“声音能播放”证明资源已完整进入最终包。

原有完整声音参考配方本身已经包含这68项正确目标。本次新增资源独立修复配方、完整性合同和最终提取目录检查，避免为了修复文字而重刷另一份 AP、覆盖已有 LUT 或其他程序补丁。

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

此命令只读，要求68个目标文件哈希完全匹配，并检查标题、开关、导入提示、音量及10%～100%记录。`0200AB60`是已停用的时长说明，预期为空；其他19项私有文字必须存在。简体中文标题应为“自定义电子快门声”“自定义对焦声音”。不要删除原厂“静音模式设置”项目来遮盖错名。

完整参考 `apply` 同样验证这套资源合同；从配方中漏删一个方向的文字文件或AP／CP／MPR组件会被拒绝。其他地址布局／文字库需要独立适配，不通过关闭哈希检查来兼容。

## 已验证与限制

维护者合并固件的资源独立修复已获用户实机确认。公开配方的68个目标资源与该修复逐字节一致；新公开工具另经合成数据回归和本地实际文件重建。上述单机反馈不代表所有固件或机身通过，也不将此前整个参考AP／CP配方记为本次机内验收。

公开Python检查解析UXC索引与文本，不执行机内字形渲染。安装后的显示、声音和重启仍应分别验证。完整SD构建及机型兼容性仍遵循主项目要求；该方法不自动接入官方基线的 `build-fl23`。

## English

One confirmed merged firmware omitted all68 horizontal/vertical UXC banks while keeping working sound code. Its AP returned the correct private text IDs, but the final filesystem lacked their records. The existing full reference recipe already has the correct targets; this update adds a resource-only repair path and mandatory completeness/text checks.

Use the commands above on an extracted filesystem. `repair-resources` accepts only the pinned missing-label inputs or the already-correct targets, validates every bank before creating output, and emits only68 resources plus a manifest. It never replaces AP, CP, MPR, settings, sounds or version metadata. Integrate the complete output into your own package, recalculate checksums/signatures, extract that **final package**, and run `verify-resources` against it. No installer or hardware operation is provided by these commands.

Verification covers exact output hashes and20 private text records per bank, including the intentionally empty retired caption `0200AB60`; it does not render camera glyphs. The resource-only merged repair has single-camera user acceptance, and all68 published targets match it exactly. That acceptance does not certify the full reference program recipe or arbitrary combinations. Unknown baselines must be ported and reviewed separately.
