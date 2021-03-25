## 5-A2I-Human-Loop

**Amazon A2I Human Loop**  
In this section we will walk through the steps on how to complete an A2I labeling task and explain how the human labeling results are processed for future training.

1. Go to the [S3](https://s3.console.aws.amazon.com/s3/home) bucket and select the folder "images_labeled_by_folder/". Make a note of the names of the folders and total number of images. At this stage you should have 2 folders and a total of 10 images.
2. Go to [Amazon A2I Human review workflows](https://console.aws.amazon.com/a2i). If you are redirected to a different region, select the correct region.
3. Select **Human review workflows** and review the list of **Human loops**. These loops were generated from the previous section where each time a Rekognition Custom Labels detection confidence level is less the minimum acceptable value.
4. Go to [Amazon SageMaker Ground Truth Labeling workforce](https://console.aws.amazon.com/sagemaker/groundtruth#/labeling-workforces). If you are redirected to a different region, select the correct region.
5. Select the **Private** tab. In **Private workforce summary** click the URL for **Labeling portal sign-in URL**. This opens the A2I web interface for human labeling task. The web interface is part of the A2I system features. However, the actual template was created as part of this demo relevant to this demo use case.
6. **Sign in** to the web interface with your **Username** and **Password**. Check your email if we have them for you. You maybe prompted to change your password if this is the first time that you sign in.
7. Click **Start working** to begin the process.
8. Review the image and select the correct Logos or "None of the Above". Keep a tally of the option you select in each task.
9. Click **Submit** to advance to the next image until you have completed all the labeling tasks.
10. Go to the [S3](https://s3.console.aws.amazon.com/s3/home) bucket and select the folder "images_labeled_by_folder/" and review the changes. For "None of the Above" option, nothing is done. For each of logos selected, a Lambda function makes a copy of the original image, append a prefix "humanLoopName" and an UUID to the original S3 object key, and add it the corresponding logo folder.

Next Step: [6-Conclusions-Cleanup](../6-Conclusions-Cleanup/)
