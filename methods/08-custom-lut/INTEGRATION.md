# 自定义 LUT 对其他方法的影响

[方法入口](README.md) · [位置与组件身份](reference-layout.json)

核对采用当前实际 AP/CP 文件、公开方法的精确布局和原始调用关系。结论是需要**同步组合规则和文档**；已有独立方法仍保留其精确输入限制，不能通过扩大哈希白名单把旧地址配方用于新布局。

| 方法 | 影响与处理 |
| --- | --- |
| 自定义公钥、报告版本 | LUT 方法不修改更新器公钥、验签函数或 `updater/dat4`；最终包仍由原封装/签名流程处理。组件变化后必须重新计算校验和及签名。 |
| FL2/FL3 | 共用 CP 颜色消费者、Gamma 与网格。自定义代际只作用于私有标记，普通外观走原厂/既有移植路径；关闭恢复必须保留。不能把旧整份 CP 覆盖到新 LUT CP。 |
| 副厂电池 | 已逐项核对现有电池补丁位置，补丁字节保留；没有改充电、温度或认证源规则。 |
| 镜头 AF | **辅助函数已迁至 `0xBA5718`**；原独立配方 `0xBA4E00` 在组合布局中属于 LUT 常驻区。五个调用位置仍为 `0x3B3CB4/3B3006/3B321E/990ADC/990BAC`，均调用迁移后的函数；函数 34 字节与公开原配方一致。旧独立配方仅适用于其原输入哈希，不能对当前 CP 重放。未增加 AF 速度实测结论。 |
| 自定义声音 | AP 共用注册链、GUI 生命周期、存储模型与语言资源；CP 共用启动/消息分派空间。必须保留声音 owner、队列、实际消息长度和 `libmpr.so` 扩展；不能只判断“菜单能显示”。本布局 `libmpr.so` 与公开 JPEG EXIF 修正输出完全一致。 |
| 自定义纵横比 | CP 冻结与复制入口要同时保留比例和 LUT。`0xA049B0`、`0xA03142` 的 LUT 包装先保留原比例适配目标，再绑定 LUT 值与引用；不用错误 LR 进入按返回地址分派的旧包装。AP 比例 RX/RW 与 CP 比例代码/常驻门逐字节保持；BOOT/READY 与调用入口由组合链管理。 |
| JPEG EXIF 与 AVCAM | 本布局 `libmpr.so` 的声音/EXIF 输出哈希、`av-cam.bin` 的裁切输出哈希与已公开方法一致，无需再次修改。 |

## 共享空间

AP 纵横比 RX `0x09010000`、RW `0x09020000` 与 LUT 控制 RX `0x09000000`、后台 RX `0x09030000` 分开。程序头、相对重定位和注册入口仍须按完整对象组合；地址分开不代表可以整文件覆盖。

CP 纵横比实际 RX 为 `0x11B000..0x11B67C`，BSS 在 `0x11D000`，独立 READY 为 `0x1565F0C`。LUT 网格/生命周期 RX 使用 `0x11C000..0x11D000`；不要继续将旧链接脚本的整个预留区当作当前比例代码长度。LUT 的 READY、Gamma 表、声音状态各自分区，详情见位置清单。

声音状态的区间也必须保留：owner 为 `0x1564840..0x15648FC`，driver/gain 诊断合计到 `0x1564A84`。原厂 Gamma 回退表从 `0x1565000` 开始，177 行动态 Gamma 表位于 LUT 引擎堆对象中，不能把扩展表放回声音 RAM。检查声音代码字节不变还不够；同一份 CP RAM 中应串接启动、声音绑定、LUT 发布/关闭与两种声音播放，避免单独清空 fixture 掩盖覆盖。

文字 ID `0x0200AB60..AB63` 属于声音对话框；比例在组合布局使用 `0x0200AB4C..AB4F`。修改只作用于所属功能的引用，不能全文件替换。68 个横/竖屏银行必须作为完整资源集进入最终文件系统；应保留其他功能记录，而不是从旧方法整套回拷覆盖。

## 原工具如何使用

`a7m4.feature_integration` 保留为其列明输入的基础组合配方，不自动升级为 SD JSON/16 槽实现。`a7m4.custom_sound apply`、`repair-resources` 和 `verify-resources` 同样保持精确输入/目标合同：不同但合法的新组合资源可能无法通过旧目标哈希，拒绝本身不证明声音功能坏了。新组合需按当前组件/资源身份单独核对，不关闭检查或覆盖新 AP。

`a7m4.jpeg_exif_dimensions` 的目标 MPR 在当前布局仍被保留。电池和 AF 的原独立方法仍可对其原精确输入执行；组合后应重新定位/重新链接，不能把“原补丁功能保留”理解成“原整文件配方接受新输入”。

English: current integration preserves the aspect bodies, battery patch sites, relocated lens-AF helper and the published sound/EXIF MPR and AVCAM identities. Shared AP metadata, CP boot/capture/dispatch paths and language resources require composition. The AF helper now occupies `0xBA5718`, not the old standalone `0xBA4E00`. Existing patch tools remain pinned to their original inputs; do not extend their allowlists or replay old whole-file outputs over this layout. These structural checks do not establish physical AF speed or universal camera acceptance.
