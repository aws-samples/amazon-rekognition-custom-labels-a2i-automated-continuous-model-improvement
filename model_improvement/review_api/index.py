"""Review API for the human review portal.

An API Gateway HTTP API with a Cognito JWT authorizer calls this function for three routes:

  POST /api/tasks/claim               Claim the oldest waiting review task.
  POST /api/tasks/{taskId}/submit     Submit a label for a task that you claimed.
  POST /api/tasks/{taskId}/release    Give a claimed task back to the queue.

A review task is a set of attributes on a detection's inference log item. The review state
machine adds them, then waits until this function sends the label with SendTaskSuccess.

API Gateway checks the sign-in token before the function runs, so the function trusts the token
claims in the event. It also checks that the caller is in the reviewers group.
"""
import base64
import binascii
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

LOG = logging.getLogger()
LOG.setLevel(logging.INFO)

TABLE_NAME = os.environ["TABLE_NAME"]
QUEUE_INDEX = os.environ["QUEUE_INDEX"]
LABELS_PARAMETER = os.environ["LABELS_PARAMETER"]
REVIEWER_GROUP = os.environ["REVIEWER_GROUP"]
CLAIM_SECONDS = int(os.environ["CLAIM_SECONDS"])
IMAGE_URL_SECONDS = int(os.environ["IMAGE_URL_SECONDS"])
REGION = os.environ["AWS_REGION"]

NONE_OF_THE_ABOVE = "None of the above"
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
MAX_BODY_BYTES = 4096
LABELS_CACHE_SECONDS = 60
CLOSED_TASK_ERRORS = ("TaskTimedOut", "TaskDoesNotExist", "InvalidToken")

dynamodb = boto3.client("dynamodb")
stepfunctions = boto3.client("stepfunctions")
ssm = boto3.client("ssm")
# A Regional endpoint with Signature Version 4, so presigned URLs work in every Region, including
# right after the bucket is created. All Custom Labels Regions use the amazonaws.com domain.
s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)

_labels_cache = {"labels": None, "expires": 0.0}


class ApiError(Exception):
    """An error that the caller gets back with an HTTP status code."""

    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def handler(event, context):
    route = event.get("routeKey", "")
    action = ROUTES.get(route)
    try:
        if action is None:
            raise ApiError(404, "NotFound", "There's no such route.")
        return action(event)
    except ApiError as error:
        log("rejected", route=route, status=error.status, error=error.code)
        return respond(error.status, {"error": error.code, "message": error.message})
    except Exception:  # Log the details, and return a generic error.
        LOG.exception("Unhandled error on route %s", route)
        return respond(500, {"error": "InternalError", "message": "Something went wrong. Try again."})


# Routes -------------------------------------------------------------------------------------


def claim_task(event):
    """Claims a task for the caller, oldest first. A caller who already holds a claim gets the
    same task back, for example after reloading the page, and the claim is renewed."""
    reviewer_id, reviewer_name = reviewer(event)
    now = int(time.time())
    queue = list(queued_tasks())
    mine = [item for item in queue if is_claimed_by(item, reviewer_id, now)]
    available = [item for item in queue if is_available(item, now)]
    claimed = None
    for item in mine + available:
        claimed = try_claim(item_id(item), reviewer_id, reviewer_name, now)
        if claimed:
            break
    claimed_id = item_id(claimed) if claimed else None
    waiting = sum(1 for item in available if item_id(item) != claimed_id)
    log("claim", reviewer=reviewer_id, task=claimed_id, waiting=waiting)
    return respond(200, {"task": task_view(claimed) if claimed else None, "waiting": waiting})


def submit_label(event):
    """Sends the caller's label to the waiting review workflow."""
    reviewer_id, reviewer_name = reviewer(event)
    task_id = path_task_id(event)
    label = request_body(event).get("label")
    if not isinstance(label, str) or label not in review_labels():
        raise ApiError(400, "InvalidLabel", "Choose one of the labels that the task lists.")
    now = int(time.time())
    # Marks the task as submitted only if the caller still holds the claim. A task that's being
    # submitted can't be claimed again, so the next claim gets a different task.
    try:
        item = dynamodb.update_item(
            TableName=TABLE_NAME,
            Key=task_key(task_id),
            UpdateExpression="SET ReviewStatus = :submitted",
            ConditionExpression="ReviewStatus = :claimed AND ReviewClaimedBy = :reviewer AND ReviewClaimExpires > :now",
            ExpressionAttributeValues={
                ":submitted": {"S": "SUBMITTED"},
                ":claimed": {"S": "CLAIMED"},
                ":reviewer": {"S": reviewer_id},
                ":now": {"N": str(now)},
            },
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as error:
        if error_code(error) == "ConditionalCheckFailedException":
            raise ApiError(409, "ClaimNotHeld", "You don't hold a claim on this task, or your claim ran out. Claim a task again.") from error
        raise
    answer = {"label": label, "reviewerId": reviewer_id, "reviewerName": reviewer_name, "submitted": iso(now)}
    try:
        stepfunctions.send_task_success(taskToken=text(item, "ReviewTaskToken"), output=json.dumps(answer))
    except ClientError as error:
        if error_code(error) in CLOSED_TASK_ERRORS:
            raise ApiError(409, "TaskClosed", "This task isn't waiting for a label anymore.") from error
        reopen_claim(task_id, reviewer_id)
        raise
    log("submit", reviewer=reviewer_id, task=task_id, label=label)
    return respond(200, {"id": task_id, "label": label})


def release_task(event):
    """Gives a task that the caller claimed back to the queue."""
    reviewer_id, _ = reviewer(event)
    task_id = path_task_id(event)
    try:
        dynamodb.update_item(
            TableName=TABLE_NAME,
            Key=task_key(task_id),
            UpdateExpression="SET ReviewStatus = :open REMOVE ReviewClaimedBy, ReviewClaimedByName, ReviewClaimExpires",
            ConditionExpression="ReviewStatus = :claimed AND ReviewClaimedBy = :reviewer",
            ExpressionAttributeValues={
                ":open": {"S": "OPEN"},
                ":claimed": {"S": "CLAIMED"},
                ":reviewer": {"S": reviewer_id},
            },
        )
    except ClientError as error:
        if error_code(error) == "ConditionalCheckFailedException":
            raise ApiError(409, "ClaimNotHeld", "You don't hold a claim on this task.") from error
        raise
    log("release", reviewer=reviewer_id, task=task_id)
    return respond(200, {"id": task_id})


ROUTES = {
    "POST /api/tasks/claim": claim_task,
    "POST /api/tasks/{taskId}/submit": submit_label,
    "POST /api/tasks/{taskId}/release": release_task,
}


# Review queue -------------------------------------------------------------------------------


def queued_tasks(max_pages=10):
    """Yields the tasks in the review queue, oldest first. The index can lag the table by a
    moment, so every claim is a conditional write against the table."""
    request = {
        "TableName": TABLE_NAME,
        "IndexName": QUEUE_INDEX,
        "KeyConditionExpression": "ReviewQueue = :pending",
        "ExpressionAttributeValues": {":pending": {"S": "pending"}},
    }
    for _ in range(max_pages):
        page = dynamodb.query(**request)
        yield from page.get("Items", [])
        if "LastEvaluatedKey" not in page:
            return
        request["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def is_available(item, now):
    status = text(item, "ReviewStatus")
    return status == "OPEN" or (status == "CLAIMED" and number(item, "ReviewClaimExpires") <= now)


def is_claimed_by(item, reviewer_id, now):
    return (
        text(item, "ReviewStatus") == "CLAIMED"
        and text(item, "ReviewClaimedBy") == reviewer_id
        and number(item, "ReviewClaimExpires") > now
    )


def try_claim(task_id, reviewer_id, reviewer_name, now):
    """Claims a task with a conditional write, so two reviewers can't hold the same task.
    Returns the task, or None if someone else got it first."""
    try:
        return dynamodb.update_item(
            TableName=TABLE_NAME,
            Key=task_key(task_id),
            UpdateExpression="SET ReviewStatus = :claimed, ReviewClaimedBy = :reviewer, "
            "ReviewClaimedByName = :name, ReviewClaimExpires = :expires",
            ConditionExpression="ReviewQueue = :pending AND (ReviewStatus = :open OR (ReviewStatus = :claimed "
            "AND (ReviewClaimExpires <= :now OR ReviewClaimedBy = :reviewer)))",
            ExpressionAttributeValues={
                ":pending": {"S": "pending"},
                ":open": {"S": "OPEN"},
                ":claimed": {"S": "CLAIMED"},
                ":reviewer": {"S": reviewer_id},
                ":name": {"S": reviewer_name},
                ":now": {"N": str(now)},
                ":expires": {"N": str(now + CLAIM_SECONDS)},
            },
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as error:
        if error_code(error) == "ConditionalCheckFailedException":
            return None
        raise


def reopen_claim(task_id, reviewer_id):
    """Puts a task back in the caller's claim after SendTaskSuccess failed, so they can submit again."""
    try:
        dynamodb.update_item(
            TableName=TABLE_NAME,
            Key=task_key(task_id),
            UpdateExpression="SET ReviewStatus = :claimed",
            ConditionExpression="ReviewStatus = :submitted AND ReviewClaimedBy = :reviewer",
            ExpressionAttributeValues={
                ":claimed": {"S": "CLAIMED"},
                ":submitted": {"S": "SUBMITTED"},
                ":reviewer": {"S": reviewer_id},
            },
        )
    except ClientError:
        LOG.exception("Couldn't reopen the claim on task %s", task_id)


def task_view(item):
    """What the review page needs. The model's label and confidence aren't included, so they
    can't bias the reviewer."""
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": text(item, "S3Bucket"), "Key": text(item, "S3ObjectKey")},
        ExpiresIn=IMAGE_URL_SECONDS,
    )
    return {
        "id": item_id(item),
        "imageUrl": url,
        "imageUrlExpires": iso(int(time.time()) + IMAGE_URL_SECONDS),
        "labels": review_labels(),
        "claimExpires": iso(number(item, "ReviewClaimExpires")),
    }


def review_labels():
    """The label choices: Human-Review-Labels plus None of the above. Cached for a minute."""
    now = time.time()
    if _labels_cache["labels"] is None or now >= _labels_cache["expires"]:
        value = ssm.get_parameter(Name=LABELS_PARAMETER)["Parameter"]["Value"]
        labels = [label.strip() for label in value.split(",") if label.strip()]
        _labels_cache["labels"] = labels + [NONE_OF_THE_ABOVE]
        _labels_cache["expires"] = now + LABELS_CACHE_SECONDS
    return list(_labels_cache["labels"])


# Request handling ---------------------------------------------------------------------------


def reviewer(event):
    """Returns the caller's user ID and name from the token claims that API Gateway checked."""
    authorizer = (event.get("requestContext") or {}).get("authorizer") or {}
    claims = (authorizer.get("jwt") or {}).get("claims") or {}
    reviewer_id = claims.get("sub")
    if not reviewer_id:
        raise ApiError(401, "Unauthorized", "Sign in to review images.")
    groups = claims.get("cognito:groups") or []
    if isinstance(groups, str):
        # HTTP APIs pass a list claim as one string, such as "[reviewers admins]".
        groups = [group for group in re.split(r"[\s,]+", groups.strip("[]")) if group]
    if REVIEWER_GROUP not in groups:
        raise ApiError(403, "Forbidden", f"Your user isn't in the {REVIEWER_GROUP} group.")
    name = claims.get("username") or claims.get("cognito:username") or claims.get("email") or reviewer_id
    return reviewer_id, name


def path_task_id(event):
    task_id = (event.get("pathParameters") or {}).get("taskId") or ""
    if not TASK_ID_PATTERN.match(task_id):
        raise ApiError(400, "InvalidTaskId", "The task ID isn't valid.")
    return task_id


def request_body(event):
    body = event.get("body") or ""
    try:
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as error:
        raise ApiError(400, "InvalidBody", "The request body isn't valid.") from error
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise ApiError(400, "InvalidBody", "The request body is too large.")
    try:
        parsed = json.loads(body) if body else {}
    except ValueError as error:
        raise ApiError(400, "InvalidBody", "The request body isn't valid JSON.") from error
    if not isinstance(parsed, dict):
        raise ApiError(400, "InvalidBody", "The request body must be a JSON object.")
    return parsed


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body),
    }


# Helpers ------------------------------------------------------------------------------------


def task_key(task_id):
    return {"DetectLabelRequestId": {"S": task_id}}


def item_id(item):
    return text(item, "DetectLabelRequestId")


def text(item, name):
    return (item.get(name) or {}).get("S", "")


def number(item, name):
    value = (item.get(name) or {}).get("N")
    return int(float(value)) if value is not None else 0


def iso(epoch_seconds):
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def error_code(error):
    return error.response.get("Error", {}).get("Code", "")


def log(action, **fields):
    # Never log task tokens or presigned URLs. Both work as credentials.
    LOG.info(json.dumps({"action": action, **fields}))
