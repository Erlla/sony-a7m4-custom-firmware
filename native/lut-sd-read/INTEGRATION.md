# 合并进 Erlla / 其他开发者项目

上游参考仓库：[Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware)（GPLv3）。  
本目录位于 `native/lut-sd-read/`，可随本仓 PR 审阅；不含完整 `BODYDATA.DAT`、机身备份或额外私钥。

## 方案对比

| 方案 | 适合谁 | 做法 | 优点 | 注意 |
|---|---|---|---|---|
| **A. Issue + 补丁包** | 先沟通、不直接改对方树 | 开 Issue，附本目录 zip / 子树链接 + `ANALYSIS.md` | 零侵入；作者可审位点 | 不保证合入时间线 |
| **B. Fork PR → `native/lut-sd-read/`** | 希望进主仓 | 按对方 `native/<feature>/` 惯例放本目录；PR 只含源码/JSON/文档 | 符合 CONTRIBUTING；可复现 | 需钉输入 appFw 哈希；对方可能要求 Zig/layout 配方 |
| **C. 下游集成脚本** | 自己出包 / 社区 1119 | `apply_to_appfw.py` 改 `.so`，再用对方 `a7m4.firmware` encode+resign | 今天就能用 | 位点随 appFw 变；1119≠0.12 |
| **D. 子模块 / subtree** | 长期跟双方仓库 | `git subtree add` 本目录到对方 `native/` | 双向同步方便 | 许可须保持 GPLv3 兼容 |

**推荐路径：** 对 Erlla 用 **A → B**；对社区自签包用 **C**（本仓库已验证 `community_1119`）。

## 给 Erlla 的 PR 清单（建议）

1. **范围声明（写进 PR 正文）**  
   - 仅 SD Import 列表加速 + 边界翻页  
   - 机内 USER 槽保持 16；不抬 GUI 单页窗口 `0x10→0x40`  

2. **钉死输入身份**（`layout.json`）  
   - 目标 appFw SHA-256  
   - `VA = fo + 0x31B0000`  
   - before/after 十六进制与 cave 空区地址  

3. **目录落点（建议）**  
   ```
   native/lut-sd-read/
     README.md
     ANALYSIS.md
     layout.json
     patches/*.json
     asm/
     apply_to_appfw.py
   ```  
   命名可随作者习惯改为 `custom-lut-sd-paging` 等。

4. **构建边界**  
   - 本脚本只产出 `appFw.*.so`，**不**签名、不写相机  
   - 完整包仍走对方现有：替换 nflasha15 → `part_image.sum` → encode → resign  

5. **验证分层**（对方 CONTRIBUTING 要求）  
   - 指令级：before 匹配 / cave 反汇编  
   - 容器级：sum / 自签 decode 比对  
   - 实机：151 json（无 `._*`）列表可开、底行再滚换页、首尾不再换页  

6. **不要提交**  
   - 完整索尼/社区 `BODYDATA.DAT`  
   - 个人备份、额外私钥  

## 合并冲突时怎么对齐位点

对方 appFw 与 `author_0.12` / `community_1119` 任一不一致时：

1. 在新 `.so` 上搜 fast-scan `before` 80 字节；命中则 fast-scan 可复用。  
2. 找 open-import：`mov w10,#1` + `str` 到 msg `type`/`+0x18`/`+0x68`，记录 **msg 基址** 与尾部 `b`。  
3. 找列表 wrap：`csinc`/`csel` 环绕块（48 字节）→ `WRAP_SITE` / `WRAP_RESUME`。  
4. 把新基线写入 `patches/pagination_baselines.json`，再跑 `apply_to_appfw.py --baseline …`。

## 许可

原创内容按与上游一致的 **GPL-3.0-only** 提供，便于直接 PR。若对方要求额外署名，在 PR 中保留本目录作者信息即可。

## 最小对外说明（可贴 Issue）

```text
功能：Custom LUT → Import from SD
1) fast-scan：列表阶段跳过逐文件 JSON 解析（确认导入仍重解析）
2) edge page-flip：列表顶/底发 type=2，复用已有页加载器；页大小仍为 16
不改：机内 16 USER 槽；不抬高单页窗口（0x40 曾闪退）
基线：见 native/lut-sd-read/patches/pagination_baselines.json
工具：python apply_to_appfw.py --input appFw.so --output appFw.sd.so --baseline <name>
```
