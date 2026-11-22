import hashlib

from app.services.s3 import sign_v4


def test_sigv4_matches_aws_documented_example():
    """AWS S3 docs, 'Example: GET Object' (examplebucket/test.txt, Range: bytes=0-9)."""
    auth = sign_v4(
        method="GET", path="/test.txt", query="", payload_hash=hashlib.sha256(b"").hexdigest(), region="us-east-1", service="s3",
        access_key="AKIAIOSFODNN7EXAMPLE", secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", amz_date="20130524T000000Z",
        headers={"host": "examplebucket.s3.amazonaws.com", "range": "bytes=0-9", "x-amz-content-sha256": hashlib.sha256(b"").hexdigest(), "x-amz-date": "20130524T000000Z"})
    assert auth.endswith("Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")
    assert "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date" in auth
    assert "Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request" in auth
