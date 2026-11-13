# LUT touch selection and aspect-menu icons

[自定义 LUT](../../methods/08-custom-lut/README.md) · [自定义纵横比](../../methods/07-custom-aspect-ratios/README.md) · [Exact component recipe](layout.json)

后续 AP 标题字形修改见[图片配置文件与 LUT 图标](TITLE-ICONS.md)。[运行时精简](../../methods/08-custom-lut/RUNTIME-CLEANUP.md)将本页触摸逻辑并入 GUI 分发，原独立组件仍用于重建前置阶段。

## 修改与组合

本组件补齐两处界面行为：自定义LUT左侧编号栏可触摸选择和预览；纵横比菜单的17:6、65:24、5:4、7:6显示各自对应的小图标。维护者已实机确认两项问题修复。

AP顺序为：已有声音生命周期 → 相册放大兼容AP → `lut-touch` → `aspect-ap`。纵横比图标同时需要`image-23`和`image-32`两个资源组件，它们作用于`/share/app/image_00_23_IPSX.uxc`与`/share/app/image_00_32_IPSX.uxc`。每一步只接受[配方](layout.json)中列明的完整输入哈希；这些是已集成功能的组件，不是官方固件的直接补丁。

LUT选择通知是原生`020F0001`、type4；消息`+10/+14/+18`分别是widget9、sceneD9和绝对行号。0为“关”，1–16对应内部槽0–15。`03010000`只是触摸开始，不包含行号。新入口在`904D000`，由固定分发表`903104C`调用；继续使用原预览队列和OK/MENU保存/取消，不在触摸时提交。原尺寸识别`904C000`、原事务函数及对象所有权保持。`abi.h`只描述访问到的字段，不是可另行分配的完整GUI对象。

纵横比菜单小图标在选项表`9020000+(4+i)*80h+0Ch`，与Fn的`+20/+24`不同。新增四项原先复制了3:2的小图标字段；现在映射到`02001E98..02001E9B`。新资源保持菜单原厂76×40画布、80像素对齐行宽和RGBA4444格式，复用已有Fn资源的数字画面，编码为4096/2304两个F0块。保留全部原厂和Fn压缩图像字节，利用全零尾部预留空间保持文件长度与文件系统分配不变。

## 离线构建

在仓库根目录使用Python 3.11+和项目依赖；原生入口使用配方指定的Zig编译器。输入文件由使用者从匹配组件中提取，输出路径必须未存在。

```powershell
python -m a7m4.menu_ui_fixes --component lut-touch --input appFw.playback.so --zig C:/tools/zig/zig.exe --output appFw.touch.so
python -m a7m4.menu_ui_fixes --component aspect-ap --input appFw.touch.so --output appFw.menu.so
python -m a7m4.menu_ui_fixes --component image-23 --input image_00_23_IPSX.uxc --output image_00_23_IPSX.menu.uxc
python -m a7m4.menu_ui_fixes --component image-32 --input image_00_32_IPSX.uxc --output image_00_32_IPSX.menu.uxc
```

图标AP字段与两个资源库一起集成，之后按原流程更新分区校验、封装和签名。组件工具只处理本地文件，不写相机。完整AP、资源库和固件不在本目录发布。

## Scope and implementation

The LUT number column now accepts touch selection through the native row-selection notification. Row zero means Off; rows 1–16 map to slots 0–15. The original preview queue, confirmation and cancellation retain transaction ownership. Touch-begin is a separate event without a selected-row payload.

The aspect popup uses a separate compact icon field from the Fn images. Each added ratio now has its own 76×40 menu image. The resource builder reuses the accepted numeric artwork, preserves all original/Fn compressed payloads, and retains both bank lengths. Its two independent compressed blocks match the existing 4KiB block profile.

Apply the AP components after sound lifecycle and the aspect-playback AP layer, in the order shown above, and apply both image-bank components for the aspect popup. The exact inputs and outputs are pinned in `layout.json`; earlier standalone recipes retain their own limits. CP, MPR, capture geometry and the existing playback helpers are unchanged by these UI layers.

The public source rebuilds the accepted AP stages and both image banks exactly. Native instruction replays cover row handling, menu queries and resource parsing; OS/model/render services and hardware decoding have separate boundaries. The maintainer confirmed the two reported UI issues on camera; this is not acceptance of every mode, output or body.
