import json
import os
import boto3
ssm = boto3.client('ssm')
sns = boto3.client('sns')
rekognition = boto3.client('rekognition')
dynamodb = boto3.client('dynamodb')
def get_parameter(name):
    response = ssm.get_parameter(
        Name=os.environ['parameter_store_path']+name
    )
    return json.loads(response['Parameter']['Value'])
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
            'DetectedLabel': {'S':detected_label},
            'DetectedConfidenceLevel': {'N':str(confidence_level)},
            'MinimumConfidenceLevel': {'N':str(minimum_confidence_level)},
            'A2IEnabled': {'BOOL':A2I},
            'Sampled': {'S':'No'}
        }
    )
def publish_message(sns_subject, sns_message, topic_arn):
    response = sns.publish(
        TopicArn=topic_arn,
        Message=sns_message,
        Subject=sns_subject
    )
def handler(event, context):
    sys_vars = get_parameter('For-System-Use-Only')
    project_version = sys_vars['rekognition_project_version_arn']
    dynamodb_table = sys_vars['dynamodb_table']
    minimum_confidence_level= float(get_parameter('Minimum-Label-Detection-Confidence'))
    s3_bucket_name=event['s3event']['s3']['bucket']['name']
    s3_object_key=event['s3event']['s3']['object']['key']
    s3_object_eTag=event['s3event']['s3']['object']['eTag']
    s3_event_time=event['s3event']['eventTime']
    rekognition_response = rekognition.detect_custom_labels(
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
    confidence_level = rekognition_response['CustomLabels'][0]['Confidence']
    detected_label = rekognition_response['CustomLabels'][0]['Name']
    detectlabel_request_id = rekognition_response['ResponseMetadata']['RequestId']
    a2i = get_parameter('Enable-A2I-Workflow')
    if confidence_level <  minimum_confidence_level:
        next_task = 'A2I'
        task_details = 'Detection Fail Minimum Confidence Level'
    else:
        next_task = 'End'
        task_details = 'Detection Pass Minimum Confidence Level'
    store_detection_results(dynamodb_table, detectlabel_request_id, s3_event_time, s3_bucket_name, s3_object_key, s3_object_eTag, project_version, detected_label, confidence_level, minimum_confidence_level, a2i)
    response = {
        'NextTask': next_task,
        'Task': {
            'Details': task_details,
            'DetectedLabel': detected_label,
            'DetectedConfidenceLevel': confidence_level,
            'S3Object': {
                'Bucket': s3_bucket_name,
                'Name': s3_object_key
            },
            'UserSettings': {
                'EnableA2IWorkflow': a2i,
                'MinimumConfidenceLevel': minimum_confidence_level
            }
        },
        'SystemVariables': sys_vars,
        'ResponseMetadata': rekognition_response['ResponseMetadata']
    }
    publish_message('Rekognition Detect Custome Label', json.dumps(response), sys_vars['sns-topic'])
    return {
        'message': response
    }
