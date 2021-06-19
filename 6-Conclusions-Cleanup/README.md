## 6 Conclusion and cleanup resources

**Conclusions**  
In this demo we explained how to build an automated and configurable continuous model improvement workflow for [Amazon Rekognition Custom Labels](https://aws.amazon.com/rekognition/custom-labels-features/) and [Amazon Augmented AI](https://aws.amazon.com/augmented-ai/) (Amazon A2I). By incorporating [Amazon Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html), we demonstrated how to use parameters as variables for [AWS Step Functions](https://aws.amazon.com/step-functions/) to customize the behaviors of the ML workflow without needing development rework. We walked through the steps to deploy the solution with [AWS CloudFormation](https://aws.amazon.com/cloudformation/) and completed an end-to-end process to train and deploy a Rekognition Custom Labels model, perform custom label detection, and create and complete Amazon A2I human labeling tasks.

Things to consider to enhance this worfklow:
- Add additional parameters to control the behaviors of this workflow.
- Build a web interface for the Model Operator and Model Consumer for:
  - Uploading images to [Amazon S3](https://aws.amazon.com/s3/)
  - Modifying Parameter Store values
  - Fan out the [Amazon Simple Notification Service](https://aws.amazon.com/sns/) (Amazon SNS) topic to integrate other AWS services

**Clean up**  
Complete the following steps to clean up the AWS resources that we created as part of this post to avoid potential recurring charges.

1. On the [CloudFormation](https://console.aws.amazon.com/cloudformation) console, choose the stack you used in this demo.
2. Choose **Delete** to delete the stack.

The following resources are not deleted by CloudFormation:
  - S3 bucket
  - Rekognition Custom Labels project
  - [Amazon SageMaker Ground Truth](https://aws.amazon.com/sagemaker/groundtruth/) private workforce

3. On the S3 console, choose the bucket you used for this post.
4. Choose **Empty**.
5. Choose **Delete**
6. On the Rekognition Custom Label console, choose the running model.
7. On the **Evaluate and use model** tab, expand the **API Code** section.
8. Run the [AWS Command Line Interface](http://aws.amazon.com/cli) (AWS CLI) stop model command.
9.	On the **Projects** page, select the project and choose **Delete**.
10.	To delete the private workforce, enter the following code (leave the workforce name as `default` and provide your Region):  

  `aws sagemaker delete-workforce --workforce-name default --region your-region-x`
