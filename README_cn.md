# AWS Resource Hibernator

一个用于在指定时间段自动停止AWS资源的Lambda函数，专为STG环境设计，支持EC2、ECS、RDS资源的智能休眠管理。

## 项目特性

- 🕒 **智能时间控制**: 在周末全天和工作日夜间自动停止资源
- 🔧 **多服务支持**: 支持EC2实例、ECS服务、RDS实例
- 🏗️ **Lambda原生**: 专为AWS Lambda环境设计，轻量高效
- ⚙️ **环境变量配置**: 通过环境变量管理资源ARN，易于部署和维护
- 🛡️ **幂等安全**: 执行前检查资源状态，避免重复操作
- 📝 **详细日志**: 完整的操作日志记录，便于问题排查
- 🎯 **STG优化**: 专为STG环境资源规模优化

## 架构设计

```
EventBridge Rule → Lambda Function → AWS Resource APIs
                       ↓
                 Environment Variables
                       ↓
                 CloudWatch Logs
```

## 配置说明

### 环境变量

| 变量名 | 描述 | 示例 | 必需 |
|--------|------|------|------|
| `EC2_INSTANCE_ARNS` | EC2实例ARN列表，逗号分隔 | `arn:aws:ec2:us-east-1:123:instance/i-abc,arn:aws:ec2:us-east-1:123:instance/i-def` | 否 |
| `ECS_SERVICE_ARNS` | ECS服务ARN列表，逗号分隔 | `arn:aws:ecs:us-east-1:123:service/cluster/service1,arn:aws:ecs:us-east-1:123:service/cluster/service2` | 否 |
| `RDS_INSTANCE_ARNS` | RDS实例ARN列表，逗号分隔 | `arn:aws:rds:us-east-1:123:db:database1,arn:aws:rds:us-east-1:123:db:database2` | 否 |
| `AWS_REGION` | AWS区域 | `us-east-1` | 是 |
| `LOG_LEVEL` | 日志级别 | `INFO` (默认), `DEBUG`, `WARNING`, `ERROR` | 否 |

### ARN格式说明

- **EC2实例**: `arn:aws:ec2:region:account-id:instance/instance-id`
- **ECS服务**: `arn:aws:ecs:region:account-id:service/cluster-name/service-name`
- **RDS实例**: `arn:aws:rds:region:account-id:db:db-instance-identifier`

## 停止策略

### 资源停止行为

| 服务类型 | 停止方式 | 状态检查 | 备注 |
|----------|----------|----------|------|
| EC2 | `stop_instances()` | 检查实例状态，跳过已停止的实例 | 保留EBS卷，按秒计费停止 |
| ECS | `update_service(desiredCount=0)` | 检查当前desired count，跳过已为0的服务 | 优雅停止所有任务 |
| RDS | `stop_db_instance()` | 检查实例状态，跳过已停止的实例 | 最多停止7天后自动启动 |

### 执行逻辑

1. **参数验证**: 检查环境变量格式和ARN有效性
2. **状态检查**: 获取每个资源的当前状态
3. **智能跳过**: 跳过已经停止或正在停止的资源
4. **并行处理**: 同时处理不同类型的资源
5. **错误隔离**: 单个资源失败不影响其他资源处理
6. **结果记录**: 详细记录成功、失败和跳过的资源

## IAM权限要求

Lambda执行角色需要以下最小权限：

### 基础权限
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

### EC2权限（如果使用EC2资源）
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

### ECS权限（如果使用ECS资源）
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

### RDS权限（如果使用RDS资源）
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

### 组合策略示例
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

## 部署指南

### 1. 创建Lambda函数
```bash
# 使用AWS CLI创建函数
aws lambda create-function \
    --function-name aws-resource-hibernator \
    --runtime python3.9 \
    --role arn:aws:iam::ACCOUNT:role/lambda-hibernator-role \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://deployment.zip \
    --timeout 300 \
    --memory-size 256
```

### 2. 配置环境变量
```bash
# 设置环境变量
aws lambda update-function-configuration \
    --function-name aws-resource-hibernator \
    --environment Variables='{
        "AWS_REGION":"us-east-1",
        "EC2_INSTANCE_ARNS":"arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
        "ECS_SERVICE_ARNS":"arn:aws:ecs:us-east-1:123456789012:service/my-cluster/my-service",
        "RDS_INSTANCE_ARNS":"arn:aws:rds:us-east-1:123456789012:db:my-database",
        "LOG_LEVEL":"INFO"
    }'
```

### 3. 创建EventBridge规则
```bash
# 工作日夜间触发规则
aws events put-rule \
    --name hibernator-weeknight \
    --schedule-expression "cron(0 22 ? * MON-FRI *)" \
    --state ENABLED

# 周末触发规则
aws events put-rule \
    --name hibernator-weekend \
    --schedule-expression "cron(0 0 ? * SAT,SUN *)" \
    --state ENABLED

# 添加Lambda目标
aws events put-targets \
    --rule hibernator-weeknight \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT:function:aws-resource-hibernator"

aws events put-targets \
    --rule hibernator-weekend \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT:function:aws-resource-hibernator"
```

## 使用场景

### STG环境成本优化
- **开发时间外自动停止**: 夜间和周末自动停止STG环境资源
- **精确的资源控制**: 只停止指定的资源，不影响其他服务
- **灵活的配置管理**: 通过环境变量轻松管理不同项目的资源

### 多项目支持
为不同STG项目部署独立的Lambda函数：
```
stg-project-a-hibernator  # 项目A的资源休眠器
stg-project-b-hibernator  # 项目B的资源休眠器
stg-project-c-hibernator  # 项目C的资源休眠器
```

## 监控和故障排除

### CloudWatch监控
- **函数执行次数**: 监控Lambda执行频率
- **执行时长**: 确保在超时限制内完成
- **错误率**: 监控执行失败情况
- **内存使用**: 优化函数配置

### 常见问题

#### 1. 权限错误
```
AccessDenied: User is not authorized to perform action
```
**解决方案**: 检查Lambda执行角色是否包含所需的IAM权限

#### 2. ARN格式错误
```
Invalid ARN format
```
**解决方案**: 验证环境变量中的ARN格式是否正确

#### 3. 区域不匹配
```
Instance not found
```
**解决方案**: 确保`AWS_REGION`环境变量与资源所在区域一致

#### 4. 资源状态异常
```
Cannot stop instance in current state
```
**解决方案**: 检查资源当前状态，某些状态下无法执行停止操作

### 日志分析
查看CloudWatch Logs获取详细执行信息：
```bash
aws logs filter-log-events \
    --log-group-name /aws/lambda/aws-resource-hibernator \
    --start-time 1640995200000
```

## 注意事项

### 限制和约束
- **Lambda超时**: 默认300秒，处理大量资源时可能需要调整
- **环境变量大小**: 总计不超过4KB
- **RDS停止限制**: Aurora集群不支持停止操作
- **ECS任务停止**: 服务停止时会优雅终止正在运行的任务

### 成本影响
- **EC2**: 停止后只收取EBS存储费用，计算费用停止
- **ECS**: 任务停止后不产生计算费用，但负载均衡器等关联资源可能继续收费
- **RDS**: 停止期间不收取实例费用，但存储费用继续

### 安全建议
- **最小权限原则**: 只授予必需的IAM权限
- **资源标签**: 建议为STG资源添加标签便于识别
- **测试验证**: 在非生产环境充分测试后再部署

## 版本历史

- **v1.0.0**: 初始版本，支持EC2、ECS、RDS资源的基础停止功能
- **v1.1.0**: 增加状态检查和幂等性支持
- **v1.2.0**: 优化错误处理和日志记录

## 贡献指南

欢迎提交Issue和Pull Request来改进项目。

## 许可证

MIT License
