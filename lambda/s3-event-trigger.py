import json
import os
import uuid
import boto3
sfn = boto3.client('stepfunctions')
ssm = boto3.client('ssm')
def get_parameter(parameter_name):
    response = ssm.get_parameter(Name=parameter_name)
    return json.loads(response['Parameter']['Value'])
def handler(event, context):
    parameter_name = os.environ['parameter_store_path'] + 'For-System-Use-Only'
    sys_vars = get_parameter(parameter_name)
    for item in event['Records']:
        input = {}
        if 'images_for_detection' in item['s3']['object']['key']:
            input['source'] = 's3-detection-event'
        elif 'a2i-human-loop-data' in item['s3']['object']['key']:
            input['source'] = 's3-a2i-event'
        else:
            input['source'] = ''
        input['s3event'] = item
        response = sfn.start_execution(
            stateMachineArn = sys_vars['state_machine_arn'],
            name = str(uuid.uuid4()),
            input = json.dumps(input, default=str)
        )
    return {
        'message': json.dumps(response, default=str)
    }
