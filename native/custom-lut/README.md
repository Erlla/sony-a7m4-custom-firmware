# 自定义 LUT 原子缓存核心

[完整方法](../../methods/08-custom-lut/README.md) · [生命周期接线](../../methods/08-custom-lut/IMPLEMENTATION.md) · [源码身份](source-manifest.json)

`cache_core.c/.h` 为实际实现中的原创引用/回收核心，保持源字节；`cache_thread_fixture.c` 是 Windows 主机线程压力夹具，不链接进固件。它们不包含厂商颜色表。

核心采用单写者、每 lease 单所有者：先获取原子引用，再读取 generation；发布内容持有初始引用；最后一个使用者释放后才允许覆盖。全部 63 个 bank 被引用时返回 BUSY。旧编号在复用后不能冒充新内容。这里的驻留数量不是用户槽位数量，也不是累计编辑上限。

使用支持 GCC 原子内建的 C11 编译器。独立主机检查（Windows，Zig 或兼容 Clang/GCC）：

```powershell
python tools/test_custom_lut_cache.py --zig path/to/zig.exe
```

脚本在系统临时目录编译测试 DLL，执行全占用/释放/陈旧引用检查和并发读写压力，不访问相机。临时编译产物不加入 Git。此核心依赖正确的原生对象交接，完整 AP/CP 接线见方法说明；仅编译这几个文件不会生成完整 LUT 固件。

English: original atomic cache implementation and a Windows-only host fixture. Single serialized writer, uniquely owned leases, pin-before-generation-read, and reclamation only after the final reference. The host test verifies the core; it is not a complete firmware build or a physical camera scheduling test.
