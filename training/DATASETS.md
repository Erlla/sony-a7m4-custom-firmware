# 大色卡与富士目标数据

[English](DATASETS.en.md) · [机器可读清单](charts/manifest.json) · [训练入口](README.md)

## 输入不能互换

本素材使用由 Hearts-Ace 的 R5 研究提供的合成100MP大色卡载体，共 **99,372** 个颜色块，布局364列×273行、每块32像素。它是一份合成输入，不是99,372张实拍，也不是独立场景验证。

| 文件 | 用途 | SHA-256 |
|---|---|---|
| `SONY-v4.5-100MP-5300K.ARW` | M4模型唯一对应RAW输入 | `45455a7c46d7aa2454e73a67c32b01a29a13739d203e54ed24592a451fd48bd6` |
| `GFX100SII-v4.5-100MP-5300K.RAF` | 在富士RFCEX导出同源风格目标 | `fd31efd39ed671e39891984ee0f9c56933599d52764a77138c905166cbb8dcda` |
| `SONY-v4.5-100MP-5300K.DNG` | 参考载体，不能静默替代ARW输入 | `0b9ea8efa0c67f7584409473d959da04716ae469441661955a8a30ab934026b1` |

素材包含三份原始载体、实际ARW推导的输入数组、设计／类别标签和12款富士目标采样。ARW／RAF不是同格式文件，不能相互改扩展名使用。源ARW的CFA、黑电平、WB增益、缩放、裁切和SSCS已与该数据的输入映射核对；设计RGB只用于标签和曲线横轴，不送入模型冒充RAW。

## 文件组织

```text
M4-training-assets/
  models/forward_model.json
  models/grid_response.pt
  models/bridge/
  charts/dataset.json
  charts/SONY-v4.5-100MP-5300K.ARW
  charts/GFX100SII-v4.5-100MP-5300K.RAF
  charts/SONY-v4.5-100MP-5300K.DNG
  charts/sony_input.npz
  charts/design_pairs.npz
  charts/fuji_targets.npz
  manifest.json
```

目标按每块内部 `y=16、x=14…18` 的5个像素取编码sRGB均值，保持原块序、float64值和原始TIFF身份。不额外平滑、不重新定白点、不做曝光或直方图匹配。`fuji_targets.npz` 是该训练采样的无损存储，不能用于声称已评价整幅TIFF所有像素。完整的12份目标TIFF不混入源码。

富士目标来自 **RAW FILE CONVERTER EX 3.0 powered by SILKYPIX**，包括CC、Provia、Velvia、Astia、Reala Ace、Pro Neg.Hi／Std、Classic Neg.、Nostalgic Neg.、Eterna、Eterna Bleach Bypass、Acros。不替换成Lightroom＋DCP。

**白平衡记录：** CC使用后来受控确认的拍摄时WB目标 `as_shot.tif`。其它11款保留历史目标，其元数据已核对，但WB设置未逐款独立验证；不能把整套写成“已全部确认统一as-shot”。清单保留逐款身份和这一状态，不利用改目标来制造训练进步。

## 新滤镜需要什么

已有12款目标可以直接复用，无需重新导出或实拍。新的富士风格可用同一RAF生成目标；自己的风格可提供同一ARW的目标图和明确配方。导出优先16位sRGB、原尺寸／方向、曝光补偿0，保持既定WB；不同软件的Kelvin读数不能当作同一个白点强行对齐。电脑不增加镜头校正。

大色卡负责密集色域、灰轴、暗部和色相随亮度的变化。真实材质、肤色阴影、不同曝光／WB仍使用已有同源实拍作为保护；新用户没有色卡也可提供普通照片配对。它们可反复用于电脑拟合，不需每个候选重新拍摄。若将某组数据用于选型，应登记为开发／回归，另留未见场景作最终验证。
