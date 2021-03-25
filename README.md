## Automate Continuous Model Improvement with Amazon Rekognition Custom Labels and A2I

In this sample we will build an automated and configurable continuous model improvement workflow for [Amazon Rekognition Custom Labels](https://aws.amazon.com/rekognition/custom-labels-features/) and [Amazon Augmented AI (A2I)](https://aws.amazon.com/augmented-ai/) with [AWS Step Functions](https://aws.amazon.com/step-functions/).

### Automated and Configurable Workflow
The automated workflow is depicted in the diagram below. The processes, as shown in green, are configurable by the **Model Operator** without requiring development rework.

![Automated Workflow](./assets/automated_workflow.png)

We use a set of configurable parameters in [AWS System Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html) to control the behaviors of the state machine. The seven parameters are defined below:

1. **Enable-Automatic-Training:** A toggle switch to enable or disable automated model training and deployment process.
2. **Automatic-Training-Poll-Frequency:** A schedule on how frequently the process checks for new model training.
3. **Minimum-Untrained-Images:** The minimum number of untrained images (new images added) since the last successful training.
4. **Minimum-F1-Score:** The minimum F1 Score for a trained model to be acceptable for deployment.
5. **Minimum-Inference-Units:** The minimum* *number of inference unit to deploy the trained model.
6. **Minimum-Label-Detection-Confidence:** The minimum confidence of a detection to be deemed acceptable.
7. **Enable-A2I-Workflow:** A toggle switch to enable or disable the A2I human labeling process.

### Workflow Orchestration

We use [AWS Step Functions](https://aws.amazon.com/step-functions/) to deploy a state machine as shown below for the orchestration of the workflow. The state machine is event driven and is divided into four separate processes.

![State Machine](./assets/state_machine.png)

**AWS System Manager Parameter Store**  
When the **Model Operator** updates a parameter, an [AWS Lambda](https://aws.amazon.com/lambda/) function in invoked to apply the changes to the impacted resources. For example, when the **Model Operator** updates the parameter *Enable-Automatic-Training* value to false, the Lambda function disables the automatic model training process.

**Amazon Rekognition Custom Labels Model**  
The Rekognition Custom Labels Model process is invoked by an Amazon EventBridge scheduled rule on a polling schedule set by the **Model Operator** as a parameter. The state machine first evaluates whether new model training criteria, set by the **Model Operator** as a parameter, has been met before initiating training. Once the training is complete, the state machine evaluates the **F1 Score** of the new model against the acceptance criteria, set by **Model Operator** as a parameter, for model deployment. If the **F1 Score** meets the the acceptance criteria, the state machine initiates a Blue-Green deployment process. The Blue-Green deployment process includes, starting the new model, update the the new model inference endpoint, and stopping the previous running model.

**Amazon Rekognition Custom Labels Detection**  
The Rekognition Custom Labels Detection process is invoked by an [Amazon Simple Storage Service (Amazon S3)](https://aws.amazon.com/s3/) PutObject event. When the **Model Consumer** uploads images to  S3, a PutObject event invokes a Lambda function to redirect the required action to the state machine. The state machine invokes another Lambda function to perform the custom labels detection. Next the state machine evaluates the inference **Confidence** against the confidence level set by the the **Model Operator** as a parameter. The state machine initiates an A2I Human review workflow if the inference **Confidence** is below the criteria, provided that the **A2I Workflow** is enabled, set by the **Model Operator** as a parameter.

**Amazon A2I Human Loop Data**  
The A2I Human Loop Data process is invoked by a S3 PutObject event. Once an A2I Human review workflow is complete, the output is stored in S3 by A2I system by default. A S3 PutObject event invokes a Lambda function to redirect the required action to the state machine. The state machine invokes another Lambda function to evaluate the human loop response and place a copy of the initial image into a S3 folder corresponding to the evaluated label. This is the processes where new human labeled images are added to the training dataset.

### Architecture
The architecture, as shown below, is build on **AWS** serverless technologies.  

![Architecture](./assets/architecture.png)  

**AWS Step Functions**  
AWS Step Functions is a serverless function orchestrator that makes it easy to sequence Lambda functions and multiple AWS services into business-critical applications. We use Step Functions to deploy the state machine. The state machine initiates different processes based on the events received from the [Amazon EventBridge](https://aws.amazon.com/eventbridge/). In addition, the state machine uses internal process such as **Wait** to wait for model training and deployment to complete or **Choice** to evaluate for next task.

**AWS System Manager Parameter Store**  
AWS Systems Manager Parameter Store provides secure, hierarchical storage for configuration data management and secrets management. We use the Parameter Store in two different ways. One we provide a set of single-value parameters for the **Model Operator** to use to control the workflow. Two we provide a JSON-based parameter for the system to use to store environmental variables and operational data.

**Amazon Rekognition**  
Amazon Rekognition makes it easy to add image and video analysis to your applications using proven, highly scalable, deep learning technology that requires no machine learning expertise to use. We use Rekognition Custom Labels as the core machine learning service. A Recognition Custom Labels project is created as part the initial [AWS CloudFormation](https://aws.amazon.com/cloudformation/) deployment process. Creating, starting, and stopping project versions are performed automatically as orchestrated by the state machine backed by Lambda.

**Amazon Augmented AI (A2I)**  
Amazon A2I is a machine learning service which makes it easy to build the workflows required for human review. We use A2I to provide a human labeling workflow to label images. An A2I Human Flow Definition are created as part of the initial CloudFormation deployment process. An A2I human labeling task is generated per image by Lambda as part of the Rekognition Custom Labels detection process.

**AWS Lambda**  
AWS Lambda is a serverless compute service that lets you run code without provisioning or managing servers, creating workload-aware cluster scaling logic, maintaining event integrations, or managing runtimes. We use three different sets of Lambda functions. The first set consists of two Lambda functions that builds the Rekognition Custom Labels project and A2I Human Flow Definition. These two Lambda functions are only used initially as part of the CloudFormation deployment process. The second set of Lambda functions that are invoked by the state machine to execute Rekognition & A2I APIs, create manifest file for training, collect labeled images for training, and manage system resources. The last set is a single Lambda function to redirect S3 PutObject events to the state machine.

**Amazon Simple Storage Service (Amazon S3)**  
Amazon Amazon S3 is an object storage service that offers industry-leading scalability, data availability, security, and performance. We use a S3 bucket to store the assets generated in this workflow. We create the S3 bucket and a set of folders as part of the CloudFormation deployment process. Each folder has a dedicated purpose. For example, labeled images for training are stored in the folder *images_labeled_by_folder*.

**Amazon EventBridge**  
Amazon EventBridge is a serverless event bus service that makes it easy to connect your applications with data from a variety of sources. We use two EventBridge rules to initiate the state machine. The first rule is based on Systems Manager (SSM) event pattern. The SSM rule is triggered by changes to the Parameter Store and initiates the state machine to invoke a Lambda function to apply changes to the impacted resources. The second rule is based a scheduled rule. The scheduled rule is triggered periodically and invokes the state machine to invoke a Lambda function to check for new model training.

**Amazon Simple Notification Service (Amazon SNS)**  
[Amazon SNS](https://aws.amazon.com/sns/?whats-new-cards.sort-by=item.additionalFields.postDateTime&whats-new-cards.sort-order=desc) is a fully managed messaging service for both application-to-application (A2A) and application-to-person (A2P) communication. We use SNS as a communication mechanism to alert the **Model Operator** and **Model Consumer** of relevant model training and detection events. All SNS messages are published by the corresponding Lambda functions.

**Amazon SageMaker Ground Truth**  
[Amazon SageMaker Ground Truth](https://aws.amazon.com/sagemaker/groundtruth/) is a fully managed [data labeling](https://aws.amazon.com/sagemaker/groundtruth/what-is-data-labeling/) service that makes it easy to build highly accurate training datasets for machine learning. We optionally deploy a Ground Truth Private Workforce and Team, if none existed, as part of initial CloudFormation deployment process. The A2I Human Flow Definition has a dependency on the Ground Truth Private Team to function.

**Amazon Cognito**  
[Amazon Cognito](https://aws.amazon.com/cognito/) lets you add user sign-up, sign-in, and access control to your web and mobile apps quickly and easily. We optionally deploy a Cognito User Pool and an App Client, if none existed, as part of initial CloudFormation deployment process. The Ground Truth Private Workforce has a dependency on the Cognito User Pool and an App Client to function.


Next Step: [0-Prequisites](./0-Prequisites/)
