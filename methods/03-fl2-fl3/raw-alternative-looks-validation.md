# 机内 RAW 备选外观验证 / RAW alternative-look validation

## 维护者实测反馈 / Maintainer report

2026-11-11，维护者在测试后确认：Edit已能识别FL2和FL3。本次记录关联所交付CP组件`5ec4dee8e126ed54ff476b349e4d76318c98d3cc2f0ac9a5583ec98155b93fc4`。这确认了机内新增目录在Edit中的识别；此条反馈没有另行报告JPEG导出、逐像素颜色比较或全部RAW格式/连拍组合，也没有提供新的原片用于独立字节核查。

On 2026-11-11 the maintainer reported that Edit recognizes FL2 and FL3 after testing the delivered implementation. This record is associated with CP component `5ec4dee8e126ed54ff476b349e4d76318c98d3cc2f0ac9a5583ec98155b93fc4`. It confirms recognition of the camera-written alternatives. This feedback does not separately establish JPEG export, pixel-level colour agreement or every RAW-format/burst combination; no new original ARW was supplied for independent byte inspection in this confirmation.

## 原生离线检查 / Native offline scope

原指令重放覆盖构造、指针连接、头部、通用字段、Gamma backend/vtable、WB和SG导出描述。原十组有效字段及主SR2除`74C0`外保持，十二组各114项，指针和载荷在各自步长内，下一结构前的间隙保持。原始`A0FCA0`绑定还验证了task+`20`处理视图与实际RAW root/child字段的对应关系。

新增两组各105项A1矩阵/系数、三组CC1、128点Gamma及缩放C/D与参考对应值一致。104个公共字段与该合成状态的Standard一致；运行时量的该比较不是完整光照或渲染验收。唯一原生调用替身提供Backup项`3C0376=1C00`的两字节值；颜色、Gamma、IFD及布局函数均为保存的原始指令。处理状态为明确的合成fixture。完整包还做过块校验、分区CRC、明文回比与签名验证，二进制及私人fixture不随方法发布。

Native replay covered construction, pointer linking, headers, common fields, gamma/backend initialization, WB and SG export descriptors. Existing alternatives and root fields other than `74C0` stayed equal. All twelve children parsed as 114 tags, with bounded payload pointers and the reserved gap intact. Original `A0FCA0` binding also checked the task+`20` view against the actual root/child fields.

The added looks' 105 A1 matrix/coefficient values, three CC1 fields, 128 gamma points and C/D scale controls matched the corresponding reference values. The 104 common fields matched Standard under the supplied synthetic processing state. This does not establish all-lighting rendering equivalence. The sole native-call substitute supplied the two-byte Backup value `3C0376=1C00`; colour, gamma, IFD and layout code executed as original instructions. Full-package checks covered block checksums, partition CRCs, plaintext comparison and signing; complete binaries and private fixtures remain outside the publication.

## 与其他结果区分 / Related evidence

- [本组件方法](raw-alternative-looks.md) / [English](raw-alternative-looks.en.md)：相机直接生成供Edit选择的备选列表。
- [此前主矩阵与JPEG对比](color-validation-20261017.md)：另一次主拍摄参数/软件重选颜色测量，保留当时日期和范围；不自动转作本组件的新渲染结果。
