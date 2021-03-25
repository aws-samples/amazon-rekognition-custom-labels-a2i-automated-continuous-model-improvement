import json
import os
import boto3
ssm = boto3.client('ssm')
events = boto3.client('events')
sns = boto3.client('sns')
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
    if 'Automatic-Training-Poll-Frequency' in event['detail']['name']:
        resource = sys_vars['events_scheduled_rule']
        value = 'rate(' + parameter_store['Automatic-Training-Poll-Frequency'] + ' minutes)'
        response = events.put_rule(Name=resource, ScheduleExpression=value)
    elif 'Enable-Automatic-Training' in event['detail']['name']:
        resource = sys_vars['events_scheduled_rule']
        if parameter_store['Enable-Automatic-Training'] in ['True', 'true', 'TRUE']:
            value = 'Enabled'
            response = events.enable_rule(Name=resource)
        else:
            response = events.disable_rule(Name=resource)
            value = 'Disabled'
    publish_message('Parameter Applied '+resource, json.dumps(response), sys_vars['sns-topic'])
    response = {'NextTask': 'End', 'Value': value , 'Resource': resource, 'Response': response, 'Event': event }
    return {
        'message': response
    }
