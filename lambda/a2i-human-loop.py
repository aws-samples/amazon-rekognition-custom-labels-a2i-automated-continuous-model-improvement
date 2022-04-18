import json
import os
import boto3
s3 = boto3.client('s3')
s3_resource = boto3.resource('s3')
ssm = boto3.client('ssm')
dynamodb = boto3.client('dynamodb')
sns = boto3.client('sns')
def get_parameter(name):
    response = ssm.get_parameter(
        Name=os.environ['parameter_store_path']+name
    )
    return json.loads(response['Parameter']['Value'])
def append_human_results(dynamodb_table, detectlabel_request_id, label, new_key, submission_time):
    response = dynamodb.update_item(
        TableName=dynamodb_table,
        Key={
            'DetectLabelRequestId': {'S':detectlabel_request_id}
        },
        ExpressionAttributeNames={
            '#HL':'HumanLabel',
            '#S3':'CopiedS3ObjectKey',
            '#AT': 'HumanLableCompletedDate'
        },
        ExpressionAttributeValues={
            ':h': {'S':label},
            ':s': {'S':new_key},
            ':a': {'S':submission_time}
        },
        UpdateExpression='SET #HL=:h, #S3=:s, #AT=:a'
    )
def publish_message(sns_subject, sns_message, topic_arn):
    response = sns.publish(
        TopicArn=topic_arn,
        Message=sns_message,
        Subject=sns_subject
    )
def handler(event, context):
    sys_vars = get_parameter('For-System-Use-Only')
    dynamodb_table = sys_vars['dynamodb_table']
    bucket = event['s3event']['s3']['bucket']['name']
    key = event['s3event']['s3']['object']['key']
    s3_response = s3.get_object(Bucket = bucket, Key = key)
    s3_json = json.loads(s3_response['Body'].read())
    new_key=''
    task_details =  'Error: Unable to process humanLoop data'
    label = 'NA'
    submission_time = 'NA'
    if len(s3_json['humanAnswers']) != 0:
        label = s3_json['humanAnswers'][0]['answerContent']['crowd-image-classifier']['label']
        if label != 'None of the Above' and s3_json['inputContent']['source'] == 'A2I Workflow':
            taskObject = s3_json['inputContent']['taskObject']
            bucket, key = taskObject.replace("s3://", "").split("/", 1)
            copy_source = {'Bucket': bucket, 'Key': key}
            image_name = 'humanLoopName-' + s3_json['humanLoopName'] + '-' + taskObject.split('/')[-1]
            new_key = 'images_labeled_by_folder/' + label + '/' + image_name
            s3_resource.meta.client.copy(copy_source, sys_vars['s3_bucket'], new_key)
            task_details =  'Image copied to training folder'
        else:
            task_details =  'Image NOT copied to training folder'
    detectlabel_request_id=s3_json['inputContent']['detectLabelRequestId']
    submission_time = s3_json['humanAnswers'][0]['submissionTime']
    append_human_results(dynamodb_table, detectlabel_request_id, label, new_key, submission_time)
    response = {
        'NextTask': 'End',
        'Task': {
            'Details': task_details,
            'HumanLoopSource': s3_json['inputContent']['source'],
            'HumanLabel': label
        },
        'SystemVariables': sys_vars,
        'ResponseMetadata': s3_json
    }
    publish_message('Process HumanLoop Labeled Data', json.dumps(response), sys_vars['sns-topic'])
    return {
        'message': response
    }
