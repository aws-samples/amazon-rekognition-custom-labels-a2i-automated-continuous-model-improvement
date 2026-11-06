# 7. Conclusions and cleanup

You trained a Rekognition Custom Labels model from labeled S3 folders, ran detection on new images, labeled the images that the model was unsure about, and sampled detections to check the model's accuracy. Reviewed images flow back into the training folders, and the training workflow trains, checks, and replaces the model when enough new images arrive.

## Stop the model to save costs

A running model costs $4 an hour for each inference unit, even when it isn't checking images. If you keep the stack, stop the model when you don't need it:

```bash
MODEL_ARN=$(aws dynamodb get-item --table-name "$STATE_TABLE" --key '{"StateId": {"S": "current"}}' \
  --query "Item.RunningModelArn.S" --output text)
aws rekognition stop-project-version --project-version-arn "$MODEL_ARN"
```

While the model is stopped, detection fails and emails you for each new image. To start the model again, which takes about 6 minutes:

```bash
aws rekognition start-project-version --project-version-arn "$MODEL_ARN" --min-inference-units 1
```

## Delete the stack

1. Set the variables from [section 1](../1-Deployment/README.md#set-the-variables-for-the-next-sections), if they aren't set. They come from the stack's outputs, so set them before you delete the stack. The later steps need them.
2. Delete the stack from the repository folder, with the virtual environment active. Enter `y` to confirm.

   ```bash
   npx cdk destroy
   ```

   If you deployed with another stack name, add `-c stackName=AnotherName`. Before the stack's resources are deleted, the cleanup workflow stops the project's running models. Deleting the stack takes 5 to 15 minutes, mostly for the CloudFront distribution.

The stack deletes its workflows, the state table, the settings, the log groups, the review portal, and the Cognito user pool with its users. It keeps your data, so that you don't lose images, results, or models by accident:

- The S3 bucket, with the training images, the detection images, the manifests, and the evaluation results
- The inference log table, with every detection and review
- The Custom Labels project and its models, all stopped

## Delete the kept resources

These commands delete your data, and you can't undo them.

1. Delete the project's models and datasets, and then the project. Deleting each model takes a moment, and the project can be deleted only after they're gone.

   ```bash
   PROJECT_NAME=$(echo "$PROJECT_ARN" | cut -d/ -f2)
   for model in $(aws rekognition describe-project-versions --project-arn "$PROJECT_ARN" \
       --query "ProjectVersionDescriptions[].ProjectVersionArn" --output text); do
     aws rekognition delete-project-version --project-version-arn "$model"
   done
   for dataset in $(aws rekognition describe-projects --project-names "$PROJECT_NAME" \
       --query "ProjectDescriptions[0].Datasets[].DatasetArn" --output text); do
     aws rekognition delete-dataset --dataset-arn "$dataset"
   done
   sleep 60
   aws rekognition delete-project --project-arn "$PROJECT_ARN"
   ```

   If `delete-project` reports that the project still has models or datasets, wait a minute and run it again.

2. Delete the inference log table:

   ```bash
   aws dynamodb delete-table --table-name "$LOG_TABLE"
   ```

3. Delete the bucket and everything in it:

   ```bash
   aws s3 rb "s3://$BUCKET" --force
   ```

The `CDKToolkit` stack from bootstrapping stays in the account. Other CDK apps in the same account and Region use it, so keep it unless you know that nothing else needs it.

## Next steps

To take this further:

- Add AWS WAF to the CloudFront distribution and the Cognito user pool.
- Add Amazon CloudWatch alarms for failed workflow runs, in addition to the emails.
- Let reviewers label objects with bounding boxes, or have more than one reviewer label each image.
- Keep the Cognito user pool when the stack is deleted, if your reviewer accounts need to outlive the stack.

Back to the [overview](../README.md).
