# 6.63：JPEG EXIF 宽高修正组件

6.62 组合包已获单机 A～J 和菜单／声音复测支持，但四种自定义比例的 JPEG 像素已裁切、ExifIFD A002/A003 仍保留 7008×4672。本组件在**现有声音版 libmpr** 上修正 JPEG 专属写入路径。6.63 离线原生回放及签名包核验完成，**实机修复待验证**。

## 实现

原厂 JPEG 对象的 header vfunc 0x2732F0 读取 ExifSrcArea+5C/+60。448 字节前置函数读取当前编码主图的 SOF0，范围不超过 min(length, 0x800)，只接受完整的 8 位／3 分量帧头。宽高不同时，使用原厂已经分配的 object+13C0 私有区域复制 0xBC 字节源记录，改写两字段，并只重定向本 JPEG 的 add_if；共享源及 RAW 不写。无效输入、原本一致的尺寸不修改对象。所有寄存器、NZCV 和原函数栈行为保持。

声音版有效 ELF 程序头已经移到 **0x370000**；不能沿用旧的 0x40 表偏移或用原厂无声音库覆盖。补丁只扩展原 RX 到 0x2EA010，并使用已经核对的零填充区。声音 CommonStop、附加 RX/RW、重定位、文件长度及 RAW 独立入口保持。

历史 T8 曾将旧 EXIF 候选与菜单修改一起撤回，菜单重启并未唯一归因；本修订以已验收的合并 6.62 为基线，不恢复那组旧程序，仍需新版实机回归。

## 使用

[精确输入与输出身份](layout.json)；[组件工具](../../a7m4/jpeg_exif663.py)。固定输入为本项目声音版 libmpr，固定编译器为 Windows x86_64 Zig 0.14.1，二者按完整 SHA-256 检查。需要自行持有输入文件；仓库不附带完整厂商程序或 DAT。

```powershell
python -m pip install -e ".[firmware,test]"
python -m a7m4.jpeg_exif663 --input local/libmpr.sound.so --zig path/to/zig.exe --output local/libmpr.exif663.so
python -m pytest -q tests/test_jpeg_exif663.py tests/test_combined662.py
```

输出目录应已存在，输出文件不得已存在；工具拒绝覆盖和 Python -O。它只生成组件，不打包、不签名、不接触相机。完整合并需要更新 nflasha15、对应 CRC 及版本，不能直接把 .so 交给 SD 更新器。

## 验证与边界

[validation.json](validation.json) 记录当前输出身份：148 项双基址原生 JPEG 回放，包含 10 张 6.62 实拍主图编码头、L/M/S、原比例、失败输入、ABI 与 RAW 派发隔离；7 项完整新 MPR 的声音生命周期回放。便携工具在真实输入上重建得到相同组件哈希。最终本地 DAT 的 739,727 块、5 个分区 CRC、169 个 TAR 项、32 套颜色模板以及 1,122 个文件系统路径通过核验；相对已验收组合 6.62，仅 MPR、版本及校验值变化。

原生测试使用 libc／allocator／OS／AV 服务模型，XML 仅覆盖原厂分配失败分支；不声称物理扬声器、完整 RAW writer 或相机线程调度已验证。本补丁只修 JPEG 的 EXIF A002/A003，不修 SIDB 内部数据库或 HEIF。旧照片不会自动变化，必须检查新拍 JPEG 的实际尺寸与 EXIF 是否一致。LUT P2 的定量性能及同包 FL2 对照仍未关闭。
