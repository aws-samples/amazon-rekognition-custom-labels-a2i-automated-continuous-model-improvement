import json
import os
import boto3
import uuid
ssm = boto3.client('ssm')
sns = boto3.client('sns')
rekognition = boto3.client('rekognition')
def get_parameters():
    response = ssm.get_parameters_by_path(
        Path=os.environ['parameter_store_path'],
        Recursive=True
    )
    parameter_store = {}
    for parameter in response['Parameters']:
        parameter_name = (parameter['Name'].split('/'))[-1]
        parameter_store[parameter_name] = parameter['Value']
    return parameter_store
def publish_message(sns_subject, sns_message, topic_arn):
    response = sns.publish(
        TopicArn=topic_arn,
        Message=sns_message,
        Subject=sns_subject
    )
def handler(event, context):
    parameter_store = get_parameters()
    sys_vars = json.loads(parameter_store['For-System-Use-Only'])
    response = rekognition.detect_custom_labels(
        ProjectVersionArn=sys_vars['rekognition_project_version_arn'],
        Image={
            'S3Object': {
                'Bucket': event['s3event']['s3']['bucket']['name'],
                'Name': event['s3event']['s3']['object']['key']
            }
        },
        MaxResults=1,
        MinConfidence=0
    )
    confidence_level = response['CustomLabels'][0]['Confidence']
    publish_message('Rekgnition Custom Labels Detection Invoked', json.dumps(response), sys_vars['sns-topic'])
    if confidence_level < float(parameter_store['Minimum-Label-Detection-Confidence']):
        if parameter_store['Enable-A2I-Workflow'] in ['True', 'true', 'TRUE']:
            response['A2I'] = True
        else:
            response['A2I'] = False
    response['s3event'] = event['s3event']
    return {
        'message': response
    }
