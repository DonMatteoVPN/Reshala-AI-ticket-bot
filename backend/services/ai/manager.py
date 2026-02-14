# AI Provider Manager - Multi-provider with key failover
import logging
import requests
import json
import asyncio
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Для работы nested event loops
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# Emergent integrations для работы с EMERGENT_LLM_KEY
EMERGENT_LLM_KEY = None
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import os
    EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "sk-emergent-f2c59A63a8639De58B")
except ImportError:
    logger.warning("emergentintegrations not available, using direct API calls")


class AIProviderManager:
    """Manages multiple AI providers with key failover."""

    def __init__(self, db):
        self.db = db

    def get_providers(self) -> List[Dict]:
        return list(self.db.ai_providers.find({}, {"_id": 0}))

    def get_provider(self, name: str) -> Optional[Dict]:
        return self.db.ai_providers.find_one({"name": name}, {"_id": 0})

    def get_active_provider(self) -> Optional[Dict]:
        settings = self.db.settings.find_one({}, {"_id": 0})
        if not settings:
            return None
        active = settings.get("active_provider", "groq")
        return self.get_provider(active)

    def set_active_provider(self, name: str):
        self.db.settings.update_one({}, {"$set": {"active_provider": name}})

    def add_key(self, provider_name: str, key: str):
        self.db.ai_providers.update_one(
            {"name": provider_name},
            {"$addToSet": {"api_keys": key}}
        )

    def remove_key(self, provider_name: str, key_index: int):
        provider = self.get_provider(provider_name)
        if not provider:
            return
        keys = provider.get("api_keys", [])
        if 0 <= key_index < len(keys):
            keys.pop(key_index)
            active_idx = provider.get("active_key_index", 0)
            if active_idx >= len(keys):
                active_idx = max(0, len(keys) - 1)
            self.db.ai_providers.update_one(
                {"name": provider_name},
                {"$set": {"api_keys": keys, "active_key_index": active_idx}}
            )

    def set_model(self, provider_name: str, model: str):
        self.db.ai_providers.update_one(
            {"name": provider_name},
            {"$set": {"selected_model": model}}
        )

    def set_enabled(self, provider_name: str, enabled: bool):
        self.db.ai_providers.update_one(
            {"name": provider_name},
            {"$set": {"enabled": enabled}}
        )

    def _get_working_key(self, provider: Dict) -> Optional[str]:
        keys = provider.get("api_keys", [])
        if not keys:
            return None
        active_idx = provider.get("active_key_index", 0)
        if active_idx < len(keys):
            return keys[active_idx]
        return keys[0] if keys else None

    def _rotate_key(self, provider_name: str, failed_key: str):
        provider = self.get_provider(provider_name)
        if not provider:
            return
        keys = provider.get("api_keys", [])
        if len(keys) <= 1:
            return
        current_idx = provider.get("active_key_index", 0)
        next_idx = (current_idx + 1) % len(keys)
        self.db.ai_providers.update_one(
            {"name": provider_name},
            {"$set": {"active_key_index": next_idx}}
        )
        logger.info(f"Rotated key for {provider_name}: {current_idx} -> {next_idx}")

    def test_connection(self, provider_name: str, key: Optional[str] = None) -> Dict:
        provider = self.get_provider(provider_name)
        if not provider:
            return {"ok": False, "error": "Provider not found", "models": []}
        test_key = key or self._get_working_key(provider)
        if not test_key:
            return {"ok": False, "error": "No API keys configured", "models": []}

        try:
            if provider_name == "groq":
                return self._test_groq(provider, test_key)
            elif provider_name == "openai":
                return self._test_openai(provider, test_key)
            elif provider_name == "anthropic":
                return self._test_anthropic(provider, test_key)
            elif provider_name == "google":
                return self._test_google(provider, test_key)
            elif provider_name == "openrouter":
                return self._test_openrouter(provider, test_key)
            return {"ok": False, "error": "Unknown provider", "models": []}
        except Exception as e:
            logger.warning(f"test_connection {provider_name}: {e}")
            return {"ok": False, "error": str(e), "models": []}

    def _test_groq(self, provider: Dict, key: str) -> Dict:
        base = provider.get("base_url", "https://api.groq.com/openai/v1")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        r = requests.get(f"{base}/models", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            models = [m["id"] for m in data.get("data", [])]
            return {"ok": True, "models": models, "count": len(models)}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}", "models": []}

    def _test_openai(self, provider: Dict, key: str) -> Dict:
        base = provider.get("base_url", "https://api.openai.com/v1")
        headers = {"Authorization": f"Bearer {key}"}
        r = requests.get(f"{base}/models", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            models = [m["id"] for m in data.get("data", []) if "gpt" in m["id"].lower() or "o1" in m["id"].lower() or "o3" in m["id"].lower()]
            return {"ok": True, "models": sorted(models), "count": len(models)}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}", "models": []}

    def _test_anthropic(self, provider: Dict, key: str) -> Dict:
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        payload = {"model": "claude-3-5-haiku-20241022", "max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]}
        r = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            models = ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
            return {"ok": True, "models": models, "count": len(models)}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}", "models": []}

    def _test_google(self, provider: Dict, key: str) -> Dict:
        base = provider.get("base_url", "https://generativelanguage.googleapis.com/v1beta")
        headers = {"x-goog-api-key": key}
        r = requests.get(f"{base}/models", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            models = [m["name"].replace("models/", "") for m in data.get("models", []) if "generateContent" in str(m.get("supportedGenerationMethods", []))]
            return {"ok": True, "models": models, "count": len(models)}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}", "models": []}

    def _test_openrouter(self, provider: Dict, key: str) -> Dict:
        headers = {"Authorization": f"Bearer {key}"}
        r = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            models = [m["id"] for m in data.get("data", [])[:100]]
            return {"ok": True, "models": models, "count": len(models)}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}", "models": []}

    def chat(self, messages: List[Dict], provider_name: Optional[str] = None) -> Optional[str]:
        settings = self.db.settings.find_one({}, {"_id": 0})
        name = provider_name or (settings.get("active_provider") if settings else "groq")
        provider = self.get_provider(name)
        if not provider or not provider.get("enabled"):
            all_providers = self.get_providers()
            for p in all_providers:
                if p.get("enabled") and p.get("api_keys"):
                    provider = p
                    name = p["name"]
                    break
            if not provider or not provider.get("enabled"):
                return None

        keys = provider.get("api_keys", [])
        if not keys:
            return None

        active_idx = provider.get("active_key_index", 0)
        tried = set()
        for attempt in range(len(keys)):
            idx = (active_idx + attempt) % len(keys)
            if idx in tried:
                continue
            tried.add(idx)
            key = keys[idx]
            try:
                result = self._call_provider(name, provider, key, messages)
                if result:
                    if idx != active_idx:
                        self.db.ai_providers.update_one(
                            {"name": name}, {"$set": {"active_key_index": idx}}
                        )
                    return result
            except Exception as e:
                logger.warning(f"AI {name} key#{idx} failed: {e}")
                continue

        logger.warning(f"All keys exhausted for {name}, trying other providers")
        all_providers = self.get_providers()
        for p in all_providers:
            if p["name"] != name and p.get("enabled") and p.get("api_keys"):
                for k in p["api_keys"]:
                    try:
                        result = self._call_provider(p["name"], p, k, messages)
                        if result:
                            return result
                    except Exception as e:
                        logger.warning(f"Fallback AI {p['name']} failed: {e}")
                        continue
        return None

    def _call_provider(self, name: str, provider: Dict, key: str, messages: List[Dict]) -> Optional[str]:
        model = provider.get("selected_model", "")
        proxy = provider.get("proxy", "")
        proxies = {"http": proxy, "https": proxy} if proxy else None
        
        # Проверяем Emergent LLM key
        is_emergent_key = key.startswith("sk-emergent-") if key else False
        if is_emergent_key and EMERGENT_LLM_KEY:
            return self._call_emergent(key, model, messages, name)
        
        # Проверяем кастомный endpoint
        custom_endpoint = provider.get("endpoint", "")
        if custom_endpoint and not is_emergent_key:
            return self._call_openai_compat(custom_endpoint.rstrip("/"), key, model, messages, proxies)

        if name == "groq":
            return self._call_openai_compat(provider.get("base_url", "https://api.groq.com/openai/v1"), key, model, messages, proxies)
        elif name == "openai":
            return self._call_openai_compat(provider.get("base_url", "https://api.openai.com/v1"), key, model, messages, proxies)
        elif name == "openrouter":
            return self._call_openai_compat(provider.get("base_url", "https://openrouter.ai/api/v1"), key, model, messages, proxies)
        elif name == "anthropic":
            return self._call_anthropic(key, model, messages, proxies)
        elif name == "google":
            # Если нет кастомного endpoint — используем нативный Google API
            return self._call_google(provider.get("base_url", ""), key, model, messages)
        return None

    def _call_emergent(self, key: str, model: str, messages: List[Dict], provider_name: str = "gemini") -> Optional[str]:
        """Вызов AI через emergentintegrations библиотеку"""
        if not EMERGENT_LLM_KEY:
            logger.warning("emergentintegrations not available")
            return None
        
        try:
            # Определяем провайдера по модели
            if model.startswith("gpt") or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
                provider = "openai"
            elif model.startswith("claude"):
                provider = "anthropic"
            elif model.startswith("gemini"):
                provider = "gemini"
            else:
                provider = provider_name
            
            # Извлекаем system message и все сообщения
            system_msg = ""
            conversation = []
            for m in messages:
                if m.get("role") == "system":
                    system_msg = m.get("content", "")
                elif m.get("role") == "user":
                    conversation.append(("user", m.get("content", "")))
                elif m.get("role") == "assistant":
                    conversation.append(("assistant", m.get("content", "")))
            
            # Берём последнее сообщение пользователя
            last_user_content = ""
            for role, content in reversed(conversation):
                if role == "user":
                    last_user_content = content
                    break
            
            if not last_user_content:
                return None
            
            async def _async_call():
                chat = LlmChat(
                    api_key=key,
                    session_id=f"support_{hash(str(messages)) % 100000}",
                    system_message=system_msg
                ).with_model(provider, model)
                
                user_message = UserMessage(text=last_user_content)
                return await chat.send_message(user_message)
            
            # Запускаем в новом event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Если уже есть running loop — используем nest_asyncio
                    import nest_asyncio
                    nest_asyncio.apply()
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(lambda: asyncio.run(_async_call()))
                        response = future.result(timeout=60)
                else:
                    response = loop.run_until_complete(_async_call())
            except RuntimeError:
                # Нет event loop — создаём
                response = asyncio.run(_async_call())
            
            logger.info(f"Emergent AI response: {response[:100] if response else 'None'}...")
            return response.strip() if response else None
                
        except Exception as e:
            logger.warning(f"Emergent AI error: {e}")
            raise Exception(f"Emergent error: {e}")

    def _call_openai_compat(self, base_url: str, key: str, model: str, messages: List[Dict], proxies=None) -> Optional[str]:
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 2048}
        r = requests.post(url, json=payload, headers=headers, timeout=60, proxies=proxies)
        if r.status_code == 200:
            data = r.json()
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                return content.strip() if content else None
        if r.status_code in (429, 402, 403):
            raise Exception(f"Key limit/auth error: {r.status_code}")
        logger.warning(f"OpenAI-compat {model}: {r.status_code} {r.text[:200]}")
        return None

    def _call_anthropic(self, key: str, model: str, messages: List[Dict], proxies=None) -> Optional[str]:
        system_parts = []
        chat_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_parts.append(m.get("content", ""))
            else:
                chat_messages.append({"role": m["role"], "content": m.get("content", "")})
        if not chat_messages:
            return None
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        payload = {"model": model, "max_tokens": 2048, "messages": chat_messages}
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        r = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=60, proxies=proxies)
        if r.status_code == 200:
            data = r.json()
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0].get("text", "").strip()
        if r.status_code in (429, 402, 403):
            raise Exception(f"Key limit/auth error: {r.status_code}")
        logger.warning(f"Anthropic {model}: {r.status_code} {r.text[:200]}")
        return None

    def _call_google(self, base_url: str, key: str, model: str, messages: List[Dict]) -> Optional[str]:
        if not base_url:
            base_url = "https://generativelanguage.googleapis.com/v1beta"
        system_parts = []
        contents = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_parts.append(content)
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})
        if not contents:
            return None
        payload = {"contents": contents, "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}}
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        url = f"{base_url}/models/{model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        if r.status_code in (429, 403):
            raise Exception(f"Key limit/auth error: {r.status_code}")
        logger.warning(f"Google {model}: {r.status_code} {r.text[:200]}")
        return None
