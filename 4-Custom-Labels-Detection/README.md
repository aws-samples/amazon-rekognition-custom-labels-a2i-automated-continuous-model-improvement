## 4-Custom-Labels-Dection

**Amazon Rekognition Custom Label Detection**  
In this section we will walk through the steps on how to invoke Rekognition detection and to trigger the A2I Human Loop process.

1. Go to the [S3](https://s3.console.aws.amazon.com/s3/home) bucket and select the "images_for_detection/" folder.
2. Upload an image that you used previous for training to trigger a Rekognition Custom Labels detection event. You should receive an email with the detection results indicating a **Confidence** of at least 70.0 as expected.
3. Upload an image from the "inference_images" folder. You should receive an email with the detection results indicating a **Confidence** of less than 70.0 as expected and another email indicating that an A2I Human Loop has been initiated.
4. Upload the entire "inference_images" folder to the S3 "images_for_detection/" folder to stage A2I tasks for the next section.
5. (Optional) Go to [AWS Step Functions](https://console.aws.amazon.com/states/) to review the state machine executions.

Next Step: [5-A2I-Human-Loop](../5-A2I-Human-Loop/)
