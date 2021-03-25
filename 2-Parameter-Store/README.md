## 2-Parameter-Store

**AWS System Manager Parameter Store**  
We provide a set of configurable parameters for the **Model Operator** to use to control the MLOps process. Go to [AWS Systems Manager Parameter Store](https://console.aws.amazon.com/systems-manager/parameters). You should see list of parameters similar the ones below.

**Note:** The parameter store uses string to store value regardless of type. Do NOT use comma separator for numeric values.

- **Automatic-Training-Poll-Frequency**  
This is the polling frequency (in integer minutes) on how often the Amazon EventBridge Scheduled Rule is triggered to initiate the check for automatic model training. As you update this value, the value is applied to the rule by a Lambda function.
- **Enable-A2I-Workflow**
This value (true/false) determines whether an A2I Human Loop is created regardless of the confidence level from the custom label detection result.
- **Enable-Automatic-Training**
This value (true/false) determines whether automatic model training is enabled/disabled. When this value is updated to true, a Lambda function enables the EventBride Scheduled Rule. When the value is updated to false, a Lambda function disables the EventBride Scheduled Rule.
- **For-System-Use-Only**
Do NOT modify this value. This is a reserved parameter consisting of environmental variables and operation data. The value is used and updated by Lambda functions.
- **Minimum-Label-Detection-Confidence**
Rekognition Custom Labels returns a Confidence between 0-100 on each detection. The Minimum Confidence (Float 0.00-100.00) determines whether a detection result is acceptable. If the detection Confidence is greater than or equal to the Minimum Confidence, then the detection is accepted. If not, the image is sent to A2I process, provided that Enable-A2I-Workflow is enabled.
- **Minimum-F1-Score**
This value is the minimum F1 Score (Float 0.00-1.00) that evaluate a newly trained model with a status of TRAINING-COMPLETE to accept for deployment. If the F1 Score is greater or equal to the minimum F1 Score, the model will be deployed. If not, the model is marked as failed training.
- **Minimum-Inference-Units**
This value (Int), with a minimum of 1, inference unit to use for the running Rekognition Customs Label model. A single inference unit represents 1 hour of processing and can support up to 5 Transaction Pers Second (TPS). Use a higher number to increase the TPS throughput of your model. You are charged for the number of inference units that you use.
- **Minimum-Untrained-Images**
The value (Int) represents the minimum number of untrained or newly added images that will qualify the state machine to start a new model training process on the scheduled polled event. At the instance the polled event is triggered, a Lambda function first determines the total number of training images in the designated S3 folder. Next it retrieves the value "previous_trained_images" from the parameter "For-System-Use-Only". If the difference between the total number of images in S3 and the previous_trained_images is greater than or equal to minimum untrained images, then it will trigger a new model training. On a successful training, a Lambda updates the previous_trained_images with the current total number of images trained.

Next Step: [3-Model-Training](../3-Model-Training/)
