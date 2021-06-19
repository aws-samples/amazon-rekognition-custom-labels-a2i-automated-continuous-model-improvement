## 1 Deploy the solution resources

We show you how to use [AWS CloudFormation](https://console.aws.amazon.com/cloudformation) to deploy the required and optional AWS resources for this solution.

1. Sign in to the [AWS Management Console](https://aws.amazon.com/console/) with your IAM username and password.
2. Go to [AWS CloudFormation](https://console.aws.amazon.com/cloudformation).
3. Choose your **AWS Region** (as noted in the prerequisites).
4. Create a new stack with the provided template ``rekognition-a2i-automate-workflow.yml``.
5. Choose **Next**
6. For **Stack name**, enter a name.
7. For **A2IPrivateTeamName**, leave it blank if you don't have a SageMaker private workforce. If you have a private workforce, enter the private team name, not ARN.
8. For **SNSEmail**, enter a valid email address.
9. Choose **Next**.
10. Choose **Next** on the **Configure stack options** screen.
11. Scroll down to select **I acknowledge that AWS CloudFormation might create IAM resources with custom names** on the **Review** screen.
12. Choose **Create stack**.

The CloudFormation stack takes about 5 minutes to complete. You should receive an email “AWS Notification - Subscription Confirmation” asking you to confirm a subscription. Choose **Confirm subscription** in the email to confirm the subscription. Additionally, if AWS CloudFormation deployed the private work team for you, you should receive an email “Your temporary password” with a username and temporary password. You need this information later to access the Amazon A2I web UI to perform the human labeling tasks.

Next Step: [2-Parameter-Store](../2-Parameter-Store/)
