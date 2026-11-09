# M4 电脑模型与滤镜参数模型

[English](MODEL.en.md) · [训练入口](README.md)

这里包含两个不同对象：冻结的 **M4 前向模型**预测相机如何处理参数；**滤镜拟合器**搜索应交给相机的参数。新风格复用前者，训练后者。

| 部分 | 实现及文件 | 是否逐款重训 |
|---|---|---|
| RAW 原生前段 | Sony Look Bridge：CFA、黑电平、拍摄时 WB、ITP、SSCS、原生颜色／Gamma、细节及输出；`native_frontend.py` | 否，原生参数变化时重新计算 |
| M4 零网格桥接 | 素材 `models/bridge` 的冻结校准与参考网格 | 否 |
| M4 signed7 响应 | `response_network.py` 与 `models/grid_response.pt` | 否；以既有 M4 实拍标定得到 |
| 滤镜参数 | 拍照／预览原生系数、矩阵、Gamma、菜单默认值及 `3×5×9×9` 网格 | 这是优化对象 |

整条路线：

`Sony ARW → 显式原生前段（由 JSON 控制）→ 冻结 M4 桥接 → 冻结 signed7 响应 → 正式129³表／RGB16内核 → 预测图`

## 模型文件

训练素材目录中的 `models/forward_model.json` 是入口合同。内部路径相对素材目录解析；`code:` 指本仓库 `training/source`，`external:` 指使用者本地提供的文件。每个依赖绑定 SHA-256。不要只复制权重而遗漏桥接、参考网格和原生编解码器。

模型入口的原数学合同 SHA-256 为 `4e516ebced9075eba9a4a69a89f410606abb87434077c4ac8986ca0690968e6d`。本次整理改变路径组织和导入边界，保持冻结权重和前向运算；迁移核验单独记录，不视为重新训练。

Sony 参考文件要求：

| 文件 | SHA-256 |
|---|---|
| macOS Edit 通用二进制（供读取常量） | `43ae5e1cb4bc18a52183b430e02b16a4506b89a907a6fd0feed359fa85a82ce9` |
| 其中 ARM64 slice | `c250f466835c5380d244de33a6824e9930fe3f250ce9b1d948d5e379cc4c8133` |
| `srsettings0000.tbl` | `ef1dd637b6656dc895246265bd311fbc63b0e95f7b50005ceb61c19d472d9aba` |

匹配的官方安装文件为 [IE410_2603a.dmg](https://di.update.sony.net/NEX/3Kb405393d/IE410_2603a.dmg)，SHA-256 `d7927efe5a4d67707b8d74b14511b39f353a5ca5cb79240554d73b3bda4707ab`。下载到本机后，可用7-Zip只解出所需参考文件，不安装或运行Sony程序：

```powershell
python training/prepare_sony.py --package 'D:\Downloads\IE410_2603a.dmg' `
  --sevenzip 'C:\Program Files\7-Zip\7z.exe' --output 'D:\Sony-reference'
```

使用脚本最后打印的两个实际路径传给run.py。此处不重新分发 Sony 程序或常量；Windows 的 Edit.exe 不能直接替代上述文件。Sony Look Bridge 固定提交为 `6302d69d6ecc827503c5f110579a7c579db101c7`，MIT 源码及许可保留在 `third_party`。Windows 仅在工作副本把三处 libSystem 数学库路径改为 UCRT。

## 参数维度与缓存

网格为 1215 项 signed7 整数，范围 −64～63，不是 64³ 或 129³ 相机原生网格。`129³` 是电脑输出采样表，不能混为原生存储尺寸。

原生精选方向共 116 项：12 个 Gamma 形状方向、96 个矩阵方向、8 个基础系数方向。Gamma 各上下文同步变形，矩阵端点同步改变；它们不是所有上下文／端点分别独立的全参数族。代码提供这些方向与有符号整数求解器，Agent 按已测响应扩展联合搜索，不将未测导数当作零。

只改网格可以复用相同 RAW／原生参数的前段。改 Gamma、矩阵或系数必须重算原生像素。正式评分保持129³节点顺序、32768分块、float64桥接、float32网格响应、float64插值和最终RGB16量化。连续解或局部代理分数不能代替该路径。

## 已验证范围

现有显式模型在一份历史同源 M4 RAW／机内 JPEG 的140块中心对照中，平均 ΔE00 约0.823、P95约2.002、RGB RMSE约1.563／255。这是模型对相机的复现误差，不是滤镜对富士目标的误差，也不是新独立场景验收。

完整硬件 ISP 未证明逐位等价，网格部分仍为经验响应。当前主要使用拍照 Gamma context6、历史端点0或已测固定有效端点、RAW中记录的WB权重，保持已标定菜单默认值。独立菜单微调、任意ISO／光源／端点、自适应降噪和DRO不在通用等价承诺内。当前入口关闭额外镜头校正、RawNR、DRO及Marble。


本次迁移核对使用PyTorch 2.14.1+cpu：两组冻结响应、99,372点原生结果与完整129³表均与原实现一致；CPU／NVRTC CUDA RGB16结果逐码一致。只运行两步参数梯度冒烟，没有重新训练相机模型或整批滤镜；本轮未复测CUDA版PyTorch训练。


### 连续迭代的复用接口

`frozen_table.FrozenTable(model)`一次缓存零网格桥接，之后按同样129³节点／32768分块生成不同网格的正式表，不降采样；需要保留旧表时复制其返回缓冲。`spatial_native.native_pixels`复用已解码的带邻域RAW图集，在原生参数改变后重新渲染ROI。图集的linear文件为uint16 RGB14，selection.npz含y、x、ends；使用原图ROI及12像素邻域，改变空间算子后应重新核对邻域范围。两者分别缓存后段桥接和RAW前段，不允许用旧原生像素代替新Gamma／矩阵的结果。
