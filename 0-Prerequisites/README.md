# 0. Prerequisites

## AWS account and Region

- An AWS account, and permissions to deploy an AWS CDK app. The deployment creates IAM roles, so it needs administrator access or an equivalent set of permissions.
- One of the 11 Regions where [Rekognition Custom Labels is available](https://docs.aws.amazon.com/general/latest/gr/rekognition.html#rekognition_region):

  | Region | Code |
  |---|---|
  | US East (N. Virginia) | `us-east-1` |
  | US East (Ohio) | `us-east-2` |
  | US West (Oregon) | `us-west-2` |
  | Europe (Ireland) | `eu-west-1` |
  | Europe (London) | `eu-west-2` |
  | Europe (Frankfurt) | `eu-central-1` |
  | Asia Pacific (Mumbai) | `ap-south-1` |
  | Asia Pacific (Singapore) | `ap-southeast-1` |
  | Asia Pacific (Sydney) | `ap-southeast-2` |
  | Asia Pacific (Tokyo) | `ap-northeast-1` |
  | Asia Pacific (Seoul) | `ap-northeast-2` |

- Room for two running Custom Labels models. An account can run 2 models at a time by default. When a new model replaces the running one, both run for a few minutes, because the workflow stops the old model only after the new one is running. Check the [Custom Labels quotas](https://docs.aws.amazon.com/general/latest/gr/rekognition.html#limits_rekognition) if other models run in the same account.
- An email address for notifications. The first reviewer account uses the same address.

## Tools on your computer

Deploy from your own computer. AWS CloudShell isn't supported, because its Python is version 3.9, and the CDK library that this sample uses needs Python 3.10 or later.

| Tool | Version | Check with |
|---|---|---|
| [Python](https://www.python.org/downloads/) | 3.11 or later | `python3 --version` |
| [Node.js](https://nodejs.org/) | 22 or later, which the [AWS CDK requires](https://docs.aws.amazon.com/cdk/v2/guide/prerequisites.html) | `node --version` |
| [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) | Version 2 | `aws --version` |
| [Git](https://git-scm.com/downloads) | Any recent version | `git --version` |

You don't need to install the CDK CLI globally. The sample pins its version in `package.json`, and you run it with `npx cdk`.

Configure the AWS CLI with credentials for your account, and set your Region. For example, to use US West (Oregon):

```bash
aws configure set region us-west-2
aws sts get-caller-identity
```

The second command shows the account that you're signed in to. Use the same account and Region for every step.

## Rekognition Custom Labels console

You don't have to open the Custom Labels console for this sample, because the workflows call the Custom Labels APIs directly. If you open the console in a new Region, it offers to create a console bucket. You can create it or skip it. The sample doesn't use it.

Next: [Deployment](../1-Deployment/)
