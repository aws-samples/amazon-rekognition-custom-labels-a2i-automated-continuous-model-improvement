"""The review portal (H3): Cognito sign-in, the HTTP API in front of the review API function,
and the review page, served from a private S3 bucket through CloudFront.

The resources reference each other in one direction only, so there's no dependency loop:
HTTP API -> CloudFront -> user pool and app client -> JWT authorizer -> routes.
"""
import json
from pathlib import Path

from aws_cdk import (
    Aws,
    Duration,
    Fn,
    RemovalPolicy,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_authorizers as authorizers,
    aws_apigatewayv2_integrations as integrations,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
    custom_resources as cr,
)
from constructs import Construct

PAGE_DIR = Path(__file__).parent / "portal_page"
PAGE_FILES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "app.css": "text/css; charset=utf-8",
}
API_ROUTES = ("/api/tasks/claim", "/api/tasks/{taskId}/submit", "/api/tasks/{taskId}/release")


class ReviewPortal(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        review_api: lambda_.IFunction,
        images_bucket: s3.IBucket,
        reviewer_group: str,
        first_reviewer_email: str,
        name_suffix: str,
        log_group: logs.ILogGroup,
        test_sign_in: bool = False,
        web_acl_arn: str | None = None,
    ) -> None:
        super().__init__(scope, construct_id)
        stack_name = Aws.STACK_NAME

        # HTTP API. Its routes are added after the app client exists.
        self.http_api = apigw.HttpApi(
            self,
            "Api",
            description="Review portal API. CloudFront forwards /api/* requests here.",
            create_default_stage=True,
        )
        # Limits each route to 10 requests per second, with bursts of 20.
        self.http_api.default_stage.node.default_child.add_property_override(
            "DefaultRouteSettings", {"ThrottlingRateLimit": 10, "ThrottlingBurstLimit": 20}
        )

        # The page's bucket. Only CloudFront can read it.
        page_bucket = s3.Bucket(
            self,
            "PageBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Security headers for the page and the API. The page loads images from the images
        # bucket with presigned URLs, and calls Cognito to exchange the sign-in code for tokens.
        cognito_domain_prefix = Fn.join("-", ["review", name_suffix])
        cognito_origin = Fn.join("", ["https://", cognito_domain_prefix, ".auth.", Aws.REGION, ".amazoncognito.com"])
        images_origin = Fn.join("", ["https://", images_bucket.bucket_name, ".s3.", Aws.REGION, ".amazonaws.com"])
        csp = Fn.join(
            "",
            [
                "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' ",
                images_origin,
                "; connect-src 'self' ",
                cognito_origin,
                "; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            ],
        )
        headers = cloudfront.ResponseHeadersPolicy(
            self,
            "SecurityHeaders",
            comment="Security headers for the review portal",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                content_security_policy=cloudfront.ResponseHeadersContentSecurityPolicy(
                    content_security_policy=csp, override=True
                ),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.DENY, override=True
                ),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=cloudfront.HeadersReferrerPolicy.NO_REFERRER, override=True
                ),
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(365), include_subdomains=True, override=True
                ),
            ),
        )

        api_domain = Fn.select(2, Fn.split("/", self.http_api.api_endpoint))
        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment=f"Review portal for {construct_id}",
            default_root_object="index.html",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            http_version=cloudfront.HttpVersion.HTTP2_AND_3,
            web_acl_id=web_acl_arn,
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(page_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                response_headers_policy=headers,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(api_domain, protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    response_headers_policy=headers,
                )
            },
        )
        self.portal_url = Fn.join("", ["https://", self.distribution.distribution_domain_name, "/"])

        # Reviewers sign in with Cognito's managed login pages. Only administrators add users.
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True),
            sign_in_case_sensitive=False,
            standard_attributes=cognito.StandardAttributes(email=cognito.StandardAttribute(required=True, mutable=True)),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(otp=True, sms=False, email=False),
            password_policy=cognito.PasswordPolicy(min_length=12, temp_password_validity=Duration.days(7)),
            user_invitation=cognito.UserInvitationConfig(
                email_subject="Your reviewer account for the image review portal",
                email_body=Fn.join(
                    "",
                    [
                        "You've been added as a reviewer. Sign in at ",
                        self.portal_url,
                        " with the user name {username} and the temporary password {####}. "
                        "You'll choose a new password when you first sign in. The temporary password expires in 7 days.",
                    ],
                ),
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        cognito.UserPoolGroup(
            self,
            "Reviewers",
            user_pool=self.user_pool,
            group_name=reviewer_group,
            description="Users who can claim and label review tasks",
        )

        self.client = self.user_pool.add_client(
            "PortalClient",
            generate_secret=False,
            # The admin flow lets a test script get tokens with IAM credentials. It's off unless the
            # stack is deployed with -c reviewerTestSignIn=true.
            auth_flows=cognito.AuthFlow(admin_user_password=test_sign_in),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callback_urls=[self.portal_url],
                logout_urls=[self.portal_url],
            ),
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
            prevent_user_existence_errors=True,
            enable_token_revocation=True,
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.hours(12),
        )
        domain = self.user_pool.add_domain(
            "Domain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=cognito_domain_prefix),
            managed_login_version=cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN,
        )
        # Managed login needs a style for each app client. This one uses Cognito's default look.
        branding = cognito.CfnManagedLoginBranding(
            self,
            "LoginBranding",
            user_pool_id=self.user_pool.user_pool_id,
            client_id=self.client.user_pool_client_id,
            use_cognito_provided_values=True,
        )
        branding.node.add_dependency(domain)

        # The first reviewer is the notification email address. Cognito emails the invitation.
        first_reviewer = cognito.CfnUserPoolUser(
            self,
            "FirstReviewer",
            user_pool_id=self.user_pool.user_pool_id,
            username=first_reviewer_email,
            desired_delivery_mediums=["EMAIL"],
            user_attributes=[
                cognito.CfnUserPoolUser.AttributeTypeProperty(name="email", value=first_reviewer_email),
                cognito.CfnUserPoolUser.AttributeTypeProperty(name="email_verified", value="true"),
            ],
        )
        attachment = cognito.CfnUserPoolUserToGroupAttachment(
            self,
            "FirstReviewerGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name=reviewer_group,
            username=first_reviewer_email,
        )
        attachment.node.add_dependency(first_reviewer)
        attachment.node.add_dependency(self.node.find_child("Reviewers"))

        # Routes. API Gateway checks the access token before the function runs.
        authorizer = authorizers.HttpUserPoolAuthorizer(
            "ReviewerAuthorizer", self.user_pool, user_pool_clients=[self.client]
        )
        integration = integrations.HttpLambdaIntegration("ReviewApi", review_api)
        for path in API_ROUTES:
            self.http_api.add_routes(
                path=path, methods=[apigw.HttpMethod.POST], integration=integration, authorizer=authorizer
            )

        # The page files. CDK's built-in custom resource writes them, so no extra Lambda function
        # is needed, and it deletes them when the stack is deleted.
        config = {
            "region": Aws.REGION,
            "clientId": self.client.user_pool_client_id,
            "cognitoDomain": cognito_origin,
            "redirectUri": self.portal_url,
        }
        files = {name: (PAGE_DIR / name).read_text() for name in PAGE_FILES}
        files["config.json"] = Fn.to_json_string(config)
        content_types = {**PAGE_FILES, "config.json": "application/json"}
        for name, body in files.items():
            put = cr.AwsSdkCall(
                service="S3",
                action="putObject",
                parameters={
                    "Bucket": page_bucket.bucket_name,
                    "Key": name,
                    "Body": body,
                    "ContentType": content_types[name],
                    "CacheControl": "no-cache",
                },
                physical_resource_id=cr.PhysicalResourceId.of(f"page-{name}"),
            )
            cr.AwsCustomResource(
                self,
                f"Page{name.replace('.', '').title()}",
                on_create=put,
                on_update=put,
                on_delete=cr.AwsSdkCall(
                    service="S3",
                    action="deleteObject",
                    parameters={"Bucket": page_bucket.bucket_name, "Key": name},
                ),
                policy=cr.AwsCustomResourcePolicy.from_statements(
                    [
                        iam.PolicyStatement(
                            actions=["s3:PutObject", "s3:DeleteObject"],
                            resources=[page_bucket.arn_for_objects(name)],
                        )
                    ]
                ),
                install_latest_aws_sdk=False,
                log_group=log_group,
            )
