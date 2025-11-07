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


@task(name="Resume Pipedream Workflow", retries=3, retry_delay_seconds=10)
def resume_pipedream(record_id: str, final_text: str) -> None:
    """
    Send the final generated text to the Pipedream resume URL to continue the workflow.

    Args:
        record_id: The Airtable record ID to fetch the resume URL
        final_text: The final generated memo text to send back
    """
    if not record_id:
        print("No record_id provided, skipping Pipedream workflow resume")
        return

    try:
        response = requests.post(
            "https://eo3ph3sbyg22xc7.m.pipedream.net",
            json={"final_memo": final_text, "record_id": record_id},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        print(
            f"Successfully resumed Pipedream workflow. Status: {response.status_code}"
        )
    except requests.exceptions.RequestException as e:
        print(f"Error resuming Pipedream workflow: {e}")
        raise


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
        # return {
        #     "data": {
        #         "about": (
        #             "Accomplished CEO, business executive, and entrepreneur with an exceptional track "
        #             "record of P&L ownership, driving fiscally responsible business operations, and "
        #             "achieving remarkable growth and customer success.\n\nA proven leader and mentor, "
        #             "I am passionate about guiding the next generation of tech entrepreneurs to reach "
        #             "their full potential."
        #         ),
        #         "city": "Huntington Beach",
        #         "company": None,
        #         "company_description": None,
        #         "company_domain": "",
        #         "company_employee_count": None,
        #         "company_employee_range": None,
        #         "company_industry": None,
        #         "company_linkedin_url": None,
        #         "company_logo_url": None,
        #         "company_website": None,
        #         "company_year_founded": None,
        #         "connection_count": 4562,
        #         "country": "United States",
        #         "current_company_join_month": None,
        #         "current_company_join_year": None,
        #         "current_job_duration": "",
        #         "educations": [],
        #         "email": "",
        #         "experiences": [],
        #         "first_name": "Brent",
        #         "follower_count": 5281,
        #         "full_name": "Brent Hayward",
        #         "headline": "Head of Competitive Intelligence, Salesforce",
        #         "hq_city": None,
        #         "hq_country": None,
        #         "hq_region": None,
        #         "is_creator": False,
        #         "is_influencer": False,
        #         "is_premium": False,
        #         "is_verified": True,
        #         "job_title": None,
        #         "languages": [],
        #         "last_name": "Hayward",
        #         "linkedin_url": "https://www.linkedin.com/in/brenthayward/",
        #         "location": "Huntington Beach, California, United States",
        #         "phone": "",
        #         "profile_id": "8613225",
        #         "profile_image_url": (
        #             "https://media.licdn.com/dms/image/v2/D4D03AQEqybBivFdZtQ/profile-displayphoto-"
        #             "shrink_800_800/profile-displayphoto-shrink_800_800/0/1715269992354?"
        #             "e=1764201600&v=beta&t=5GYp7Cjbf8-Dhr8Fd60yO2RvRjUgW6m_YV7zSxHRPwU"
        #         ),
        #         "public_id": "brenthayward",
        #         "school": "",
        #         "state": "California",
        #         "urn": "ACoAAACDbWkB8KJrVGkdxL9H-10JuniQwgRE9xk",
        #     },
        #     "message": "ok",
        # }
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
        # return {
        #     "data": [
        #         {
        #             "attributes": [
        #                 {
        #                     "first": "Joe",
        #                     "headline": "General Partner at 8VC",
        #                     "last": "Lonsdale",
        #                     "public_id": "jtlonsdale",
        #                     "type": "profile",
        #                     "urn": "ACoAAAAWNzEBFz86iNKBrSdxjEOkqpZZvV76vQs",
        #                 },
        #                 {
        #                     "company_id": "10317593",
        #                     "name": "8VC",
        #                     "public_id": "8vc",
        #                     "type": "company",
        #                 },
        #                 {
        #                     "first": "Eric",
        #                     "headline": "CEO at Addepar - We're Hiring!!",
        #                     "last": "Poirier",
        #                     "public_id": "epoirier",
        #                     "type": "profile",
        #                     "urn": "ACoAAABCAiABfXPQjNQTuUuuw69IMo8VZhPQ1M4",
        #                 },
        #                 {
        #                     "company_id": "705598",
        #                     "name": "Addepar",
        #                     "public_id": "addepar",
        #                     "type": "company",
        #                 },
        #                 {
        #                     "first": "Brent",
        #                     "headline": "Head of Competitive Intelligence, Salesforce",
        #                     "last": "Hayward",
        #                     "public_id": "brenthayward",
        #                     "type": "profile",
        #                     "urn": "ACoAAACDbWkB8KJrVGkdxL9H-10JuniQwgRE9xk",
        #                 },
        #                 {
        #                     "company_id": "3185",
        #                     "name": "Salesforce",
        #                     "public_id": "salesforce",
        #                     "type": "company",
        #                 },
        #                 {
        #                     "first": "David",
        #                     "headline": "Vice President and CTO for Strategic Incubations at Microsoft | Author, O'Reilly's \"The AI Organization\"",
        #                     "last": "Carmona",
        #                     "public_id": "david-carmona",
        #                     "type": "profile",
        #                     "urn": "ACoAAACwKUUBaMp5tJwkp-qLN2ctY8lCJCZZIqE",
        #                 },
        #                 {
        #                     "company_id": "1035",
        #                     "name": "Microsoft",
        #                     "public_id": "microsoft",
        #                     "type": "company",
        #                 },
        #             ],
        #             "images": [],
        #             "num_comments": 3,
        #             "num_empathy": 3,
        #             "num_interests": 2,
        #             "num_likes": 127,
        #             "num_praises": 12,
        #             "num_reactions": 144,
        #             "num_reposts": 21,
        #             "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7204773567891173377/",
        #             "posted": "2024-06-07 09:17:56",
        #             "poster_linkedin_url": "https://www.linkedin.com/company/hgcapital",
        #             "repost_stats": {
        #                 "num_appreciations": 0,
        #                 "num_comments": 3,
        #                 "num_empathy": 0,
        #                 "num_interests": 4,
        #                 "num_likes": 71,
        #                 "num_maybe": 0,
        #                 "num_praises": 7,
        #                 "num_reactions": 82,
        #                 "num_reposts": 2,
        #             },
        #             "repost_urn": "7207385164815945728",
        #             "reposted": "2024-06-14 14:15:30",
        #             "reshared": True,
        #             "resharer_comment": "It was great to speak with so many like-minded leaders at the Hg Capital Leadership conference last week and thank you for the great questions and quality of the debate. Some post conference thoughts:\n\n1) The speed of change in the generative AI field is actually increasing, and no one can afford to sit on the sidelines. Companies need to address how generative AI changes both their internal operations and external products/services.\n\n2) To be successful, generative AI projects need to be integrated into the flow of day-to-day work. This allows you to bring relevant context to enhance the quality of any response - and metadata matters!  And as the early wave of consumer AI starts to merge with business AI, nothing is more important than trust.\n\n3) Generative AI projects need exec sponsorship and a business value case first - they are too important to sit as a pilot/POC with no outcome in mind.  Every great experiment starts with a discovery in mind, or a hypothesis to be proven or disproven. \n\nThank you Christopher Kindt, Sebastien Briens, Jason Richards, Lucio Di Ciaccio, Matthew Brockman for the invitation to speak and your hospitality. Special thanks to Polly Dean, and everyone at team Hg for the organizing and logistics.",
        #             "text": "Today wraps our Software Leadership Gathering 2024! This year brought an even larger congregation of 120+ specially selected transatlantic leaders, who all stepped away from their day-to-day to engage in our annual retreat to discuss the shifting ‘techtonics’ impacting our industry.\n \nThe quality of discussion and value of expertise shared this year was outstanding - leaders from inside and outside of the Hg ecosystem taking on the world of fast-evolving technology. \n \nA special thank you to our speakers Joe Lonsdale (8VC) and founder of several tech unicorns), Eric Poirier (Addepar), Brent Hayward (Salesforce), David Carmona (Microsoft), Nagraj Kashyap (Touring Capital), Jae  Sook Evans (Oracle), Raghu Raghuram (VMware), Morgan Housel (best-selling author) and special guest Massimo Bottura - one of Michelin’s most highly decorated chefs and owner of two-year best restaurant in the world.\n\nMore to come in the coming weeks, but these snippets open up a little of the quality of the discussion: \n \n- The billion-dollar playbook => if you want to build a $ billion company today, you need to look at what’s possible now, that wasn’t possible five years ago.\n \n- The greatest value that AI unlocks is in services => AI suddenly allows us to compete with decades-old services companies. This is where the next value creation and innovation wave is.\n \n- Innovation through an engineering-led culture =>The greatest technology happens when people ignore ROI. Keep the ‘adults’ separate from the innovators!\n \n- Step back from the GenAI hype-cycle => People tend to over-estimate the speed-of-change and underestimate long-term impact and scale-of-change.\n \n- Agentic models and ‘middleware’ in GenAI => Here lies the next wave of GenAI adoption, moving on from internal productivity and efficiency gains, and towards long term revenue growth.\n\n- Cloud evolution in response to data sovereignty =>  Data privacy is really at the core of what is important - customers want control over their data.\n\n- Applications will become intrinsically tied to LLMs => The app stack will fundamentally change over the next few years. \n\n- What doesn’t change => Focusing on the things that never change is the secret to really understand the future. \n \nTo everyone else who attended across the software ecosystem, we’ll see you again next year!\n\n#SLG2024 #shiftingtechtonics. \n \nFor the latest on Hg and portfolio news, subscribe to our monthly updates: https://lnkd.in/esXyfRAv",
        #             "time": "1 year ago",
        #             "urn": "7204773567891173377",
        #             "video": {
        #                 "duration": 106433,
        #                 "stream_url": "https://dms.licdn.com/playlist/vid/v2/D4E05AQETjwui8_am2A/mp4-720p-30fp-crf28/mp4-720p-30fp-crf28/0/1717751875741?e=1762912800&v=beta&t=3Ih3F51NOkcp-TggqdsPcTjVQbyyq7Kmgg20MxM0b74",
        #             },
        #         },
        #         {
        #             "attributes": [
        #                 {
        #                     "first": "Brent",
        #                     "headline": "Head of Competitive Intelligence, Salesforce",
        #                     "last": "Hayward",
        #                     "public_id": "brenthayward",
        #                     "type": "profile",
        #                     "urn": "ACoAAACDbWkB8KJrVGkdxL9H-10JuniQwgRE9xk",
        #                 }
        #             ],
        #             "images": [],
        #             "num_appreciations": 2,
        #             "num_comments": 1,
        #             "num_empathy": 6,
        #             "num_interests": 9,
        #             "num_likes": 266,
        #             "num_praises": 11,
        #             "num_reactions": 294,
        #             "num_reposts": 40,
        #             "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7071488498809135105/",
        #             "posted": "2023-06-05 14:10:40",
        #             "poster_linkedin_url": "https://www.linkedin.com/company/mulesoft",
        #             "repost_stats": {
        #                 "num_appreciations": 2,
        #                 "num_comments": 1,
        #                 "num_empathy": 6,
        #                 "num_interests": 9,
        #                 "num_likes": 266,
        #                 "num_maybe": 0,
        #                 "num_praises": 11,
        #                 "num_reactions": 294,
        #                 "num_reposts": 40,
        #             },
        #             "repost_urn": "7071488877013680128",
        #             "reposted": "2023-06-05 14:12:10",
        #             "reshared": True,
        #             "text": "1, 2, 3...automate! Brent Hayward shares three steps to drive intelligent automation in your business: https://muley.cc/45NGcG5",
        #             "time": "2 years ago",
        #             "urn": "7071488498809135105",
        #             "video": {
        #                 "duration": 30000,
        #                 "stream_url": "https://dms.licdn.com/playlist/vid/v2/D4D10AQHr5dOfnGoMlw/mp4-720p-30fp-crf28/mp4-720p-30fp-crf28/0/1685974224095?e=1762912800&v=beta&t=J51D6u4V3jQy5A8Yme7Go0XCJ9KxByfFslZ19lKyUkI",
        #             },
        #         },
        #         {
        #             "attributes": [
        #                 {
        #                     "company_id": "31354582",
        #                     "name": "Agentforce 360 Platform",
        #                     "public_id": "salesforce-platform",
        #                     "type": "company",
        #                 },
        #                 {
        #                     "first": "Brent",
        #                     "headline": "Head of Competitive Intelligence, Salesforce",
        #                     "last": "Hayward",
        #                     "public_id": "brenthayward",
        #                     "type": "profile",
        #                     "urn": "ACoAAACDbWkB8KJrVGkdxL9H-10JuniQwgRE9xk",
        #                 },
        #                 {
        #                     "first": "Marla",
        #                     "headline": "Senior Vice President, Product Management at Salesforce",
        #                     "last": "Hay ",
        #                     "public_id": "marlahay",
        #                     "type": "profile",
        #                     "urn": "ACoAAACP6okBf8YgWEaX31lS7QDKXo3G8hIhn4c",
        #                 },
        #                 {
        #                     "first": "Sarah",
        #                     "headline": "VP of Technology, AI (+ Machine Learning) at Intuit! Former Salesforce, Pivotal, PhD Biomedical Informatics, Stanford, SAIL (Stanford Artificial Intelligence Laboratory)",
        #                     "last": "Aerni",
        #                     "public_id": "sarahaerni",
        #                     "type": "profile",
        #                     "urn": "ACoAAAJ4YtQBqd6DpwxHTU_VIPWI5UD_KAI0Oig",
        #                 },
        #                 {
        #                     "first": "Sanjna",
        #                     "headline": "SVP of Product Marketing at Salesforce",
        #                     "last": "Parulekar",
        #                     "public_id": "sanjna-parulekar-0248a537",
        #                     "type": "profile",
        #                     "urn": "ACoAAAfI29wB9itqXFz_Okw_RnFfJ44r3wvI3H8",
        #                 },
        #                 {
        #                     "first": "Kreena",
        #                     "headline": "Director, Product Management at Salesforce (MuleSoft)",
        #                     "last": "Mehta",
        #                     "public_id": "kreenasmehta",
        #                     "type": "profile",
        #                     "urn": "ACoAABC-zdQBSIAVBk9pTX3PvuIE-CetJo7gjac",
        #                 },
        #             ],
        #             "document": {
        #                 "page_count": 3,
        #                 "title": "IT Keynote: Build Your Customer Company at WTNY",
        #                 "url": "https://media.licdn.com/dms/document/media/v2/D4E1FAQEZujDCzbJsaA/feedshare-document-url-metadata-scrapper-pdf/feedshare-document-url-metadata-scrapper-pdf/0/1682600524136?e=1762912800&v=beta&t=9FaDNO3smDXm0TNh6pKmiJfNikb8RqxtCWVV50OOEgs",
        #             },
        #             "images": [],
        #             "num_comments": 2,
        #             "num_likes": 68,
        #             "num_praises": 2,
        #             "num_reactions": 70,
        #             "num_reposts": 12,
        #             "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7057375355241652225/",
        #             "posted": "2023-04-27 15:30:04",
        #             "poster_linkedin_url": "https://www.linkedin.com/company/mulesoft",
        #             "repost_stats": {
        #                 "num_appreciations": 0,
        #                 "num_comments": 2,
        #                 "num_empathy": 0,
        #                 "num_interests": 0,
        #                 "num_likes": 68,
        #                 "num_maybe": 0,
        #                 "num_praises": 2,
        #                 "num_reactions": 70,
        #                 "num_reposts": 12,
        #             },
        #             "repost_urn": "7058828883910877184",
        #             "reposted": "2023-05-01 15:45:52",
        #             "reshared": True,
        #             "text": "MuleSoft 🤝 Salesforce Platform\nMaking it easier for you to deploy faster, increasing developer efficiency, and saving on IT costs by connecting your data, automating intelligent processes, and deploying securely. Tune into the IT Keynote at #SalesforceTour New York or on Salesforce+. Let’s unleash innovation together: https://muley.cc/3LxoOgK\n\nJoin Brent Hayward, Marla Hay, Sarah Aerni, Sanjna Parulekar, and Kreena Mehta to Build Your Customer Company.",
        #             "time": "2 years ago",
        #             "urn": "7057375355241652225",
        #         },
        #     ]
        # }
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
    profile_data = profil_data.get("data", {})
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
def update_at_record(record_id: str, description: str) -> None:
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
        table.update(record_id, {"Description": description})

        print(f"Successfully updated Airtable record {record_id}")
    except Exception as e:
        print(f"Error updating Airtable record: {e}")
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

    if not linkedin_url:
        print("No LinkedIn URL provided, cannot enrich contact")
        return

    profil_url = urllib.parse.quote(linkedin_url, safe=":/?&=")
    print(profil_url)
    profil_data = get_linkedin_profil(profil_url)
    profil_posts = get_linkedin_posts(profil_url)

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
        gen_description = generate_text(
            user_prompt=f"Here is the description: {profil_data.get('data').get('about')}",
            system_prompt="""
Goal: Create a concise, systematic, and readable profile of a CRM contact. Include professional, personal, and ecosystem-related information. Format in short bullet points or mini-paragraphs that are easy to scan.

Prompt:
Focus on key professional roles, skills, and accomplishments.
Include company, position, experience, and expertise areas.
Mention projects, startups founded, GitHub/portfolio links, or notable work.
Include personal interests, hobbies, or travel, if relevant.
Include industry ecosystem insights (accelerators, investors, communities) if the contact is active in it.
Keep each bullet or line simple, clear, and informative.
Avoid fluff, exaggeration, or irrelevant details.
*Do not add section titles just the content*
""",
            model="openai/gpt-4o",
            temperature=0.7,
        )
        print(f"Generated Description: {gen_description}")

        # formatting - safely handle experiences
        profile_data = profil_data.get("data", {})
        experiences = profile_data.get("experiences", [])

        history = ""
        if experiences:
            history = "".join(
                [
                    f"""{exp.get("company", "")}
            {exp.get("title", "")}
            {exp.get("date_range", "")}
            {exp.get("description", "")}
            """
                    for exp in experiences
                ]
            )

        formatted_description = f"""
        {gen_description}

        {history}
        """
        print(formatted_description)

        # update record in airtable - safely get record ID
        record_id = _data.get("id", "")
        if record_id:
            update_at_record(record_id, formatted_description)
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
