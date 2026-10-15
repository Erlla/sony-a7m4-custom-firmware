# 已公开的实验签名密钥 / Intentionally public research signing keys

这两个文件是维护者此前实际使用、并明确授权公开的一对 RSA-2048 密钥，未重新生成替代品。指纹见 [fingerprints.json](fingerprints.json)。

**私钥已公开，任何人都能生成在此公钥下有效的签名。有效签名不再证明包来自维护者，也不证明内容安全。不要将此密钥用于生产、账号、证书、SSH、保密或可信发行。** 安装使用此公钥的更新器后，只应刷入你自行审核、构建并核对内容的包。

如需自己的签名身份，生成新密钥并离线保管私钥：

```powershell
python -m a7m4.offline keygen local/my-keys
```

只发布你自己的公钥。此目录的显式公开例外不适用于其他人的私钥。

These are the maintainer's existing, owner-authorized RSA-2048 experimental keys, not a replacement pair. Anyone can sign with this private key. A valid signature under this public key provides no publisher authentication or safety assurance. Never reuse the pair for credentials, production trust, encryption, SSH or certificates. Generate a new local identity using the command above when you need private signing authority. Publication of this exact pair does not authorize publication of any other private keys.
