# AWS Resource Hibernator

A Lambda function designed for STG environments to automatically stop AWS resources during specified time periods, with support for intelligent hibernation management of EC2, ECS, and RDS resources.

## Features

- 🕒 **Smart Time Control**: Automatically stops resources on weekends and weekday nights.
- 🔧 **Multi-Service Support**: Supports EC2 instances, ECS services, and RDS instances.
- 🏗️ **Lambda Native**: Designed for the AWS Lambda environment, making it lightweight and efficient.
- ⚙️ **Environment Variable Configuration**: Manages resource ARNs via environment variables for easy deployment and maintenance.
- 🛡️ **Idempotent and Safe**: Checks resource status before execution to prevent duplicate operations.
- 📝 **Detailed Logging**: Provides complete operational logs for easy troubleshooting.
- 🎯 **STG Optimized**: Tailored for the resource scale of STG environments.

## Architecture

```
EventBridge Rule → Lambda Function → AWS Resource APIs
                       ↓
                 Environment Variables
                       ↓
                 CloudWatch Logs
```

## Configuration

### Environment Variables

| Variable Name | Description | Example | Required |
|---|---|---|---|
| `EC2_INSTANCE_ARNS` | Comma-separated list of EC2 instance ARNs | `arn:aws:ec2:us-east-1:123:instance/i-abc,arn:aws:ec2:us-east-1:123:instance/i-def` | No |
| `ECS_SERVICE_ARNS` | Comma-separated list of ECS service ARNs | `arn:aws:ecs:us-east-1:123:service/cluster/service1,arn:aws:ecs:us-east-1:123:service/cluster/service2` | No |
| `RDS_INSTANCE_ARNS` | Comma-separated list of RDS instance ARNs | `arn:aws:rds:us-east-1:123:db:database1,arn:aws:rds:us-east-1:123:db:database2` | No |
| `AWS_REGION` | AWS Region | `us-east-1` | Yes |
| `LOG_LEVEL` | Log level | `INFO` (default), `DEBUG`, `WARNING`, `ERROR` | No |

### ARN Format

- **EC2 Instance**: `arn:aws:ec2:region:account-id:instance/instance-id`
- **ECS Service**: `arn:aws:ecs:region:account-id:service/cluster-name/service-name`
- **RDS Instance**: `arn:aws:rds:region:account-id:db:db-instance-identifier`

## Stop Strategy

### Resource Stop Behavior

| Service Type | Stop Method | Status Check | Notes |
|---|---|---|---|
| EC2 | `stop_instances()` | Checks instance state, skips already stopped instances | EBS volumes are preserved, per-second billing stops |
| ECS | `update_service(desiredCount=0)` | Checks current desired count, skips services already at 0 | Gracefully stops all tasks |
| RDS | `stop_db_instance()` | Checks instance state, skips already stopped instances | Automatically restarts after being stopped for 7 days |

### Execution Logic

1. **Parameter Validation**: Checks the format of environment variables and the validity of ARNs.
2. **Status Check**: Retrieves the current status of each resource.
3. **Smart Skip**: Skips resources that are already stopped or in the process of stopping.
4. **Parallel Processing**: Handles different types of resources concurrently.
5. **Error Isolation**: The failure of one resource does not impact the processing of others.
6. **Result Logging**: Records detailed information on successful, failed, and skipped resources.

## IAM Permissions

The Lambda execution role requires the following minimum permissions:

### Basic Permissions
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

### EC2 Permissions (if using EC2)
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

### ECS Permissions (if using ECS)
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

### RDS Permissions (if using RDS)
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

### Combined Policy Example
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

## Deployment Guide

### 1. Create Lambda Function
```bash
# Create the function using AWS CLI
aws lambda create-function \
    --function-name aws-resource-hibernator \
    --runtime python3.9 \
    --role arn:aws:iam::ACCOUNT:role/lambda-hibernator-role \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://deployment.zip \
    --timeout 300 \
    --memory-size 256
```

### 2. Configure Environment Variables
```bash
# Set environment variables
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

### 3. Create EventBridge Rules
```bash
# Rule to trigger on weeknights
aws events put-rule \
    --name hibernator-weeknight \
    --schedule-expression "cron(0 22 ? * MON-FRI *)" \
    --state ENABLED

# Rule to trigger on weekends
aws events put-rule \
    --name hibernator-weekend \
    --schedule-expression "cron(0 0 ? * SAT,SUN *)" \
    --state ENABLED

# Add Lambda target
aws events put-targets \
    --rule hibernator-weeknight \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT:function:aws-resource-hibernator"

aws events put-targets \
    --rule hibernator-weekend \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT:function:aws-resource-hibernator"
```

## Use Cases

### STG Environment Cost Optimization
- **Auto-stop outside development hours**: Automatically stops STG resources at night and on weekends.
- **Precise resource control**: Stops only specified resources, leaving other services unaffected.
- **Flexible configuration**: Easily manage resources for different projects using environment variables.

### Multi-Project Support
Deploy separate Lambda functions for different STG projects:
```
stg-project-a-hibernator  # Hibernator for Project A
stg-project-b-hibernator  # Hibernator for Project B
stg-project-c-hibernator  # Hibernator for Project C
```

## Monitoring and Troubleshooting

### CloudWatch Monitoring
- **Invocations**: Monitor the frequency of Lambda executions.
- **Duration**: Ensure the function completes within the timeout limit.
- **Error Rate**: Track execution failures.
- **Memory Usage**: Optimize the function's memory configuration.

### Common Issues

#### 1. Permission Errors
```
AccessDenied: User is not authorized to perform action
```
**Solution**: Verify that the Lambda execution role has the required IAM permissions.

#### 2. Invalid ARN Format
```
Invalid ARN format
```
**Solution**: Check that the ARNs in the environment variables are correctly formatted.

#### 3. Region Mismatch
```
Instance not found
```
**Solution**: Ensure the `AWS_REGION` environment variable matches the region of your resources.

#### 4. Invalid Resource State
```
Cannot stop instance in current state
```
**Solution**: Check the resource's current state, as stop operations are not allowed in all states.

### Log Analysis
Review detailed execution information in CloudWatch Logs:
```bash
aws logs filter-log-events \
    --log-group-name /aws/lambda/aws-resource-hibernator \
    --start-time 1640995200000
```

## Considerations

### Limitations
- **Lambda Timeout**: The default is 300 seconds; this may need to be increased if handling many resources.
- **Environment Variable Size**: The total size is limited to 4KB.
- **RDS Stop Restrictions**: Aurora clusters do not support stop operations.
- **ECS Task Termination**: Stopping a service will gracefully terminate its running tasks.

### Cost Impact
- **EC2**: When stopped, you are only charged for EBS storage; compute charges cease.
- **ECS**: No compute costs are incurred for stopped tasks, but related resources like load balancers may still have charges.
- **RDS**: Instance charges do not apply while stopped, but storage costs continue.

### Security Recommendations
- **Least Privilege**: Grant only the necessary IAM permissions.
- **Resource Tagging**: Tag STG resources for easier identification.
- **Testing**: Fully test in a non-production environment before deploying.

## Version History

- **v1.0.0**: Initial release with basic stop functionality for EC2, ECS, and RDS.
- **v1.1.0**: Added status checks and idempotency.
- **v1.2.0**: Improved error handling and logging.

## Contributing

Contributions are welcome! Please submit an Issue or Pull Request to improve the project.

## License

MIT License
