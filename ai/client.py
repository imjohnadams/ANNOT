from openai import OpenAI

from config import LUNA_API_KEY, LUNA_BASE_URL


def get_client() -> OpenAI:
    if not LUNA_API_KEY:
        raise RuntimeError(
            "LUNA_API_KEY is not set. Add it to ANNOT/.env or your environment."
        )
    return OpenAI(api_key=LUNA_API_KEY, base_url=LUNA_BASE_URL)
