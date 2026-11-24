"""SigV4 request signing for MCP servers exposed through IAM-authenticated Lambda Function URLs."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import httpx2
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

from agent.config import AWS_REGION, MCP_IAM_AUTH


def make_mcp_client(target: Any) -> Client:
    """Client for one MCP server. URLs get SigV4 signing when MCP_IAM_AUTH is set."""
    if MCP_IAM_AUTH and isinstance(target, str):
        return Client(StreamableHttpTransport(target, auth=SigV4Auth(region=AWS_REGION)))
    return Client(target)


class SigV4Auth(httpx2.Auth):
    """Sign each outgoing MCP request with the caller's AWS credentials (service `lambda`).

    Credentials come from the default boto3 chain: the Lambda execution role when deployed,
    or a local profile or environment variables when run on a workstation.
    """

    requires_request_body = True

    def __init__(self, region: str, service: str = "lambda") -> None:
        self.region = region
        self.service = service

    def auth_flow(self, request: httpx2.Request) -> Generator[httpx2.Request, httpx2.Response, None]:
        import boto3
        from botocore.auth import SigV4Auth as BotocoreSigV4Auth
        from botocore.awsrequest import AWSRequest

        credentials = boto3.Session().get_credentials()
        if credentials is None:
            raise RuntimeError("No AWS credentials found for signing MCP requests.")

        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers={"Content-Type": request.headers.get("content-type", "application/json")},
        )
        BotocoreSigV4Auth(credentials.get_frozen_credentials(), self.service, self.region).add_auth(
            aws_request
        )

        for name, value in aws_request.headers.items():
            request.headers[name] = value
        yield request
