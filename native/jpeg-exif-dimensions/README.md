# JPEG EXIF 宽高同步

JPEG 编码主图可能已裁切或缩小，但 EXIF 写入器仍读取原始幅面的宽高。本组件在**带有自定义声音扩展的 libmpr** 中修正 JPEG 专属写入路径，使 A002／A003 跟随本张主图尺寸。

## 实现

原厂 JPEG 对象的 header vfunc `0x2732F0` 读取 ExifSrcArea+5C/+60。448 字节前置函数读取当前主图 SOF0，范围不超过 min(length, 0x800)，只接受完整的 8 位／3 分量帧头。宽高不同时，在原厂已分配的 object+13C0 私有区域复制 0xBC 字节源记录，改写两字段，仅重定向本 JPEG 的 add_if。共享源及 RAW 不写；无效输入或尺寸已一致时保持对象不变。寄存器、NZCV 和原函数栈行为保持。

声音版有效 ELF 程序头位于 **0x370000**，不能沿用原厂 0x40 表偏移。补丁扩展原 RX 到 0x2EA010，使用已核对的零填充区，保留声音 CommonStop、附加 RX/RW、重定位、文件长度及 RAW 独立入口。

## 使用

[精确输入／输出及源码身份](layout.json)、[组件工具](../../a7m4/jpeg_exif_dimensions.py)。输入 libmpr 和 Windows x86_64 Zig 0.14.1 均按 SHA-256 检查，不接受任意相近版本。

```powershell
python -m pip install -e ".[firmware,test]"
python -m a7m4.jpeg_exif_dimensions --input local/libmpr.sound.so --zig path/to/zig.exe --output local/libmpr.exif.so
python -m pytest -q tests/test_jpeg_exif_dimensions.py tests/test_feature_integration.py
```

从源码 checkout 运行，保留相邻 `native/`。输出目录须已存在、文件须尚不存在；工具拒绝覆盖和 Python `-O`。它只生成组件，不打包、签名或访问设备。完整集成仍需文件系统和分区校验，不能把 .so 直接交给 SD 更新器。

## 验证范围

[组件检查摘要](validation.json)：148 项双基址原生 JPEG 回放，覆盖实际编码主图头、L/M/S、原比例、失败输入、ABI 与 RAW 派发隔离；7 项新 MPR 声音生命周期回放。便携工具使用精确输入重建得到相同组件哈希。

原生测试使用 libc／allocator／OS／AV 模型，XML 仅覆盖原厂分配失败分支，不代替完整 RAW writer、机内调度或物理声音验收。本组件只处理 JPEG EXIF A002/A003，SIDB 内部数据库和 HEIF 不在修改范围。需要检查新拍照片；已有照片不会自动改变。

具体固件版本、安装包身份、逐轮实拍与操作验收留在研究库。公开目录保留可复核的实现、适用输入哈希和组件验证边界。
