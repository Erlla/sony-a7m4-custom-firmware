# 六个自定义比例与自动检视

[English](README.en.md) · [方法7](../../methods/07-custom-aspect-ratios/README.md) · [精确配方](layout.json)

在已有组合固件上增加21:9、2.35:1，并修复不显示直方图时的自定义比例自动检视拉伸。现有17:6、65:24、5:4、7:6及原厂四比例保留。

维护者已确认新增两比例正常，随后确认本实现修复自动检视拉伸。反馈上下文为RAW+JPEG、不显示直方图；未提供完整输出设备、格式和方向测试矩阵。[实测记录](acceptance.json)与[离线验证范围](validation.json)分开保存。

## 输入与构建

输入是已集成标题图标和运行时精简的AP、其后带声音缓冲恢复的CP、既有相册放大兼容的libmpr，以及匹配的68个文字库和2个图像库。输入和输出完整SHA-256见layout.json。CP输入含尚未在旧基础配方中提供独立构建器的声音恢复层，不能直接用精简CP替代；本配方不重建此前的全部固件。

需要从自己的兼容基线提取组件；仓库不分发这些输入。使用Python项目依赖、Zig 0.14.1和布局清单固定的ARM GCC工具链。资源构建另外需要Pillow，以及清单指定SHA-256的Arial Bold字体。

以下命令假定当前目录为仓库根目录，输入放在input，工具放在tools/local，output已经建立：

```powershell
python -m a7m4.aspect_autoreview --component ap --input input/appFw.so --compiler tools/local/zig/zig.exe --output output/appFw.so
python -m a7m4.aspect_autoreview --component cp --input input/cp.bin --compiler tools/local/gcc/bin/arm-none-eabi-gcc.exe --output output/cp.bin
python -m a7m4.aspect_autoreview --component mpr --input input/libmpr.so --compiler tools/local/zig/zig.exe --output output/libmpr.so
python -m a7m4.aspect_ratio_resources --input-directory input/resources --output-directory output/resources --font C:/Windows/Fonts/arialbd.ttf
```

resources目录使用各银行原文件名，完整机内路径列于layout.json。输出目录不得已存在。构建器只处理本地文件，不连接、写入或重启相机。将组件装回固件仍需遵循既有重建、分区CRC、块校验和签名流程；这些命令不直接生成DAT。

## 组成

| 部分 | 修改 |
| --- | --- |
| AP状态与菜单 | 逻辑ID4–9，十行菜单；原ID4–7不变。token低4位为ID，bit4为完成位，bit5以上为epoch；schema2不变 |
| AP预览 | 选择页、Fn和拍摄页同步支持六比例，BSS地址与大小保持 |
| CP裁切 | 每张照片冻结的比例传给复制任务、JPEG/HEIF和1005/1012预检视YC构造；RAW幅面保持 |
| AP自动检视 | 根据本张YC PIN宽高计算居中的目标区域，显式布局避免后端按3:2重新铺满 |
| 回放 | AP和libmpr的尺寸表同步扩至18对 |
| 资源 | 68个文字库新增AB66/AB67，两个图像库新增六张Fn/菜单图像，保留既有有效载荷 |

新增21:9采用7/3，2.35:1采用47/20；全画幅L的JPEG尺寸分别为7008×3000、7008×2984，遵守原编码对齐。RAW保留完整幅面。

## 自动布局缺陷

仅改变YC裁切或提交目标矩形仍可能拉伸。CP 627A8C按014B命令体偏移1选择显式或自动布局；自动值1会经628004按原生比例重算目的区域。最终实现把自定义图像临时几何表的该值设为0，使目标区域与黑边保留。

为精确复建已实测机器码，fit.c保留共同计算结构，构建器再按layout.json把901F0F0的一条LDRB替换为MOV W10,WZR。explicit_mode.S记录这条指令；等价C语义为临时geometry[2]=0。该指令保留NZCV，原厂比例旁路和既有地址不变。

该适配器只接普通自动检视316B974内的三次布局调用，不接带直方图的316BD70。零尺寸哨兵布局未作为可用拟合基准验证。不要将本次RAW+JPEG实测扩展为所有格式、输出或方向均已验收。

## 与现有功能集成

精确链为[标题图标及精简](../../methods/08-custom-lut/RUNTIME-CLEANUP.md)→CP声音恢复基线→本配方。先前的[相册放大](../aspect-playback/README.md)、[任务复制](../aspect-capture-clone/README.md)和[菜单图标](../menu-ui-fixes/README.md)配方保留原哈希限制，不重复套用到本输出。

CP保留LUT捕获包装、机内RAW FL2/FL3参数、声音恢复页、AWB和已有常驻门；AP保留LUT触摸与标题图标、持久缓存和声音生命周期。AVCAM不变。AP、CP、libmpr和70个资源必须配套更新；旧token消费者或旧尺寸表不能混用。
