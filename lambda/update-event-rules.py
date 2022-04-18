import json
import os
import boto3
ssm = boto3.client('ssm')
events = boto3.client('events')
sns = boto3.client('sns')
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
def handler(event, context):
    sys_vars = get_parameter('For-System-Use-Only')
    if 'Automatic-Training-Poll-Frequency' in event['detail']['name']:
        resource = sys_vars['events_scheduled_rule']
        value = 'rate(' + str(get_parameter('Automatic-Training-Poll-Frequency')) + ' minutes)'
        events_response = events.put_rule(Name=resource, ScheduleExpression=value)
    elif 'Automatic-Human-Sampling-Frequency' in event['detail']['name']:
        resource = sys_vars['sampling_scheduled_rule']
        value = 'rate(' + str(get_parameter('Automatic-Human-Sampling-Frequency')) + ' minutes)'
        events_response = events.put_rule(Name=resource, ScheduleExpression=value)
    elif 'Enable-Automatic-Training' in event['detail']['name']:
        resource = sys_vars['events_scheduled_rule']
        value = str(get_parameter('Enable-Automatic-Training'))
        if value in ['True', 'true', 'TRUE']:
            events_response = events.enable_rule(Name=resource)
        else:
            events_response = events.disable_rule(Name=resource)
    elif 'Enable-Automatic-Human-Sampling' in event['detail']['name']:
        resource = sys_vars['sampling_scheduled_rule']
        value = str(get_parameter('Enable-Automatic-Human-Sampling'))
        if value in ['True', 'true', 'TRUE']:
            events_response = events.enable_rule(Name=resource)
        else:
            events_response = events.disable_rule(Name=resource)
    response = {
        'NextTask': 'End',
        'Task': {
            'Details': 'Parameter Applied',
            'Parameter': event['detail']['name'],
            'NewValue': value
        },
        'ResponseMetadata': events_response['ResponseMetadata']
    }
    publish_message('Update Parameter Store Value', json.dumps(response), sys_vars['sns-topic'])
    return {
        'message': response
    }
