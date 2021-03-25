## 6-Conclusions-Cleanup

**Conclusions**  
In this demo we demonstrated how to build an automated and configurable continuous model improvement workflow for  **Amazon Rekognition Custom Labels** and **Amazon Augmented AI (A2I)** with an iterative process to continuously monitor and retrain custom models to meet business objectives. We also demonstrated how to parameterized the workflow to provide flexibility without needing development rework.

Things to consider to enhance this worfklow:
- Add additional parameters to control the behaviors of this workflow.
- Build a web interface for the Model Operator and Model Consumer for:
  - Uploading images to **Amazon S3**
  - Modifying **Amazon Systems Manager Parameter Store** values
  - Fan out the **Amazon SNS** topic to integrate other **AWS** services

**Cleanup**
Please follow the steps below to cleanup the AWS resources that we created as part of this demo to avoid unnecessary charges.

1. Go to [AWS CloudFormation](https://console.aws.amazon.com/cloudformation) and select stack for this demo.
2. Select **Delete** to delete the stack. Some resources cannot be deleted by CloudFormation:
  - Amazon S3 bucket
  - Amazon Rekognition Custom Labels project (Charges apply to running models)
  - Amazon SageMaker Ground Truth Private workforce (We created for you)
3. (Optional) Delete Amazon S3 bucket
  - Check the bucket name.
  - Select **Empty** to empty the bucket.
  - Select **Delete** to delete the bucket.
4. (Optional) Delete Rekognition Custom Label project:
  - Stop any running models
    - Select the running model.
    - In the "Evaluate and use model" tab, scroll down and expand the **API Code** section.
    - Execute the **Stop model** **AWS** CLI command to stop the running model.
  - Delete project
    - Select the project and click **Delete** to delete the project and models.
5. (Optional) Delete Amazon SageMaker Ground Truth Private workforce (We created for you):
  - Execute the **AWS** ClI command below. Leave the workforce name ad default and replace the region with your region.   
  `aws sagemaker delete-workforce --workforce-name default --region your-region-x`
