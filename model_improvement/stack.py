"""The stack for the Amazon Rekognition Custom Labels continuous model improvement sample.

Four Step Functions state machines do the work (D4, D5). Their definitions are in the
statemachines folder, and this stack fills in resource names and grants each one only
the permissions it needs.
"""
from pathlib import Path

from aws_cdk import (
    Aws,
    CfnOutput,
    CfnParameter,
    Duration,
    Fn,
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as events_targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_rekognition as rekognition,
    aws_s3 as s3,
    aws_scheduler as scheduler,
    aws_scheduler_targets as scheduler_targets,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_ssm as ssm,
    aws_stepfunctions as sfn,
    custom_resources as cr,
)
from constructs import Construct

STATE_MACHINE_DIR = Path(__file__).parent / "statemachines"

TRAINING_IMAGES_PREFIX = "images_labeled_by_folder/"
DETECTION_IMAGES_PREFIX = "images_for_detection/"
MANIFESTS_PREFIX = "manifests/"
EVALUATION_PREFIX = "evaluation/"

# One default for both the schedule and its parameter (F8).
DEFAULT_TRAINING_FREQUENCY_MINUTES = 720

# Operator settings in Parameter Store: name -> (default value, allowed pattern, description).
SETTINGS = {
    "Enable-Automatic-Training": (
        "true",
        r"^(true|false|True|False|TRUE|FALSE)$",
        "Turns automatic training on (true) or off (false). When you change it, the settings "
        "workflow turns the training schedule on or off. You can still start a training run by hand.",
    ),
    "Automatic-Training-Poll-Frequency": (
        str(DEFAULT_TRAINING_FREQUENCY_MINUTES),
        r"^[1-9][0-9]{0,5}$",
        "How often, in whole minutes, the training workflow checks for new training images. When "
        "you change it, the settings workflow updates the training schedule.",
    ),
    "Minimum-Untrained-Images": (
        "10",
        r"^[1-9][0-9]{0,6}$",
        "How many images must be added since the last training run before a scheduled check "
        "starts a new one. This also applies after a failed run, so the same images aren't "
        "retrained on every check.",
    ),
    "Minimum-F1-Score": (
        "0.8",
        r"^(0(\.[0-9]+)?|1(\.0+)?)$",
        "The lowest F1 score, from 0 to 1, that a newly trained model needs before it's started "
        "and replaces the running model.",
    ),
    "Minimum-Inference-Units": (
        "1",
        r"^[1-9][0-9]?$",
        "The number of inference units to start a new model with. More units give more "
        "throughput. You're charged for each inference unit while the model runs.",
    ),
    "Minimum-Label-Detection-Confidence": (
        "70.0",
        r"^(100(\.0+)?|[0-9]{1,2}(\.[0-9]+)?)$",
        "The lowest confidence, from 0 to 100, for a detection to be accepted. Detections below "
        "it are marked as low confidence in the inference log and emailed, and they get a human "
        "review when Enable-Human-Review is true.",
    ),
    "Enable-Human-Review": (
        "true",
        r"^(true|false|True|False|TRUE|FALSE)$",
        "Turns human review of low-confidence detections on (true) or off (false). After a reviewer "
        "labels a low-confidence image, it's added to the training images.",
    ),
    "Enable-Automatic-Human-Sampling": (
        "true",
        r"^(true|false|True|False|TRUE|FALSE)$",
        "Turns human sampling on (true) or off (false). Sampling sends every Nth detection to human "
        "review, where N is Human-Sampling-Interval, to check the model's accuracy. Sampled images "
        "aren't added to the training images.",
    ),
    "Human-Sampling-Interval": (
        "1000",
        r"^[1-9][0-9]{0,8}$",
        "Sends every Nth detection to human review when Enable-Automatic-Human-Sampling is true.",
    ),
    "Human-Review-Labels": (
        "amazon_logo,aws_logo",
        r"^[A-Za-z0-9_-]+(,[A-Za-z0-9_-]+)*$",
        "The labels that reviewers choose from, separated by commas. Each label is also a folder name "
        "under images_labeled_by_folder/. Reviewers also get a None of the above choice.",
    ),
    "Human-Review-Timeout-Hours": (
        "72",
        r"^[0-9]{1,4}(\.[0-9]{1,2})?$",
        "How long a review task waits for a reviewer before it expires, in hours. Decimals are "
        "allowed. The shortest timeout is 1 minute.",
    ),
}

STANDARD_RETENTION = logs.RetentionDays.ONE_MONTH

# Human review (H2). The reviewers group is created with the user pool in H3.
REVIEW_QUEUE_INDEX = "ReviewQueue"
REVIEWER_GROUP = "reviewers"
CLAIM_SECONDS = 15 * 60
IMAGE_URL_SECONDS = 5 * 60
REVIEW_API_DIR = Path(__file__).parent / "review_api"


class ModelImprovementStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        notification_email = CfnParameter(
            self,
            "NotificationEmail",
            type="String",
            description="The email address for training, detection, and failure notifications. "
            "Amazon SNS sends a confirmation email to it after deployment.",
            allowed_pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
            constraint_description="Enter a valid email address.",
        )

        # Storage --------------------------------------------------------------------------

        bucket = s3.Bucket(
            self,
            "Bucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        # Send S3 events to EventBridge (D4). Setting this on the CloudFormation resource avoids
        # the Lambda-backed custom resource that the eventBridgeEnabled property adds.
        bucket.node.default_child.add_property_override(
            "NotificationConfiguration.EventBridgeConfiguration.EventBridgeEnabled", True
        )

        inference_log = dynamodb.TableV2(
            self,
            "InferenceLog",
            partition_key=dynamodb.Attribute(name="DetectLabelRequestId", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            removal_policy=RemovalPolicy.RETAIN,
        )
        # The review queue. Only items with a waiting review task have ReviewQueue, so this sparse
        # index lists exactly the open and claimed tasks, oldest first.
        inference_log.add_global_secondary_index(
            index_name=REVIEW_QUEUE_INDEX,
            partition_key=dynamodb.Attribute(name="ReviewQueue", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="ReviewCreated", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.INCLUDE,
            non_key_attributes=["ReviewStatus", "ReviewClaimedBy", "ReviewClaimExpires"],
        )

        # One item holds the run-time state: the running model and the counters (D8).
        state_table = dynamodb.TableV2(
            self,
            "StateTable",
            partition_key=dynamodb.Attribute(name="StateId", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # The project and its models are kept when the stack is deleted (D4), so the name gets
        # the stack ID's last segment. Redeploying a stack with the same name gets a new project.
        stack_id_suffix = Fn.select(4, Fn.split("-", Fn.select(2, Fn.split("/", Aws.STACK_ID))))
        project_name = Fn.join("-", [self.stack_name, stack_id_suffix])
        project = rekognition.CfnProject(self, "Project", project_name=project_name)
        project.apply_removal_policy(RemovalPolicy.RETAIN)
        project_resources = Fn.join(
            "", ["arn:", Aws.PARTITION, ":rekognition:", Aws.REGION, ":", Aws.ACCOUNT_ID, ":project/", project_name, "/*"]
        )

        topic = sns.Topic(self, "Notifications", display_name=self.stack_name[:100], enforce_ssl=True)
        topic.add_subscription(subscriptions.EmailSubscription(notification_email.value_as_string))

        parameter_prefix = f"/{self.stack_name}"
        settings = {
            name: ssm.StringParameter(
                self,
                name.replace("-", ""),
                parameter_name=f"{parameter_prefix}/{name}",
                string_value=value,
                allowed_pattern=pattern,
                description=description,
            )
            for name, (value, pattern, description) in SETTINGS.items()
        }

        # CDK's own custom resource function (D4) logs here, and the log group is deleted with
        # the stack (T1 teardown finding).
        custom_resource_logs = logs.LogGroup(
            self, "CustomResourceLogs", retention=STANDARD_RETENTION, removal_policy=RemovalPolicy.DESTROY
        )

        # Folder placeholders, so the folders show up in the S3 console for uploads.
        for folder_id, folder in (("TrainingFolder", TRAINING_IMAGES_PREFIX), ("DetectionFolder", DETECTION_IMAGES_PREFIX)):
            cr.AwsCustomResource(
                self,
                folder_id,
                on_create=cr.AwsSdkCall(
                    service="S3",
                    action="putObject",
                    parameters={"Bucket": bucket.bucket_name, "Key": folder},
                    physical_resource_id=cr.PhysicalResourceId.of(folder),
                    output_paths=["ETag"],
                ),
                policy=cr.AwsCustomResourcePolicy.from_statements(
                    [iam.PolicyStatement(actions=["s3:PutObject"], resources=[bucket.arn_for_objects(folder)])]
                ),
                install_latest_aws_sdk=False,
                log_group=custom_resource_logs,
            )

        # State machines -------------------------------------------------------------------

        substitutions = {
            "BucketName": bucket.bucket_name,
            "ProjectArn": project.attr_arn,
            "ProjectName": project_name,
            "StateTableName": state_table.table_name,
            "LogTableName": inference_log.table_name,
            "TopicArn": topic.topic_arn,
            "ParameterPrefix": parameter_prefix,
            "StackName": self.stack_name,
        }

        training = self._state_machine("Training", "training.asl.json", substitutions)
        review = self._state_machine("Review", "review.asl.json", substitutions)
        detection = self._state_machine(
            "Detection",
            "detection.asl.json",
            {**substitutions, "ReviewStateMachineArn": review.state_machine_arn},
        )
        cleanup = self._state_machine(
            "Cleanup",
            "cleanup.asl.json",
            substitutions,
            state_machine_type=sfn.StateMachineType.EXPRESS,
            log_level=sfn.LogLevel.ALL,
        )

        # The training schedule (O1). It passes {"trigger": "schedule"}, so the workflow knows
        # the run wasn't started by hand.
        schedule_role = iam.Role(
            self,
            "TrainingScheduleRole",
            assumed_by=iam.ServicePrincipal(
                "scheduler.amazonaws.com",
                conditions={"StringEquals": {"aws:SourceAccount": Aws.ACCOUNT_ID}},
            ),
        )
        training_schedule = scheduler.Schedule(
            self,
            "TrainingSchedule",
            schedule=scheduler.ScheduleExpression.rate(Duration.minutes(DEFAULT_TRAINING_FREQUENCY_MINUTES)),
            target=scheduler_targets.StepFunctionsStartExecution(
                training,
                input=scheduler.ScheduleTargetInput.from_object({"trigger": "schedule"}),
                role=schedule_role,
                retry_attempts=2,
                max_event_age=Duration.hours(1),
            ),
            description="Starts the training workflow, which trains a new model when enough images were "
            "added. The settings workflow changes this schedule when Enable-Automatic-Training or "
            "Automatic-Training-Poll-Frequency changes.",
        )

        settings_workflow = self._state_machine(
            "Settings",
            "settings.asl.json",
            {**substitutions, "ScheduleName": training_schedule.schedule_name, "ScheduleGroupName": "default"},
        )

        # Permissions ----------------------------------------------------------------------

        for workflow in (training, detection, settings_workflow, cleanup):
            topic.grant_publish(workflow)

        # Training: settings, state, the S3 folders, the project, and itself.
        for name in ("Enable-Automatic-Training", "Minimum-Untrained-Images", "Minimum-F1-Score", "Minimum-Inference-Units"):
            settings[name].grant_read(training)
        state_table.grant(training, "dynamodb:GetItem", "dynamodb:UpdateItem")
        bucket.grant_read(training, f"{TRAINING_IMAGES_PREFIX}*")
        bucket.grant_read(training, f"{MANIFESTS_PREFIX}*")
        bucket.grant_put(training, f"{MANIFESTS_PREFIX}*")
        # CreateProjectVersion writes evaluation results with the caller's permissions.
        bucket.grant_put(training, f"{EVALUATION_PREFIX}*")
        training.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "rekognition:CreateDataset",
                    "rekognition:DeleteDataset",
                    "rekognition:DescribeDataset",
                    "rekognition:DistributeDatasetEntries",
                    "rekognition:CreateProjectVersion",
                    "rekognition:DescribeProjectVersions",
                    "rekognition:StartProjectVersion",
                    "rekognition:StopProjectVersion",
                ],
                resources=[project_resources],
            )
        )
        # DescribeProjects doesn't support resource-level permissions.
        training.add_to_role_policy(iam.PolicyStatement(actions=["rekognition:DescribeProjects"], resources=["*"]))
        # The Distributed Map starts child runs of this state machine, and the run checks for other
        # training runs. A separate policy avoids a dependency loop between the role and the state machine.
        training_name = Fn.select(6, Fn.split(":", training.state_machine_arn))
        training_executions = Fn.join(
            "", ["arn:", Aws.PARTITION, ":states:", Aws.REGION, ":", Aws.ACCOUNT_ID, ":execution:", training_name]
        )
        iam.Policy(
            self,
            "TrainingSelfPolicy",
            roles=[training.role],
            statements=[
                iam.PolicyStatement(
                    actions=["states:StartExecution", "states:ListExecutions"],
                    resources=[training.state_machine_arn],
                ),
                iam.PolicyStatement(
                    actions=["states:DescribeExecution", "states:StopExecution"],
                    resources=[Fn.join("", [training_executions, ":*"]), Fn.join("", [training_executions, "/*"])],
                ),
            ],
        )

        # Detection: its settings, the state item, the log, the model, the uploaded images, and
        # starting reviews.
        for name in (
            "Minimum-Label-Detection-Confidence",
            "Enable-Human-Review",
            "Enable-Automatic-Human-Sampling",
            "Human-Sampling-Interval",
        ):
            settings[name].grant_read(detection)
        state_table.grant(detection, "dynamodb:GetItem", "dynamodb:UpdateItem")
        inference_log.grant(detection, "dynamodb:PutItem")
        bucket.grant_read(detection, f"{DETECTION_IMAGES_PREFIX}*")
        detection.add_to_role_policy(
            iam.PolicyStatement(actions=["rekognition:DetectCustomLabels"], resources=[project_resources])
        )
        review.grant_start_execution(detection)

        # Review: its setting, the review attributes, and copying images into the training folders.
        settings["Human-Review-Timeout-Hours"].grant_read(review)
        inference_log.grant(review, "dynamodb:UpdateItem")
        bucket.grant_read(review, f"{DETECTION_IMAGES_PREFIX}*")
        bucket.grant_put(review, f"{TRAINING_IMAGES_PREFIX}*")
        topic.grant_publish(review)

        # The review API, the only Lambda function the sample owns (D4). API Gateway calls it in H3.
        review_api_logs = logs.LogGroup(
            self, "ReviewApiLogs", retention=STANDARD_RETENTION, removal_policy=RemovalPolicy.DESTROY
        )
        review_api = lambda_.Function(
            self,
            "ReviewApi",
            description="Review API: claims review tasks, submits labels, and releases claims.",
            runtime=lambda_.Runtime.PYTHON_3_14,
            architecture=lambda_.Architecture.ARM_64,
            handler="index.handler",
            code=lambda_.Code.from_asset(str(REVIEW_API_DIR), exclude=["__pycache__", "*.pyc"]),
            memory_size=256,
            timeout=Duration.seconds(10),
            log_group=review_api_logs,
            environment={
                "TABLE_NAME": inference_log.table_name,
                "QUEUE_INDEX": REVIEW_QUEUE_INDEX,
                "LABELS_PARAMETER": settings["Human-Review-Labels"].parameter_name,
                "REVIEWER_GROUP": REVIEWER_GROUP,
                "CLAIM_SECONDS": str(CLAIM_SECONDS),
                "IMAGE_URL_SECONDS": str(IMAGE_URL_SECONDS),
            },
        )
        inference_log.grant(review_api, "dynamodb:Query", "dynamodb:UpdateItem")
        # The presigned image URLs use the function's permissions.
        bucket.grant_read(review_api, f"{DETECTION_IMAGES_PREFIX}*")
        settings["Human-Review-Labels"].grant_read(review_api)
        review.grant(review_api, "states:SendTaskSuccess")

        # Settings: its parameters and the schedule.
        for name in ("Enable-Automatic-Training", "Automatic-Training-Poll-Frequency"):
            settings[name].grant_read(settings_workflow)
        settings_workflow.add_to_role_policy(
            iam.PolicyStatement(
                actions=["scheduler:GetSchedule", "scheduler:UpdateSchedule"],
                resources=[training_schedule.schedule_arn],
            )
        )
        settings_workflow.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[schedule_role.role_arn],
                conditions={"StringEquals": {"iam:PassedToService": "scheduler.amazonaws.com"}},
            )
        )

        # Cleanup: list and stop the project's models.
        cleanup.add_to_role_policy(
            iam.PolicyStatement(
                actions=["rekognition:DescribeProjectVersions", "rekognition:StopProjectVersion"],
                resources=[project_resources],
            )
        )

        # Triggers ---------------------------------------------------------------------------

        events.Rule(
            self,
            "DetectionRule",
            description="Starts the detection workflow for each object created under images_for_detection/.",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [bucket.bucket_name]},
                    "object": {"key": [{"prefix": DETECTION_IMAGES_PREFIX}]},
                },
            ),
            targets=[events_targets.SfnStateMachine(detection, retry_attempts=8, max_event_age=Duration.hours(2))],
        )

        events.Rule(
            self,
            "SettingsRule",
            description="Starts the settings workflow when Enable-Automatic-Training or "
            "Automatic-Training-Poll-Frequency changes.",
            event_pattern=events.EventPattern(
                source=["aws.ssm"],
                detail_type=["Parameter Store Change"],
                detail={
                    "name": [
                        settings["Enable-Automatic-Training"].parameter_name,
                        settings["Automatic-Training-Poll-Frequency"].parameter_name,
                    ],
                    "operation": ["Update"],
                },
            ),
            targets=[events_targets.SfnStateMachine(settings_workflow)],
        )

        # When the stack is deleted, CDK's built-in custom resource runs the cleanup workflow,
        # which stops the running models (D4, F4). The fixed physical ID keeps stack updates
        # from running it.
        cr.AwsCustomResource(
            self,
            "StopModelsOnDelete",
            on_create=cr.AwsSdkCall(
                service="SFN",
                action="describeStateMachine",
                parameters={"stateMachineArn": cleanup.state_machine_arn},
                physical_resource_id=cr.PhysicalResourceId.of("stop-models-on-delete"),
                output_paths=["stateMachineArn"],
            ),
            # A cleanup error must not block stack deletion. The workflow emails if a model
            # can't be stopped.
            on_delete=cr.AwsSdkCall(
                service="SFN",
                action="startSyncExecution",
                parameters={"stateMachineArn": cleanup.state_machine_arn, "input": "{}"},
                output_paths=["status"],
                ignore_error_codes_matching=".*",
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=["states:DescribeStateMachine", "states:StartSyncExecution"],
                        resources=[cleanup.state_machine_arn],
                    )
                ]
            ),
            install_latest_aws_sdk=False,
            log_group=custom_resource_logs,
            timeout=Duration.minutes(5),
        )

        # Outputs --------------------------------------------------------------------------

        CfnOutput(
            self,
            "BucketName",
            value=bucket.bucket_name,
            description="Add training images under images_labeled_by_folder/<label>/ and images to check "
            "under images_for_detection/.",
        )
        CfnOutput(self, "ProjectArn", value=project.attr_arn, description="The Custom Labels project.")
        CfnOutput(
            self,
            "TrainingStateMachineArn",
            value=training.state_machine_arn,
            description="Start a training run by hand with: aws stepfunctions start-execution "
            "--state-machine-arn <this value>",
        )
        CfnOutput(self, "DetectionStateMachineArn", value=detection.state_machine_arn)
        CfnOutput(self, "ReviewStateMachineArn", value=review.state_machine_arn)
        CfnOutput(self, "ReviewApiFunctionName", value=review_api.function_name)
        CfnOutput(self, "InferenceLogTableName", value=inference_log.table_name)
        CfnOutput(self, "StateTableName", value=state_table.table_name)
        CfnOutput(self, "SettingsPath", value=f"{parameter_prefix}/", description="The settings in Parameter Store.")

    def _state_machine(
        self,
        construct_id: str,
        file_name: str,
        substitutions: dict,
        *,
        state_machine_type: sfn.StateMachineType = sfn.StateMachineType.STANDARD,
        log_level: sfn.LogLevel = sfn.LogLevel.ERROR,
    ) -> sfn.StateMachine:
        # Log group names under /aws/vendedlogs/ keep the CloudWatch Logs resource policy small.
        log_group = logs.LogGroup(
            self,
            f"{construct_id}Logs",
            log_group_name=f"/aws/vendedlogs/states/{self.stack_name}-{construct_id}",
            retention=STANDARD_RETENTION,
            removal_policy=RemovalPolicy.DESTROY,
        )
        return sfn.StateMachine(
            self,
            construct_id,
            definition_body=sfn.DefinitionBody.from_file(str(STATE_MACHINE_DIR / file_name)),
            definition_substitutions=substitutions,
            state_machine_type=state_machine_type,
            logs=sfn.LogOptions(destination=log_group, level=log_level, include_execution_data=True),
        )
