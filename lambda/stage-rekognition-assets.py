import cfnresponse
import boto3
import json
import os
rekognition=boto3.client('rekognition')
s3 = boto3.client('s3')
ssm = boto3.client('ssm')
def handler(event, context):
    responseData = {}
    responseData['ProjectArn'] = 'Deleted'
    project_name=event['ResourceProperties']['StackPrefix'] + '-custom-labels-project'
    if event['RequestType'] == 'Create':
        bucket=event['ResourceProperties']['Bucket']
        lambda_arn=event['ResourceProperties']['LambdaS3EventTriggerArn']
        try:
            s3.put_object(Bucket=bucket, Key='images_labeled_by_folder/')
            s3.put_object(Bucket=bucket, Key='a2i-human-loop-data/')
            s3.put_object(Bucket=bucket, Key='images_for_detection/')
            s3.put_object(Bucket=bucket, Key='manifests/')
            s3.put_object(Bucket=bucket, Key='evaluation/')
            s3.put_bucket_notification_configuration(
            Bucket=bucket,
            NotificationConfiguration={
              'LambdaFunctionConfigurations': [
                {
                  'LambdaFunctionArn': lambda_arn,
                  'Events': ['s3:ObjectCreated:Put'],
                  'Filter': {'Key': {'FilterRules': [{'Name': 'prefix', 'Value': 'images_for_detection/'}]}}
                },
                {
                  'LambdaFunctionArn': lambda_arn,
                  'Events': ['s3:ObjectCreated:Put'],
                  'Filter': {'Key': {'FilterRules': [{'Name': 'prefix', 'Value': 'a2i-human-loop-data/'}, {'Name': 'suffix', 'Value': '.json'}]}}
                }
              ]
            }
            )
            response=rekognition.create_project(ProjectName=project_name)
            responseData['ProjectArn'] = response['ProjectArn']
        except:
            cfnresponse.send(event, context, cfnresponse.FAILED, responseData)
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
    else:
        try:
            parameter_name = os.environ['parameter_store_path'] + 'For-System-Use-Only'
            response = ssm.get_parameter(Name=parameter_name)
            parameter =  json.loads(response['Parameter']['Value'])
            responseData['ProjectArn'] = parameter['rekognition_project_arn']
            if event['RequestType'] == 'Delete':
                response = rekognition.describe_project_versions(ProjectArn=responseData['ProjectArn'])
                for project_version in response['ProjectVersionDescriptions']:
                    if project_version['Status'] == 'RUNNING':
                        rekognition.stop_project_version(ProjectVersionArn=project_version['ProjectVersionArn'])
        except:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
    return {'message': responseData}
