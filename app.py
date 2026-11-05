#!/usr/bin/env python3
"""Entry point for the CDK app. Deploy with: npx cdk deploy --parameters NotificationEmail=you@example.com"""
import aws_cdk as cdk

from model_improvement.stack import ModelImprovementStack

DEFAULT_STACK_NAME = "CustomLabelsModelImprovement"

app = cdk.App()

# Deploy a second copy in the same account and Region with: npx cdk deploy -c stackName=AnotherName
stack_name = app.node.try_get_context("stackName") or DEFAULT_STACK_NAME

ModelImprovementStack(
    app,
    stack_name,
    stack_name=stack_name,
    description="Amazon Rekognition Custom Labels continuous model improvement sample: automated training and detection with Step Functions",
)

app.synth()
