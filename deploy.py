"""
Deployment configuration for memo generation flow
This creates a deployment that can be triggered by webhooks
"""

from hello import memo_generation

if __name__ == "__main__":
    # Create a deployment that runs on demand (triggered by webhooks/automations)
    # Using GitHub as the source repository
    memo_generation.from_source(
        source="https://github.com/s16vc/memos.git",
        entrypoint="hello.py:memo_generation",
    ).deploy(
        name="memo-generation-webhook",
        tags=["webhook", "memo-generation"],
        description="Memo generation flow triggered via webhooks",
        work_pool_name="mainPool",
    )
