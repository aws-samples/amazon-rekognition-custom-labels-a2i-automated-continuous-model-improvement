import json
import os
import boto3
import uuid
sns = boto3.client('sns')
a2i = boto3.client('sagemaker-a2i-runtime')
ssm = boto3.client('ssm')
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
def handler(event, context):
    parameter_name = os.environ['parameter_store_path'] + 'For-System-Use-Only'
    sys_vars = get_parameter(parameter_name)
    response = a2i.start_human_loop(
        HumanLoopName = str(uuid.uuid4()),
        FlowDefinitionArn = sys_vars['flow_definition_arn'],
        HumanLoopInput = {
            'InputContent': json.dumps({
                'initialValue': event['message']['CustomLabels'][0]['Confidence'],
                'taskObject': 's3://'+event['message']['s3event']['s3']['bucket']['name']+'/'+event['message']['s3event']['s3']['object']['key']
            })
        }
    )
    response['s3event'] = event['message']['s3event']
    publish_message('A2I Human Loop Initiated', json.dumps(response), sys_vars['sns-topic'])
    return {
        'message': response
    }
