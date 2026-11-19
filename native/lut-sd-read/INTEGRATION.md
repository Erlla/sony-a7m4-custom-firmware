# 集成到自定义固件

快扫和确认导入位点来自 Hippasu 的 [PR #35](https://github.com/Erlla/sony-a7m4-custom-firmware/pull/35)。

1. 按 [组件清单](layout.json) 核对输入 `appFw.so` 的完整 SHA-256 和大小。
2. 用 [快扫脚本](README.md#apply-to-an-extracted-appfwso) 生成独立 AP 文件，逐处核对快扫和确认导入的三个改写位点。
3. 使用项目的固件构建链封装。实机在 SD 导入目录放入超过 16 个有效 JSON，回放左右换页、上下选文件及确认导入。

## 许可

原创内容按与上游一致的 **GPL-3.0-only** 提供，便于直接 PR。若对方要求额外署名，在 PR 中保留本目录作者信息即可。
