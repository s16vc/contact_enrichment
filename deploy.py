"""
Deployment configuration for memo generation flow
This creates a deployment that can be triggered by webhooks
"""

from dotenv import load_dotenv
from hello import contact_enrichment
import os

load_dotenv()

if __name__ == "__main__":
    # Create a deployment that runs on demand (triggered by webhooks/automations)
    # Using GitHub as the source repository

    airtable_key = os.getenv("AIRTABLE_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    rapid_key = os.getenv("RAPID_API_KEY")

    contact_enrichment.from_source(
        source="https://github.com/s16vc/contact_enrichment.git",
        entrypoint="hello.py:contact_enrichment",
    ).deploy(
        name="contact-enrichment-webhook",
        tags=["webhook", "contact-enrichment"],
        description="Contact enrichment flow triggered via webhooks",
        work_pool_name="mainPool",
        job_variables={
            "env": {
                "OPENROUTER_API_KEY": openrouter_key,  # Pass the actual value
                "RAPID_API_KEY": rapid_key,
                "AIRTABLE_API_KEY": airtable_key,
            }
        },
    )
