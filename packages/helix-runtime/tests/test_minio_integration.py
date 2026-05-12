"""Integration tests for :class:`S3CompatibleObjectStore` against MinIO.

Boots the same ``infra/docker-compose.yml`` stack used by the PgBouncer
integration test and exercises the real aiobotocore code path.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from testcontainers.compose import DockerCompose

from helix_agent.runtime.storage import (
    ObjectNotFoundError,
    S3CompatibleConfig,
    make_object_store,
)

pytestmark = pytest.mark.integration

_INFRA_DIR = Path(__file__).resolve().parents[3] / "infra"


@pytest.fixture(scope="module")
def compose_stack() -> DockerCompose:
    """Bring up the dev stack for the module's lifetime."""
    stack = DockerCompose(
        context=str(_INFRA_DIR),
        compose_file_name="docker-compose.yml",
        pull=True,
        wait=True,
    )
    with stack:
        yield stack


def _config(stack: DockerCompose) -> S3CompatibleConfig:
    host, port_str = stack.get_service_host_and_port("minio", 9000)
    user = os.environ.get("HELIX_MINIO_ROOT_USER", "helix_agent")
    password = os.environ.get("HELIX_MINIO_ROOT_PASSWORD", "helix_agent_dev_minio")
    bucket = os.environ.get("HELIX_MINIO_BUCKET", "helix-agent-dev")
    return S3CompatibleConfig(
        endpoint_url=f"http://{host}:{port_str}",
        region="us-east-1",
        bucket=bucket,
        access_key=user,
        secret_key=password,
        use_path_style=True,
    )


@pytest.mark.asyncio
async def test_put_get_delete_round_trip(compose_stack: DockerCompose) -> None:
    config = _config(compose_stack)
    payload = b"hello world"

    async with make_object_store("s3-compatible", config) as store:
        await store.put("t1/uploads/hello.txt", payload, content_type="text/plain")
        assert await store.get("t1/uploads/hello.txt") == payload

        await store.delete("t1/uploads/hello.txt")
        with pytest.raises(ObjectNotFoundError):
            await store.get("t1/uploads/hello.txt")


@pytest.mark.asyncio
async def test_list_prefix(compose_stack: DockerCompose) -> None:
    config = _config(compose_stack)
    async with make_object_store("s3-compatible", config) as store:
        await store.put("list-prefix/a.txt", b"a")
        await store.put("list-prefix/b.txt", b"b")
        await store.put("other/c.txt", b"c")

        listed = await store.list_prefix("list-prefix/")
        assert "list-prefix/a.txt" in listed
        assert "list-prefix/b.txt" in listed
        assert all(k.startswith("list-prefix/") for k in listed)


@pytest.mark.asyncio
async def test_presigned_url_format(compose_stack: DockerCompose) -> None:
    config = _config(compose_stack)
    async with make_object_store("s3-compatible", config) as store:
        url = await store.presigned_url("t1/uploads/foo.txt", expires_in=60)
        # Pre-signed URLs always carry an X-Amz-Signature query param under
        # SigV4; this is the cheapest assertion that signing actually ran.
        assert "X-Amz-Signature" in url


@pytest.mark.asyncio
async def test_delete_missing_is_idempotent(compose_stack: DockerCompose) -> None:
    config = _config(compose_stack)
    async with make_object_store("s3-compatible", config) as store:
        # Must not raise; ObjectStore contract.
        await store.delete("definitely-missing-key")
