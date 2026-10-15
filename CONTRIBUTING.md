# Contributions / 贡献说明

修改前阅读中英文 README、各独立方法和验证范围。每个新固件基线应记录机型、原始文件 SHA-256、ELF/CP 地址映射、明确的改动范围、回滚方式及验证证据。原生函数回放、完整包校验和实机测试应分别说明。镜头对焦速度功能必须保留未经实机测试状态；FL2/FL3 的当前颜色差异不得描述为官方色彩一致。

Please identify each new firmware baseline with model, input hashes, address mappings, bounded changes, rollback and verification evidence. Keep native instruction replay, container validation and hardware acceptance distinct.

不要提交完整索尼固件、个人机身备份、校准、外部驱动/payload 或额外私钥。唯一经授权的公开私钥例外是 `keys/published/` 中原有的指定密钥对；不要替换它，也不要把该公开身份用于生产信任。外部本地资源只放入忽略目录。

Do not submit complete Sony images, personal camera data, external driver/payload bundles or additional private keys. The existing explicitly published research pair is the only private-key exception. Preserve its identity and do not use it for production trust.

```powershell
python -m pip install -e ".[test,firmware]"
python -m pytest -q
python tools/check_public_tree.py
```

测试应使用合成数据，不接触相机。分发外部二进制前按它们的实际许可证保留 notices、源代码和构建证据，不能把“GitHub 可见”当作再分发授权。

Tests must use synthetic data without camera I/O. Before distributing external binaries, satisfy their actual licensing/source/notice requirements; public GitHub visibility is not redistribution permission.
