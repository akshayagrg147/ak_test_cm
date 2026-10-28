"""Produce the reviewable CloudFormation template for the dedicated ViaCRM host."""

import json
from pathlib import Path


def REF(value):
    return {"Ref": value}


def SUB(value):
    return {"Fn::Sub": value}


def GET(resource, key):
    return {"Fn::GetAtt": [resource, key]}


def template():
    account = "${AWS::AccountId}"
    region = "${AWS::Region}"
    ecr_arns = [
        SUB(f"arn:aws:ecr:{region}:{account}:repository/viacrm/{name}")
        for name in ["api", "web"]
    ]
    user_data = r"""#!/bin/bash
set -euo pipefail
umask 077
dnf install -y docker python3 tar gzip util-linux
command -v aws
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins /opt/viacrm/bin /opt/viacrm/shared /opt/viacrm/releases /opt/viacrm/backups
curl --fail --location --retry 5 https://github.com/docker/compose/releases/download/${ComposeVersion}/docker-compose-linux-x86_64 -o /tmp/docker-compose-linux-x86_64
curl --fail --location --retry 5 https://github.com/docker/compose/releases/download/${ComposeVersion}/checksums.txt -o /tmp/compose-checksums.txt
cd /tmp
grep 'docker-compose-linux-x86_64$' /tmp/compose-checksums.txt | sha256sum --check
install -m 755 docker-compose-linux-x86_64 /usr/local/lib/docker/cli-plugins/docker-compose
cat > /opt/viacrm/shared/host.env <<'ENV'
AWS_REGION=${AWS::Region}
ECR_REGISTRY=${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com
RELEASE_BUCKET=${ReleaseBucket}
PUBLIC_HOST=${HostName}
ENV
cat > /opt/viacrm/bin/apply-release <<'SCRIPT'
#!/bin/bash
set -euo pipefail
umask 077
commit="$1"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || exit 2
set -a
source /opt/viacrm/shared/host.env
set +a
destination="/opt/viacrm/releases/$commit"
if [[ ! -f "$destination/images.env" ]]; then
    temporary="$(mktemp -d /opt/viacrm/releases/.incoming-XXXXXX)"
    trap 'rm -rf "$temporary"' EXIT
    aws s3 cp "s3://$RELEASE_BUCKET/releases/$commit.tar.gz" "$temporary/release.tar.gz" --only-show-errors
    mkdir "$temporary/content"
    tar --extract --gzip --file "$temporary/release.tar.gz" --directory "$temporary/content" --no-same-owner --no-same-permissions
    mv "$temporary/content" "$destination"
fi
bash "$destination/deploy.sh"
SCRIPT
chmod 700 /opt/viacrm/bin/apply-release /opt/viacrm/shared /opt/viacrm/releases /opt/viacrm/backups
chmod 600 /opt/viacrm/shared/host.env
docker compose version
touch /opt/viacrm/shared/host-ready
"""
    resources = {
        "ReleaseBucket": {
            "Type": "AWS::S3::Bucket",
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
            "Properties": {
                "BucketName": SUB("viacrm-releases-${AWS::AccountId}-${AWS::Region}"),
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                    ]
                },
                "PublicAccessBlockConfiguration": {
                    key: True
                    for key in [
                        "BlockPublicAcls",
                        "IgnorePublicAcls",
                        "BlockPublicPolicy",
                        "RestrictPublicBuckets",
                    ]
                },
                "VersioningConfiguration": {"Status": "Enabled"},
                "LifecycleConfiguration": {
                    "Rules": [
                        {
                            "Id": "ReleaseRetention",
                            "Status": "Enabled",
                            "Prefix": "releases/",
                            "ExpirationInDays": 90,
                            "NoncurrentVersionExpiration": {"NoncurrentDays": 7},
                        }
                    ]
                },
            },
        },
        "ReleaseBucketPolicy": {
            "Type": "AWS::S3::BucketPolicy",
            "Properties": {
                "Bucket": REF("ReleaseBucket"),
                "PolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Deny",
                            "Principal": "*",
                            "Action": "s3:*",
                            "Resource": [
                                GET("ReleaseBucket", "Arn"),
                                SUB("${ReleaseBucket.Arn}/*"),
                            ],
                            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                        }
                    ],
                },
            },
        },
        "HostRole": {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "AssumeRolePolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "ec2.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                },
                "ManagedPolicyArns": [
                    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
                ],
                "Policies": [
                    {
                        "PolicyName": "ViaCrmReleaseRead",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "ecr:GetAuthorizationToken",
                                    "Resource": "*",
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "ecr:BatchGetImage",
                                        "ecr:GetDownloadUrlForLayer",
                                        "ecr:BatchCheckLayerAvailability",
                                    ],
                                    "Resource": ecr_arns,
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": "s3:GetObject",
                                    "Resource": SUB("${ReleaseBucket.Arn}/releases/*"),
                                },
                            ],
                        },
                    }
                ],
            },
        },
        "HostProfile": {
            "Type": "AWS::IAM::InstanceProfile",
            "Properties": {"Roles": [REF("HostRole")]},
        },
        "SecurityGroup": {
            "Type": "AWS::EC2::SecurityGroup",
            "Properties": {
                "GroupDescription": "ViaCRM public HTTPS; administration through SSM only",
                "VpcId": REF("VpcId"),
                "SecurityGroupIngress": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": port,
                        "ToPort": port,
                        "CidrIp": "0.0.0.0/0",
                    }
                    for port in [80, 443]
                ],
            },
        },
        "PublicIp": {
            "Type": "AWS::EC2::EIP",
            "Properties": {
                "Domain": "vpc",
                "Tags": [{"Key": "Name", "Value": "viacrm"}],
            },
        },
        "Host": {
            "Type": "AWS::EC2::Instance",
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
            "Properties": {
                "ImageId": REF("AmiId"),
                "InstanceType": REF("InstanceType"),
                "SubnetId": REF("SubnetId"),
                "IamInstanceProfile": REF("HostProfile"),
                "SecurityGroupIds": [REF("SecurityGroup")],
                "MetadataOptions": {
                    "HttpTokens": "required",
                    "HttpPutResponseHopLimit": 1,
                },
                "BlockDeviceMappings": [
                    {
                        "DeviceName": "/dev/xvda",
                        "Ebs": {
                            "VolumeType": "gp3",
                            "VolumeSize": 30,
                            "Encrypted": True,
                            "DeleteOnTermination": False,
                        },
                    }
                ],
                "CreditSpecification": {"CPUCredits": "standard"},
                "Tags": [
                    {"Key": "Name", "Value": "viacrm"},
                    {"Key": "Project", "Value": "viacrm"},
                ],
                "UserData": {
                    "Fn::Base64": {
                        "Fn::Sub": [
                            user_data,
                            {
                                "HostName": {
                                    "Fn::If": [
                                        "HasDomain",
                                        REF("Domain"),
                                        REF("PublicIp"),
                                    ]
                                }
                            },
                        ]
                    }
                },
            },
        },
        "IpAssociation": {
            "Type": "AWS::EC2::EIPAssociation",
            "Properties": {
                "InstanceId": REF("Host"),
                "AllocationId": GET("PublicIp", "AllocationId"),
            },
        },
        "GitHubOidc": {
            "Type": "AWS::IAM::OIDCProvider",
            "Condition": "CreateOidc",
            "Properties": {
                "Url": "https://token.actions.githubusercontent.com",
                "ClientIdList": ["sts.amazonaws.com"],
            },
        },
        "DeployRole": {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "MaxSessionDuration": 3600,
                "AssumeRolePolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "Federated": {
                                    "Fn::If": [
                                        "CreateOidc",
                                        REF("GitHubOidc"),
                                        SUB(
                                            "arn:aws:iam::${AWS::AccountId}:oidc-provider/token.actions.githubusercontent.com"
                                        ),
                                    ]
                                }
                            },
                            "Action": "sts:AssumeRoleWithWebIdentity",
                            "Condition": {
                                "StringEquals": {
                                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                                "token.actions.githubusercontent.com:sub": SUB(
                                    "${GitHubSubjectPrefix}:ref:refs/heads/main"
                                ),
                                }
                            },
                        }
                    ],
                },
                "Policies": [
                    {
                        "PolicyName": "ViaCrmDeploy",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "ecr:GetAuthorizationToken",
                                    "Resource": "*",
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": [
                                        "ecr:BatchCheckLayerAvailability",
                                        "ecr:CompleteLayerUpload",
                                        "ecr:InitiateLayerUpload",
                                        "ecr:PutImage",
                                        "ecr:UploadLayerPart",
                                        "ecr:BatchGetImage",
                                        "ecr:GetDownloadUrlForLayer",
                                    ],
                                    "Resource": ecr_arns,
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": "s3:PutObject",
                                    "Resource": SUB("${ReleaseBucket.Arn}/releases/*"),
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": "ssm:SendCommand",
                                    "Resource": [
                                        SUB(
                                            "arn:aws:ssm:${AWS::Region}::document/AWS-RunShellScript"
                                        ),
                                        SUB(
                                            "arn:aws:ec2:${AWS::Region}:${AWS::AccountId}:instance/${Host}"
                                        ),
                                    ],
                                },
                                {
                                    "Effect": "Allow",
                                    "Action": "ssm:GetCommandInvocation",
                                    "Resource": "*",
                                },
                            ],
                        },
                    }
                ],
            },
        },
    }
    for name in ["api", "web"]:
        resources[name.title() + "Repository"] = {
            "Type": "AWS::ECR::Repository",
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
            "Properties": {
                "RepositoryName": f"viacrm/{name}",
                "ImageTagMutability": "IMMUTABLE",
                "ImageScanningConfiguration": {"ScanOnPush": True},
                "EncryptionConfiguration": {"EncryptionType": "AES256"},
                "LifecyclePolicy": {
                    "LifecyclePolicyText": json.dumps(
                        {
                            "rules": [
                                {
                                    "rulePriority": 1,
                                    "description": "Keep 20 release images",
                                    "selection": {
                                        "tagStatus": "any",
                                        "countType": "imageCountMoreThan",
                                        "countNumber": 20,
                                    },
                                    "action": {"type": "expire"},
                                }
                            ]
                        }
                    )
                },
            },
        }
    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "ViaCRM Mumbai EC2, private releases, ECR and GitHub main-branch OIDC deployment",
        "Parameters": {
            "VpcId": {"Type": "AWS::EC2::VPC::Id"},
            "SubnetId": {"Type": "AWS::EC2::Subnet::Id"},
            "AmiId": {
                "Type": "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
                "Default": "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64",
            },
            "InstanceType": {
                "Type": "String",
                "Default": "t3.small",
                "AllowedValues": ["t3.small", "t3.medium"],
            },
            "GitHubRepository": {
                "Type": "String",
                "Default": "akshayagrg147/ak_test_cm",
                "AllowedPattern": "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
            },
            "GitHubSubjectPrefix": {
                "Type": "String",
                "Default": "repo:akshayagrg147@54131590/ak_test_cm@1437454984",
                "AllowedPattern": "repo:[A-Za-z0-9_.@-]+/[A-Za-z0-9_.@-]+",
                "Description": "Exact sub_claim_prefix from the repository OIDC settings, including immutable IDs when enabled",
            },
            "Domain": {
                "Type": "String",
                "Default": "",
                "AllowedPattern": "^$|[A-Za-z0-9][A-Za-z0-9.-]+[A-Za-z0-9]",
            },
            "ComposeVersion": {
                "Type": "String",
                "Default": "v5.6.1",
                "AllowedPattern": "v[0-9]+\\.[0-9]+\\.[0-9]+",
            },
            "CreateGitHubProvider": {
                "Type": "String",
                "Default": "true",
                "AllowedValues": ["true", "false"],
            },
        },
        "Conditions": {
            "HasDomain": {"Fn::Not": [{"Fn::Equals": [REF("Domain"), ""]}]},
            "CreateOidc": {"Fn::Equals": [REF("CreateGitHubProvider"), "true"]},
        },
        "Resources": resources,
        "Outputs": {
            "InstanceId": {"Value": REF("Host")},
            "PublicIp": {"Value": REF("PublicIp")},
            "PublicHost": {
                "Value": {"Fn::If": ["HasDomain", REF("Domain"), REF("PublicIp")]}
            },
            "DeployRoleArn": {"Value": GET("DeployRole", "Arn")},
            "ReleaseBucket": {"Value": REF("ReleaseBucket")},
            "ApiRepository": {"Value": GET("ApiRepository", "RepositoryUri")},
            "WebRepository": {"Value": GET("WebRepository", "RepositoryUri")},
        },
    }


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[2] / "infra/aws/stack.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(template(), indent=2) + "\n")
    print(destination)
