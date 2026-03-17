import httpx

from app.core.config import get_settings

settings = get_settings()


async def start_gmail_watch(access_token: str) -> dict:
    topic_name = f"projects/{settings.gcp_project_id}/topics/{settings.gcp_pubsub_topic}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "topicName": topic_name,
        "labelIds": ["INBOX"],
        "labelFilterBehavior": "INCLUDE",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/watch",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()