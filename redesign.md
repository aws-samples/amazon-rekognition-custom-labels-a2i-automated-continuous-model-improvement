# Redesign tracker

This file tracks the work to bring the sample up to date. The work started with a currency review on November 4, 2026. The repository was last changed in `db61b19` on July 20, 2022, and the line numbers in this file refer to that commit.

## Status

| Workstream | Status |
|---|---|
| Currency review | Done, November 4, 2026 |
| D1: How to handle A2I | Decided November 4, 2026: option B, replace A2I and Ground Truth |
| D2: Deployment tooling | Decided November 4, 2026: AWS CDK in Python, deployed from the reader's computer. AWS CloudShell isn't supported. |
| D3: Review providers | Decided November 4, 2026: custom review portal only. A2I and Ground Truth are dropped completely. |
| D4: Step Functions only | Decided November 4, 2026: workflows use direct service integrations, and the review portal API is the only Lambda function the sample owns |
| D5: State machine layout | Decided November 4, 2026: one state machine per job |
| D6: Human sampling | Decided November 4, 2026: a counter picks every Nth detection as it's logged |
| D7: Training data | Decided November 4, 2026: rebuild the Custom Labels datasets from the S3 folders before each training run |
| D8: Run-time state | Decided November 4, 2026: fixed values go into the state machine definitions, and changing values go into a DynamoDB state item (O10) |
| D9: Failed training runs | Decided November 4, 2026: the next automatic run waits for new images |
| D10: Email notifications | Decided November 4, 2026: milestones and problems only |
| D11: Automated tests | Decided November 4, 2026: none. Each phase is tested by deploying it. |
| Human review design | Approved November 4, 2026 |
| Trial T1 | Done November 4, 2026. All seven checks passed, and the trial resources are deleted. |
| Build (H0 to H4) | H0 done November 4, 2026. H1 in progress on the local `v2-h1` branch. H2 to H4 not started. |
| Optional modernization | O1 and O4 adopted for H1, November 4, 2026. The other open items aren't decided. |

## Why the sample needs a redesign

- Amazon A2I and Amazon SageMaker Ground Truth are in maintenance, not shut down. New customers can't use them from July 30, 2026. Existing customers can keep using them, and AWS keeps operating and supporting them but plans no new features. As of the September 29, 2026 availability update, AWS hasn't announced an end-of-support date for either.
- During stack creation, the template creates A2I resources and, with the default parameters, a Ground Truth work team. In an account that doesn't already use A2I, the stack will probably fail to deploy. This conclusion comes from the announcements and hasn't been tested.
- Amazon Mechanical Turk closed on September 30, 2026. The README still offers it as a workforce option.
- Rekognition Custom Labels has no announced availability change. It's offered in the same 11 Regions, and the APIs the sample calls haven't changed.
- All 11 Lambda functions use `python3.9`, which is deprecated.
- The docs have outdated service names, links, console steps, and screenshots. They also contradict each other in places.

## Decisions

### D1: How to handle the A2I dependency

Status: decided November 4, 2026.

Decision: option B, replace A2I and Ground Truth. The workflow needs a human in the loop to stay automated, and new customers can't use A2I or Ground Truth.

| Option | Changes | Effort | Who can run it afterward |
|---|---|---|---|
| A. Keep A2I, make it optional | Add a template condition so the stack deploys without A2I, Ground Truth, and Cognito. Add a notice to the README and 0-Prerequisites. | Small to medium | Anyone can run training and detection. Human review works only in accounts that already use A2I. |
| **B. Replace A2I and Ground Truth (chosen)** | Build a review step that the sample owns. See [Human review design](#human-review-design). | Large | Anyone |
| C. Archive | Add a deprecation notice that links to the AWS maintenance announcement. | Minimal | No new users |

### D2: Deployment tooling

Status: decided November 4, 2026.

Decision: P4, AWS CDK in Python. The redesign adds a web page, Cognito, an HTTP API, and more state machines, and a hand-written template gets hard to maintain at that size. CDK keeps the code, the page, and the state machine definitions in normal files, builds least-privilege IAM permissions from grants, and fixes several baseline defects by construction. Python matches the Lambda code.

| Option | For users | For maintainers |
|---|---|---|
| P1. Inline code only. Delete `lambda/` and `assets/task_ui.html`. | One template, deployed from the console | The code lives in YAML, with no linting or tests. |
| P2. Source files in `lambda/` and `ui/`, embedded into the one template by a small build script | One template, deployed from the console | Real files that can be linted and tested. Run the script after each edit. |
| P3. AWS SAM | Users need the SAM CLI (`sam build`, `sam deploy`). | Standard project layout that stays close to CloudFormation |
| **P4. AWS CDK in Python (chosen)** | Users run a few commands on their own computer, which needs Python, Node.js, the AWS CLI, and Git. AWS CloudShell isn't supported (see below). Each account and Region needs a one-time `cdk bootstrap`. | The code and the review page are normal files. IAM permissions come from grants, and resource names are generated. |

What changes with CDK:

- CDK still deploys through CloudFormation, so stacks, stack events, and deletion policies work as they do today.
- The console-only deployment goes away. A one-click template would need public asset buckets in every Region, which doesn't fit an aws-samples repository.
- CDK requires Node.js 22 or later, even for Python projects.
- AWS CloudShell isn't supported (decided November 4, 2026). Its `python3` is 3.9, which Amazon Linux 2023 keeps for its whole life, and `aws-cdk-lib` 2.275.0 needs Python 3.10 or later. Python 3.10 reached end of life in October 2026, so the docs should ask for Python 3.11 or later.
- `cdk bootstrap` creates a `CDKToolkit` stack with an S3 bucket, an ECR repository, and IAM roles. Some organizations restrict or customize bootstrapping.
- Several baseline items get fixed by construction: generated names (F7), the partition and least-privilege grants (O8), S3 notification permissions and ordering (F6), and custom resource responses (F5).
- The `aws-cdk-lib` and CDK CLI versions need periodic updates.

### D3: Review providers

Status: decided November 4, 2026.

Decision: custom review portal only. A2I and Ground Truth are removed completely, and there's no A2I adapter. The reasons:

- Most readers can't use A2I or Ground Truth. New customers are blocked, and AWS hasn't said how it decides who counts as an existing customer, so even a new account at a company that uses A2I might not qualify.
- Neither service gets new features. Mechanical Turk was on the same June 30 maintenance list and closed on September 30, 2026, three months later.
- A second review path would double the review code, docs, and testing, and the A2I path could only be tested in an account that already uses A2I.
- A2I charges for each reviewed object, even when your own employees do the reviews. The portal has no per-review charge.

What the sample gives up: AWS's managed reviewer portal, vendor workforces from AWS Marketplace, and more than one reviewer per task. The sample used only the managed portal, and it now owns its portal code and that code's security.

Readers who need the A2I version can use the `v1-a2i` tag (H0), which the new README links to (H4).

### D4: Step Functions only

Status: decided November 4, 2026.

Decision: the workflows call AWS services directly through Step Functions service integrations instead of through Lambda functions. The only Lambda function the sample owns is the review portal API. If a step can't be written cleanly as states, it gets a small function instead of a workaround.

Why:

- Step Functions AWS SDK integrations can call almost any AWS API. They cover every operation the sample uses in Rekognition, S3, DynamoDB, Systems Manager, EventBridge, and Step Functions. The only S3 operation listed as unsupported, `SelectObjectContent`, isn't used.
- JSONata and variables handle the data shaping that the Python code does today: string building, arithmetic, dates, filtering, and parsing JSON strings.
- The workflow logic has no runtime to upgrade. Runtime deprecation is what made the current sample stale.
- Every step's input and output shows in the Step Functions console, and retries need no code.

| Current function | Replacement |
|---|---|
| `s3-event-trigger` | S3 EventBridge notifications, plus a rule with a key-prefix filter that starts the detection state machine |
| `rekognition-detect-label` | `rekognition:detectCustomLabels`, a Choice state, `dynamodb:putItem`, and `sns:publish` |
| `check-auto-training` | An `s3:listObjectsV2` loop that counts the images, `rekognition:describeProjectVersions`, and a Choice state |
| `create-training-manifest` | A Distributed Map that writes JSON Lines with `ResultWriter` (D7) |
| `train-deploy-model` | `rekognition:createProjectVersion`, wait loops on `describeProjectVersions`, `startProjectVersion`, and a Map with `stopProjectVersion` |
| `update-event-rules` | `ssm:getParameter`, a Choice state, and `eventbridge:putRule`, `enableRule`, or `disableRule` |
| `create_human_sampling` | A DynamoDB counter in the detection state machine (D6) |
| `a2i_create_humanloop` and `a2i-human-loop` | The review state machine |
| `stage-rekognition-assets` | CDK resources: `CfnProject`, a bucket with EventBridge turned on, CDK's built-in custom resource for the folder placeholders, and the cleanup workflow |
| `stage-a2i-assets` | Removed with A2I |

What still needs Lambda:

- The review portal API. Presigned image URLs have to be generated by code. HTTP APIs can start, start synchronously, and stop executions, but they can't call `SendTaskSuccess`.
- Stopping running models when the stack is deleted. CloudFormation custom resources can't target a state machine. CDK's built-in custom resource function starts a short Express cleanup workflow, so the sample doesn't own that code. The project and trained models are retained, like the bucket and the table, and section 7 explains how to delete them.

Costs accepted:

- The logic lives in JSONata expressions inside the definitions. The manifest build is the densest part.
- Each state's input and output is limited to 256 KiB. S3 listings are paged small or handled by a Distributed Map.
- Step Functions Local is unsupported, so the state machines can't run offline. The sample has no automated tests (D11), and changes are tested by deploying them.
- Step Functions can't generate IAM policies for SDK integrations, so each call needs an explicit permission.

### D5: State machine layout

Status: decided November 4, 2026.

Decision: one Standard state machine per job: detection, training, settings, and review. The Express cleanup workflow from D4 is separate. Each EventBridge rule or schedule targets its own state machine.

Why:

- Small definitions are easier to read now that the logic lives in them.
- It removes the routing Choice state and its matching on `$.resources[0]` ARN patterns, which also hardcode the `aws` partition.
- Each state machine gets its own IAM role.
- Standard keeps every execution visible in the console for the walkthrough. At sample scale, the cost difference from Express doesn't matter. At high volume, detection could move to Express, which is cheaper but is at-least-once and keeps its history in CloudWatch Logs.

### D6: Human sampling

Status: decided November 4, 2026.

Decision: the detection state machine increments a counter in DynamoDB (`UpdateItem` with `ADD` on `DetectionCount` in the D8 state item) for each detection and sends every Nth detection (`Human-Sampling-Interval`) to review right away.

Why:

- It picks exactly every Nth detection.
- There's no sampling schedule and no query loop over a date index, so the pagination and date-format problems (F2) go away.
- It removes the `Automatic-Human-Sampling-Frequency` parameter, the sampling schedule rule, and the `Sampled_GSI` index. `Enable-Automatic-Human-Sampling` and `Human-Sampling-Interval` stay.

Notes:

- This changes documented behavior. Sampling happens as detections arrive instead of on a schedule, and H4 rewrites section 6.
- If a sampled detection is already in a low-confidence review, the review execution name (the detection request ID) prevents a second review.
- One counter item is fine at sample scale. A very high detection rate would make it a hot key.

### D7: Training data

Status: decided November 4, 2026.

Decision: the training state machine rebuilds the project's datasets from the S3 folders at the start of each run:

1. Build the manifest from `images_labeled_by_folder/` with a Distributed Map.
2. Delete the old training and test datasets.
3. Create the training dataset from the manifest (`CreateDataset`).
4. Create an empty test dataset, then move 20% of the images into it (`DistributeDatasetEntries`).
5. Train the model (`CreateProjectVersion`), which uses the project's datasets.

The dataset steps finish in the background, so the state machine waits until each one is complete before moving on.

Why:

- It keeps the designed behavior. The S3 folders stay the source of truth, every run trains on the existing images plus the newly added ones, and the 80/20 split is redrawn each run. Deleting a file, or moving it to another label folder, changes the next model, as it does today.
- The project uses datasets, which AWS recommends, so opening it in the Custom Labels console no longer breaks training (R2).

Rejected alternative: add new images to long-lived datasets with `UpdateDatasetEntries`. That API can add or update entries but not delete them, so deletes and moves in S3 wouldn't carry over. The test split would also have been fixed instead of redrawn each run.

Constraints the workflow has to respect:

- Through the API, training needs both a training dataset and a test dataset. Only the console splits a dataset automatically.
- The test dataset can't share images with the training dataset, and it has to contain at least half of the training labels.
- A dataset can't be deleted while it's being created or updated.
- Edits made to the datasets in the console are replaced on the next run, and the docs have to say so.

### D8: Run-time state

Status: decided November 4, 2026. This was O10.

Decision: replace the `For-System-Use-Only` parameter. CDK writes the fixed values into the state machine definitions at deploy time, the keys the redesign no longer needs are dropped, and the values that change at run time move to one item in a small DynamoDB state table.

| Current key | New home |
|---|---|
| `s3_bucket`, `rekognition_project_arn`, `sns-topic`, `dynamodb_table`, `events_scheduled_rule` | Written into the state machines that use them at deploy time |
| `sampling_scheduled_rule`, `dynamodb_table_GSI` | Removed (D6) |
| `state_machine_arn` | Removed (D4, D5) |
| `a2i_workflow`, `flow_definition_arn` | Removed (D3). No code reads `a2i_workflow` today. |
| `rekognition_project_version_arn` | `RunningModelArn` in the state item |
| `previous_trained_images` | `TrainedImageCount` in the state item |
| (new) | `LastRunImageCount` in the state item, the image count of the most recent training run, whether or not it succeeded (D9) |
| (new) | `DetectionCount` in the state item, the D6 sampling counter |

The state item, shown as plain JSON:

```json
{
  "StateId": "current",
  "RunningModelArn": "arn:aws:rekognition:us-east-1:111122223333:project/logo-project/version/20261104120000/1730721600000",
  "TrainedImageCount": 20,
  "LastRunImageCount": 20,
  "DetectionCount": 1532
}
```

Why:

- Today the stack owns the parameter, but the functions overwrite it, so CloudFormation reports drift. A stack update that changes the parameter's value in the template resets it, which drops the running model's ARN (detection then fails) and sets the trained image count back to 0 (the next check starts an unneeded training run).
- The training function writes back the whole JSON it read when its run started, often an hour earlier, so changes made in between are lost.
- Almost every function starts by reading and parsing the parameter to learn names that were fixed at deploy time.
- Operators see a parameter they mustn't touch, and section 2 has to warn them about it.

Notes:

- Each write changes only its own attribute, so training can't overwrite the counter, and detection can't overwrite training's values.
- The stack owns the table but not the item, so the values don't drift and stack updates don't reset them.
- If the item doesn't exist yet, the state machines treat it as no model running and zero trained images.
- Dataset ARNs aren't stored. D7 recreates the datasets every run, so the training state machine looks them up from the project.
- The state table is separate from the inference log, so the log stays clean for analytics and each state machine's permissions stay narrow.
- The operator settings stay in Parameter Store. H4 removes `For-System-Use-Only` from section 2.

### D9: Failed training runs

Status: decided November 4, 2026.

Decision: after a failed training run, the next automatic run waits until `Minimum-Untrained-Images` more images have been added. A run fails when the model's F1 score is below `Minimum-F1-Score`, or when dataset creation, training, or model start fails. An operator can still start a run by hand.

How it works: when the training state machine decides to train, it saves the image count in the state item as `LastRunImageCount` (D8). Scheduled checks count new images against that value. `TrainedImageCount` still records the images behind the running model.

Rejected:
- Retry at every scheduled check, which is today's behavior. The same images are retrained every 12 hours until a run passes, and each retry costs training time.
- Turn off automatic training after a failure, until an operator turns it back on.

### D10: Email notifications

Status: decided November 4, 2026.

Decision: email only milestones and problems:
- Training started, with the image counts and the model version name
- Training finished, with the F1 score
- New model running, and which models were stopped
- Low-confidence detections
- Settings applied to the training schedule
- Any workflow failure, with the error and a link to the run

A training run that ends below `Minimum-F1-Score` is reported as a workflow failure, with the F1 score in the email.

Today the stack sends email for every detection, every scheduled check (even when nothing happens), every 5-minute status poll during training and model start, every new manifest, and every settings change.

Rejected: keeping every email as today, and failures only.

Note: section 4's walkthrough shows passing detections in the inference log and the Step Functions console instead of email (H4).

### D11: Automated tests

Status: decided November 4, 2026.

Decision: the repository has no automated tests. Each phase is tested by deploying it to the test account and running the walkthrough.

Rejected: template tests (pytest checks on the template CDK generates), and template tests plus workflow tests with the Step Functions TestState API and mocked AWS responses.

## Human review design

Status: approved November 4, 2026.

The sample keeps Step Functions as the orchestrator. The two SageMaker features are replaced by parts that the stack deploys itself:

- A2I human loops become executions of a new review state machine. Each execution writes a review task and a Step Functions task token to DynamoDB, then waits for the token (`.waitForTaskToken`).
- The Ground Truth private workforce and worker portal become a Cognito user pool and a small review portal. The portal's page is one HTML file in a private S3 bucket, served through CloudFront. CloudFront forwards `/api/*` requests to an API Gateway HTTP API with a Cognito JWT authorizer, and one Lambda function handles those API calls.

All of the new parts are serverless and billed per use, except optional AWS WAF, which has a monthly charge when it's turned on. None of them depend on SageMaker. The running Custom Labels model is still the main cost.

### What replaces what

| A2I or Ground Truth | Replacement |
|---|---|
| Private workforce and work team | A Cognito user pool with a `reviewers` group. The stack always creates the pool, and the one-workforce-per-Region limit no longer applies. |
| Worker portal (`*.labeling.<region>.sagemaker.aws`) | A review portal at the CloudFront distribution's URL, published as the stack output `ReviewPortalUrl`. Reviewers sign in on Cognito's hosted sign-in pages (managed login). |
| Human task UI (the `crowd-image-classifier` template) | One HTML page, served from S3 through CloudFront, that shows the image and a choice of labels. The labels come from an SSM parameter. |
| Flow definition | The review state machine, plus SSM parameters for the labels and the timeout |
| `StartHumanLoop` | `StartExecution` on the review state machine. The execution name is the detection request ID, which stops a detection from being reviewed twice. |
| Human loop output in S3, read by a Lambda function on an S3 event | The portal calls `SendTaskSuccess`, which resumes the waiting execution, and the execution applies the label. |
| Task availability lifetime | A timeout on the waiting state. Tasks that time out are marked `EXPIRED`. |
| Worker ID in the output | The reviewer's Cognito user ID and username, recorded with the label |

### How a review works

Two paths start a review. One is a detection whose confidence is below `Minimum-Label-Detection-Confidence` while human review is enabled. The other is human sampling, which picks every Nth detection (D6). Both start the review state machine with the same input, and a `source` field records which path it was (`LowConfidence` or `HumanSampling`).

```mermaid
sequenceDiagram
    autonumber
    participant M as Detection state machine
    participant RV as Review state machine
    participant D as DynamoDB
    participant A as Review API
    participant CF as CloudFront
    participant C as Cognito
    actor R as Reviewer
    M->>RV: StartExecution (name = DetectLabelRequestId)
    RV->>D: Write task and task token (OPEN)
    Note over RV: Waits for the token, with a timeout
    R->>CF: Open the portal page (served from S3)
    R->>C: Sign in
    C-->>R: Tokens
    Note over A,CF: CloudFront forwards /api/ requests to the Review API
    R->>A: Start working (with token)
    A->>D: Claim the oldest open task (conditional write)
    A-->>R: Presigned image URL and label options
    R->>A: Submit label
    A->>RV: SendTaskSuccess (label, reviewer)
    RV->>D: Record the label and reviewer
    RV->>RV: Copy image to training folder (low-confidence only, skipped for None of the above)
    Note over RV: On timeout, mark the task EXPIRED
```

### Stack changes

These changes are relative to the current template.

New:
- The review state machine, a Standard workflow built from direct service integrations with retries and logging (D4).
- A private S3 bucket for the review page. Only the CloudFront distribution can read it, through origin access control (OAC). At deploy time, CDK uploads the page and a small configuration file with the Cognito and API settings the page needs.
- A CloudFront distribution that serves the page from the bucket and forwards `/api/*` requests to the HTTP API. The page and the API share one domain, so the browser needs no CORS setup. A response headers policy adds the security headers, such as Content-Security-Policy and HSTS.
- An HTTP API with a Cognito JWT authorizer, and one Lambda function that handles only the API routes: claim, submit, and release a task. It's the only Lambda function the sample owns (D4).
- Optional AWS WAF, off by default. See [Security](#security).
- A Cognito app client (public, authorization code flow with PKCE) whose callback URL is the CloudFront URL, a domain, and a `reviewers` group. The stack always creates the user pool. The first reviewer is the notification email address, as in the current template.
- Review attributes on the existing inference log items, plus a sparse GSI that lists open tasks by creation time.
- SSM parameters: `Enable-Human-Review` (replaces `Enable-A2I-Workflow`), `Human-Review-Labels`, and `Human-Review-Timeout-Hours`.

Changed:
- In the detection state machine, "Create HumanLoop" becomes a `states:startExecution` task. The A2I output branch (`s3-a2i-event`) goes away.
- Human sampling moves into the detection state machine as a counter (D6).
- The review state machine applies the label with `s3:copyObject`, `dynamodb:updateItem`, and `sns:publish`. For a low-confidence review, it still copies the image into `images_labeled_by_folder/<label>/`, because the S3 folders stay the source of truth for training (D7). If the reviewer chose "None of the above", it records that answer in the inference log and doesn't copy the image.
- The inference log attributes named after A2I, such as `HumanLoopName`, are renamed.

Removed:
- `A2IWorkFlowAssets` and its Lambda, `FlowDefinitionRole`, `AWS::SageMaker::Workteam`, the `A2IPrivateTeamName` parameter and condition, and the task UI mapping.
- The `a2i-human-loop-data/` prefix and its S3 notification.
- All `sagemaker:*` permissions.
- The sampling schedule rule, the `Automatic-Human-Sampling-Frequency` parameter, and the `Sampled_GSI` index (D6).
- In the docs: the private workforce checks in 0-Prerequisites and the `delete-workforce` cleanup step.

### Defaults

- One reviewer per task, the same as A2I `TaskCount: 1`.
- Tasks expire after 72 hours (`Human-Review-Timeout-Hours`).
- A claim lasts 15 minutes. If a reviewer walks away, the task becomes available to other reviewers again.
- Reviewers don't see the model's label or confidence. This matches the current task UI and avoids biasing the sampling audits.
- Sampled reviews are recorded but not added to the training data, as in the current design.
- A "None of the above" answer is recorded in the inference log, but the image isn't added to the training data, as in the current design.
- The label options are `Human-Review-Labels` (default `amazon_logo,aws_logo`) plus "None of the above".

### Security

- Every API route requires a valid Cognito token, which API Gateway checks before the function runs. The Lambda function also checks that the caller is in the `reviewers` group.
- Images stay private. The API returns presigned URLs that expire after 5 minutes.
- On submit, the API checks that the caller holds the claim and that the label is in the allowed list.
- The page uses no third-party JavaScript. CloudFront adds a strict Content-Security-Policy and the other security headers.
- The page's bucket is private, and only the CloudFront distribution can read it.
- AWS WAF is a deploy-time option, off by default:
  - When it's on, the stack adds a web ACL to the CloudFront distribution, plus a regional web ACL on the Cognito user pool to cover the hosted sign-in pages.
  - A web ACL for CloudFront has to be created in us-east-1, so CDK puts it in a small us-east-1 stack. Readers in other Regions also have to bootstrap CDK in us-east-1.
  - With a basic rule set (AWS managed common rules, an IP reputation list, and a rate limit), each web ACL costs about $8 a month, even when idle.
  - CloudFront's flat-rate plans include WAF in a fixed monthly price, with a $0 tier, but you sign up for them outside CloudFormation. The docs can mention them.
  - Without WAF, API Gateway still rejects requests that don't carry a valid sign-in token, and only invited users can sign in.
- Amazon Cognito Sync is in maintenance, but user pools, which this design uses, are not.

### Alternatives considered

| Alternative | Why not |
|---|---|
| Email with approval links (the Step Functions human approval pattern) | A plain-text email can't show the image safely. Anyone who has the email can use the links, mail scanners can follow them, and there's no reviewer identity. |
| Rekognition Custom Labels console labeling | Reviewers would need AWS console access. There's no task queue and no completion event to automate on, and it doesn't fit sampling audits. |
| Self-hosted Label Studio or CVAT on ECS Fargate | These tools support bounding boxes and richer labeling workflows, but they add containers, a database, and always-on cost. They suit production use but are too heavy for this sample. |
| An SQS queue for review tasks | SQS works with task tokens, but the portal needs to count, list, and release tasks, which DynamoDB handles better. |
| The Lambda function serving the page through the HTTP API | It needs fewer resources and deploys faster the first time. But every page load runs code, the security headers live in the function's code, and HTTP APIs can't use AWS WAF. |
| Lambda Web Functions (October 2026) | They support only Node.js and are available in 5 Regions, while Custom Labels is in 11. |

### Out of scope for the first version

- Bounding-box labeling. The sample uses image-level labels.
- Multiple reviewers per task and consensus.
- A user-management page. Reviewers are added in the Cognito console or with the AWS CLI.

### Build plan

Each phase ends with a stack that deploys and can be tested. Commits stay local: nothing is pushed to GitHub, and no pull requests are opened, unless the owner says otherwise.

Each phase is built on its own local branch (`v2-h1`, `v2-h2`, and so on), created from a local `v2` branch. After the owner reviews a phase, it's squash-merged into `v2`, so each phase becomes one commit. After H4, `v2` is merged into `main`. This tracker is committed on `v2`.

- [x] **H0.** Tag the current commit, `db61b19`, as `v1-a2i` and push the tag, so readers can still find the A2I version. Done November 4, 2026: the annotated tag `v1-a2i` points to `db61b19` and is on GitHub.
- [x] **T1.** Run a trial in a test account (us-west-2) before H1, to prove the parts of D4 and D7 that the docs don't settle. All seven checks passed on November 4, 2026, and the trial resources were deleted the same day. A throwaway CDK app in `spikes/t1/` created two stacks, `T1Core` and `T1Flows`, and used the 10 sample training images. The app wasn't part of the sample and was deleted after the trial. Each check has a pass condition and a fallback:
  1. **Manifest.** A Distributed Map writes the training manifest as JSON Lines, the state machine finds the results file through the map run's `manifest.json`, and `CreateDataset` builds the training dataset from it. Passes if the dataset has all 10 images and both labels. Fallback: build the manifest with a small Lambda function, which D4 allows.
  2. **Test split.** `DistributeDatasetEntries` moves 20% of the images into the test dataset. Passes if the test set includes every label, because Custom Labels needs at least half of the training labels in the test set. Fallback: pick the test images per label in the state machine and create the test dataset from its own manifest.
  3. **Models survive dataset deletion.** Train a model from the datasets and start it, delete both datasets, and run a detection. Then stop the model, start it again, and run another detection. Passes if both detections work. Fallback: revisit D7.
  4. **Dataset timings.** Time the create, distribute, and delete steps during checks 1 to 3. The results set the wait intervals in the training state machine.
  5. **S3 key encoding.** Upload files whose names contain spaces, plus signs, parentheses, and non-ASCII characters, and log the EventBridge events. This shows whether keys arrive URL-encoded. If they do, the state machine decodes them.
  6. **Callback through DynamoDB.** A state saves its task token in a DynamoDB item with `dynamodb:putItem.waitForTaskToken`. Passes if the run pauses and resumes with the `SendTaskSuccess` payload, and if a second run times out into its Catch. Fallback: write the item with a small Lambda function.
  7. **Listing page size.** List about 1,000 objects with realistic names, using `MaxKeys` values of 1,000 and 500. This finds the largest page that stays under 256 KiB, and whether the limit applies before or after the state's `Output` trims the result. Fallback: smaller pages, or count the objects with a Distributed Map.

  Not in T1: the review portal, WAF, the settings and review workflows beyond check 6, the final CDK project layout, the docs, and H0. The expected cost is roughly $5 to $10, mostly Custom Labels training ($1 per training hour) and model hosting ($4 per hour while the model runs). Teardown deletes the model, the project, the bucket, and both stacks.

  Results (November 4, 2026). All seven checks passed, so none of the fallbacks are needed:

  | Check | Result | Details |
  |---|---|---|
  | 1. Manifest | Pass | The Distributed Map wrote `manifests/<map run ID>/SUCCEEDED_0.jsonl` with 10 lines. The folder placeholder objects were skipped by returning an empty array from the child state. The map run's `manifest.json` lists the file under `ResultFiles.SUCCEEDED[0].Key`. `CreateDataset` accepted the file: 10 labeled images, 2 labels, no errors. The S3 item reader reports `LastModified` in epoch seconds, so the child state converts it for `creation-date`. |
  | 2. Test split | Pass | With 2 labels: 8 training and 2 test images, one test image per label. A second run with 3 labels of uneven size (5, 5, and 3 images) gave 10 training and 3 test images, again one per label, so the split follows labels. |
  | 3. Models survive dataset deletion | Pass | Model `t1-v1` trained from the project datasets in about 20 minutes (11 billable minutes) with an F1 score of 1.0. While it was running, the second run deleted both of its datasets and rebuilt them. The model stayed running, kept its evaluation results, and returned the same detection (`amazon_logo`, 93.7%). After a stop and a restart, with its source datasets gone, it started again and detection still worked. |
  | 4. Timings | Measured | Deleting the old datasets, creating the training dataset, and distributing the entries each finished within one 10-second polling interval. Creating the empty test dataset finished within one 5-second interval. The manifest build took 2 to 7 seconds. Starting the model took about 6 minutes both times, and stopping it took about 12 seconds. The training state machine can poll the dataset steps every 10 seconds, the model start every minute, and training every 5 minutes. |
  | 5. S3 key encoding | Pass | EventBridge delivers object keys as-is. Spaces, plus signs, parentheses, and non-ASCII characters arrive unencoded, unlike classic S3 notifications. No decoding step is needed, which also removes today's bug with such file names. |
  | 6. Callback through DynamoDB | Pass | The state machine deployed with `dynamodb:putItem.waitForTaskToken` and stored a 648-character token in the item. `SendTaskSuccess` resumed the run with its payload, and a run with a 20-second timeout went to its Catch. A JSONata expression in `TimeoutSeconds` worked. |
  | 7. Listing page size | Pass, with a limit | `MaxKeys` 1,000 failed with `States.DataLimitExceeded`. `MaxKeys` 500 succeeded with a 140,357-character result, about 280 bytes per object for 87-character keys. The limit applies to the raw SDK result, before `Output` trims it. Use `MaxKeys` 500. |

  Tooling finding: the CDK CLI installed on the test machine (2.1117.0) was too old for the current `aws-cdk-lib` (2.275.0 needs CLI 2.1147.0 or later), so the trial installed the CLI locally in `spikes/t1/`. The test machine's global CLI was updated to 2.1147.0 after the trial. H1 should pin both versions.

  Teardown finding: after the model and both datasets were deleted, `cdk destroy` removed both stacks and everything in them, including the project. It left three CloudWatch log groups, one for each Lambda function that CDK adds for its own custom resources (S3 auto-delete, S3 bucket notifications, and the EventBridge-to-Logs resource policy). Lambda creates these log groups on first run, outside the stack, so they were deleted by hand. The `@aws-cdk/aws-lambda:useCdkManagedLogGroup` flag, which `cdk init` turns on, doesn't fix this: it gives the `AwsCustomResource` function a stack log group that's retained on delete, and the other two functions get none. H1 should pass its cleanup `AwsCustomResource` a log group that's deleted with the stack (the `log_group` property). Section 7 should list the log groups that remain, and the `CDKToolkit` stack and its assets bucket, which `cdk destroy` doesn't remove.
- [ ] **H1.** Rebuild the stack in CDK (Python) without A2I and Ground Truth: one Step Functions state machine per job (D4, D5), dataset-based training (D7), counter-based sampling (D6), the state table (D8), the Scheduler schedule (O1), on-demand tables (O4), the failed-run rule (D9), and the D10 emails. Apply R2, R3, and the open F items, and remove the old template, the `lambda/` folder, and `assets/task_ui.html` (DOC11). After this phase the stack deploys in any account, and training and detection work. Human review, including sampling, stays off until H2.

  H1 defaults: one stack. `aws-cdk-lib` 2.275.0, `constructs` 10.8.1, and CDK CLI 2.1147.0 are pinned, with the CLI in `package.json` and run through `npx cdk`. The schedule and its parameter share one default, 720 minutes (F8). Only `.jpg`, `.jpeg`, and `.png` files count as images, for training and for detection.
- [ ] **H2.** Build the review backend: the review state machine, the DynamoDB attributes and GSI, the SSM parameters, and the portal API function (R1). Turn on human review and sampling, and test them with a script.
- [ ] **H3.** Build the review portal: the Cognito app client and domain, the HTTP API and authorizer, the page bucket and CloudFront distribution, the review page, and the optional WAF web ACLs.
- [ ] **H4.** Rewrite the README and sections 0, 1, 4, 5, 6, and 7, apply the DOC items, and redraw the diagrams. Section 1 switches from the CloudFormation console to running `cdk deploy` on the reader's computer. It lists the prerequisites and says that CloudShell isn't supported. The README explains that the first version used A2I and links the `v1-a2i` tag.

## Baseline updates

R2, R3, and the open F items are part of H1. R1 applies to the portal function in H2. The DOC items are part of H4 unless noted.

### Runtime and code

- [ ] **R1.** Use `python3.13` or `python3.14` for the portal function, which after D4 is the only Lambda function the sample owns. Today all 11 functions use `python3.9` (template L712). Lambda deprecated `python3.9` on December 15, 2025. It blocks creating functions with that runtime from July 29, 2027 and updating them from August 31, 2027. Skip `python3.10` and `python3.11`, which run on Amazon Linux 2.
- [ ] **R2.** Handle the Custom Labels console trap. Today the sample trains with manifests (`lambda/train-deploy-model.py` L25-31). If anyone opens the project in the console after a model has been trained from manifests, the console creates datasets, and manifest training no longer works for that project. D7 fixes this in H1, because training uses datasets. 3-Model-Training step 13 can stay, with a note that dataset edits in the console are replaced on the next training run.
- [ ] **R3.** Update the inference unit description. The current docs don't give a fixed TPS per inference unit. Remove "up to 5 TPS" from 2-Parameter-Store and from the `Minimum-Inference-Units` parameter description (template L496).

### Defects

- ~~**F1.** `create-training-manifest` opens `/tmp/manifest.txt` in append mode (template L920).~~ Superseded by D4. The Lambda function goes away, and a Distributed Map builds the manifest (D7).
- ~~**F2.** Human sampling formats dates with `%-S` (`lambda/create_human_sampling.py` L19), which drops the zero padding.~~ Superseded by D6. Sampling no longer compares dates.
- [ ] **F3.** `update-event-rules` builds `rate(1 minutes)` for a value of 1, which EventBridge rejects. It also calls `PutRule` without `State`. If only the frequency changes, that call re-enables a disabled schedule (`lambda/update-event-rules.py` L22-27). The settings state machine has to send `State` and build "minute" or "minutes".
- [ ] **F4.** On stack deletion, CloudFormation deletes `ParameterSystemVariables` before the Rekognition custom resource. The custom resource's Delete handler then can't read the parameter, so it doesn't stop the running models. It still reports success. In H1, the cleanup workflow (D4) gets the project ARN directly instead of reading it from SSM.
- ~~**F5.** The custom resources don't set a `PhysicalResourceId`, and they swallow exceptions without logging them.~~ Superseded by D4. The sample no longer owns custom resource code, and CDK's built-in custom resource handles the folder placeholders and the cleanup.
- ~~**F6.** `RekognitionProjectAssets` doesn't depend on `LambdaS3EventTriggerPermission`, so writing the S3 notification can fail intermittently.~~ Superseded by D4. S3 events go through EventBridge, so there's no Lambda notification or permission to order.
- [ ] **F7.** Resource names use `!Select [6, !Split ['-', StackId]]`. If the stack name has exactly four hyphens, a `/` ends up in resource names and stack creation fails. Stack names longer than about 26 characters make Lambda function names exceed the 64-character limit. In H1, let CloudFormation generate the names.
- [ ] **F8.** Align the training schedule's defaults. The rule uses `rate(600 minutes)` (template L544), but the SSM parameter defaults to 720 (L464). The sampling schedule goes away with D6.

### Documentation

- ~~**DOC1.** 1-Deployment step 4 names `rekognition-a2i-automate-workflow.yml`, but the file is `rekonginition-a2i-automate-workflow.yml`.~~ Superseded by D2. The template goes away, and H4 rewrites section 1 for `cdk deploy`.
- [ ] **DOC2.** Update the service names:
  - Amazon SageMaker is now Amazon SageMaker AI.
  - Amazon QuickSight is now Amazon Quick Sight, part of Amazon Quick Suite.
  - "AWS System Manager" in the architecture diagram and the template description should be AWS Systems Manager.
  - "Amazon Parameter Store" in sections 3, 6, and 7 should be AWS Systems Manager Parameter Store.
  - Optional: AWS docs now call standard functions "Lambda Event Functions".
- [ ] **DOC3.** Remove the Mechanical Turk workforce option from the README intro.
- [ ] **DOC4.** In the 0-Prerequisites Region list, drop the "June 2021" label and the duplicate Europe (Ireland) entry. The 11 Regions are still correct.
- [ ] **DOC5.** 3-Model-Training step 15: the Step Functions "Graph inspector" is now **Graph view**.
- [ ] **DOC6.** Remove the 0-Prerequisites screenshots. They date from January 2021, show an MTurk tab, and cover the private workforce setup, which option B removes.
- [ ] **DOC7.** In 7-Conclusions-Cleanup steps 6 to 9, replace the console steps with the AWS CLI commands `stop-project-version`, `delete-project-version`, and `delete-project`.
- [ ] **DOC8.** Fix the links:
  - `customlabels-dg/gs-step-evaluate-model.html` (F1 score) → `customlabels-dg/im-metrics-use.html`
  - `customlabels-dg/rm-run-model.html` → `customlabels-dg/running-model.html`
  - `customlabels-dg/cd-manifest-files-object-detection.html` → `customlabels-dg/md-create-manifest-file-object-detection.html`
  - `customlabels-dg/rv-assign-labels.html` → `customlabels-dg/md-assign-image-level-labels.html`
  - `aws.amazon.com/sagemaker/groundtruth/` → `aws.amazon.com/sagemaker/ai/groundtruth/`
  - `aws.amazon.com/quicksight/` → `aws.amazon.com/quick/quicksight/`
  - `https:///aws.amazon.com/cognito/` (0-Prerequisites) → `https://aws.amazon.com/cognito/`
- [ ] **DOC9.** Resolve the contradictions, and check that the rewritten sections agree on the new counts of parameters, state machines, and rules:
  - The README says "ten configurable parameters" and later "seven single-value parameters". There are 10. Section 2 counts 11 because it includes `For-System-Use-Only`.
  - The README says the state machine has "four separate states" and then describes five.
  - The README says "two EventBridge rules", but the template has three.
  - 3-Model-Training says the polling frequency is 600 minutes (see F8).
  - 3-Model-Training says new images must be "greater than" the minimum, but the code uses `>=`.
- ~~**DOC10.** Fix the task UI.~~ Superseded by option B. The review page replaces the A2I task UI, and the labels come from `Human-Review-Labels`.
- [ ] **DOC11.** Remove the duplicate code as part of H1. Delete `lambda/` and `assets/task_ui.html`, and keep the portal function's code in the CDK app. Today `lambda/` and `assets/task_ui.html` are copies that the template doesn't use, and `lambda/update-event-rules.py` L51 has a different SNS subject than the deployed code.
- [ ] **DOC12.** Fix the typos:
  - Docs: Prerequsites, Supprted, Recognition, amazon_log, EventBride, Labelsdetections, Customs Labelsmodel, Transaction Pers Second, qualify control, worfklow, Labelsconsole, DyanmoDB. Step 1 of 3-Model-Training also repeats its own sentence.
  - Template: configurrable, Rekongition (state names), Internval, paramater-store, RekogntionProjectArn, Preject, Autmatic. Don't carry these into the new state machines in H1.
- [ ] **DOC13.** In `CONTRIBUTING.md`, replace the `${GITHUB_REPO}` placeholders and the `awsdocs` organization with `aws-samples/amazon-rekognition-custom-labels-a2i-automated-continuous-model-improvement`.
- [ ] **DOC14.** Redraw the architecture, workflow, and state machine diagrams in `assets/` for the new state machines and the review components, and fix the old labels "AWS System Manager" and "Amazon SageMaker".

## Optional modernization

Decide each item separately.

- ~~**O1.** Replace the training schedule rule with EventBridge Scheduler, which EventBridge now recommends. With D5, the schedule targets the training state machine directly.~~ Adopted for H1, November 4, 2026. The settings state machine reads the schedule with `GetSchedule` and saves it with `UpdateSchedule`, because `UpdateSchedule` resets any field it isn't given.
- ~~**O2.** Route S3 events through EventBridge to Step Functions and remove `LambdaS3EventTrigger`.~~ Adopted in D4.
- ~~**O3.** Use Step Functions integrations with `Retry` and `Catch`, turn on logging, and consider JSONata.~~ Adopted in D4. Every state machine uses direct service integrations, `Retry` and `Catch`, logging, and JSONata.
- ~~**O4.** Switch DynamoDB to on-demand capacity. The D6 counter adds one write per detection.~~ Adopted for H1, November 4, 2026. Both tables use on-demand capacity, which is also the default for CDK's `TableV2`.
- ~~**O5.** Replace the custom resource with the native `AWS::Rekognition::Project` resource.~~ Adopted in D4 (`CfnProject`).
- ~~**O6.** Train with project datasets instead of manifests.~~ Adopted in D7, with the datasets rebuilt from the S3 folders for each run.
- [ ] **O7.** Add `MaxInferenceUnits` so the model can auto-scale.
- [ ] **O8.** Harden IAM and resources:
  - Scope `iam:PassRole` with `iam:PassedToService`.
  - Give each state machine and the portal function its own role (D5 covers the state machines).
  - Use `${AWS::Partition}` instead of `arn:aws`.
  - Add `aws:SourceAccount` and `aws:SourceArn` conditions to the bucket policy.
  - Encrypt the SNS topic.
- ~~**O9.** In the Cognito app client, remove the duplicate `DefaultRedirectURI` key and the implicit OAuth flow.~~ Superseded by H3. The new app client uses the authorization code flow with PKCE.
- ~~**O10.** Replace the `For-System-Use-Only` parameter.~~ Adopted in D8, with its own small state table.

## Open questions and risks

- The repository name and the README title both mention A2I. Should the repository be renamed (GitHub redirects the old URL) and the sample retitled?
- The two-part AWS Machine Learning Blog series from July 2021 describes the A2I design. Should it be updated, given a note, or left as is?
- Which account and Region can we use for T1 and the test deployments? Training a model takes about an hour and incurs training and inference charges.
- Existing deployments can't be upgraded in place, because the A2I resources go away and the stack moves to CDK. The docs should tell existing users to delete the old stack and deploy the new one. The old stack's bucket and table are retained.
- The console labels in Rekognition Custom Labels haven't been checked, because checking them requires signing in.
- Rekognition Custom Labels has no announced change, but its developer guide history lists no updates after April 19, 2023. Check the AWS lifecycle pages again before starting H2.

## Log

| Date | Entry |
|---|---|
| 2026-11-04 | Finished the currency review and created this tracker. |
| 2026-11-04 | Decided D1: option B. Added the proposed human review design and opened D2 (packaging). |
| 2026-11-04 | Confirmed that A2I and Ground Truth are closed to new customers but not shut down. Renamed D2 to deployment tooling and added CDK (recommended). Opened D3 (review providers) and added H5. |
| 2026-11-04 | Decided D2: AWS CDK in Python. Decided D3: custom review portal only, with A2I and Ground Truth dropped completely. Removed H5, added H0 (tag the A2I version), and updated H1 and H4 for CDK. |
| 2026-11-04 | Decided D4 (Step Functions only), D5 (one state machine per job), D6 (counter-based sampling), and D7 (rebuild datasets from the S3 folders before each training run). Added trial T1 and proposed O10. Marked O2, O3, O5, and O6 adopted, and F1, F2, F5, and F6 superseded. |
| 2026-11-04 | Decided O10 and recorded it as D8 (run-time state): fixed values go into the state machine definitions, and changing values go into one item in a small DynamoDB state table. Added D8 to H1. |
| 2026-11-04 | Updated the review design. A "None of the above" answer is recorded, but the image isn't added to the training data. The page is served from S3 through CloudFront, `/api/*` requests go to the HTTP API, the portal function handles only API calls, and AWS WAF is a deploy-time option that's off by default. |
| 2026-11-04 | Approved the human review design. Renamed its section to "Human review design" and its defaults are no longer marked as proposed. |
| 2026-11-04 | Ran trial T1 in a test account (us-west-2). All seven checks passed: the Distributed Map manifest, the label-aware test split, models surviving dataset deletion, the dataset and model timings, unencoded S3 keys in EventBridge events, the DynamoDB callback, and a 500-key listing page. The trial cost about $2 to $3: 11 billable training minutes and 25 to 40 minutes of model hosting, depending on whether hosting is billed from the start request or from when the model is running. Teardown is pending. |
| 2026-11-04 | Tore down trial T1. Deleted model `t1-v1` and both datasets, then ran `cdk destroy` on `T1Flows` and `T1Core`, which also deleted the project. Deleted three leftover Lambda log groups by hand. Marked T1 done and added a teardown finding for H1 and section 7. |
| 2026-11-04 | Finished H0: created the annotated tag `v1-a2i` on `db61b19` and pushed it to GitHub. Deleted the local T1 app (`spikes/t1/`) and updated the test machine's global CDK CLI from 2.1117.0 to 2.1147.0. |
| 2026-11-04 | Decided not to support AWS CloudShell. Readers deploy from their own computer. CloudShell's `python3` is 3.9, and `aws-cdk-lib` 2.275.0 needs Python 3.10 or later. Updated D2, H4, and the T1 tooling finding. |
| 2026-11-04 | Added a working rule to the build plan: commits stay local, and nothing is pushed to GitHub unless the owner says otherwise. |
| 2026-11-04 | Adopted O1 (EventBridge Scheduler) and O4 (on-demand tables) for H1. Decided D9 (after a failed training run, wait for new images), D10 (email only milestones and problems), and D11 (no automated tests). Added `LastRunImageCount` to the D8 state item, the local branch flow and the H1 defaults to the build plan, and replaced the D4 note about TestState unit tests. Committed this tracker on the local `v2` branch and started H1 on `v2-h1`. |

## Sources

- [AWS Service Availability Updates, June 30, 2026](https://aws.amazon.com/about-aws/whats-new/2026/06/aws-service-availability/)
- [AWS Service Availability Updates, September 29, 2026](https://aws.amazon.com/about-aws/whats-new/2026/09/aws-service-availability/)
- [Services in Maintenance](https://docs.aws.amazon.com/general/latest/gr/maintenance_services.html)
- [AWS Lifecycle Changes](https://docs.aws.amazon.com/general/latest/gr/service-lifecycle.html)
- [Using Amazon Augmented AI for Human Review](https://docs.aws.amazon.com/sagemaker/latest/dg/use-augmented-ai-a2i-human-review-loops.html)
- [Amazon A2I events in EventBridge](https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-cloudwatch-events.html)
- [Amazon A2I pricing](https://aws.amazon.com/augmented-ai/pricing/)
- [Amazon SageMaker Ground Truth](https://docs.aws.amazon.com/sagemaker/latest/dg/sms.html)
- [Amazon Mechanical Turk closure notice](https://www.mturk.com/)
- [Amazon Rekognition feature availability changes](https://docs.aws.amazon.com/rekognition/latest/dg/rekognition-availability-changes.html)
- [Amazon Rekognition endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/rekognition.html)
- [CreateProjectVersion API reference](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_CreateProjectVersion.html)
- [TestingData API reference](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_TestingData.html)
- [CreateDataset API reference](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_CreateDataset.html)
- [DeleteDataset API reference](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_DeleteDataset.html)
- [DistributeDatasetEntries API reference](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_DistributeDatasetEntries.html)
- [UpdateDatasetEntries API reference](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_UpdateDatasetEntries.html)
- [Training a Custom Labels model](https://docs.aws.amazon.com/rekognition/latest/customlabels-dg/training-model.html)
- [Creating training and test datasets with images](https://docs.aws.amazon.com/rekognition/latest/customlabels-dg/md-create-dataset.html)
- [Validation rules for manifest files](https://docs.aws.amazon.com/rekognition/latest/customlabels-dg/md-create-manifest-file-validation-rules.html)
- [Running a trained Custom Labels model](https://docs.aws.amazon.com/rekognition/latest/customlabels-dg/running-model.html)
- [Custom Labels document history](https://docs.aws.amazon.com/rekognition/latest/customlabels-dg/document-history.html)
- [Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)
- [AWS Lambda announces Lambda Web Functions](https://aws.amazon.com/about-aws/whats-new/2026/10/aws-lambda-web-functions/)
- [AWS::Lambda::Function Code](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-lambda-function-code.html)
- [Supported AWS SDK service integrations](https://docs.aws.amazon.com/step-functions/latest/dg/supported-services-awssdk.html)
- [Step Functions service integration patterns](https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html)
- [Transforming data with JSONata in Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/transforming-data.html)
- [Distributed Map ResultWriter](https://docs.aws.amazon.com/step-functions/latest/dg/input-output-resultwriter.html)
- [Step Functions service quotas](https://docs.aws.amazon.com/step-functions/latest/dg/service-quotas.html)
- [Step Functions Local is unsupported](https://docs.aws.amazon.com/step-functions/latest/dg/sfn-local.html)
- [Testing state machines with the TestState API](https://docs.aws.amazon.com/step-functions/latest/dg/test-state-isolation.html)
- [Step Functions execution details](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-view-execution-details.html)
- [Amazon S3 events in EventBridge](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ev-events.html)
- [HTTP API AWS service integration reference](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-aws-services-reference.html)
- [Resources that AWS WAF can protect](https://docs.aws.amazon.com/waf/latest/developerguide/how-aws-waf-works-resources.html)
- [AWS::WAFv2::WebACL](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-wafv2-webacl.html)
- [AWS WAF pricing](https://aws.amazon.com/waf/pricing/)
- [CloudFront flat-rate pricing plans](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html)
- [EventBridge scheduled rules (legacy)](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)
- [EventBridge PutRule API reference](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutRule.html)
- [AWS::Cognito::UserPool](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cognito-userpool.html)
- [AWS CDK prerequisites](https://docs.aws.amazon.com/cdk/v2/guide/prerequisites.html)
- [AWS CDK bootstrapping](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html)
- [AWS CloudShell pre-installed software](https://docs.aws.amazon.com/cloudshell/latest/userguide/vm-specs.html)
- [Python in Amazon Linux 2023](https://docs.aws.amazon.com/linux/al2023/ug/python.html)
- [aws-cdk-lib on PyPI](https://pypi.org/project/aws-cdk-lib/)
- [Python 3.10.22, the final 3.10 release](https://www.python.org/downloads/release/python-31022/)
- [Amazon QuickSight evolves to Amazon Quick Suite](https://aws.amazon.com/blogs/business-intelligence/reimagine-business-intelligence-amazon-quicksight-evolves-to-amazon-quick-suite/)
- [Automate continuous model improvement with Amazon Rekognition Custom Labels and Amazon A2I: Part 1](https://aws.amazon.com/blogs/machine-learning/part1-automate-continuous-model-improvement-with-amazon-rekognition-custom-labels-and-amazon-a2i/)

Content was rephrased for compliance with licensing restrictions.
