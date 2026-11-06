# 6. Human sampling

Low-confidence reviews only show you the detections that the model was unsure about. A confident model can still be wrong, so human sampling also sends every Nth detection to review, whatever its confidence. Comparing the reviewers' labels with the model's labels shows how accurate the model is.

## How sampling works

The detection workflow numbers every detection with a counter. When `Enable-Automatic-Human-Sampling` is `true`, every detection whose number is a multiple of `Human-Sampling-Interval` is sampled. With the default of 1,000, that's detections 1,000, 2,000, 3,000, and so on.

- A sampled detection gets a sampling review, which reviewers label in the review portal like any other task ([section 5](../5-Human-Review/)). The portal doesn't tell them whether a task is a sample.
- A sampled image isn't added to the training images, whatever the reviewer chooses.
- A detection that's both sampled and low confidence gets one low-confidence review, so its image can be added to the training images. The inference log still records it as sampled.
- The detection log records `HumanSampled` for every detection, `true` or `false`.

## Try it with a short interval

To see sampling without uploading 1,000 images, set the interval to 2, so every second detection is sampled:

```bash
aws ssm put-parameter --name "/$STACK/Human-Sampling-Interval" --value 2 --overwrite
for i in 1 2; do
  aws s3 cp sample-images/aws_logo/aws-2.jpg "s3://$BUCKET/images_for_detection/sampling-test-$i.jpg"
done
```

One of the two detections gets a sampling review. Label it in the review portal, and then set the interval back:

```bash
aws ssm put-parameter --name "/$STACK/Human-Sampling-Interval" --value 1000 --overwrite
```

## Measure the model's accuracy

Each finished review records the reviewer's answer in `HumanLabel`, and whether it matches the model's label in `HumanLabelMatchesModel`. This command lists the finished sampling reviews:

```bash
aws dynamodb scan --table-name "$LOG_TABLE" \
  --filter-expression "ReviewSource = :sampling AND ReviewStatus = :completed" \
  --expression-attribute-values '{":sampling": {"S": "HumanSampling"}, ":completed": {"S": "COMPLETED"}}' \
  --query "Items[].[S3ObjectKey.S, DetectedLabel.S, HumanLabel.S, HumanLabelMatchesModel.BOOL]" --output text
```

The share of `True` values in the last column estimates the model's accuracy. A falling share is a sign that the images you're checking have changed, and that the model needs new training images.

Next: [Cleanup](../7-Conclusions-Cleanup/)
