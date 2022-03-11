import json
import os
import boto3
import uuid
sns = boto3.client('sns')
a2i = boto3.client('sagemaker-a2i-runtime')
ssm = boto3.client('ssm')
dynamodb = boto3.client('dynamodb')
def get_parameter(parameter_name):
    response = ssm.get_parameter(Name=parameter_name)
    parameter_value = json.loads(response['Parameter']['Value'])
    return parameter_value
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
    parameter_name = os.environ['parameter_store_path'] + 'For-System-Use-Only'
    sys_vars = get_parameter(parameter_name)
    dynamodb_table = sys_vars['dynamodb_table']
    detectlabel_request_id=event['message']['ResponseMetadata']['RequestId']
    s3_bucket_name=event['message']['s3event']['s3']['bucket']['name']
    s3_object_key=event['message']['s3event']['s3']['object']['key']
    detected_label=event['message']['CustomLabels'][0]['Name']
    confidence_level=event['message']['CustomLabels'][0]['Confidence']
    human_loop_name=str(uuid.uuid4())
    response = a2i.start_human_loop(
        HumanLoopName = human_loop_name,
        FlowDefinitionArn = sys_vars['flow_definition_arn'],
        HumanLoopInput = {
            'InputContent': json.dumps({
                'initialValue': confidence_level,
                'detectLabelRequestId': detectlabel_request_id,
                'taskObject': 's3://'+s3_bucket_name+'/'+s3_object_key
            })
        }
    )
    humanloop_request_id=response['ResponseMetadata']['RequestId']
    append_a2i_request(dynamodb_table, detectlabel_request_id, human_loop_name, humanloop_request_id)
    response['s3event'] = event['message']['s3event']
    publish_message('A2I Human Loop Initiated', json.dumps(response), sys_vars['sns-topic'])
    return {
        'message': response
    }
