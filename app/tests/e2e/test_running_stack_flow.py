import os

import pytest

from tests.e2e.test_compose_quickstart import main_flow, wait_ready


def test_main_flow_against_running_stack() -> None:
    url = os.getenv("NOTES_STACK_URL")
    if not url:
        pytest.skip("NOTES_STACK_URL is required for a running-stack acceptance test")
    wait_ready(url, timeout=120)
    main_flow(url)
