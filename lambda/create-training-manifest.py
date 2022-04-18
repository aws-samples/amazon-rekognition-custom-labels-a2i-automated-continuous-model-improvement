import json
import boto3
import os
import datetime
ssm = boto3.client('ssm')
s3 = boto3.client('s3')
paginator = s3.get_paginator('list_objects_v2')
s3_resource = boto3.resource('s3')
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
    s3_bucket = sys_vars['s3_bucket']
    image_count = 0
    pages = paginator.paginate(Bucket=s3_bucket)
    f = open("/tmp/manifest.txt", "a")
    for page in pages:
        for image in page['Contents']:
            object = image['Key'].split("/")
            if len(object) == 3 and object[0] == 'images_labeled_by_folder':
                if object[2] != '':
                    creation_date = image['LastModified'].strftime("%Y-%m-%dT%H:%M:%S.0000")
                    json_text = {
                        "source-ref": "s3://" + s3_bucket + "/" + image['Key'],
                        "rekongition-custom-labels-brand-detection": 1,
                        "rekongition-custom-labels-brand-detection-metadata": {
                            "confidence": 1,
                            "class-name": object[1],
                            "human-annotated": "yes",
                            "creation-date": creation_date,
                            "type": "groundtruth/image-classification"
                        }
                    }
                    json_object = json.dumps(json_text)
                    f.write(json_object + '\n')
                    image_count += 1
    f.close()
    file_name = 'manifests/groundtruth-' + datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + '.manifest'
    s3_resource.meta.client.upload_file('/tmp/manifest.txt', s3_bucket, file_name)
    response = event['message']
    response['NextTask'] = 'CreateProjectVersion'
    response['Task'] = {'Manifest':  file_name, 'TotalImages': image_count}
    publish_message('New Training Manifest Created', json.dumps(response), sys_vars['sns-topic'])
    return {
        'message': response
    }
