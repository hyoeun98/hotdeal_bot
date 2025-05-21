# lambda-common/aws_utils.py
import boto3
import json
import os # For default region

# Default region, can be overridden by parameters if needed
DEFAULT_REGION = os.environ.get("REGION", "ap-northeast-2") 

def publish_to_sns(topic_arn, message_body_dict, message_attributes, region_name=DEFAULT_REGION):
    '''Publishes a message to an SNS topic.'''
    sns = boto3.client('sns', region_name=region_name)
    try:
        response = sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message_body_dict), # Ensure message body is JSON string
            MessageAttributes=message_attributes
        )
        print(f"Message published to SNS Topic {topic_arn}. MessageID: {response.get('MessageId')}")
        return response
    except Exception as e:
        print(f"Error publishing to SNS Topic {topic_arn}: {e}")
        raise # Re-raise the exception to be handled by the caller

def send_to_sqs(queue_url, message_body_dict, message_attributes, region_name=DEFAULT_REGION):
    '''Sends a message to an SQS queue.'''
    sqs = boto3.client('sqs', region_name=region_name)
    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body_dict), # Ensure message body is JSON string
            MessageAttributes=message_attributes
        )
        print(f"Message sent to SQS Queue {queue_url}. MessageID: {response.get('MessageId')}")
        return response
    except Exception as e:
        print(f"Error sending to SQS Queue {queue_url}: {e}")
        raise # Re-raise the exception to be handled by the caller
