## 6 Automatic human sampling

In this section, we explain the design principle and the processes behind the human sampling workflow.

**Design principle**  
The principle for the human-in-the-loop workflow is intended for model improvement by capturing inference images with [Amazon Rekognition Custom Labels](https://aws.amazon.com/rekognition/custom-labels-features/) with low confidence detection result and add them to the training dataset for new training. The principle for human sampling workflow is intended for business improvement. In human sampling, for every `nth` detection, the detection is flagged for human review and the human-labeled result is compared against the detected one, regardless of the original detection confidence level. The sampled detections can then used for qualify control, audit, analytics, etc. Although both workflows use the same [Amazon A2I](https://aws.amazon.com/augmented-ai/) process, inference images flagged as `sampled only` are **not** add to the training dataset.

**Workflow**  
The human sampling workflow is configurable by three [Amazon Parameter Store](https://console.aws.amazon.com/systems-manager/parameters) parameters as explained in [Section 2-Parameter Store](../2-Parameter-Store/). When **Enable-Automatic-Human-Sampling** is enabled, an [Amazon EventBridge](https://aws.amazon.com/eventbridge/) schedule rule is triggered every `nth` minutes as set in **Automatic-Human-Sampling-Frequency** to invoke the processes orchestrated by [AWS Step Functions](https://aws.amazon.com/step-functions/). The processes include:

1. Initialize the starting `query date` with the `Last modified date` of **Enable-Automatic-Human-Sampling**. The purpose is to sample forward instead retroactively finding historic samples.
2. Query the minimum number (`limit`) of detection events as set in **Human-Sampling-Interval** forward from the `query date`
3. If the query result count is less than the minimum number, then the process ends. Otherwise the last (`limit`) detection event is marked as sampled and the new `query date` is set to the detection event date.
4. Next an A2I human labeling task is created if none exists from another process and the originating source is marked as `Human Sampling`.
5. Repeat Steps 2 through 4.

Finally the labeling task is completed as explained in [Section 5-A2I Human Loop](../5-A2I-Human-Loop/).










Next Step: [7-Conclusions-Cleanup](../7-Conclusions-Cleanup/)
