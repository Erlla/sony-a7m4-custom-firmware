# Custom LUT：SD 卡列表 / 翻页 /「151」说明

本目录只覆盖 Custom LUT **Import from SD** 浏览链路（列表加速 + 边界翻页）。机内 USER 槽位数保持 16，不在此扩容。

## 1. 「151」到底指什么

| 概念 | 上限 | 本方案是否改动 |
|---|---|---|
| SD 目录枚举（含 `._*` 等垃圾项） | **256** 项 @`0x903491C` | 否 |
| 扫描结果数组 | 256 × `0xD8` | 否 |
| 列表 UI 窗口 | **16 行**（0…15 + 占位 `0x10`） | **否**（抬到 64 曾在 ~151 json 上闪退） |
| 单次批量/页请求 | **16** @`0x90333D8` / `0x9035E58` | 否 |
| 机内 USER 槽 | **16** | **否**（另题） |
| 实测可浏览 json 数 | 清理 `._*` 后 **151** | 靠 fast-scan + 翻页达成 |

结论：**151 是 SD 上可列出的有效 `.json` 数量**（配合翻页），不是把机内存储扩到 151 槽。

## 2. 为什么作者包「看起来只有 ~15 条」

1. GUI 固定 16 行窗口，从未发 `type=2` 翻页消息。  
2. 扫描成功路径永远 `mov w1,wzr` 只拉第 0 页。  
3. 作者自带滤镜包约 15 款，与窗口同量级。  
4. 若目录项 >256（常见：151 json + 大量 macOS `._*`），整次扫描失败，不是「只显示前 N」。

## 3. 后台其实已有翻页 API

| 点 | VA（AP） | 行为 |
|---|---|---|
| 消息分发 | `0x9032494` 一带 | `[msg+8]==2` → 按 `[msg+0x18]` 起始下标加载 |
| 页加载器 | `0x9033390` | 先清 `0xD90` 页缓冲，再要 16 条 |
| 打开 Import | open-import | 写 `type=1`、`start=0` |

缺的是 **GUI 状态机**：从未构造 `type=2` 且 `+0x18≠0`。

## 4. 本方案两刀

### A. Fast-scan + import-relax

- 列表扫描时跳过逐文件 JSON 全解析（`0x9034B6C`），只登记文件名并清零 meta。  
- Import 确认路径已会重解析所选文件；放宽与 scan-time size/meta 的比对（否则报 `-0x57d`）。  
- 目的：151 个文件打开列表不再像死机。

### B. 边界翻页（edge page-flip）

- BSS `0x8F73A00`：`page_start` / `total`。  
- 打开 Import：清 `page_start`。  
- 页加载成功：记下 `total`。  
- 列表顶/底 wrap：若还有上一/下一页 → `page_start±16`，写 msg `type=2`；否则保持原 in-page wrap / 首尾不动。  
- **禁止**在 wrap cave 里同步 `bl` producer/refresh（会卡死 UI 线程）。

## 5. 基线位点（必须按 appFw 选）

| 符号 | author / Toolkit 0.12 | community BODYDATA1119 |
|---|---|---|
| WRAP_SITE | `0x9002D1C` | `0x9001F6C` |
| OPEN clear 钩 | `0x900774C` → `0x900748C` | `0x90063FC` → `0x900613C` |
| msg 基址 | `0x8F77614`（page+`0x614`） | `0x8F7741C`（page+`0x41C`） |
| TOTAL_SITE | `0x90333E0` | 同 |
| FAST_SCAN | `0x9034B6C` | 同（before 字节一致） |

详见 `patches/pagination_baselines.json`。

## 6. SD 卡使用注意

路径：`/PRIVATE/M4ROOT/GENERAL/LUT/`  

- 目录项总数（含隐藏文件）须 **≤256**。  
- macOS：`cp -X` 或拷完后 `dot_clean`。  
- 单 json ≤128KiB；UUID 冲突会导致扫描失败。
