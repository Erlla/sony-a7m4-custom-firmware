# 复用现有 sshd，开启 root SSH 与 SFTP

[总览](README.md) · [组件身份](reference-layout.json) · [验证边界](validation.md)

普通 6.02 系统已包含 `/usr/sbin/sshd`。本方法在 p15 补齐开机启动、NSS 账号、独立配置及 SFTP 子程序，不需要把 1.05 ULOGIO 整库搬过来。

## 文件布局

| p15 镜像内路径 | 运行时路径 | 处理 |
|---|---|---|
| `/bin/bootin.elf` | `/usr/bin/bootin.elf` | 加启动钩子，保持原主流程 |
| `/lib/libnss_ssh.so.2` | `/usr/lib/libnss_ssh.so.2` | 统一按名／UID 的 root 账号构造 |
| `/ssh/sshd_config` | `/usr/ssh/sshd_config` | 独立服务配置，0644 |
| `/ssh/ssh_host_ecdsa_key` | `/usr/ssh/ssh_host_ecdsa_key` | 自行生成的相机主机私钥，0600 |
| `/ssh/authorized_keys` | `/usr/ssh/authorized_keys` | 允许登录的客户端公钥，0600 |
| `/ssh/ssh_name_password` | `/usr/ssh/ssh_name_password` | `service,x` 加换行，0644 |
| `/ssh/sftp-server` | `/usr/ssh/sftp-server` | 匹配目标 ABI 的 AArch64 程序，0755 |

`/ssh` 目录为 root 所有、0755。客户端私钥留在电脑；相机主机私钥与允许登录的客户端公钥用途不同，均由使用者自行生成。账号文件中的 `x` 不是可用登录密码。

## bootin 启动钩子

对 JSON 绑定的原 `bootin.elf`，主入口 VA `0x4017e0` 改为跳到 `0x404340`（文件偏移 `0x4340`），将文件偏移 0 起始的 RX LOAD 覆盖范围扩展至 `0x4d58`，文件总长保持 23960 字节。

钩子保存参数、寄存器和栈，双 fork 后由子进程执行：

```sh
export LD_LIBRARY_PATH=/usr/lib:/lib
/usr/sbin/sshd -f /usr/ssh/sshd_config -E /tmp/sshd.log
```

父进程重放被覆盖的序言 `stp x29,x30,[sp,#-0x40]!`，返回 `main+4` 继续原启动。采用自行选定的诊断字符串时，重新计算 ADR、argv 和 cave 占用，不能保留旧指针或覆盖其他文件数据。

`/tmp`、`/etc` 和 `/var` 在这里同属持久 p10；日志和 marker 可能跨启动保留。用新连接和新命令验证，不凭旧 marker 宣称启动成功。

## NSS 账号修改

只对输入 SHA-256 为 `21c29cad2acc9af2183f81512a2ebdbc729bbf643fc41fd0cd28635944f051e4` 的 `libnss_ssh.so.2` 使用下列文件偏移；此文件相应 VA 与文件偏移一致。

| 偏移 | 写入的 AArch64 u32 | 作用 |
|---|---|---|
| `0x11b8`、`0x11cc`、`0x1348` | `0x52800000` | UID／GID 返回0 |
| `0x1264` | `0x7100001f` | 按UID查询选择0 |
| `0x11fc`、`0x1384` | `0xd28000a1` | home长度界限5 |
| `0x122c`、`0x13b4` | `0xd28000e1` | shell长度界限7 |

字符串完整槽先清零，再写 NUL 结尾的新值：

| 文件偏移 | 槽长度 | 新值 |
|---|---|---|
| `0x1428` | 8字节 | `/root` |
| `0x1438` | 11字节 | `/bin/sh` |
| `0x1445` | 35字节 | `/usr/ssh/ssh_name_password` |

按名和按UID查询必须同时得到 `service / UID0 / GID0 / /root / /bin/sh`。该模块读的是逗号格式的 `service,x`，不是 `/etc/passwd` 式冒号行。运行时 `/etc/nsswitch.conf` 还需 `passwd: files ssh`；匹配的6.02配置已有这一项。

## 配置与密钥

配置使用以下已验证的设置组合：

```text
Port 22
HostKey /usr/ssh/ssh_host_ecdsa_key
PubkeyAuthentication yes
AuthorizedKeysFile /usr/ssh/authorized_keys
PasswordAuthentication no
AllowUsers service
PermitRootLogin yes
UsePAM no
MaxSessions 10
PermitTTY yes
StrictModes no
Subsystem sftp /usr/ssh/sftp-server
```

这是该方法的服务端配置。Windows客户端是否接受私钥还取决于本地文件ACL；服务端 `StrictModes` 不解决 `UNPROTECTED PRIVATE KEY FILE`。客户端私钥应仅允许自己的 Windows 账户访问。

SFTP子程序必须与普通系统 loader/libc 的实际导出匹配。已使用的AArch64输入需要 `reallocarray@GLIBC_2.26`；普通 p7 可满足，p1 更新 libc 不满足。不要把普通p15 sshd/SFTP直接复制到p1后就视为能运行。

## 构建、部署与登录

将上述文件级修改合入本机完整 p15，保持其他文件和元数据。若需要新建 ext2 目录，`.` 的记录长度必须填充至12字节，`..`从偏移12开始，并同步位图、空闲数、目录计数和链接数。文件系统体积与物理分区长度分开处理。按[共同流程](README.md#共同的集成流程)写入并完整读回后正常启动。

已经部署对应修改、网络互通且客户端公钥已加入 `authorized_keys` 时：

```powershell
ssh -i .\local\camera_client_key service@<相机IP>
sftp -i .\local\camera_client_key service@<相机IP>
```

命令中的 `<相机IP>` 替换为实际地址；`camera_client_key` 是自己的客户端私钥，不是相机主机私钥。进入Shell后：

```sh
grep -E '^(Uid|Gid):' /proc/self/status
```

四项UID/GID均为0。精简环境可能没有PATH中的 `id`、`whoami` 或 `readlink`，不能据命令缺失判断root失败。SSH用 `exit` 退出，SFTP用 `bye`。

回退使用本机修改前的 p15；与 ULOGIO 方法叠加时做文件级合并并另行验收，不能覆盖整分区后假定两套功能都在。
