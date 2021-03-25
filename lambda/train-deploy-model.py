import json
import boto3
import os
import datetime
ssm = boto3.client('ssm')
rekognition = boto3.client('rekognition')
sns = boto3.client('sns')
def publish_message(sns_subject, sns_message, topic_arn):
    response = sns.publish(
        TopicArn=topic_arn,
        Message=sns_message,
        Subject=sns_subject
    )
def handler(event, context):
    response = event['message']
    project_arn = event['message']['Project']['rekognition_project_arn']
    s3_bucket = event['message']['Project']['s3_bucket']
    if event['message']['NextTask'] == 'CreateProjectVersion':
        version_name = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        rekognition_response = rekognition.create_project_version(
            ProjectArn=project_arn,
            VersionName=version_name,
            OutputConfig={'S3Bucket':s3_bucket, 'S3KeyPrefix':'evaluation/'},
            TrainingData={'Assets': [{'GroundTruthManifest': {'S3Object': {'Bucket': s3_bucket,'Name': event['message']['Task']['Manifest']}}},]},
            TestingData={'AutoCreate': True}
        )
        response['Task']['ProjectVersionArn'] = rekognition_response['ProjectVersionArn']
        response['Task']['VersionName'] = version_name
        next_task = 'DescribeProjectVersions'
    elif event['message']['NextTask'] == 'DescribeProjectVersions':
        version_name = event['message']['Task']['VersionName']
        rekognition_response = rekognition.describe_project_versions(ProjectArn=project_arn, VersionNames=[version_name])
        status = rekognition_response['ProjectVersionDescriptions'][0]['Status']
        if status in ['TRAINING_IN_PROGRESS', 'STARTING']:
            next_task = 'DescribeProjectVersions'
        elif status == 'TRAINING_COMPLETED':
            if rekognition_response['ProjectVersionDescriptions'][0]['EvaluationResult']['F1Score'] >= float(event['message']['UserSettings']['Minimum-F1-Score']):
                next_task = 'StartProjectVersion'
            else:
                next_task = 'FailedF1Evaluation'
                status = next_task
        elif status == 'RUNNING':
            next_task = 'ModelRunning'
        else:
            next_task = 'FAILED'
        publish_message('Rekognition Model Status', 'Status: '+status+'\n'+json.dumps(response['Task']), event['message']['Project']['sns-topic'])
    elif event['message']['NextTask'] == 'StartProjectVersion':
        project_version_arn = event['message']['Task']['ProjectVersionArn']
        min_inteference_unit = int(event['message']['UserSettings']['Minimum-Inference-Units'])
        rekognition_response = rekognition.start_project_version(ProjectVersionArn=project_version_arn, MinInferenceUnits=min_inteference_unit)
        next_task = 'DescribeProjectVersions'
    elif event['message']['NextTask'] == 'ModelRunning':
        parameter_name = os.environ['parameter_store_path']+'For-System-Use-Only'
        project_version_arn = event['message']['Task']['ProjectVersionArn']
        event['message']['Project']['rekognition_project_version_arn'] = project_version_arn
        event['message']['Project']['previous_trained_images'] = event['message']['Task']['TotalImages']
        ssm_response = ssm.put_parameter(Name=parameter_name, Value=json.dumps(event['message']['Project']), Type='String',Overwrite=True)
        rekognition_response = rekognition.describe_project_versions(ProjectArn=project_arn)
        for project_version in rekognition_response['ProjectVersionDescriptions']:
            if project_version['Status'] == 'RUNNING' and project_version['ProjectVersionArn'] != project_version_arn:
                rekognition.stop_project_version(ProjectVersionArn=project_version['ProjectVersionArn'])
        rekognition_response = rekognition.describe_project_versions(ProjectArn=project_arn)
        next_task = 'Succeed'
    response['NextTask'] = next_task
    response['Response'] = json.loads(json.dumps(rekognition_response, default=str))
    return {
        'message': response
    }
