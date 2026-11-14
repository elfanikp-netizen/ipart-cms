import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.routers.runs import create_run


class RunIdempotencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_request_returns_existing_run_without_reprocessing_upload(self) -> None:
        existing_run = SimpleNamespace(id=42)
        database = MagicMock()
        database.scalar.return_value = existing_run
        user = SimpleNamespace(id=7)
        upload = MagicMock()

        with patch("app.routers.runs.to_out", return_value={"id": 42}) as serialize:
            result = await create_run(
                crawler_id="missing-crawler",
                file=upload,
                idempotency_key="same-request-key",
                db=database,
                user=user,
            )

        self.assertEqual(result, {"id": 42})
        serialize.assert_called_once_with(existing_run, user)
        database.scalar.assert_called_once()
        database.add.assert_not_called()
        upload.read.assert_not_called()
