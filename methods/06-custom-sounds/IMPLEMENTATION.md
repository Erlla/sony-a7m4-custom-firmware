# 修改位置与实现方法

本说明对应[精确文件配方](../../a7m4/profiles/custom-sounds-reference.json)和[原生源码](../../native/custom-sounds/README.md)。以下地址均属于该参考布局的运行时 VA，不能当成其他程序的文件偏移；AP 必须通过 ELF `PT_LOAD` 映射，CP 平面文件偏移为 `VA - 0x108000`。协议 schema、资源 ID、会话代次与表 ID 是运行数据，不是报告的固件版本。

## 文件与源码分工

| 修改对象 | 公开源码 / 配方 | 修改内容 |
|---|---|---|
| `/lib/appFw.so` | [runtime](../../native/custom-sounds/runtime/src)、[worker](../../native/custom-sounds/worker/src)、[volume](../../native/custom-sounds/volume/src)、[ui](../../native/custom-sounds/ui/src) | 菜单、SD WAV 导入、持久化、异步工作线程、事件去重、PCM 转码、资源恢复、音量及完成刷新 |
| `/lib/libmpr.so` | 文件配方中 `kind=fs,path=lib/libmpr.so` | 追加/暴露声音菜单字符串资源范围；不替换整个原厂资源系统 |
| `/share/app/string_*_horizontal.uxc` 与 `_vertical.uxc` | 文件配方的 68 个 UXC 条目 | 横竖语言银行新增标题、开关/默认/导入提示、音量标签；保持原有字符串索引语义 |
| `cpapp-b.bin` | [owner](../../native/custom-sounds/owner/src)、[cp-gain](../../native/custom-sounds/cp-gain/src)与文件配方 | 原厂事件旁路采样、私有交易/消息路由、原生短音资源覆盖、焦点回退和私有音量标量 |
| `updater/dat4` | 不在本方法允许的文件集合中 | 不修改、不读取、不生成内部固件版本号 |

## 1. 菜单接入与可选状态

将“自定义电子快门声”“自定义对焦声音”作为独立父项放入“拍摄 → 快门/静音”。两个父页分别绑定专有状态，不能直接把原厂 User 槽标题当作开关枚举，否则会出现未展开的 `User${v1}` 或“此功能当前被禁止”。

菜单不是只添加字符串：需要同时补齐 parent/leaf/option/profile 注册表、别名、枚举值到显示 ID 的映射、回调地址和 `R_AARCH64_RELATIVE` 项。导入/音量的 availability 读取已提交开关，默认对焦项仅对焦槽拥有。音量枚举的 1–10 对应 10%–100%，不是旧 User 槽编号。

AP 新代码/状态的主要分区：

| 模块 | 代码 VA | 状态 VA | 备注 |
|---|---|---|---|
| 菜单/存储 runtime | `0x8F92000` 起 | 链接计划列明 | 原厂 controller、文件列表与 POSIX/Fsys 适配 |
| 声音 worker | `0x8FB0000`–`0x8FB8000` | `0x8FF7000` 起 | 当前代码 29584 B、BSS 3992 B |
| 音量 sidecar | `0x8FB8000` 起 | `0x8FFF000` 起 | 独立 CRC 音量记录与原生菜单回调 |
| GUI 完成刷新 | `0x8FB9400` 起 | `0x8FFF100` 起 | 312 B 代码、8 B BSS |

原通用事件入口 `0x19D7998` 先完整执行原处理；只在私有声音父页 `1592/1595`、私有控制器 `0x2D7` 的周期事件 `0x20F0000` 检查异步提交完成。随后更新开关、导入、音量三个 profile（原更新入口 `0x1C1E98C`），调用原父页刷新 `0x221D418`。刷新只消费一次，不伪造方向键，不从存储线程调用 GUI。这样选择“关”后文字与灰色状态一起更新。

## 2. WAV 文件列表与导入

`runtime/src/ap_sd_backend.c` 使用原厂媒体信息与 Fsys，从当前卡的 `/PRIVATE/SONY/PRO/SOUNDS/` 枚举 WAV。媒体状态是原生枚举，不可当成简单的 true/false；`FindFirst/FindNext` 对象需要独立 4 KiB 缓冲，不能用不足大小的栈对象。

保留原列表的移动、取消和确认调用合同；在原列表完成刷新后更新模型，避免“实际索引已变、橙色框未动”。声音页面隐藏旧 LUT 的日期/时间列，确认文字绑定音频文件和声音槽，不沿用“导入 LUT 到 UserN”。文件名显示来自已提交槽元数据。

输入由 `runtime/src/sound_core.c::ss_parse_wav` 严格解析 RIFF/chunk 长度、PCM 格式、采样率、通道、对齐与帧数。验证完成后才提交候选状态；不允许路径分隔符、目录跳转或格式错误内容冒充 WAV。导入后把完整 WAV 与名称保存到内部设置，不依赖下次开机仍插有同一张卡。

## 3. 持久化与提交边界

`ss_state` 保存两个槽的开关、名称、波形摘要/字节和 generation；序列化记录不含进程指针。`ap_runtime.c` 使用：

```text
/setting/csnd/settings.bin
/setting/csnd/settings.tmp
/setting/csnd/settings.bak
```

先写完整临时记录、检查实际写入和 fsync，再备份/改名并同步目录；失败保持原已提交状态。启动核验 schema、总长度、CRC、每槽波形 SHA-256、名称和 RIFF；主记录坏时尝试核验备份，不把坏数据标成成功。

音量使用同目录 `volume.bin/.tmp/.bak` 独立 sidecar，双槽初值为 50%。成功保存或恢复后才通知声音 worker。GUI 只排队，卡 I/O、转换和持久化不在合焦或快门中断/回调里执行。

## 4. 事件接入与播放格式

原厂电子快门没有可替换的快门 WAV，因此从已核验曝光消息产生电子声音 job，而不是把合焦声当成快门声。`worker/src/event_runtime.c` 对 28 B 消息检查长度、类型和字段，再用槽、照片序号、成员和 ordinal 去重；32 项队列与 64 项去重缓存均有界，旧 revision/generation 的 job 不再播放。

合焦通道保持原生提示流程：原厂合焦音资源 ID 为 17，电子短音使用独立资源 4。照片同时合焦时二者不应共用一个槽。原厂路径能直接播放时不再由 AP 重复排队；回退路径只有在通过对应策略/资源合同后才替换。

不能直接把 WAV 文件头送给 Sysnd，也不能把录像/视频回放的 PCM 接口当成原厂短提示音接口。最终 `worker/src/convert.c` 把 PCM 混为单声道，用 Q24 FIR 重采样到 24 kHz，再编码成 format 0 的 f0 块：每 31 个样本用 1 B 块指数＋31 B 量化样本，尾部补齐并保留 64 B guard。输入、暂存和描述符不得重叠；转换不分配活动 DMA 资源、不使用浮点/SIMD。

## 5. AP/CP 资源交易与重启恢复

CP 文件中 `0xBA5C80` 起的 owner 模块只处理私有协议；原回复消费、队列返回与资源注册表保持原调用合同。其 BSS 从 `0x1564840` 起。相关短音原入口包括播放 `0xA55998`、配置 `0xA55926`、停止 `0xA55F80` 与回调 `0x5DEB18`；所有跳板均需保留被覆盖原指令和 ARM/Thumb 状态。

每个声音槽使用三段连续 51200 B 原生 DMM 单元，两个槽共六个租约。执行顺序为：

```text
申请并核验六个新 CLAIM ACK
→ BIND（句柄/范围/容量/相邻/唯一性）
→ PREPARE（等待原生播放退休，不覆盖活动数据）
→ COPY（分段传输并统计长度/CRC）
→ COMMIT（核验 generation、长度、CRC、guard 与缓存清理）
→ POLICY/原生 Start → 原回复消费及自然退休
```

正常 OFF→ON 不一定清掉 AP 保存的数字句柄，而 CP 池可能已经重建。故障的关键是“旧数字还存在”不等于“仍归声音所有”。`worker/src/resource.c::reclaim_eligible` 只把完整 owner=0/phase=0、无有效旧租约、所有探测齐全的失效/异容量结果当作放弃旧引用的负面证据，再申请六个新租约。

尤其是编号被别的容量资源复用时，不释放、不读写、不借用这个旧编号。新 CLAIM ACK 与后续 BIND 才是新所有权依据。失败、BUSY 和超时走有界状态机，不通过清共享计数或缩短等待伪造成功，以免重现写卡不结束和 OFF/ON 失效。

## 6. 音量一致与原厂回退

`convert.c::csnd_pcm_f0_volume` 对两个槽采用同一数字增益：`volume_step/5` 乘以当前基准；50% 对应 1 倍、100% 对应 2 倍，并有整段峰值控制。增加幅度不等于任意录音的主观响度都相同。

原厂对焦和独立电子声还经过不同的 CP 音量消费者。`cp-gain/src/gain_scalar.S` 在 `0x1905E4` 的原消费者附近只对已认证私有 descriptor/cookie 选择一致标量；不能全局抬高原厂提示、录像或视频声音。新增采样/标量代码位于 `0xBA5000` 起，BSS 位于 `0x1564900`，结束 `0x1564A84`；相应映射/冷启动清零上界随之更新。只写 BSS 变量而不检查原清零循环会在再次开机时失败。

静音优先于两类播放。非电子快门的电子声音关闭由维护 worker 持久提交；原厂对焦提示关闭、自定义关闭或“默认”仍使用原来的静音与 AF 模式规则。默认回退不能依赖自定义资源必须成功初始化。

## 配方复核方法与验证边界

`a7m4/custom_sound.py` 对每个输入先做完整 SHA-256，再重建 COPY/ADD 操作，核对完整输出 SHA-256。所有文件预检通过才建立新输出目录。`tools/build_custom_sound_native.py` 则从公开源码构建六个 ELF，检查已定义符号、每个分配段地址/长度与源编译摘要；应用已列明 post-link 细补丁后再核对最终安装段摘要。

runtime 与 CP owner 的少量后链接差异已单列在 `build-plan.json` 的 `post_link_ops`，不能忽略它们而把较早 C 源直接替代当前安装段。完整镜像配方还包括菜单元数据、重定位表、原生消息跳板与语言银行，不是六个 ELF 的简单拼接。

证据 → 结论 → 使用路径：公开源码清单/模块验证和 71 个完整文件摘要证明此配方能复现列明参考布局的声音实现；C/Python 测试证明覆盖的解析、策略、持久化拒绝与输出保护行为；机内听音/重启反馈属于既有单机测试。新的地址布局或与其他补丁重新组合，仍需重新完成 AP/CP 原指令验证、完整包检查与实机验收。
