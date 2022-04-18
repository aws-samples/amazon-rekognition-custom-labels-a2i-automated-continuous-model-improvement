import json
import os
import boto3
ssm = boto3.client('ssm')
s3_resource = boto3.resource('s3')
sns = boto3.client('sns')
rekognition = boto3.client('rekognition')
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
    next_task = 'End'
    enable_automatic_training = str(get_parameter('Enable-Automatic-Training'))
    minimum_untrained_images = int(get_parameter('Minimum-Untrained-Images'))
    if enable_automatic_training in ['True', 'true', 'TRUE']:
        s3_bucket = sys_vars['s3_bucket']
        bucket = s3_resource.Bucket(s3_bucket)
        image_count = -1
        for object in bucket.objects.filter(Prefix='images_labeled_by_folder/'):
            image_count += 1
        trained_image = int(sys_vars['previous_trained_images'])
        untrained_images = image_count - trained_image
        if untrained_images >= minimum_untrained_images:
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
        untrained_images = 'NA'
    response = {
        'NextTask': next_task,
        'Task': {
            'Details': task_details,
            'UntrainedImages': untrained_images,
            'UserSettings': {
                'EnableAutomaticTraining': enable_automatic_training,
                'MinimumUntrainedImages': minimum_untrained_images
            }
        },
        'SystemVariables': sys_vars
    }
    publish_message('Check for Automatic Model Training', json.dumps(response), sys_vars['sns-topic'])
    return {
        'message': response
    }
