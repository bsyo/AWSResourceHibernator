# AWSリソースハイバーネーター

STG環境向けに設計されたLambda関数で、指定した時間帯にAWSリソースを自動的に停止し、EC2、ECS、RDSリソースのインテリジェントな休止管理をサポートします。

## 特徴

- 🕒 **スマートな時間管理**: 週末および平日の夜間にリソースを自動的に停止します。
- 🔧 **複数サービス対応**: EC2インスタンス、ECSサービス、RDSインスタンスをサポートします。
- 🏗️ **Lambdaネイティブ**: AWS Lambda環境向けに設計されており、軽量で効率的です。
- ⚙️ **環境変数による設定**: 環境変数でリソースARNを管理し、デプロイとメンテナンスを容易にします。
- 🛡️ **べき等で安全**: 実行前にリソースの状態を確認し、重複操作を防止します。
- 📝 **詳細なロギング**: 完全な操作ログを提供し、問題解決を容易にします。
- 🎯 **STG環境に最適化**: STG環境のリソース規模に合わせて調整されています。

## アーキテクチャ

```
EventBridge Rule → Lambda Function → AWS Resource APIs
                       ↓
                 Environment Variables
                       ↓
                 CloudWatch Logs
```

## 設定

### 環境変数

| 変数名 | 説明 | 例 | 必須 |
|---|---|---|---|
| `EC2_INSTANCE_ARNS` | EC2インスタンスARNのコンマ区切りリスト | `arn:aws:ec2:us-east-1:123:instance/i-abc,arn:aws:ec2:us-east-1:123:instance/i-def` | いいえ |
| `ECS_SERVICE_ARNS` | ECSサービスARNのコンマ区切りリスト | `arn:aws:ecs:us-east-1:123:service/cluster/service1,arn:aws:ecs:us-east-1:123:service/cluster/service2` | いいえ |
| `RDS_INSTANCE_ARNS` | RDSインスタンスARNのコンマ区切りリスト | `arn:aws:rds:us-east-1:123:db:database1,arn:aws:rds:us-east-1:123:db:database2` | いいえ |
| `AWS_REGION` | AWSリージョン | `us-east-1` | はい |
| `LOG_LEVEL` | ログレベル | `INFO` (デフォルト), `DEBUG`, `WARNING`, `ERROR` | いいえ |

### ARNフォーマット

- **EC2インスタンス**: `arn:aws:ec2:region:account-id:instance/instance-id`
- **ECSサービス**: `arn:aws:ecs:region:account-id:service/cluster-name/service-name`
- **RDSインスタンス**: `arn:aws:rds:region:account-id:db:db-instance-identifier`

## 停止戦略

### リソースの停止動作

| サービスタイプ | 停止方法 | 状態チェック | 注意事項 |
|---|---|---|---|
| EC2 | `stop_instances()` | インスタンスの状態をチェックし、停止済みのインスタンスはスキップ | EBSボリュームは保持され、秒単位の課金が停止 |
| ECS | `update_service(desiredCount=0)` | 現在のdesired countをチェックし、既に0のサービスはスキップ | 全てのタスクを正常に停止 |
| RDS | `stop_db_instance()` | インスタンスの状態をチェックし、停止済みのインスタンスはスキップ | 7日間停止後、自動的に再起動 |

### 実行ロジック

1. **パラメータ検証**: 環境変数のフォーマットとARNの有効性をチェックします。
2. **状態チェック**: 各リソースの現在の状態を取得します。
3. **スマートスキップ**: 既に停止している、または停止中のリソースをスキップします。
4. **並列処理**: 異なるタイプのリソースを同時に処理します。
5. **エラー分離**: 1つのリソースの失敗が他のリソースの処理に影響を与えません。
6. **結果の記録**: 成功、失敗、スキップしたリソースの詳細情報を記録します。

## IAM権限

Lambda実行ロールには、以下の最小権限が必要です。

### 基本権限
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

### EC2権限（EC2利用時）
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:StopInstances"
            ],
            "Resource": "*"
        }
    ]
}
```

### ECS権限（ECS利用時）
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecs:DescribeServices",
                "ecs:UpdateService"
            ],
            "Resource": "*"
        }
    ]
}
```

### RDS権限（RDS利用時）
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "rds:DescribeDBInstances",
                "rds:StopDBInstance"
            ],
            "Resource": "*"
        }
    ]
}
```

### 統合ポリシーの例
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:StopInstances",
                "ecs:DescribeServices",
                "ecs:UpdateService",
                "rds:DescribeDBInstances",
                "rds:StopDBInstance"
            ],
            "Resource": "*"
        }
    ]
}
```

## デプロイガイド

### 1. Lambda関数の作成
```bash
# AWS CLIを使用して関数を作成
aws lambda create-function \
    --function-name aws-resource-hibernator \
    --runtime python3.9 \
    --role arn:aws:iam::ACCOUNT:role/lambda-hibernator-role \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://deployment.zip \
    --timeout 300 \
    --memory-size 256
```

### 2. 環境変数の設定
```bash
# 環境変数を設定
aws lambda update-function-configuration \
    --function-name aws-resource-hibernator \
    --environment Variables='{
        "AWS_REGION":"us-east-1",
        "EC2_INSTANCE_ARNS":"arn:aws:ec2:us-east-1:123456789012:instance/i-123,arn:aws:ec2:us-east-1:123456789012:instance/i-456",
        "ECS_SERVICE_ARNS":"arn:aws:ecs:us-east-1:123456789012:service/my-cluster/service1,arn:aws:ecs:us-east-1:123456789012:service/my-cluster/service2",
        "RDS_INSTANCE_ARNS":"arn:aws:rds:us-east-1:123456789012:db:db1,arn:aws:rds:us-east-1:123456789012:db:db2",
        "LOG_LEVEL":"INFO"
    }'
```

### 3. EventBridgeルールの作成
```bash
# 平日の夜間にトリガーするルール
aws events put-rule \
    --name hibernator-weeknight \
    --schedule-expression "cron(0 22 ? * MON-FRI *)" \
    --state ENABLED

# 週末にトリガーするルール
aws events put-rule \
    --name hibernator-weekend \
    --schedule-expression "cron(0 0 ? * SAT,SUN *)" \
    --state ENABLED

# Lambdaターゲットを追加
aws events put-targets \
    --rule hibernator-weeknight \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT:function:aws-resource-hibernator"

aws events put-targets \
    --rule hibernator-weekend \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT:function:aws-resource-hibernator"
```

## ユースケース

### STG環境のコスト最適化
- **開発時間外の自動停止**: 夜間や週末にSTG環境のリソースを自動停止します。
- **正確なリソース制御**: 指定されたリソースのみを停止し、他のサービスには影響を与えません。
- **柔軟な設定管理**: 環境変数を使用して、異なるプロジェクトのリソースを簡単に管理します。

### 複数プロジェクトのサポート
異なるSTGプロジェクト用に個別のLambda関数をデプロイします。
```
stg-project-a-hibernator  # プロジェクトA用のハイバーネーター
stg-project-b-hibernator  # プロジェクトB用のハイバーネーター
stg-project-c-hibernator  # プロジェクトC用のハイバーネーター
```

## 監視とトラブルシューティング

### CloudWatchによる監視
- **呼び出し回数**: Lambdaの実行頻度を監視します。
- **実行時間**: 関数がタイムアウト制限内に完了することを確認します。
- **エラー率**: 実行の失敗を追跡します。
- **メモリ使用量**: 関数のメモリ設定を最適化します。

### よくある問題

#### 1. 権限エラー
```
AccessDenied: User is not authorized to perform action
```
**解決策**: Lambda実行ロールに必要なIAM権限があることを確認します。

#### 2. 不正なARNフォーマット
```
Invalid ARN format
```
**解決策**: 環境変数内のARNが正しくフォーマットされていることを確認します。

#### 3. リージョンの不一致
```
Instance not found
```
**解決策**: `AWS_REGION`環境変数がリソースのリージョンと一致していることを確認します。

#### 4. 不正なリソース状態
```
Cannot stop instance in current state
```
**解決策**: リソースの現在の状態を確認します。すべての状態で停止操作が許可されているわけではありません。

### ログ分析
CloudWatch Logsで詳細な実行情報を確認します。
```bash
aws logs filter-log-events \
    --log-group-name /aws/lambda/aws-resource-hibernator \
    --start-time 1640995200000
```

## 考慮事項

### 制限事項
- **Lambdaタイムアウト**: デフォルトは300秒です。多くのリソースを処理する場合は増やす必要があるかもしれません。
- **環境変数のサイズ**: 合計サイズは4KBに制限されています。
- **RDSの停止制限**: Auroraクラスターは停止操作をサポートしていません。
- **ECSタスクの終了**: サービスを停止すると、実行中のタスクが正常に終了します。

### コストへの影響
- **EC2**: 停止中はEBSストレージに対してのみ課金され、コンピューティング料金は発生しません。
- **ECS**: 停止したタスクに対してコンピューティングコストは発生しませんが、ロードバランサーなどの関連リソースには引き続き料金がかかる場合があります。
- **RDS**: 停止中はインスタンス料金は適用されませんが、ストレージコストは引き続き発生します。

### セキュリティに関する推奨事項
- **最小権限の原則**: 必要なIAM権限のみを付与します。
- **リソースのタグ付け**: STGリソースを簡単に識別できるようにタグを付けます。
- **テスト**: デプロイする前に、非本番環境で十分にテストします。

## バージョン履歴

- **v1.0.0**: EC2、ECS、RDSの基本的な停止機能を備えた初期リリース。
- **v1.1.0**: 状態チェックとべき等性を追加。
- **v1.2.0**: エラーハンドリングとロギングを改善。

## コントリビューション

貢献を歓迎します！IssueやPull Requestを送信して、プロジェクトを改善してください。

## ライセンス

MITライセンス
