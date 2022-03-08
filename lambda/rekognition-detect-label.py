import json
import os
import boto3
ssm = boto3.client('ssm')
sns = boto3.client('sns')
rekognition = boto3.client('rekognition')
dynamodb = boto3.client('dynamodb')
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
def store_detection_results(dynamodb_table, detectlabel_request_id, detectlabel_date, s3_bucket_name, s3_object_key, s3_object_eTag, project_version, detected_label, confidence_level, minimum_confidence_level, A2I):
    response = dynamodb.put_item(
        TableName=dynamodb_table,
        Item={
            'DetectLabelRequestId': {'S':detectlabel_request_id},
            'DetectLabelDate': {'S':detectlabel_date},
            'S3Bucket': {'S':s3_bucket_name},
            'S3ObjectKey': {'S':s3_object_key},
            'S3ObjectEtag': {'S':s3_object_eTag},
            'ProjectVersionArn': {'S':project_version},
            'DectectedLabel': {'S':detected_label},
            'DetectedConfidenceLevel': {'N':str(confidence_level)},
            'MinimumConfidenceLevel': {'N':str(minimum_confidence_level)},
            'A2IEnabled': {'BOOL':A2I}
        }
    )
def publish_message(sns_subject, sns_message, topic_arn):
    response = sns.publish(
        TopicArn=topic_arn,
        Message=sns_message,
        Subject=sns_subject
    )
def handler(event, context):
    parameter_store = get_parameters()
    a2i = True if parameter_store['Enable-A2I-Workflow'].lower().capitalize() == 'True' else False
    sys_vars = json.loads(parameter_store['For-System-Use-Only'])
    project_version = sys_vars['rekognition_project_version_arn']
    dynamodb_table = sys_vars['dynamodb_table']
    minimum_confidence_level=parameter_store['Minimum-Label-Detection-Confidence']
    s3_bucket_name=event['s3event']['s3']['bucket']['name']
    s3_object_key=event['s3event']['s3']['object']['key']
    s3_object_eTag=event['s3event']['s3']['object']['eTag']
    s3_event_time=event['s3event']['eventTime']
    response = rekognition.detect_custom_labels(
        ProjectVersionArn=project_version,
        Image={
            'S3Object': {
                'Bucket': s3_bucket_name,
                'Name': s3_object_key
            }
        },
        MaxResults=1,
        MinConfidence=0
    )
    confidence_level = response['CustomLabels'][0]['Confidence']
    detected_label = response['CustomLabels'][0]['Name']
    detectlabel_request_id = response['ResponseMetadata']['RequestId']
    if confidence_level < float(parameter_store['Minimum-Label-Detection-Confidence']):
        response['A2I'] = True if a2i else False
    store_detection_results(dynamodb_table, detectlabel_request_id, s3_event_time, s3_bucket_name, s3_object_key, s3_object_eTag, project_version, detected_label, confidence_level, minimum_confidence_level, a2i)
    publish_message('Rekgnition Custom Labels Detection Invoked', json.dumps(response), sys_vars['sns-topic'])
    response['s3event'] = event['s3event']
    return {
        'message': response
    }
