import os
import boto3
import logging

# Configure logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION')
if not AWS_REGION:
    raise ValueError("Missing required environment variable: AWS_REGION")

ec2_client = boto3.client('ec2', region_name=AWS_REGION)
ecs_client = boto3.client('ecs', region_name=AWS_REGION)
rds_client = boto3.client('rds', region_name=AWS_REGION)

def get_arns_from_env(env_var):
    """Parses comma-separated ARNs from an environment variable."""
    arns_str = os.environ.get(env_var)
    if arns_str:
        return [arn.strip() for arn in arns_str.split(',') if arn.strip()]
    return []

def stop_ec2_instances(arns):
    """Stops EC2 instances specified in the ARNs."""
    if not arns:
        logger.info("No EC2 instances to process.")
        return

    instance_ids = [arn.split('/')[-1] for arn in arns]
    logger.info(f"Processing EC2 instances: {instance_ids}")

    try:
        descriptions = ec2_client.describe_instances(InstanceIds=instance_ids)
        instances_to_stop = []
        for reservation in descriptions['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                state = instance['State']['Name']
                if state in ['pending', 'running']:
                    instances_to_stop.append(instance_id)
                    logger.info(f"EC2 instance {instance_id} is in '{state}' state, preparing to stop.")
                else:
                    logger.info(f"Skipping EC2 instance {instance_id} as it is in '{state}' state.")

        if instances_to_stop:
            response = ec2_client.stop_instances(InstanceIds=instances_to_stop)
            for instance in response['StoppingInstances']:
                logger.info(f"Successfully sent stop command for EC2 instance {instance['InstanceId']}. Current state: {instance['CurrentState']['Name']}, Previous state: {instance['PreviousState']['Name']}.")
        else:
            logger.info("No running EC2 instances to stop.")

    except Exception as e:
        logger.error(f"Error stopping EC2 instances: {e}", exc_info=True)


def stop_ecs_services(arns):
    """Scales down ECS services to zero desired tasks."""
    if not arns:
        logger.info("No ECS services to process.")
        return

    for arn in arns:
        try:
            # ARN format: arn:aws:ecs:region:account-id:service/cluster-name/service-name
            parts = arn.split('/')
            cluster_name = parts[-2]
            service_name = parts[-1]
            logger.info(f"Processing ECS service '{service_name}' in cluster '{cluster_name}'.")

            descriptions = ecs_client.describe_services(cluster=cluster_name, services=[service_name])
            if not descriptions['services']:
                logger.warning(f"ECS service '{service_name}' not found in cluster '{cluster_name}'.")
                continue

            service = descriptions['services'][0]
            if service['desiredCount'] == 0:
                logger.info(f"Skipping ECS service '{service_name}' as its desired count is already 0.")
                continue

            ecs_client.update_service(
                cluster=cluster_name,
                service=service_name,
                desiredCount=0
            )
            logger.info(f"Successfully scaled down ECS service '{service_name}' to 0 desired tasks.")

        except Exception as e:
            logger.error(f"Error stopping ECS service {arn}: {e}", exc_info=True)


def stop_rds_instances(arns):
    """Stops RDS instances specified in the ARNs."""
    if not arns:
        logger.info("No RDS instances to process.")
        return

    for arn in arns:
        try:
            # ARN format: arn:aws:rds:region:account-id:db:db-instance-identifier
            db_instance_identifier = arn.split(':')[-1]
            logger.info(f"Processing RDS instance: {db_instance_identifier}")

            descriptions = rds_client.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
            if not descriptions['DBInstances']:
                 logger.warning(f"RDS instance '{db_instance_identifier}' not found.")
                 continue

            instance = descriptions['DBInstances'][0]
            status = instance['DBInstanceStatus']

            if instance.get('DBClusterIdentifier'):
                logger.warning(f"Skipping RDS instance '{db_instance_identifier}' because it is part of an Aurora cluster '{instance['DBClusterIdentifier']}'. Aurora clusters cannot be stopped individually via this script.")
                continue

            if status == 'available':
                rds_client.stop_db_instance(DBInstanceIdentifier=db_instance_identifier)
                logger.info(f"Successfully sent stop command for RDS instance '{db_instance_identifier}'.")
            elif status == 'stopping' or status == 'stopped':
                 logger.info(f"Skipping RDS instance '{db_instance_identifier}' as it is already in '{status}' state.")
            else:
                 logger.warning(f"Cannot stop RDS instance '{db_instance_identifier}' in its current state: '{status}'.")

        except Exception as e:
            logger.error(f"Error stopping RDS instance {arn}: {e}", exc_info=True)


def lambda_handler(event, context):
    """
    Main Lambda handler function.
    It stops specified AWS resources based on environment variables.
    """
    logger.info("AWS Resource Hibernator starting.")

    # Get ARNs from environment variables
    ec2_arns = get_arns_from_env('EC2_INSTANCE_ARNS')
    ecs_arns = get_arns_from_env('ECS_SERVICE_ARNS')
    rds_arns = get_arns_from_env('RDS_INSTANCE_ARNS')

    if not ec2_arns and not ecs_arns and not rds_arns:
        logger.warning("No resource ARNs provided in environment variables. Exiting.")
        return {
            'statusCode': 200,
            'body': 'No resources specified to hibernate.'
        }

    # Process resources
    stop_ec2_instances(ec2_arns)
    stop_ecs_services(ecs_arns)
    stop_rds_instances(rds_arns)

    logger.info("AWS Resource Hibernator finished.")

    return {
        'statusCode': 200,
        'body': 'Hibernation process completed successfully.'
    }
