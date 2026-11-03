# 白平衡优化：AWB 优先级配置

[English](README.en.md) · [实现与修改位置](IMPLEMENTATION.md) · [输入与布局](reference-layout.json) · [验证范围](validation.md)

将自动白平衡的**氛围优先设为 −1、标准保持 0、白色优先设为 97**。继续使用相机原有的三种优先设置，不增加菜单或修改手动色温。

## 索尼 FX2 原厂参数与本配方对照

**Sony FX2 官方 1.01 原厂参数：**

| 设置 | FX2 原厂参数 | 对应局部主系数 |
|---|---:|---:|
| 氛围优先 | −1 | 254 |
| 标准 | 0 | 256 |
| 白色优先 | 88 | 432 |

氛围和白色参数来自 FX2 官方 1.01 的 11 个已核对升级配置，标准分支在代码中使用 0。字段与来源见[实现说明](IMPLEMENTATION.md#parameter-identity)和[验证范围](validation.md)。

**本配方参数：**

| 设置 | 本配方参数 | 对应局部主系数 |
|---|---:|---:|
| 氛围优先 | −1 | 254 |
| 标准 | 0 | 256 |
| 白色优先 | 97 | 450 |

本配方的氛围优先和标准参数与上述 FX2 原厂值相同；**白色优先 97 是自定义选择，FX2 原厂值为 88**。表中主系数属于 AWB 局部运算，不是最终色温或整体去暖比例。最终色彩取决于光源、场景及其他调校；此方法不承诺所有场景的白平衡都更好。

## 生成修改后的 CP

适用于 Sony ILCE-7M4 官方 6.02 对应的 CP 布局。工具接受两种完整文件身份：原厂 CP，以及已完成 LUT／纵横比／声音交接集成的参考 CP。具体摘要列于[补丁配方](../../a7m4/profiles/awb-priority.json)，不能仅按相机显示版本选择输入。

在仓库根目录运行：

```powershell
python -m a7m4.awb_priority --input local/cpapp-b.bin --output output/cpapp-b.awb.bin
```

输入自行从适用固件或自己的合法来源取得。先创建输出父目录；命令不会覆盖输入或已有输出，完成后打印新 CP 的 SHA-256。不支持的完整摘要或原字节会被拒绝。

## 与已有功能组合

对于[当前组合布局](../08-custom-lut/INTEGRATION.md)，先完成原有功能和[声音双向交接](../06-custom-sounds/README.md#生成修改后的组件)，再将其 CP 输出交给本工具：

```powershell
python -m a7m4.custom_sound_handoff --input local/integrated/cpapp-b.bin --output output/cpapp-b.handoff.bin
python -m a7m4.custom_sound_lifecycle --component cp --input output/cpapp-b.handoff.bin --output output/cpapp-b.sound-lifecycle.bin
python -m a7m4.awb_priority --input output/cpapp-b.sound-lifecycle.bin --output output/cpapp-b.awb.bin
```

这是两种受支持输入的不同使用路线。原厂 CP 不能代替已经包含 LUT、纵横比和声音的组合 CP；其他组合必须重新核对完整文件和修改合同。

## 完整固件与使用

输出是 CP 文件，不是整个分区或可直接安装的固件包。将其放回对应 FAT 镜像，更新分区校验，再按[集成规则](../08-custom-lut/INTEGRATION.md)和[签名方法](../01-custom-signing/README.md)生成完整包，并核对最终包中的 CP 摘要、全部分区 CRC、解密内容和签名。使用项目既有[安装流程](../../no-fastboot-install/README.md)。

安装后选择自动白平衡，再在原有的标准、氛围优先、白色优先之间切换。以固定光源和同一场景比较，分别检查拍摄与回放。

本方法在实际参数读取点固定两个输入，保留标准分支；不会改写机身备份。默认备份块中仍可能显示原值，但运行读取点使用本配方值。原理、8 字节修改和有符号边界见[实现说明](IMPLEMENTATION.md)，物理安装与成像的证据边界见[验证说明](validation.md)。
