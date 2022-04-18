## 4 Use your model for logo detection

In this section, we walk you through the steps to detect custom logos and explain how [Amazon Augmented AI](https://aws.amazon.com/augmented-ai/) (Amazon A2I) human labeling task is created.

1.	Navigate to the [Amazon S3](https://s3.console.aws.amazon.com/s3/home) bucket and choose the `images_for_detection` folder.
2.	Upload an image that you used previously for training.

The upload process triggers an S3 `PutObject` event, which invokes an [AWS Lambda](https://aws.amazon.com/lambda) function to run the [Amazon Rekognition Custom Labels](https://aws.amazon.com/rekognition/custom-labels-features/) detection process. Upon successful completion of the detection event, the Lambda function performs additional tasks:
- Log the image detection results to [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) table
- Create an Amazon A2I human labeling task if the detection confidence level is less then the minimum confidence level and A2I workflow is enabled
- Log the Amazon A2I request information to the DynamoDB table

You should receive an email with a detection result indicating a confidence score of at least 70, which is as expected because you’re using the same image you used for training.

3.	Upload all the images in the `inference_images` folder.

You should receive emails with detection results with varying confidence scores, and some should indicate that Amazon A2I human loops have been created. When a detection result has a confidence score less than the acceptance level, which is currently set at 70, a human labeling task is created to label that image.

4.	Optionally, go to the [AWS Step Functions](https://console.aws.amazon.com/states/) console to review the state machine runs of the custom label detection events.

5.	Optionally, go to the [Amazon DynamoDB](https://console.aws.amazon.com/dynamodb/) console to review the custom label detection and A2I event logs.


Next Step: [5-A2I-Human-Loop](../5-A2I-Human-Loop/)
