# 2. Settings

The workflow's settings are 11 parameters in AWS Systems Manager Parameter Store, under `/CustomLabelsModelImprovement/`. Each workflow reads the settings it needs every time it runs, so a change applies to the next run. You don't need to redeploy.

## List the settings

```bash
aws ssm get-parameters-by-path --path "/$STACK/" \
  --query "Parameters[].[Name,Value]" --output table
```

## Change a setting

```bash
aws ssm put-parameter --name "/$STACK/Minimum-F1-Score" --value 0.9 --overwrite
```

Each parameter has an allowed pattern, so Parameter Store rejects a value that isn't valid, such as a confidence above 100 or a number with a thousands separator. You can also change the settings on the [Parameter Store console](https://console.aws.amazon.com/systems-manager/parameters).

## The settings

### Training

| Setting | Default | Allowed values | What it does |
|---|---|---|---|
| `Enable-Automatic-Training` | `true` | `true` or `false` | Turns the training schedule on or off. A training run that you start yourself always trains. |
| `Automatic-Training-Poll-Frequency` | `720` | Whole minutes, 1 or more | How often the schedule starts a training check. The default is every 12 hours. |
| `Minimum-Untrained-Images` | `10` | Whole number, 1 or more | How many images must be added since the last training run before a scheduled check trains a new model. |
| `Minimum-F1-Score` | `0.8` | 0 to 1 | The lowest [F1 score](https://docs.aws.amazon.com/rekognition/latest/customlabels-dg/im-metrics-use.html) that a new model needs before it's started and replaces the running model. |
| `Minimum-Inference-Units` | `1` | Whole number, 1 or more | The number of [inference units](https://docs.aws.amazon.com/rekognition/latest/customlabels-dg/running-model.html) to start a new model with. More units handle more images per second. You're charged for each unit while the model runs. By default, a model can use at most 5 units. |

When you change `Enable-Automatic-Training` or `Automatic-Training-Poll-Frequency`, the settings workflow updates the EventBridge Scheduler schedule within a few seconds and emails you the new schedule. The schedule can start a check right after it's updated. If no new images are waiting, the check ends without training.

### Detection and human review

| Setting | Default | Allowed values | What it does |
|---|---|---|---|
| `Minimum-Label-Detection-Confidence` | `70.0` | 0 to 100 | The lowest confidence for a detection to be accepted. A detection below it is marked as low confidence in the inference log, emailed, and sent to human review when `Enable-Human-Review` is `true`. |
| `Enable-Human-Review` | `true` | `true` or `false` | Sends low-confidence detections to human review. After a reviewer labels a low-confidence image, the image is added to the training images. |
| `Enable-Automatic-Human-Sampling` | `true` | `true` or `false` | Sends every Nth detection to human review, whatever its confidence, to check the model's accuracy. Sampled images aren't added to the training images. |
| `Human-Sampling-Interval` | `1000` | Whole number, 1 or more | The N for human sampling. |
| `Human-Review-Labels` | `amazon_logo,aws_logo` | Labels separated by commas, each made of letters, digits, underscores, and hyphens | The labels that reviewers choose from. Each label is also a folder name under `images_labeled_by_folder/`. Reviewers also get a **None of the above** choice. The review page picks up a change within a minute. |
| `Human-Review-Timeout-Hours` | `72` | Hours, with up to 2 decimals | How long a review task waits for a reviewer before it expires. The shortest timeout is 1 minute. A change applies to new review tasks. |

## Run-time state

The workflows keep their run-time state in one item of the stack's DynamoDB state table, not in Parameter Store: the running model, its F1 score, the image counts of the last training runs, and the detection counter for sampling. You don't need to edit it. To see it:

```bash
aws dynamodb get-item --table-name "$STATE_TABLE" --key '{"StateId": {"S": "current"}}'
```

The first training run creates the item, so until then the command prints nothing.

## Stack updates

A stack update keeps your settings. One exception: if an update changes the schedule itself, for example after you change the sample's code, the schedule goes back to every 720 minutes and on. To fix that, set `Automatic-Training-Poll-Frequency` or `Enable-Automatic-Training` again after the update.

Next: [Model training](../3-Model-Training/)
