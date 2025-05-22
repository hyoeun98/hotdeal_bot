# lambda-common/aws_utils.py
import boto3
import json
import os # For default region

# Default region, can be overridden by parameters if needed
# 기본 리전, 필요한 경우 파라미터로 재정의 가능
DEFAULT_REGION = os.environ.get("REGION", "ap-northeast-2") 

def publish_to_sns(topic_arn, message_body_dict, message_attributes, region_name=DEFAULT_REGION):
    '''Publishes a message to an SNS topic.'''
    # SNS 토픽에 메시지를 게시합니다.
    sns = boto3.client('sns', region_name=region_name)
    try:
        response = sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message_body_dict), # 메시지 본문이 JSON 문자열인지 확인
            MessageAttributes=message_attributes
        )
        print(f"Message published to SNS Topic {topic_arn}. MessageID: {response.get('MessageId')}")
        return response
    except Exception as e:
        print(f"Error publishing to SNS Topic {topic_arn}: {e}")
        raise # 호출자에게 예외를 다시 발생시켜 처리하도록 함

def send_to_sqs(queue_url, message_body_dict, message_attributes, region_name=DEFAULT_REGION):
    '''Sends a message to an SQS queue.'''
    # SQS 대기열로 메시지를 보냅니다.
    sqs = boto3.client('sqs', region_name=region_name)
    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body_dict), # 메시지 본문이 JSON 문자열인지 확인
            MessageAttributes=message_attributes
        )
        print(f"Message sent to SQS Queue {queue_url}. MessageID: {response.get('MessageId')}")
        return response
    except Exception as e:
        print(f"Error sending to SQS Queue {queue_url}: {e}")
        raise # 호출자에게 예외를 다시 발생시켜 처리하도록 함
