# IAM Access Control Policy Examples

This document provides IAM policy examples implementing the **principle of least privilege** for secure document processing.

---

## 1. S3 Bucket Policy - Minimum Required Permissions

### Policy: Read/Write Access to Specific Bucket (No Delete)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPIIDocumentUpload",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::your-secure-pii-bucket/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    },
    {
      "Sid": "AllowReadEncryptedObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": "arn:aws:s3:::your-secure-pii-bucket/*"
    },
    {
      "Sid": "DenyUnencryptedUploads",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::your-secure-pii-bucket/*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": [
            "AES256",
            "aws:kms"
          ]
        }
      }
    }
  ]
}
```

**Key Features:**
- ✅ Allows upload with encryption only
- ✅ Allows read access
- ❌ **No delete permissions** (prevents accidental data loss)
- ❌ **No list permissions** (limits exposure)

---

## 2. KMS Key Policy - For aws:kms Encryption

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPIIProcessorToEncrypt",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/PIIProcessorRole"
      },
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "s3.us-east-1.amazonaws.com"
        }
      }
    }
  ]
}
```

---

## 3. IAM Role for Container/Lambda Execution

### Policy: Minimal Permissions for PII Processing

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3EncryptedAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::your-secure-pii-bucket/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    },
    {
      "Sid": "CloudWatchLogsForAudit",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/pii-processor/*"
    },
    {
      "Sid": "DenyAllOtherS3Access",
      "Effect": "Deny",
      "Action": "s3:*",
      "NotResource": [
        "arn:aws:s3:::your-secure-pii-bucket",
        "arn:aws:s3:::your-secure-pii-bucket/*"
      ]
    }
  ]
}
```

**Principle of Least Privilege:**
- Only access to specific bucket
- No administrative actions
- Audit logs to CloudWatch
- Explicit deny for other buckets

---

## 4. Bucket Lifecycle Policy - Automatic Retention

```json
{
  "Rules": [
    {
      "Id": "DeleteOldPIIDocuments",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "pii-masked/"
      },
      "Expiration": {
        "Days": 30
      },
      "NoncurrentVersionExpiration": {
        "NoncurrentDays": 7
      }
    },
    {
      "Id": "TransitionToGlacier",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "archive/"
      },
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

**Data Retention Features:**
- Auto-delete after 30 days
- Move to Glacier for long-term archive
- Version cleanup after 7 days

---

## 5. Cross-Account Access (Optional)

If processing happens in a separate AWS account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountPIIProcessor",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::987654321098:role/PIIProcessorRole"
      },
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::your-secure-pii-bucket/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    }
  ]
}
```

---

## 6. IAM User Policy - For Manual Operations

For human operators (limited scope):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-secure-pii-bucket",
        "arn:aws:s3:::your-secure-pii-bucket/*"
      ]
    },
    {
      "Sid": "DenyDeleteOperations",
      "Effect": "Deny",
      "Action": [
        "s3:DeleteObject",
        "s3:DeleteBucket"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Setup Instructions

### 1. Create S3 Bucket with Encryption

```bash
aws s3api create-bucket \
  --bucket your-secure-pii-bucket \
  --region us-east-1 \
  --create-bucket-configuration LocationConstraint=us-east-1

aws s3api put-bucket-encryption \
  --bucket your-secure-pii-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

### 2. Enable Versioning (for audit trail)

```bash
aws s3api put-bucket-versioning \
  --bucket your-secure-pii-bucket \
  --versioning-configuration Status=Enabled
```

### 3. Block Public Access

```bash
aws s3api put-public-access-block \
  --bucket your-secure-pii-bucket \
  --public-access-block-configuration \
    BlockPublicAcls=true,\
    IgnorePublicAcls=true,\
    BlockPublicPolicy=true,\
    RestrictPublicBuckets=true
```

### 4. Create IAM Role

```bash
aws iam create-role \
  --role-name PIIProcessorRole \
  --assume-role-policy-document file://trust-policy.json

aws iam put-role-policy \
  --role-name PIIProcessorRole \
  --policy-name PIIProcessorPolicy \
  --policy-document file://pii-processor-policy.json
```

---

## Environment Variables for boto3

```bash
# Option 1: Use IAM role (recommended for EC2/Lambda/ECS)
# No credentials needed - role is automatically assumed

# Option 2: Use AWS CLI credentials
export AWS_PROFILE=pii-processor

# Option 3: Explicit credentials (not recommended for production)
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=us-east-1
```

---

## Testing Access

```bash
# Test upload with encryption
python s3_upload.py document.md \
  --bucket your-secure-pii-bucket \
  --encryption AES256

# Test with KMS
python s3_upload.py document.md \
  --bucket your-secure-pii-bucket \
  --encryption aws:kms \
  --kms-key-id arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
```

---

## Security Best Practices

1. **Never hardcode credentials** in code or scripts
2. **Use IAM roles** for applications running on AWS
3. **Enable MFA** for human users with write access
4. **Rotate keys** regularly (if using access keys)
5. **Monitor with CloudTrail** for all S3 API calls
6. **Set up alerts** for unauthorized access attempts
7. **Use VPC endpoints** for S3 access from private subnets
8. **Enable bucket logging** for audit trail

---

## Compliance Considerations

- **GDPR**: Automatic deletion after retention period
- **HIPAA**: Encryption at rest and in transit
- **SOC 2**: Audit logs and access controls
- **PCI DSS**: Restricted access and encryption

---

For questions or issues, refer to AWS IAM documentation:
https://docs.aws.amazon.com/IAM/latest/UserGuide/

