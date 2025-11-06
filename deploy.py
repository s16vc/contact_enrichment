"""
Deployment configuration for memo generation flow
This creates a deployment that can be triggered by webhooks
"""

from hello import contact_enrichment

if __name__ == "__main__":
    # Create a deployment that runs on demand (triggered by webhooks/automations)
    # Using GitHub as the source repository
    contact_enrichment.from_source(
        source="https://github.com/s16vc/contact_enrichment.git",
        entrypoint="hello.py:contact_enrichment",
    ).deploy(
        name="contact-enrichment-webhook",
        tags=["webhook", "contact-enrichment"],
        description="Contact enrichment flow triggered via webhooks",
        work_pool_name="mainPool",
    )
