# 1. Deployment

The commands in this walkthrough are for a Bash or Zsh shell on macOS or Linux. On Windows, use Windows Subsystem for Linux (WSL).

## Get the code and install the tools

```bash
git clone https://github.com/aws-samples/amazon-rekognition-custom-labels-a2i-automated-continuous-model-improvement.git
cd amazon-rekognition-custom-labels-a2i-automated-continuous-model-improvement

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci
```

`pip` installs the pinned CDK library into a virtual environment, and `npm ci` installs the pinned CDK CLI into `node_modules`. If you open a new terminal later, run `source .venv/bin/activate` again in this folder before you use `npx cdk`.

## Bootstrap the CDK

The CDK needs a one-time setup in each account and Region, called bootstrapping. It creates a stack named `CDKToolkit` with an S3 bucket and IAM roles for deployments. If you've already bootstrapped this account and Region, you can skip this step. Running it again updates the `CDKToolkit` stack to the bootstrap version of the pinned CDK CLI.

```bash
npx cdk bootstrap
```

## Deploy the stack

Replace the email address with yours. It receives the workflow's notifications, and it becomes the first reviewer's user name.

```bash
npx cdk deploy --parameters NotificationEmail=you@example.com
```

The CDK lists the IAM changes and asks you to confirm. Enter `y`. The deployment takes about 5 minutes, mostly for the CloudFront distribution.

The stack is named `CustomLabelsModelImprovement`. To deploy a second copy in the same account and Region, give it another name with `-c stackName=AnotherName`, and use that name wherever this walkthrough uses the stack name.

## Confirm the emails

You get two emails:

1. **AWS Notification - Subscription Confirmation** from Amazon SNS. Choose **Confirm subscription**. Until you do, you don't get the workflow's notifications.
2. **Your reviewer account for the image review portal** from Amazon Cognito. It has the portal's address, your user name, and a temporary password, which expires in 7 days. You use it in [section 5](../5-Human-Review/).

## Set the variables for the next sections

The next sections use these shell variables. Run this block now, and again whenever you open a new terminal.

```bash
STACK=CustomLabelsModelImprovement
output() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
BUCKET=$(output BucketName)
PROJECT_ARN=$(output ProjectArn)
TRAINING=$(output TrainingStateMachineArn)
DETECTION=$(output DetectionStateMachineArn)
REVIEW=$(output ReviewStateMachineArn)
LOG_TABLE=$(output InferenceLogTableName)
STATE_TABLE=$(output StateTableName)
USER_POOL=$(output ReviewerUserPoolId)
PORTAL=$(output ReviewPortalUrl)
echo "Bucket: $BUCKET"
echo "Review portal: $PORTAL"
```

## What the stack creates

- An S3 bucket with two folders: `images_labeled_by_folder/` for training images and `images_for_detection/` for images to check
- A Rekognition Custom Labels project
- Five Step Functions state machines: training, detection, review, settings, and cleanup
- An EventBridge Scheduler schedule that starts a training check every 12 hours, and EventBridge rules for new images and settings changes
- Two DynamoDB tables: the inference log, with a review queue index, and a state table
- Eleven settings in Parameter Store, under `/CustomLabelsModelImprovement/`
- An SNS topic for email notifications
- The review portal: a Cognito user pool, an API Gateway HTTP API, the review API Lambda function, and the review page behind CloudFront

During the deployment, the new schedule starts a first training check. It finds no images and ends without training. You don't get an email for it.

Next: [Settings](../2-Parameter-Store/)
