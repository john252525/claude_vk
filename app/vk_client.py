import asyncio
import httpx
from app.config import VK_ACCESS_TOKEN, VK_GROUP_ID, VK_API_VERSION, VK_API_BASE, VK_RATE_LIMIT


class VKClient:
    """Async client for VK API with automatic pagination and rate limiting."""

    def __init__(self):
        self._semaphore = asyncio.Semaphore(VK_RATE_LIMIT)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _call(self, method: str, params: dict) -> dict:
        """Make a single VK API call with rate limiting."""
        async with self._semaphore:
            client = await self._get_client()
            params = {
                **params,
                "access_token": VK_ACCESS_TOKEN,
                "v": VK_API_VERSION,
            }
            resp = await client.post(f"{VK_API_BASE}/{method}", data=params)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise VKAPIError(data["error"])
            # Small delay to stay within rate limits
            await asyncio.sleep(0.05)
            return data["response"]

    async def get_conversations(self, count: int = 200, date_from_ts: int = 0) -> list[dict]:
        """Fetch ALL conversations with automatic pagination.

        If date_from_ts is set, stop paginating once last_message.date
        drops below this timestamp (VK returns conversations sorted by
        last message date descending).
        """
        all_items = []
        offset = 0

        while True:
            resp = await self._call("messages.getConversations", {
                "count": min(count, 200),
                "offset": offset,
                "group_id": VK_GROUP_ID,
                "extended": 1,
            })

            items = resp.get("items", [])
            profiles = {p["id"]: p for p in resp.get("profiles", [])}
            groups = {g["id"]: g for g in resp.get("groups", [])}

            hit_cutoff = False
            for item in items:
                item["_profiles"] = profiles
                item["_groups"] = groups

                if date_from_ts:
                    last_msg = item.get("last_message")
                    if last_msg and last_msg.get("date", 0) < date_from_ts:
                        hit_cutoff = True
                        break

                all_items.append(item)

            total = resp.get("count", 0)

            if hit_cutoff or not items or len(all_items) >= total:
                break

            offset += len(items)

        return all_items

    async def get_history(self, peer_id: int, count: int = 200) -> list[dict]:
        """Fetch ALL messages for a conversation with automatic pagination."""
        all_messages = []
        offset = 0

        while True:
            resp = await self._call("messages.getHistory", {
                "peer_id": peer_id,
                "count": min(count, 200),
                "offset": offset,
                "group_id": VK_GROUP_ID,
            })

            messages = resp.get("items", [])
            all_messages.extend(messages)
            total = resp.get("count", 0)

            if not messages or len(all_messages) >= total:
                break

            offset += len(messages)

        return all_messages

    async def get_all_data(self, date_from_ts: int = 0) -> dict:
        """Fetch all conversations and all their messages."""
        conversations = await self.get_conversations(date_from_ts=date_from_ts)

        result = []
        for conv_item in conversations:
            peer = conv_item["conversation"]["peer"]
            peer_id = peer["id"]

            messages = await self.get_history(peer_id)

            result.append({
                "conversation": conv_item["conversation"],
                "last_message": conv_item.get("last_message"),
                "profiles": conv_item.get("_profiles", {}),
                "groups": conv_item.get("_groups", {}),
                "messages": messages,
            })

        return {
            "total_conversations": len(result),
            "conversations": result,
        }

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class VKAPIError(Exception):
    def __init__(self, error_data: dict):
        self.code = error_data.get("error_code", 0)
        self.message = error_data.get("error_msg", "Unknown VK API error")
        super().__init__(f"VK API Error {self.code}: {self.message}")


vk = VKClient()
