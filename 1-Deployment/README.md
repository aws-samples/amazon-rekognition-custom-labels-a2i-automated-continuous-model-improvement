## 1-Deployment

**Deploy CloudFormation Template**  
The provided CloudFormation template deploys the complete architecture.

1. Go to [AWS CloudFormation](https://console.aws.amazon.com/cloudformation) and select the region from the previous step.
2. Create a new stack with the provided template **rekognition-a2i-automate-workflow.yml**.
3. Click **Next**
4. For **Stack name**, enter a name.
5. For **A2IPrivateTeamName**, leave it blank if you don't have a SageMaker Private Workforce. If you have a SageMaker Private Workforce, enter the Private Team name, not the ARN. Please see previous Step 0-Prerequsites for information.
6. For **SNSEmail**, enter a valid email address for this demo.
7. Click **Next**.
8. On the **Configure stack options** screen, click **Next**.
8. On the **Review** screen, scroll down to accept "I acknowledge that AWS CloudFormation might create IAM resources with custom names."
9. Click **Create stack**

**Notes**
- You will receive an email from "AWS Notification - Subscription Confirmation", please click "Confirm subscription" to confirm.
- If we are deploying a Private Team for you from Step. 5, you will receive an email "Your temporary password" with your username and temporary password. You will need that later to perform the A2I human label tasks.

Next Step: [2-Parameter-Store](../2-Parameter-Store/)
