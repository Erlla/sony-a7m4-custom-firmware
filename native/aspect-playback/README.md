# 自定义比例照片的机内回放放大

本组件补齐自定义裁切照片的本机尺寸识别与JPEG读取布局，使JPEG／RAW+JPEG可在机内相册放大查看。照片的实际裁切宽高保持，RAW原始幅面与图库不改。维护者已在机身确认该问题修复。

[方法与地址说明](../../methods/07-custom-aspect-ratios/IMPLEMENTATION.md) · [精确输入／输出与源码身份](layout.json) · [组件工具](../../a7m4/aspect_playback.py)

## 两个处理层

| 层 | 处理 |
| --- | --- |
| AP本机尺寸识别 | 在0x2E2922C接入0x904C000，STILL类型接受四比例、全幅/APS-C、L/M/S形成的12种不同输出尺寸。其余输入继续原函数；x0..x7及9个栈参数保持。四个既有调用点共同使用该结果。 |
| JPEG读取布局 | 原生Exif读取仅识别有限宽高比；65:24等尺寸会使CamMetaInfo[0xC]比例有效位为0。在JPEG专用getter出口0x272130接入0x470400，只为元数据尺寸有效、比例无效且精确匹配项目尺寸的照片补基础布局提示0和有效位1。 |

基础布局提示是原生枚举兼容信息，独立的像素宽高仍用于解码与缩放，不把65:24照片变成3:2。原生已识别的5:4等比例保持原分类，未知尺寸继续原处理。RAW类及JPEG/HEIF拍摄写入不修改。

AP代码/表160字节、预留272字节；libmpr代码/表184字节。两者扩展各自既有RX程序头范围，文件长度不变，无新增BSS、堆或持久状态。AP保留LUT与声音段；libmpr保留声音CommonStop及JPEG EXIF写入修正。不能用旧独立整库覆盖当前组件。

## 从精确输入生成组件

从源码checkout运行，保留相邻native目录。使用Zig 0.14.1 Windows x86_64，完整编译器SHA见layout.json。输入是已有功能组合后的AP和带声音／JPEG EXIF修正的libmpr，不是原厂未修改文件。工具按完整输入、源码、编译器和输出SHA核对，拒绝覆盖已有文件。

    python -m pip install -e ".[firmware,test]"
    python -m a7m4.aspect_playback --component ap --input local/appFw.input.so --zig path/to/zig.exe --output local/appFw.playback.so
    python -m a7m4.aspect_playback --component mpr --input local/libmpr.input.so --zig path/to/zig.exe --output local/libmpr.playback.so
    python -m pytest -q tests/test_aspect_playback.py

输出父目录应已存在；工具只生成两个组件，不打包、签名或访问设备。集成顺序为既有声音/LUT AP → 本组件AP；JPEG EXIF宽高同步输出libmpr → 本组件MPR。完整安装仍需文件系统、分区及升级包构建流程。

## 验证边界

公开源码从精确输入重建，与已验收AP/MPR组件逐字相同。原生读取对照中，自定义JPEG仅改变运行时比例有效位，像素宽高保留；普通3:2与RAW元数据保持。AP原生几何为7008×2584图像生成7008×2592对齐画布，有效区域仍7008×2584。实际钩子在两个加载基址保留调用约定。

读取回放使用明确的libc／分配／锁／消息服务模型；可选XMP覆盖分配失败分支。离线回放不执行硬件熵解码、SD IO或显示交互，物理放大结论来自维护者的单台A7M4。HEIF回放放大不在该JPEG读取组件的验收范围。
