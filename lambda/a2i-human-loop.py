import json
import os
import boto3
s3 = boto3.client('s3')
s3_resource = boto3.resource('s3')
ssm = boto3.client('ssm')
def get_parameter(parameter_name):
    response = ssm.get_parameter(Name=parameter_name)
    return json.loads(response['Parameter']['Value'])
def handler(event, context):
    parameter_name = os.environ['parameter_store_path'] + 'For-System-Use-Only'
    sys_vars = get_parameter(parameter_name)
    bucket = event['s3event']['s3']['bucket']['name']
    key = event['s3event']['s3']['object']['key']
    response = s3.get_object(Bucket = bucket, Key = key)
    response = json.loads(response['Body'].read())
    if len(response['humanAnswers']) != 0:
        label = response['humanAnswers'][0]['answerContent']['crowd-image-classifier']['label']
        if label != 'None of the Above':
            taskObject = response['inputContent']['taskObject']
            bucket, key = taskObject.replace("s3://", "").split("/", 1)
            copy_source = {'Bucket': bucket, 'Key': key}
            image_name = 'humanLoopName-' + response['humanLoopName'] + '-' + taskObject.split('/')[-1]
            new_key = 'images_labeled_by_folder/' + label + '/' + image_name
            s3_resource.meta.client.copy(copy_source, sys_vars['s3_bucket'], new_key)
    response['s3event'] = event['s3event']
    return {
        'message': response
    }
