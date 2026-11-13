# 图片配置文件与自定义 LUT 标题图标

[菜单 UI 组件](README.md) · [精确组件及语言银行](title-icons.json) · [后续运行时精简](../../methods/08-custom-lut/RUNTIME-CLEANUP.md)

图片配置文件的菜单行与选择页标题共用 alternate caption，原厂的 `0x0200A48F` 字符串包含相机字形 `U+E662`。已有组合 AP 将 alternate caption 指向纯文字 `0x0200A9B2`。恢复原字符串引用即可让两处标题使用同一字形。

| 项目 | 修改 |
| --- | --- |
| AP VA | `0x5914980` |
| AP 文件偏移 | `93342080`，通过原 ELF `PT_LOAD` 换算 |
| 原 little-endian u32 | `0x0200A9B2`，字节 `b2a90002` |
| 新 little-endian u32 | `0x0200A48F`，字节 `8fa40002` |
| AP 输入 SHA-256 | `a09d023c1464b35e01bfbfc12b66d418731cf752e1c85b152496ba459203cd65` |
| AP 输出 SHA-256 | `5f559e84f5e43be45116455b366faf97a9bb846e881db7bc924882f87857a1b1` |

自定义 LUT 标题为 `0x0200AB75`。在 68 个语言方向银行中，为该记录的现有文本添加相同 `U+E662` 前缀，沿用原厂字形渲染。

## 字符串容器修改

1. 通过 UXC 索引定位 `0x0200AB75` 的字符串起止位置，记为 `start` 和包含末尾 NUL 的 `end`。
2. 在 `start` 插入 UTF-8 `EE 99 A2`，复制原文本及末尾 NUL，再追加一个零字节用于四字节对齐。每个银行增加四字节。
3. 原有 u16 word-offset 索引中，目标位置大于 `start` 的有效记录将 word offset 加一。`0xFFFF` 空项保留，调整后的有效 word offset 必须小于 `0xFFFF`。
4. 重新解析全部记录，核对原有 ID 集合及各文字。标题记录应等于字形加原文字。按清单核对每个银行的完整 SHA-256。
5. 将 AP 与全部语言银行一起回写对应文件系统，重算分区校验及容器签名，再进行后续组件集成。

`title-icons.json` 列出 68 个银行的文件路径、长度与前后 SHA-256。总字符串增量为 272 字节。修改复用原有字形和标题渲染逻辑。

原生菜单/选择页查询及全部资源解析已离线核对。精简组合继承此修复，维护者已反馈组合固件运行正常。

## English

The Picture Profile menu row and selector heading share an alternate caption. Restore the four-byte AP reference at VA `0x5914980` from plain-text ID `0x0200A9B2` to the stock glyph-prefixed ID `0x0200A48F`.

For Custom LUTs, prefix title ID `0x0200AB75` with `U+E662` in all 68 language/orientation banks. Insert the three UTF-8 bytes `EE 99 A2` before the existing text and one padding byte after its NUL terminator. Each bank grows by four bytes. Increment valid word offsets for records located after the insertion by one, keeping each below `0xFFFF`. Reparse the resource and verify every record and full output identity.

The manifest lists the exact AP transition and all language-bank identities. Integrate these resources with the AP caption change before applying runtime cleanup. Native caption queries and resource parsing were checked offline, and the maintainer reported normal operation of the subsequent integrated firmware.
