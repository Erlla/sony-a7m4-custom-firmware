# SD 卡 JSON 合同与转换边界

[使用方法](README.md) · [实现](IMPLEMENTATION.md)

每个滤镜使用一个 UTF-8 JSON 文件，直接放入 `PRIVATE/M4ROOT/GENERAL/LUT/`。

| 限制对象 | 上限／规则 |
| --- | --- |
| 单个 JSON 文件 | **131,072 字节（128 KiB，含等号）**，不能是空文件；空白与来源说明等内容也占文件字节 |
| SD 导入目录 | **256 个目录项**，非 JSON 文件和子目录也计数；不递归扫描子目录，第257项使扫描失败，不是截取前256项 |
| 机内用户槽位 | **16 个滤镜**，可替换／删除；“关”单独存在，内部缓存记录数不是用户槽位数 |
| 文件名 | 含 `.json` 最多 **63 个 UTF-8 字节**，不以点开头；扩展名不区分大小写 |
| JSON 内 `name` | 独立的最多 **63 个 UTF-8 字节**限制；不是磁盘文件名 |

名称限制按字节计算，不能把63字节理解为63个汉字。压缩包需先解压；超限或无效JSON可能使本次扫描／导入失败。建议导入目录只放本批有效JSON，其余文件放在该目录之外。文件大小、SD候选数量和机内保存数量是三个不同限制。

上限常量见公开头文件：[`P4_JSON_MAX_BYTES`](../../native/persistent-cache/include/p4_json.h) 与 [`P4L_CANDIDATES` / `P4L_SLOTS`](../../native/persistent-cache/include/p4_library.h)。

这里的 `version: 2` 是**文件格式版本**，`engine_abi: 131072` 是接口合同，不是固件开发版本。核心字段如下：

| 字段 | 内容 |
| --- | --- |
| `format` / `version` | `camera-look` / 整数 `2` |
| `model` / `engine_abi` / `mode` | `ILCE-7M4` / `131072` / `photo` |
| `id` / `revision` | 小写、带连字符、非零 UUID；正整数修订 |
| `draft` | 机内使用必须为 `false`，但改标记不等于完成转换验证 |
| `name` / `author` / `description` | 名称、作者、说明；名称为最多 63 个 UTF-8 字节 |
| `parameters.photo` / `.live` | 分开的原生系数、矩阵与 Gamma 参数；不能把照片分支直接复制成取景分支 |
| `parameters.grid` | `mode: disabled`，或 `mode: custom` 加 `encoding: a7m4-grid405-native-s7-v1` 与独立 photo/live 网格 |
| `defaults` | contrast、highlights、shadows、fade、saturation、sharpness、sharpness_range、clarity 八个整数默认值 |
| `required_capabilities` | 原生系数矩阵、照片/取景 Gamma、整组代际；启用网格时额外声明独立网格能力 |
| `payload_sha256` | 规范化运行字段的 SHA-256，不是简单对整个 JSON 文件求哈希 |
| `provenance` | 可选来源说明，不参与赋予颜色准确性或生产资格 |

自定义网格的 photo/live 各为 `[3][5][9][9]` 的整数数组，取值 −64～63。JSON 数值、结构、能力声明、原生语义和内容哈希必须共同通过。机内同时保留整文件 SHA-256，导入确认时重读比较，因此只修改说明文字也会被识别为文件变化。

`payload_sha256` 使用前缀字节 `CAMLOOK2\0` 加规范运行对象。参与的字段依次为 `defaults,draft,engine_abi,format,id,mode,model,name,parameters,required_capabilities,revision,version`；对象键规范排序，数值与字符串须遵循解析器的规范化合同。不要对带缩进的原文件直接求哈希作为此字段。

通用 `.cube` LUT 和 DCP 描述的是另一种颜色映射；需要拟合/转换为该相机原生参数，再分别验证照片与取景。文件格式通过只能说明可读取和满足数值合同，不能说明与输入预设颜色完全一致。本方法不附带商业预设、厂商颜色表，也不把仍在研究的色彩标定流程作为已完成的通用转换器发布。

English: this is a native camera-look JSON contract, not a renamed Cube/DCP file. Format/ABI revisions are independent of firmware labels. Conversion and measured color agreement must be evaluated separately; the camera validates structure, capabilities, native numeric constraints and runtime identity before import.


Import limits: each extracted native JSON must be nonempty and no larger than **131,072 bytes (128 KiB), inclusive**. The designated SD directory accepts at most **256 entries**, counting non-JSON files and subdirectories; it is not recursive, and a 257th entry fails the scan rather than truncating the list. The camera has **16 user look slots**, independently of internal cache records. Filenames, including `.json`, are limited to **63 UTF-8 bytes** and must not begin with a dot; extension matching is case-insensitive. The JSON `name` field has its own separate 63-byte limit. These are byte limits, not multibyte-character counts. See the [user-facing requirements](README.en.md#file-size-and-count-requirements).
