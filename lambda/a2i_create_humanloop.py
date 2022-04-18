import json
import os
import boto3
import uuid
sns = boto3.client('sns')
a2i = boto3.client('sagemaker-a2i-runtime')
ssm = boto3.client('ssm')
dynamodb = boto3.client('dynamodb')
def get_parameter(name):
    response = ssm.get_parameter(
        Name=os.environ['parameter_store_path']+name
    )
    return json.loads(response['Parameter']['Value'])
def publish_message(sns_subject, sns_message, topic_arn):
    response = sns.publish(
        TopicArn=topic_arn,
        Message=sns_message,
        Subject=sns_subject
    )
def append_a2i_request(dynamodb_table, detectlabel_request_id, human_loop_name, humanloop_request_id):
    response = dynamodb.update_item(
        TableName=dynamodb_table,
        Key={
            'DetectLabelRequestId': {'S':detectlabel_request_id}
        },
        ExpressionAttributeNames={
            '#HLN':'HumanLoopName',
            '#HLRI':'HumanLoopRequestId'
        },
        ExpressionAttributeValues={
            ':n': {'S':human_loop_name},
            ':i': {'S':humanloop_request_id}
        },
        UpdateExpression='SET #HLN=:n, #HLRI=:i'
    )
def handler(event, context):
    sys_vars = get_parameter('For-System-Use-Only')
    dynamodb_table = sys_vars['dynamodb_table']
    detectlabel_request_id=event['message']['ResponseMetadata']['RequestId']
    s3_bucket_name=event['message']['Task']['S3Object']['Bucket']
    s3_object_key=event['message']['Task']['S3Object']['Name']
    detected_label=event['message']['Task']['DetectedLabel']
    detected_confidence_level=event['message']['Task']['DetectedConfidenceLevel']
    human_loop_name=str(uuid.uuid4())
    a2i_response = a2i.start_human_loop(
        HumanLoopName = human_loop_name,
        FlowDefinitionArn = sys_vars['flow_definition_arn'],
        HumanLoopInput = {
            'InputContent': json.dumps({
                'source': 'A2I Workflow',
                'detectLabelRequestId': detectlabel_request_id,
                'detectedConfidenceLevel': detected_confidence_level,
                'detectedLabel': detected_label,
                'taskObject': 's3://'+s3_bucket_name+'/'+s3_object_key
            })
        }
    )
    humanloop_request_id=a2i_response['ResponseMetadata']['RequestId']
    append_a2i_request(dynamodb_table, detectlabel_request_id, human_loop_name, humanloop_request_id)
    response = {
        'NextTask': 'End',
        'Task': {
            'Details': 'A2I HumanLoop Created',
            'Source': 'A2I Workflow',
            'DetectLabelRequestId': detectlabel_request_id,
            'DetectedConfidenceLevel': detected_confidence_level,
            'DetectedLabel': detected_label,
            'TaskObject': 's3://'+s3_bucket_name+'/'+s3_object_key,
            'HumanLoopRequestId': humanloop_request_id
        },
        'SystemVariables': sys_vars,
        'ResponseMetadata': a2i_response['ResponseMetadata']
    }
    publish_message('Create A2I HumanLoop', json.dumps(response), sys_vars['sns-topic'])
    return {
        'message': response
    }
