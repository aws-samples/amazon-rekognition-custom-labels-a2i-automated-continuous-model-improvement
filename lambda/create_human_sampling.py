import json
import os
import boto3
import uuid
import datetime
sns = boto3.client('sns')
a2i = boto3.client('sagemaker-a2i-runtime')
ssm = boto3.client('ssm')
dynamodb = boto3.client('dynamodb')
def get_parameter(name):
    response = ssm.get_parameter(
        Name=os.environ['parameter_store_path']+name
    )
    return json.loads(response['Parameter']['Value'])
def get_parameter_date(name):
    response = ssm.get_parameter(
        Name=os.environ['parameter_store_path']+name
    )
    return response['Parameter']['LastModifiedDate'].strftime("%Y-%m-%dT%H:%M:%-S.000Z")
def publish_message(sns_subject, sns_message, topic_arn):
    response = sns.publish(
        TopicArn=topic_arn,
        Message=sns_message,
        Subject=sns_subject
    )
def update_human_sampling(dynamodb_table, detectlabel_request_id, human_loop_name, humanloop_request_id):
    response = dynamodb.update_item(
        TableName=dynamodb_table,
        Key={
            'DetectLabelRequestId': {'S':detectlabel_request_id}
        },
        ExpressionAttributeNames={
            '#HLN':'HumanLoopName',
            '#HLRI':'HumanLoopRequestId',
            '#HSAM':'Sampled'
        },
        ExpressionAttributeValues={
            ':n': {'S':human_loop_name},
            ':i': {'S':humanloop_request_id},
            ':m': {'S':'Yes'}
        },
        UpdateExpression='SET #HLN=:n, #HLRI=:i, #HSAM=:m'
    )
def query_gsi(dynamodb_table, dynamodb_table_GSI, sampled, scan_index_forward, limit, query_date):
    if query_date == '':
        query_date = '2000-01-01T00:00:00.000Z'
    response = dynamodb.query(
        TableName=dynamodb_table,
        IndexName=dynamodb_table_GSI,
        KeyConditionExpression='Sampled=:s AND DetectLabelDate>:d',
        ExpressionAttributeValues={
            ':s': {'S':sampled},
            ':d': {'S':query_date}
        },
        ScanIndexForward=scan_index_forward,
        Limit=limit
    )
    return response
def query_table(dynamodb_table, detectlabel_request_id):
    response = dynamodb.query(
        TableName=dynamodb_table,
        KeyConditionExpression='DetectLabelRequestId=:i',
        ExpressionAttributeValues={
            ':i': {'S':detectlabel_request_id}
        },
    )
    return response
def handler(event, context):
    sys_vars = get_parameter('For-System-Use-Only')
    dynamodb_table = sys_vars['dynamodb_table']
    dynamodb_table_GSI = sys_vars['dynamodb_table_GSI']
    a2i_response = {"ResponseMetadata": ""}
    if 'message' in event:
        last_sample_date = event['message']['Task']['NewHumanSample']['DetectLabelDate']
        last_detect_label_request_id = event['message']['Task']['NewHumanSample']['DetectLabelRequestId']
    else:
        last_sample_date = get_parameter_date('Enable-Automatic-Human-Sampling')
        last_detect_label_request_id = ''
        query_results = query_gsi(dynamodb_table, dynamodb_table_GSI, 'Yes', False, 1, last_sample_date)
        if query_results['Count'] == 1:
            last_sample_date =  query_results['Items'][0]['DetectLabelDate']['S']
            last_detect_label_request_id = query_results['Items'][0]['DetectLabelRequestId']['S']
    human_sampling_interval = int(get_parameter('Human-Sampling-Interval'))
    query_results = query_gsi(dynamodb_table, dynamodb_table_GSI, 'No', True, human_sampling_interval, last_sample_date)
    if query_results['Count'] < human_sampling_interval:
        next_task = 'End'
        task_details = 'Minimum human sampling interval not met'
        new_sample_date = ''
        new_detect_label_request_id = ''
    else:
        next_task = 'Check for new human sampling'
        new_detect_label_request_id = query_results['Items'][human_sampling_interval-1]['DetectLabelRequestId']['S']
        query_item = query_table(dynamodb_table, new_detect_label_request_id)
        new_sample_date = query_item['Items'][0]['DetectLabelDate']['S']
        if 'HumanLoopName' in query_item['Items'][0] :
            task_details = 'Minimum human sampling interval met. A2I already exist.'
            human_loop_name = query_item['Items'][0]['HumanLoopName']['S']
            humanloop_request_id = query_item['Items'][0]['HumanLoopRequestId']['S']
            a2i_response = {"ResponseMetadata": "NA"}
        else:
            task_details = 'Minimum human sampling interval met. A2I created.'
            human_loop_name = str(uuid.uuid4())
            a2i_response = a2i.start_human_loop(
                HumanLoopName = human_loop_name,
                FlowDefinitionArn = sys_vars['flow_definition_arn'],
                HumanLoopInput = {
                    'InputContent': json.dumps({
                        'source': 'Human Sampling',
                        'detectLabelRequestId': new_detect_label_request_id,
                        'detectedConfidenceLevel': query_item['Items'][0]['DetectedConfidenceLevel']['N'],
                        'detectedLabel': query_item['Items'][0]['DetectedLabel']['S'],
                        'taskObject': 's3://'+query_item['Items'][0]['S3Bucket']['S']+'/'+query_item['Items'][0]['S3ObjectKey']['S']
                    })
                }
            )
            humanloop_request_id = a2i_response['ResponseMetadata']['RequestId']
        update_human_sampling(dynamodb_table, new_detect_label_request_id, human_loop_name, humanloop_request_id)
    response = {
        'NextTask': next_task,
        'Task': {
            'Details': task_details,
            'NewDetectLabelRequests': query_results['Count'],
            'HumanSamplingInternal': human_sampling_interval,
            'LastHumanSample': {
                'DetectLabelRequestId': last_detect_label_request_id,
                'DetectLabelDate': last_sample_date
            },
            'NewHumanSample': {
                'DetectLabelRequestId': new_detect_label_request_id,
                'DetectLabelDate': new_sample_date
            }
        },
        'ResponseMetadata': a2i_response['ResponseMetadata']
    }
    publish_message('Human Sampling Event', json.dumps(response), sys_vars['sns-topic'])
    return {
        'message': response
    }
