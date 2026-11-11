# 相机 RAW 内置 FL2/FL3 备选外观

[English](raw-alternative-looks.en.md) · [返回方法3](README.md) · [验证范围](raw-alternative-looks-validation.md)

相机新拍的ARW携带FL2/FL3备选参数，在Imaging Edge Edit中打开原片即可重新选择这两种外观，无需先用电脑脚本补入目录。此扩展作用于之后拍摄的RAW。

## 修改哪份数据

主SR2保存拍摄时选中的外观；`0x74C0`保存供软件重选的备选外观目录。已有主矩阵写出修复不等于备选列表已补全。本组件将原十项列表扩为十二项，继续由相机原生代码生成名称、颜色系数、A1矩阵、曲线及白平衡等字段。机型仍为ILCE-7M4。

原十项为Standard、Vivid、Neutral、Portrait、FL、VV2、IN、SH、BW、Sepia，其后增加FL2、FL3。主目录仍169项，每个备选目录仍114项。这个组件只修改CP，不修改AP、MPR、图片资源或RAW感光数据处理路径。

## 精确组件与组合顺序

[Python构建器](../../a7m4/raw_alternative_looks.py) · [原生C源码](../../native/raw-alternative-looks/raw_list.c) · [链接脚本](../../native/raw-alternative-looks/raw_list.ld) · [完整配方](../../native/raw-alternative-looks/layout.json)

本配方接受已集成FL2/FL3、自定义LUT/声音、[Capture比例继承](../07-custom-aspect-ratios/README.md)及[AWB优先级](../10-awb-priority/README.md)的精确CP。它是方法3的后续组件，不能直接应用于原厂CP或本方法早期的独立移植输出。

| 阶段 | 完整CP SHA-256 |
|---|---|
| Capture比例继承后、AWB前 | `28f3e21710ee4af035fa4c2f8661a43b5de6a23d017b5b4dabcd89b2f2a466d1` |
| 本组件输入，已应用AWB | `c9399d46f231639d467f73316243bfae2620195502c8cc21fc2779ce810211aa` |
| 本组件输出 | `5ec4dee8e126ed54ff476b349e4d76318c98d3cc2f0ac9a5583ec98155b93fc4` |

文件长度保持16,236,816字节。原有组件的哈希范围及构建器保持独立；此配方没有自动合入`firmware build-fl23`。[LUT组件清单](../08-custom-lut/reference-layout.json)保留AWB前身份，并单独登记本扩展。

## 六处修改

下列地址为CP VA，文件偏移为VA减`0x108000`。六处写入范围合计128字节，实际113字节改变。

| 地址 | 实现 |
|---|---|
| `A04144` | 原构造调用改为进入常驻`BA4960` |
| `BA4960` | 32字节helper，先补两个映射、再写数量，尾调原`A02A60`构造器 |
| `9FF88C` | 数量接口跳转至新实现 |
| `9FF8E0` | 初始化前10项和构造后12项均返回成功，其他数量保留失败 |
| `9FF8A4` | 按配置中的实际数量查找映射；未知项返回-4，输出不改 |
| `B8EE78` | RAW备选Gamma表的第10/11项由旧色号4/9改为FL2/FL3色号19/20 |

helper局部修改BKID `0x300AF`对应的RAM记录：基址`014F6FC1`，`+7A=10`、`+7B=11`、最后`+3=12`；其余253字节保留。每次经过该构造调用都会应用，因此不需要写持久备份或复制FX2整条配置。

静态TIFF模板中的count会被运行期数量覆盖。只改模板没有效果；只扩数量/映射而保留Gamma表，则新两项会选到旧外观的曲线。原十项Gamma映射保持。

## 原生长度与空间

目录构造、指针连接、字段填充与导出布局继续使用原生循环。每个child步长`C26`（3,110字节），SR2长度按`10CA + N*C26`计算：35,398→41,618字节，增加6,220字节。十二项child区域止于结构偏移`A2AA`，下一段从`AED0`开始，沿用原预留区及指针数组。

helper位于已经核对的常驻空隙，不增加堆/BSS，也不改可选P3前缀及其CRC。固定`9000`加密调用对应另一块`C634/7250`元数据，不是主`7200` SR2的长度上限，本组件不修改该调用。

## 离线复建

使用源码checkout及旁边的`native/`目录，准备上述精确CP、已创建的`output`目录与配方所固定的ARM GCC。输入、编译器和源码均按SHA-256识别。

```powershell
python -m a7m4.raw_alternative_looks --input local/CPAPP-B.integrated-awb.BIN --compiler local/toolchain/bin/arm-none-eabi-gcc.exe --output output/CPAPP-B.raw-looks.BIN
```

构建器重编译三段源码，核对原字节、section身份与完整输出哈希。命令只生成CP文件；组合SD包、校验更新及独立NOR同步沿用[方法3安装流程](README.md)。现有LUT触摸、比例图标和其他组件应按各自配方保留。

## 使用

更新后拍摄RAW或RAW+JPEG，在Edit中直接打开相机原始ARW，检查创意外观选择中的FL2/FL3。维护者已反馈Edit可以识别，具体证据范围见[验证记录](raw-alternative-looks-validation.md)。目录可识别、JPEG导出和最终颜色一致性分别记录，不混用已有颜色对比结果。
