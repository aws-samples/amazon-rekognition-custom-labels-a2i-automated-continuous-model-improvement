## 5 Complete a human labeling task

In the last section, we staged some human labeling tasks. In this section, we walk you through the steps to complete a human labeling task and explain how the human labeling results are processed for new model training.

1.	On the [Amazon S3](https://s3.console.aws.amazon.com/s3/home) console, navigate to the `images_labeled_by_folder` folder.
2.	Make a note of the names of the folders and the total number of images.

At this stage, you should have two folders and a total of 10 images.

3. Navigate to the [Amazon A2I](https://console.aws.amazon.com/a2i) console. If you are redirected to a different region, select the correct region.

4. Choose **Human review workflows** and review the list of **Human loops**.

These loops were generated from the previous section where each time an [Amazon Rekognition Custom Labels](https://aws.amazon.com/rekognition/custom-labels-features/) detection **Confidence** level is less the minimum acceptable value.

5.	On the [Amazon SageMaker Ground Truth](https://console.aws.amazon.com/sagemaker/groundtruth#/labeling-workforces).

If you’re redirected to a different Region, switch to the correct Region.

6.	On the **Private tab**, choose the URL under **Labeling portal sign-in URL**.

This opens the Amazon A2I web portal for the human labeling task.

7.	Sign in to the web interface with your username and password.

If the private team was deployed for you, the username and temporary password are in the email that was sent. If you created your own private team, you should have the information already.

8.	Choose **Start working** to begin the process.
9.	For each image, review the image and choose the correct Amazon company logo or **None of the Above** to use as label.
10.	Keep a tally of the options you choose in each task.
11. Choose **Submit** to advance to the next image until you have completed all the labeling tasks.
12. Return to the i`mages_labeled_by_folder` folder and review the changes.

For each image you labeled, an [AWS Lambda](http://aws.amazon.com/lambda) function makes a copy of the original image, appends the prefix `humanLoopName` and an UUID to the original S3 object key, and adds it to the corresponding labeled folder. If the folder doesn’t exist, the Lambda function creates a corresponding labeled folder. For the `None of the Above` labels, nothing is done. This is how newly captured and labeled images are added to the training dataset.

Next Step: [6-Conclusions-Cleanup](../6-Conclusions-Cleanup/)
