## 隐私信息（PII）加密/解密流程中文指南

本指南介绍如何在当前项目目录中，将任意 PDF 文档转换为 Markdown，并对文档中的 PII 进行识别与加密；同时也涵盖如何使用同一密钥进行解密恢复原文。

### 一、环境准备

- 需要已安装 Python 3.9+（本项目环境为 Python 3.13）。
- 进入项目根目录后，确保已安装依赖（若你此前已运行过示例，可跳过）：

```bash
pip install -r requirements.txt
pip install pymupdf cryptography presidio_analyzer presidio_anonymizer spacy
python -m spacy download en_core_web_sm
# 如需更高识别率/召回率，可安装大模型：
# python -m spacy download en_core_web_lg
```

### 二、核心脚本说明

- 将 PDF 转为 Markdown：`pdf_to_md.py`
- 识别并加密/解密 PII：`pii_encrypt_md.py`

两者的默认输出策略：会将结果写入“与输入文件同名的子文件夹”内（例如 `payment_elections.pdf` → 输出到 `payment_elections/`）。

### 三、对单个 PDF 进行加密（含自动转换）

以下命令会：
1) 若输入为 PDF，先转换为 Markdown；
2) 使用 Presidio 识别 PII；
3) 将命中的片段替换为可逆的加密标记；
4) 生成 PII 报告 JSON；
5) 控制台打印生成的密钥（请妥善保存）。

```bash
python pii_encrypt_md.py encrypt payment_elections.pdf --print-key
```

输出文件（默认）：
- 加密后的 Markdown：`payment_elections/payment_elections.md`
- PII 报告 JSON：`payment_elections/payment_elections.md.pii.json`

可选参数：
- 指定识别的实体类型（例如仅邮箱与手机号）：
```bash
python pii_encrypt_md.py encrypt payment_elections.pdf --entities EMAIL_ADDRESS PHONE_NUMBER --print-key
```
- 指定输出目录（而不是默认同名子文件夹）：
```bash
python pii_encrypt_md.py encrypt payment_elections.pdf --outdir out/payment_elections
```
- 指定输出文件路径（与 `--outdir` 互斥）：
```bash
python pii_encrypt_md.py encrypt payment_elections.pdf -o out/payment_elections_masked.md
```

### 四、解密（恢复原文）

你必须使用“加密时生成的同一把密钥”。示例：

```bash
python pii_encrypt_md.py decrypt payment_elections/payment_elections.md --key <你的密钥> -o payment_elections/payment_elections.decrypted.md
```

可选参数：
- 指定输出目录（自动创建）：
```bash
python pii_encrypt_md.py decrypt payment_elections/payment_elections.md --key <你的密钥> --outdir out/payment_elections
```
- 原地覆盖（不推荐，容易误操作）：
```bash
python pii_encrypt_md.py decrypt payment_elections/payment_elections.md --key <你的密钥>
```

### 五、仅进行 PDF → Markdown 转换（不加密）

```bash
python pdf_to_md.py path/to/file.pdf
# 默认输出：path/to/file/file.md 位于 path/to/file/ 子文件夹
```

可选：
```bash
python pdf_to_md.py path/to/file.pdf --outdir out/folder
python pdf_to_md.py path/to/file.pdf -o out/folder/custom.md
```

### 六、批量处理多个 PDF（示例）

以 PowerShell 为例，将当前目录下所有 PDF 批量加密：

```powershell
Get-ChildItem -Path . -Filter *.pdf | ForEach-Object {
  python pii_encrypt_md.py encrypt $_.FullName --print-key
}
```

如需固定输出目录：
```powershell
Get-ChildItem -Path . -Filter *.pdf | ForEach-Object {
  $name = [System.IO.Path]::GetFileNameWithoutExtension($_.FullName)
  python pii_encrypt_md.py encrypt $_.FullName --outdir out/$name --print-key
}
```

批量解密示例（需为每个文件提供正确密钥；若各文件密钥不同，需逐个指定）：
```powershell
Get-ChildItem -Path . -Recurse -Filter *.md | ForEach-Object {
  python pii_encrypt_md.py decrypt $_.FullName --key <你的密钥> --outdir out/dec
}
```

### 七、密钥管理与安全注意事项

- 加密使用对称加密 Fernet。解密必须使用与加密相同的密钥。
- 丢失密钥将无法恢复原文；请妥善保存（例如安全的密钥管理服务或加密存储）。
- 不要将密钥提交到版本库或明文共享。
- 若需更换密钥：用旧密钥解密得到明文，再使用新密钥重新加密。

### 八、识别效果与可调项

- 模型：默认优先 `en_core_web_lg`，无法获取时回退至 `en_core_web_sm`。若网络受限可手动离线安装。
- 实体类型过滤：通过 `--entities` 指定需要的 PII 类别（如 `EMAIL_ADDRESS`、`PHONE_NUMBER` 等）。
- Markdown 表格对齐：脚本采用不破坏结构的占位标记 `{{ENC:<ENTITY>:<TOKEN>}}`，一般不影响表格布局。

### 九、常见问题（FAQ）

1) 运行时报找不到解析库？
   - 安装任一 PDF 解析库即可：`pip install pymupdf` 或 `pip install pdfminer.six` 或 `pip install pypdf`。

2) 识别不准或漏检？
   - 尝试安装并使用大模型 `en_core_web_lg`；或通过 `--entities` 聚焦目标实体以减少误报。

3) 解密失败、标记未被还原？
   - 多半是密钥不正确或标记被破坏。确保提供的密钥与加密时完全一致，且文档中的 `{{ENC:...}}` 标记未被修改。

---

## 十、高级隐私与安全功能

### 10.1 不可逆匿名化模式

除了可逆的加密模式，现在支持**不可逆匿名化**，用占位符替换 PII（无法恢复原文）：

```bash
python pii_encrypt_md.py encrypt document.pdf --mode anonymize
```

输出示例：
- 原文：`john.doe@example.com`
- 匿名化后：`[EMAIL_ADDRESS_1234]`

**区别：**
- `--mode encrypt`（默认）：可逆，需要密钥解密
- `--mode anonymize`：不可逆，用于完全去标识化场景（如数据分析、LLM 输入）

### 10.2 审计日志

所有操作自动记录到 `audit.log`（JSON 格式），仅记录元数据，不含实际内容：

```json
{
  "timestamp": "2025-11-10T12:34:56Z",
  "operation": "pii_encrypt",
  "file": "document.pdf",
  "user": "username",
  "mode": "encrypt",
  "pii_total": 15,
  "entity_counts": {"EMAIL_ADDRESS": 5, "PHONE_NUMBER": 10}
}
```

自定义日志路径：
```bash
python pii_encrypt_md.py encrypt document.pdf --audit-log custom_audit.log
```

### 10.3 数据自动清理

使用 `cleanup.py` 自动删除过期文件（符合数据保留策略）：

```bash
# 删除 7 天前的文件（默认）
python cleanup.py ./output --retention-days 7

# 仅删除特定类型文件
python cleanup.py ./output --retention-days 30 --patterns .md .json

# 预览模式（不实际删除）
python cleanup.py ./output --retention-days 7 --dry-run

# 同时删除空目录
python cleanup.py ./output --retention-days 7 --remove-empty-dirs
```

**定时任务示例（Windows 任务计划程序）：**
```powershell
# 每天凌晨 2 点清理
schtasks /create /tn "PII Cleanup" /tr "python D:\path\to\cleanup.py ./output --retention-days 7" /sc daily /st 02:00
```

### 10.4 S3 加密存储

将处理后的文件上传到 S3 并启用服务端加密：

```bash
# 使用 AES256 加密
python s3_upload.py document.md --bucket your-secure-bucket --encryption AES256

# 使用 KMS 加密
python s3_upload.py document.md \
  --bucket your-secure-bucket \
  --encryption aws:kms \
  --kms-key-id arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012

# 添加元数据
python s3_upload.py document.md \
  --bucket your-secure-bucket \
  --metadata type=pii-masked version=1.0
```

**前置要求：**
```bash
pip install boto3
# 配置 AWS 凭证（使用 IAM 角色或 AWS CLI）
aws configure
```

详细 IAM 策略配置见 `IAM_POLICY.md`。

### 10.5 Docker 容器隔离处理

在临时、隔离的容器中处理文档（容器处理完自动销毁）：

**1. 构建镜像：**
```bash
docker build -t pii-processor:latest .
```

**2. 容器化处理：**
```bash
# 基础用法
python docker_process.py document.pdf -o ./output

# 匿名化模式
python docker_process.py document.pdf -o ./output --mode anonymize

# 指定实体类型
python docker_process.py document.pdf -o ./output --entities EMAIL_ADDRESS PHONE_NUMBER

# 自动构建镜像并处理
python docker_process.py document.pdf -o ./output --build
```

**安全特性：**
- ✅ 容器内以非 root 用户运行
- ✅ 输入文件只读挂载
- ✅ 处理完成后容器自动销毁
- ✅ 无持久化数据残留

**前置要求：**
```bash
pip install docker
# 确保 Docker Desktop 已启动
```

---

## 十一、完整隐私与安全架构

### 架构图

```
[PDF 文档] 
    ↓
[Docker 容器隔离处理]
    ↓
[Presidio PII 识别]
    ↓
[加密/匿名化] ← [审计日志记录]
    ↓
[S3 加密存储] ← [IAM 访问控制]
    ↓
[自动清理策略] ← [保留期限管理]
```

### 安全最佳实践

1. **使用容器隔离**：生产环境必须使用 Docker 容器处理
2. **启用审计日志**：所有操作记录到集中日志系统
3. **匿名化优先**：向 LLM 或外部系统发送数据前必须匿名化
4. **加密存储**：S3 启用服务端加密（AES256 或 KMS）
5. **最小权限**：IAM 策略仅授予必要权限
6. **定期清理**：设置自动清理任务，符合 GDPR/HIPAA 要求
7. **密钥管理**：使用 AWS Secrets Manager 或 HashiCorp Vault

### 合规性支持

- **GDPR**：自动删除 + 匿名化 + 审计日志
- **HIPAA**：加密存储 + 访问控制 + 容器隔离
- **SOC 2**：审计追踪 + 最小权限 + 数据保留策略
- **PCI DSS**：加密传输/存储 + 访问日志

---

## 十二、故障排查

### 问题：Docker 容器无法启动
**解决：**
```bash
# 检查 Docker 是否运行
docker ps

# 重新构建镜像
docker build -t pii-processor:latest . --no-cache
```

### 问题：S3 上传权限被拒绝
**解决：**
```bash
# 检查 AWS 凭证
aws sts get-caller-identity

# 验证 IAM 策略（见 IAM_POLICY.md）
aws iam get-user-policy --user-name your-user --policy-name PIIProcessorPolicy
```

### 问题：审计日志未生成
**解决：**
- 确保当前目录有写权限
- 使用 `--audit-log` 指定绝对路径

---

如需更多定制功能（如"仅加密表格区域"、"差分隐私"等），欢迎提出需求。






