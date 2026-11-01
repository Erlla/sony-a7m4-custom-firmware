# 验证范围与集成注意

[总览](README.md)

下列结论来自单台 ILCE-7M4、已绑定二进制布局的既有实机验证，公开文档整理没有重复操作相机。

| 方法 | 已验证 | 未覆盖 |
|---|---|---|
| ULOGIO网络终端 | TCP23命令往返、UID/GID0、退出重连、普通拍摄保存回放 | 原厂1.05默认开放状态、任意网络配置及其他机身 |
| ULOGIO USB终端 | 认证后双向bulk、root命令、ash退出后停用／重开、与Telnet共存 | 任意USB驱动环境、完整作业控制 |
| SSH/SFTP | 公钥认证、root命令、PTY、文件上传下载与删除、Windows原生SSH、普通拍摄 | 与ULOGIO方案叠加后的整体验收 |
| p1/Cetus UART | 二进制双向传输、缓存跨界、root命令、exit后新Shell、回普通模式拍摄 | 长时间高负载、无标记分支执行真实SD更新、其他机身 |

网络与USB的ULOGIO创建路径、SSH服务和UART桥接是不同实现。不能把门控放行、符号名、组件存在、离线模型或文件系统可枚举当作真实连接证明。

## 文件系统与账号

- p15镜像内 `/lib`、`/bin`、`/ssh` 在普通系统分别变为 `/usr/lib`、`/usr/bin`、`/usr/ssh`。
- p15文件系统长度与物理分区长度不同，保留完整尾部。新ext目录的记录填充、位图和计数必须正确；宽松解析器列出文件不证明内核能读目录。
- NSS读取逗号格式，按名和按UID构造必须一致。只改配置中的PermitRootLogin或一个shell字符串不足以实现登录。
- `/tmp`、`/etc`、`/var` 同属持久p10；旧marker不是本次启动证明。

## 终端与硬件

- USB TERM_MODE用输入／输出双字节，不按旧端点算式选错bulk接口。
- Telnet建立监听后必须纳入select nfds；仅TCP握手不能证明accept和PTY循环正常。
- CP UART0与AP ttyAMA0不是同一物理通路；RP2040的Output disable也不是自动开漏UART。
- p1更新环境不运行普通拍摄系统，关闭客户端或exit不会自行移除p2启动标记。

组件来源见 [reference-layout.json](reference-layout.json)。其中是厂商组件和接口布局身份，不是个人分区备份或当前相机状态清单。
