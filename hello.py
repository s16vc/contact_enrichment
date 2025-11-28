import os
import json
import re
from typing import Optional, Dict, Any
from prefect import flow, task
from openai import OpenAI
from dotenv import load_dotenv
from pyairtable import Api
from prompts import SYSTEM_PROMPTS, MODEL_CONFIG
import requests
import textwrap

# Load environment variables from .env file
load_dotenv()


def generate_text(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    model: str = "openai/gpt-4o",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Reusable helper function to generate text using OpenRouter API.

    Args:
        user_prompt: The user message/question to send to the model
        system_prompt: Optional system prompt to guide the model's behavior
        model: The model to use (default: openai/gpt-4o)
        temperature: Sampling temperature (default: 0.7)
        max_tokens: Maximum tokens to generate (optional)

    Returns:
        Generated text from the model
    """
    # Get API key from environment variable
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set")

    # Remove 'Bearer ' prefix if present and clean quotes
    # api_key = api_key.replace("Bearer ", "").strip().strip('"')

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": user_prompt})

    completion_params = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }

    if max_tokens:
        completion_params["max_tokens"] = max_tokens

    completion = client.chat.completions.create(**completion_params)
    return completion.choices[0].message.content


@task(name="Linkedin Profile", retries=2, retry_delay_seconds=300)
def get_linkedin_profil(profil_url: str):
    req_url = f"https://fresh-linkedin-profile-data.p.rapidapi.com/enrich-lead?linkedin_url={profil_url}&include_skills=false&include_certifications=false&include_publications=false&include_honors=false&include_volunteers=false&include_projects=false&include_patents=false&include_courses=false&include_organizations=false&include_profile_status=false&include_company_public_url=false"
    try:
        response = requests.get(
            req_url,
            headers={
                "Content-Type": "application/json",
                "x-rapidapi-host": "fresh-linkedin-profile-data.p.rapidapi.com",
                "x-rapidapi-key": os.getenv("RAPID_API_KEY"),
            },
        )
        data = response.json()
        print(data)
        return data
    except requests.exceptions.RequestException as e:
        raise


@task(name="Linkedin Posts", retries=2, retry_delay_seconds=300)
def get_linkedin_posts(profil_url: str):
    req_url = f"https://fresh-linkedin-profile-data.p.rapidapi.com/get-profile-posts?linkedin_url={profil_url}&type=posts"
    try:
        response = requests.get(
            req_url,
            headers={
                "Content-Type": "application/json",
                "x-rapidapi-host": "fresh-linkedin-profile-data.p.rapidapi.com",
                "x-rapidapi-key": os.getenv("RAPID_API_KEY"),
            },
        )
        data = response.json()
        print(data)
        return data
    except requests.exceptions.RequestException as e:
        raise


def prompt_profil_comparison(
    data: Dict[str, Any], profil_data: Dict[str, Any], profil_posts: Dict[str, Any]
) -> Dict[str, Any]:
    import json

    # Old profile from trigger event - safely access fields with defaults
    fields = data.get("fields", {})
    old_profil = {
        "name": fields.get("Name", ""),
        "desc": fields.get("Description", ""),
        "company": fields.get("Companies", []),
        "title": fields.get("Title", ""),
    }

    # Current profile from LinkedIn - safely access nested data
    # Handle case where data might be None
    profile_data = profil_data.get("data") or {}
    current_profil = {
        "name": profile_data.get("full_name", ""),
        "desc": profile_data.get("about", ""),
        "company": profile_data.get("company", ""),
        "title": profile_data.get("headline", ""),
        "recentPosts": profil_posts,  # Already a list of posts
    }

    # System prompt describing the task
    system_prompt = """
    You are an expert in LinkedIn profile analysis. Your task is to analyse an old profile and a new profile 
    and tell if the profile needs to be updated in light of the new information.
    We do not care about subtle differences, we care about key changes:
    - new position
    - new company

    You will be provided with the old profile and the new profile. Furthermore, you will be provided with recent posts. 
    Those are less important but still hold interesting information that can help.

    You will respond in JSON format.
    Here is the format of the response

    {
    "toUpdate": <true/false>,
    "reason": <reason>
    }
    """

    # User prompt with the profiles
    user_prompt = f"""
    Old profile: {json.dumps(old_profil)}
    Current profile: {json.dumps(current_profil)}
    """

    # Return messages in the format for a chat model
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return messages


def extract_json_from_response(response: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from LLM response that may contain markdown code blocks.

    Args:
        response: The LLM response string that may contain JSON in markdown code blocks

    Returns:
        Parsed JSON as a dictionary

    Raises:
        ValueError: If no valid JSON is found in the response
    """
    # Try to find JSON in markdown code block (```json ... ```)
    json_match = re.search(r"```json\s*\n(.*?)\n```", response, re.DOTALL)

    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON in plain code block (``` ... ```)
        json_match = re.search(r"```\s*\n(.*?)\n```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Assume the entire response is JSON
            json_str = response.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON from response: {e}\nResponse: {response}"
        )


@task(name="Compare Profiles", retries=2, retry_delay_seconds=30)
def does_profile_need_update(prompts: Any) -> Dict[str, Any]:
    """
    Compare LinkedIn profiles and return structured JSON result.

    Args:
        prompts: List of message dictionaries with system and user prompts

    Returns:
        Parsed JSON dictionary with toUpdate and reason fields
    """
    system_prompt = prompts[0]["content"]
    user_prompt = prompts[1]["content"]
    result = generate_text(
        user_prompt, system_prompt=system_prompt, model="openai/gpt-4o"
    )

    # Parse the JSON from the LLM response
    parsed_result = extract_json_from_response(result)
    print(f"Parsed comparison result: {parsed_result}")

    return parsed_result.get("toUpdate")


@task(name="Update Airtable Record", retries=2, retry_delay_seconds=30)
def update_at_record(record_id: str, description: str, headline: str) -> None:
    """
    Update an Airtable record with the new description.

    Args:
        record_id: The Airtable record ID to update
        description: The new description text to set
    """
    if not record_id:
        print("No record_id provided, skipping Airtable update")
        return

    # Get Airtable credentials from environment
    api_key = os.getenv("AIRTABLE_API_KEY")
    base_id = "app18YWzPlAFs2umJ"
    table_name = "tblIkmDFlC91L9EHi"

    print(f"api_key: {api_key}, base_id: {base_id}, table_name: {table_name}")

    if not all([api_key, base_id, table_name]):
        raise ValueError(
            "Missing Airtable configuration. Please set AIRTABLE_API_KEY, "
            "AIRTABLE_BASE_ID, and AIRTABLE_TABLE_NAME in your .env file"
        )

    try:
        # Initialize the Airtable API and get the table
        api = Api(api_key)
        table = api.table(base_id, table_name)

        # Update the record with the new description
        table.update(
            record_id, {"Description": description, "Enriched": True, "Title": headline}
        )

        print(f"Successfully updated Airtable record {record_id}")
    except Exception as e:
        print(f"Error updating Airtable record: {e}")
        raise


@task(name="Mark Record as Enriched", retries=2, retry_delay_seconds=30)
def mark_as_enriched(record_id: str, reason: str = "Skipped") -> None:
    """
    Mark an Airtable record as enriched without updating description.
    Used when enrichment is skipped (no LinkedIn URL, profile not found, etc.)

    Args:
        record_id: The Airtable record ID to update
        reason: Reason why enrichment was skipped
    """
    if not record_id:
        print("No record_id provided, skipping Airtable update")
        return

    # Get Airtable credentials from environment
    api_key = os.getenv("AIRTABLE_API_KEY")
    base_id = "app18YWzPlAFs2umJ"
    table_name = "tblIkmDFlC91L9EHi"

    if not all([api_key, base_id, table_name]):
        raise ValueError(
            "Missing Airtable configuration. Please set AIRTABLE_API_KEY, "
            "AIRTABLE_BASE_ID, and AIRTABLE_TABLE_NAME in your .env file"
        )

    try:
        # Initialize the Airtable API and get the table
        api = Api(api_key)
        table = api.table(base_id, table_name)

        # Mark as enriched with reason
        table.update(record_id, {"Enriched": True})

        print(f"Successfully marked record {record_id} as enriched (Reason: {reason})")
    except Exception as e:
        print(f"Error marking Airtable record as enriched: {e}")
        raise


@task(name="Send Telegram Notification", retries=1, retry_delay_seconds=30)
def send_telegram_notification(profil_data: object) -> None:
    """
    Send a notification to Telegram with the enriched profile data.
    """

    try:
        response = requests.post(
            "https://eoar54g1zm8upvr.m.pipedream.net",
            json={"profil_data": profil_data},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        print(
            f"Successfully sent Telegram notification. Status: {response.status_code}"
        )
    except requests.exceptions.RequestException as e:
        print(f"Error resuming Pipedream workflow: {e}")
        raise


@flow(name="Contact Enrichment Flow", log_prints=True)
def contact_enrichment(
    data: Optional[object] = None,
):
    """ """
    # Use provided data or fall back to defaults
    _data = data or {}

    import urllib.parse

    print(f"data: {_data}")

    # Safely access nested fields
    fields = _data.get("fields", {})
    linkedin_url = fields.get("LinkedIn", "")
    record_id = _data.get("id", "")

    if not linkedin_url:
        print("No LinkedIn URL provided, cannot enrich contact")
        if record_id:
            mark_as_enriched(record_id, "No LinkedIn URL")
        return

    profil_url = urllib.parse.quote(linkedin_url, safe=":/?&=")
    print(profil_url)
    profil_data = get_linkedin_profil(profil_url)
    profil_posts = get_linkedin_posts(profil_url)

    # Check if profile data was successfully retrieved
    if not profil_data or profil_data.get("data") is None:
        error_message = (
            profil_data.get("message", "Unknown error")
            if profil_data
            else "No response"
        )
        print(f"LinkedIn profile not found or unavailable: {error_message}")
        print("Skipping contact enrichment for this profile")
        if record_id:
            mark_as_enriched(record_id, f"Profile not found: {error_message}")
        return

    # weekly posts
    from datetime import datetime, timedelta

    # Calculate the date for one week ago
    one_week_ago = datetime.now() - timedelta(days=7)

    # Filter and map recent posts from the last 7 days
    # Handle case where data might be None
    posts_data = profil_posts.get("data") or []
    recent_posts = [
        {"article_title": item.get("article_title"), "text": item.get("text")}
        for item in posts_data
        if item.get("posted")
        and datetime.strptime(item["posted"], "%Y-%m-%d %H:%M:%S") >= one_week_ago
    ]

    prompts = prompt_profil_comparison(data, profil_data, recent_posts)
    needs_update = does_profile_need_update(prompts)
    print(f"needs_update: {needs_update}")

    if needs_update:
        # Safely get profile about section
        profile_about = profil_data.get("data", {}).get(
            "about", "No description available"
        )

        # formatting - safely handle experiences
        profile_data = profil_data.get("data", {})
        experiences = profile_data.get("experiences", [])

        history = ""
        if experiences:
            history = "\n".join(
                [
                    f"""\
{textwrap.dedent(exp.get("company", "")).strip()}
{textwrap.dedent(exp.get("title", "")).strip()}
{textwrap.dedent(exp.get("date_range", "")).strip()}
{textwrap.dedent(exp.get("description", "")).strip()}
            """
                    for exp in experiences
                ]
            ).rstrip()

        formatted_description = (
            f"{textwrap.dedent(profile_about).strip() if profile_about else ''}"
            f"\n\n"
            f"{textwrap.dedent(history).strip() if history else ''}"
        )

        print(formatted_description)

        # update record in airtable
        if record_id:
            update_at_record(
                record_id, formatted_description, profile_data.get("headline", "")
            )
            # add profile updated flag true
            send_telegram_notification(profil_data)
        else:
            print("No record ID provided, skipping Airtable update")


if __name__ == "__main__":
    data = {
        "id": "recJl2u923ejqLY5f",
        "createdTime": "2023-03-20T08:10:14.000Z",
        "fields": {
            "Name": "Camille Ricketts",
            "Description": "Mixing Board: Unlike established expert networks where you can tap the expertise of individuals across a vast range of subject matter, the power of Mixing Board is the combined perspective and expertise of an expert community that has been curated to provide complementary skills and experiences.\n",
            "Company": ["rec3V5bEWhFToZh2j", "recL9Esi2ai5MEidv"],
            "LinkedIn": "https://www.linkedin.com/in/camillericketts/",
            "Created by": {
                "id": "usrFVFTcTYVu5SMre",
                "email": "trangtrishpham@gmail.com",
                "name": "Thanh Trang Pham",
            },
            "Type": ["Advisor"],
            "4. *City": ["rec0FHw7d588iEyoB"],
            "*Country": ["rec7U48red8LvVEbs"],
            "Title": "Mixing Board Member",
            "nameFromCompany": ["Mixing Board", "Notion"],
            "recordid": "recJl2u923ejqLY5f",
            "Created time": "2023-03-20T08:10:14.000Z",
            "Last Modified Time": "2025-08-01T12:43:11.000Z",
            "CopyType": ["recB27dvXwfEYuH0z"],
            "Number of Events Attended": 0,
            "Name Rollup (from Events Attended)": 0,
            "test": [],
            "CNT Deals brought": 0,
            "Featured in advisory": 0,
            "City": ["San Francisco"],
            "Companies": ["Mixing Board", "Notion"],
            "creationDate": "2023-03-20T08:10:14.000Z",
        },
    }
    contact_enrichment(data)
