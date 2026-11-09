# LUT 训练方法、模型与大色卡

[English](README.en.md) · [AI Agent 执行指南](../docs/custom-lut-training/AGENT_TRAINING.md) · [M4 模型](MODEL.md) · [大色卡与目标数据](DATASETS.md)

让 AI Agent 使用冻结的 M4 电脑模型，读取同一份 RAW 与目标颜色，反复搜索相机支持的原生参数，最后生成可导入自定义 LUT 菜单的 JSON。已有模型覆盖范围内的参数迭代在电脑完成，不需要每轮导入相机重新拍摄。

本目录提供研究代码和命令入口，便于 Agent 读取、组合和适配；没有桌面训练软件。模型权重、大色卡 RAW 和目标采样作为独立素材附件提供，不混入源码历史。Sony 软件文件由使用者自行取得。

## 准备什么

| 内容 | 取得方式 |
|---|---|
| 本目录及第三方源码 | 克隆本仓库；保留 `third_party` 的许可 |
| 冻结模型和大色卡素材 | 项目 [Releases](https://github.com/Erlla/sony-a7m4-custom-firmware/releases) 的独立训练素材附件；组成及身份见 [模型](MODEL.md)与[数据](DATASETS.md) |
| Sony Edit 参考文件 | 自行取得匹配身份的 macOS Edit 通用二进制及 `srsettings0000.tbl`；Windows 下只读取常量，不运行该程序 |
| 滤镜起点 | 已有合法 M4 JSON；成品滤镜包仍从 Releases 单独取得 |
| 自己的目标风格 | 同源目标 TIFF，或 Agent 根据明确的处理配方生成目标；本素材另含 12 款既有富士目标采样 |

## 环境与入口

Windows x64、Python 3.12 为本次整理验证环境。安装 `requirements.txt`，按 PyTorch 官方说明选择匹配本机的 CPU／CUDA 构建。正式 CUDA RGB16 回放还需要 CUDA Toolkit 的 NVRTC；也可以显式选择 CPU。不会安装相机驱动或访问 USB。

```powershell
python -m pip install -r training/requirements.txt
```

在仓库根目录运行。以下路径是使用者实际素材所在位置，不要求复制到源码目录：

```powershell
$assets = 'D:\M4-training-assets'
$edit = 'D:\Sony-reference\Edit'
$sr = 'D:\Sony-reference\srsettings0000.tbl'

python training/run.py doctor --assets $assets --sony-edit $edit --srsettings $sr

# 同一张大色卡 RAW＋自己的 JSON → 与富士目标的对应颜色比较
python training/run.py render-chart --assets $assets --sony-edit $edit --srsettings $sr `
  --native 'D:\looks\my-look.json' --film CC --output 'D:\runs\baseline'

# 普通 M4 RAW＋JSON → 预测机内处理结果；不增加镜头校正
python training/run.py render --assets $assets --sony-edit $edit --srsettings $sr `
  --raw 'D:\photos\scene.ARW' --native 'D:\looks\my-look.json' --output 'D:\runs\scene'
```

`fit-chart` 是 Agent 可调用的网格提案与整数复核入口。使用前先按[执行指南](../docs/custom-lut-training/AGENT_TRAINING.md)固定数据角色、阴影／肤色保护、目标设置和验收条件；不能仅凭大色卡拟合分数宣布真实场景合格。`candidate.json` 是待验证候选，`fit.json` 明确记录是否满足本次检查。

```powershell
python training/run.py fit-chart --assets $assets --sony-edit $edit --srsettings $sr `
  --native 'D:\looks\my-look.json' --film CC --name 'My Classic Chrome' `
  --steps 1800 --trust 16 --output 'D:\runs\cc-proposal'
```

## 当前方法

1. 冻结相机模型、输入、目标及其白平衡／曝光设置，测量起点。
2. 优先拟合 `3×5×9×9`、共 1215 项 `−64～63` 整数网格；保持拍照与预览两分支一致。
3. 用 ΔE00、P95／最大尾差、中性暗部、肤色阴影和连续性共同选型，RGB 直方图作辅助检查。
4. 对残差难以改善的风格，测量原生 Gamma／矩阵／基础系数响应，联合有符号整数搜索。代码提供 116 个精选原生方向及 MILP 提案函数。
5. 从实际导出的 JSON 重载，重新执行正式 `129³` 表和 RGB16 内核，检查全部保护数据后再采用。

`source/response_network.py` 是冻结的相机网格响应，不是要为每款滤镜重新训练的网络。`source/fit_grid.py` 优化的是滤镜参数；`source/integer_search.py` 只产生提案，必须重新渲染验证。原生参数改变后重算原生前段；只改网格时可复用相同前段。

## 模拟范围

原生前段基于 Sony Look Bridge 的 Edit 显式算术，后接已标定的 M4 桥接与网格响应。运行时不需要打开 Sony 软件，也不需要连接相机。网格仍包含由 M4 实拍标定的经验模型，不是已证明逐位等价的完整 BIONZ 硬件复刻。

新风格通常复用已有 RAW／目标、大色卡和模型即可离线迭代。改变机型，或引入模型未覆盖的 ISO、白平衡、菜单微调及大幅原生上下文时，需补充覆盖证据；集中实机确认可留作最终验证，不插入每轮搜索。

感谢 [Hearts-Ace/sony-a7r5-custom-firmware](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware) 的作者 **Hearts-Ace 对训练方法的大力支持**，以及原生参数、网格优化与合成大色卡研究。感谢 [751K/sony-look-bridge](https://github.com/751K/sony-look-bridge) 提供原生显影算子的研究和 MIT 实现。归属与范围见[第三方说明](../THIRD_PARTY_NOTICES.md)。
