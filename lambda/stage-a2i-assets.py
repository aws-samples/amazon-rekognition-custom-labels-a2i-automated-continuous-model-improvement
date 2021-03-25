import cfnresponse
import json
import boto3
sagemaker = boto3.client('sagemaker')
ssm = boto3.client('ssm')
def get_parameter(parameter_name):
    response = ssm.get_parameter(Name=parameter_name)
    parameter_value = json.loads(response['Parameter']['Value'])
    return parameter_value
def handler(event, context):
    responseData = {}
    responseData['HumanTaskUiArn'] = 'Resource Deleted'
    responseData['FlowDefinitionArn'] = 'Resource Deleted'
    parameter_name = event['ResourceProperties']['ParameterName']
    prefix = event['ResourceProperties']['StackPrefix'].lower()
    task_ui_name = prefix + '-task-ui'
    flow_definition_name = prefix + '-flow-definition'
    if event['RequestType'] == 'Create':
        try:
            response = sagemaker.create_human_task_ui(
                HumanTaskUiName=task_ui_name,
                UiTemplate={
                    'Content': event['ResourceProperties']['TaskUiTemplate']
                }
            )
            responseData['HumanTaskUiArn'] = response['HumanTaskUiArn']
            response = sagemaker.describe_workteam(WorkteamName=event['ResourceProperties']['WorkTeam'])
            response = sagemaker.create_flow_definition(
                FlowDefinitionName = flow_definition_name,
                RoleArn= event['ResourceProperties']['FlowDefinitionRole'],
                HumanLoopConfig= {
                    "WorkteamArn": response['Workteam']['WorkteamArn'],
                    "HumanTaskUiArn": responseData['HumanTaskUiArn'],
                    "TaskCount": 1,
                    "TaskDescription": "Identify Dog Breed In Images",
                    "TaskTitle": "Identify Dog Breed",
                },
                OutputConfig={
                    "S3OutputPath": 's3://'+ event['ResourceProperties']['S3Bucket'] + '/a2i-human-loop-data/'
                }
            )
            responseData['FlowDefinitionArn'] = response['FlowDefinitionArn']
            parameter_value = get_parameter(parameter_name)
            parameter_value['flow_definition_arn'] = responseData['FlowDefinitionArn']
            ssm.put_parameter(Name=parameter_name, Value=json.dumps(parameter_value), Type='String',Overwrite=True)
        except:
            cfnresponse.send(event, context, cfnresponse.FAILED, responseData)
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
    else:
        try:
            response = sagemaker.describe_flow_definition(FlowDefinitionName=flow_definition_name)
            responseData['FlowDefinitionArn'] = response['FlowDefinitionArn']
            response = sagemaker.describe_human_task_ui(HumanTaskUiName=task_ui_name)
            responseData['HumanTaskUiArn'] = response['HumanTaskUiArn']
            if event['RequestType'] == 'Delete':
                sagemaker.delete_flow_definition(FlowDefinitionName=flow_definition_name)
                sagemaker.delete_human_task_ui(HumanTaskUiName=task_ui_name)
                parameter_value = get_parameter(parameter_name)
                parameter_value['flow_definition_arn'] = ''
                response = ssm.put_parameter(Name=parameter_name, Value=json.dumps(parameter_value), Type='String',Overwrite=True)
        except:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)
    return {'message': responseData}
