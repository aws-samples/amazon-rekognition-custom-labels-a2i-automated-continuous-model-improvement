import json
import os
import boto3
ssm = boto3.client('ssm')
s3_resource = boto3.resource('s3')
sns = boto3.client('sns')
rekognition = boto3.client('rekognition')
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
    del parameter_store['For-System-Use-Only']
    next_task = 'End'
    if parameter_store['Enable-Automatic-Training'] in ['True', 'true', 'TRUE']:
        s3_bucket = sys_vars['s3_bucket']
        bucket = s3_resource.Bucket(s3_bucket)
        image_count = -1
        for object in bucket.objects.filter(Prefix='images_labeled_by_folder/'):
            image_count += 1
        trained_image = int(sys_vars['previous_trained_images'])
        untrained_images = image_count - trained_image
        if untrained_images >= int(parameter_store['Minimum-Untrained-Images']):
            project_arn = sys_vars['rekognition_project_arn']
            response = rekognition.describe_project_versions(ProjectArn=project_arn)
            next_task = 'CreateManifest'
            task_details = "New training criteria met."
            for project_version in response['ProjectVersionDescriptions']:
                if project_version['Status'] in ['TRAINING_IN_PROGRESS', 'STARTING']:
                    next_task = 'End'
                    task_details = 'Preject Version ' + project_version['ProjectVersionArn'] + ' is currently in training'
                    break
            else:
                task_details =  'Minimum Number Untrained Images Condition Not Met'
    else:
        task_details =  'Autmatic training option is disabled'
    response = {'NextTask': next_task, 'Task': {'Details': task_details}, 'UserSettings': parameter_store, 'Project': sys_vars}
    publish_message('Checked for Automatic Model Training', task_details, sys_vars['sns-topic'])
    return {
        'message': response
    }
