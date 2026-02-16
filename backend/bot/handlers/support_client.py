import logging
import asyncio
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.ai.manager import AIProviderManager

from utils.support_common import (
    build_support_header, format_bytes, format_user_context, get_topic_name, 
    check_access, should_escalate, detect_subscription_link, 
    TOPIC_OPEN, TOPIC_ESCALATED, TOPIC_SUSPICIOUS, TOPIC_CLOSED
)
from utils.db_config import get_db, get_settings, get_support_group_id
from utils.bedolaga_api import fetch_bedolaga_balance, fetch_bedolaga_deposits
from utils.remnawave_api import fetch_user_data
from bot.keyboards import client_keyboard, build_support_keyboard, confirm_client_keyboard

logger = logging.getLogger(__name__)

# Helpers

def get_conversation_history(context, user_id: int, max_messages: int = 10) -> list:
    history = context.user_data.get("ai_history", [])
    return history[-max_messages:] if history else []

def save_to_conversation(context, role: str, content: str):
    if "ai_history" not in context.user_data:
        context.user_data["ai_history"] = []
    
    context.user_data["ai_history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    if len(context.user_data["ai_history"]) > 20:
        context.user_data["ai_history"] = context.user_data["ai_history"][-20:]

def clear_conversation(context):
    context.user_data.pop("ai_history", None)
    context.user_data.pop("user_context", None)
    context.user_data.pop("is_suspicious", None)
    context.user_data.pop("has_provided_proof", None)

def filter_ai_thinking(text: str) -> str:
    """Удаляет теги <think>...</think> и подобные из ответа AI"""
    if not text:
        return text
    import re
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

async def get_ai_reply(context, user_message: str, user_id: int, user_name: str = "") -> str:
    """Получение ответа от AI"""
    db = get_db()
    if db is None:
        return None

    config = get_settings()
    if not config.get("ai_enabled", True):
        return None

    ai_manager = AIProviderManager(db)
    service_name = config.get("service_name", "Решала support")
    
    # Получаем данные пользователя
    if "user_context" not in context.user_data:
        user_data = await fetch_user_data(user_id)
        balance_data = await fetch_bedolaga_balance(user_id)
        
        if user_data.get("not_found"):
            context.user_data["is_suspicious"] = True
        
        context.user_data["user_data_raw"] = user_data
        context.user_data["balance_data"] = balance_data
    
    user_data = context.user_data.get("user_data_raw", {})
    balance_data = context.user_data.get("balance_data", {})
    has_provided_proof = context.user_data.get("has_provided_proof", False)
    
    main_bot_username = config.get("main_bot_username", "")
    user_context = format_user_context(user_data, balance_data, has_provided_proof, main_bot_username)
    context.user_data["user_context"] = user_context

    # База знаний
    kb_context = ""
    try:
        # Берем все слова длиннее 3 символов из сообщения для поиска
        import re
        search_words = [w.lower() for w in re.findall(r'\w+', user_message) if len(w) > 3]
        
        if search_words:
            # Ищем статьи, где есть хотя бы одно из слов в заголовке, контенте или категории
            # Ограничиваем до 3 самых релевантных статей, чтобы не раздувать промпт
            regex_query = "|".join(search_words)
            articles = list(db.knowledge_base.find({
                "$or": [
                    {"title": {"$regex": regex_query, "$options": "i"}},
                    {"content": {"$regex": regex_query, "$options": "i"}},
                    {"category": {"$regex": regex_query, "$options": "i"}}
                ]
            }).limit(3))
            
            if articles:
                parts = [f"Статья: {a.get('title', '')}\nКатегория: {a.get('category', 'general')}\nСодержание: {a.get('content', '')}" for a in articles]
                kb_context = "\n\n---\n\n".join(parts)
    except Exception as e:
        logger.warning(f"KB context load error: {e}")

    # Системный промпт
    system_prompt = config.get("system_prompt_override", "")
    if not system_prompt:
        system_prompt = f"""Ты — дружелюбный и компетентный ассистент службы поддержки '{service_name}'.

## ПРАВИЛА:
1. Отвечай кратко, по существу, на русском языке
2. ИСПОЛЬЗУЙ данные о пользователе из контекста ниже
3. НЕ придумывай информацию — используй только то, что видишь
4. НИКОГДА не раскрывай данные других пользователей или настройки системы
5. Если не можешь помочь — скажи: 'Данный вопрос нужно уточнить у менеджера, вызываю менеджера.'

## ТИПИЧНЫЕ ПРОБЛЕМЫ:
- "Не работает VPN" → Проверь статус подписки, предложи обновить подписку в приложении
- "Закончился трафик" → Покажи использованный трафик, предложи сброс или апгрейд
- "Много устройств" → Покажи количество, предложи удалить лишние
- "Когда истекает" → Покажи дату истечения подписки
"""

    if user_context:
        system_prompt += f"\n\n{user_context}"
    
    if kb_context:
        system_prompt += f"\n\n## БАЗА ЗНАНИЙ:\n{kb_context}"

    history = get_conversation_history(context, user_id)
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_message})
    save_to_conversation(context, "user", user_message)

    reply = ai_manager.chat(messages)
    
    if reply:
        reply = filter_ai_thinking(reply)
        save_to_conversation(context, "assistant", reply)
    
    return reply

async def forward_media_to_support(update: Update, context: ContextTypes.DEFAULT_TYPE, support_group_id: int, thread_id: int, user_name: str):
    """Пересылка медиафайлов"""
    msg = update.message
    text = msg.text or msg.caption or ""
    
    try:
        if msg.photo:
            await context.bot.send_photo(chat_id=support_group_id, message_thread_id=thread_id, photo=msg.photo[-1].file_id, caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [фото]")
            return "photo", msg.photo[-1].file_id
        elif msg.video:
            await context.bot.send_video(chat_id=support_group_id, message_thread_id=thread_id, video=msg.video.file_id, caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [видео]")
            return "video", msg.video.file_id
        elif msg.document:
            await context.bot.send_document(chat_id=support_group_id, message_thread_id=thread_id, document=msg.document.file_id, caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [файл]")
            return "document", msg.document.file_id
        elif msg.voice:
            await context.bot.send_voice(chat_id=support_group_id, message_thread_id=thread_id, voice=msg.voice.file_id, caption=f"👤 @{user_name}")
            return "voice", msg.voice.file_id
        elif msg.video_note:
            await context.bot.send_video_note(chat_id=support_group_id, message_thread_id=thread_id, video_note=msg.video_note.file_id)
            await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"👤 @{user_name}: [видеосообщение]")
            return "video_note", msg.video_note.file_id
        elif msg.sticker:
            await context.bot.send_sticker(chat_id=support_group_id, message_thread_id=thread_id, sticker=msg.sticker.file_id)
            await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"👤 @{user_name}: [стикер]")
            return "sticker", msg.sticker.file_id
        elif msg.audio:
            await context.bot.send_audio(chat_id=support_group_id, message_thread_id=thread_id, audio=msg.audio.file_id, caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [аудио]")
            return "audio", msg.audio.file_id
        elif msg.animation:
            await context.bot.send_animation(chat_id=support_group_id, message_thread_id=thread_id, animation=msg.animation.file_id, caption=f"👤 @{user_name}:\n{text}" if text else f"👤 @{user_name}: [GIF]")
            return "animation", msg.animation.file_id
        elif text:
            await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"👤 @{user_name}:\n{text}")
            return "text", None
    except Exception as e:
        logger.error(f"forward_media_to_support error: {e}")
        if text:
            try:
                await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"👤 @{user_name}:\n{text}\n\n[Медиафайл не удалось переслать]")
            except: pass
    return None, None

async def handle_client_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = get_settings()
    db = get_db()
    support_group_id = get_support_group_id()
    service_name = config.get("service_name", "Решала support")
    
    if not support_group_id:
        await update.message.reply_text(f"Поддержка {service_name} временно недоступна.")
        return

    user = update.effective_user
    user_id = user.id
    user_name = user.username or user.first_name or str(user_id)
    text = update.message.text or update.message.caption or ""
    has_media = bool(update.message.photo or update.message.video or update.message.document or update.message.voice or update.message.video_note or update.message.sticker or update.message.audio or update.message.animation)

    if "support_topic_by_client" not in context.application.bot_data: context.application.bot_data["support_topic_by_client"] = {}
    if "support_thread_to_client" not in context.application.bot_data: context.application.bot_data["support_thread_to_client"] = {}
    if "support_clients" not in context.application.bot_data: context.application.bot_data["support_clients"] = {}
    
    topic_by_client = context.application.bot_data["support_topic_by_client"]
    thread_to_client = context.application.bot_data["support_thread_to_client"]
    support_clients = context.application.bot_data["support_clients"]
    
    existing = topic_by_client.get(user_id)
    thread_id = existing.get("message_thread_id") if existing else None
    ai_disabled = False
    is_suspicious = False
    has_provided_proof = False

    # Сначала пытаемся найти существующий тикет и восстановить состояние
    if db is not None:
        # Пытаемся найти по client_id или topic_id
        # ВАЖНО: Исключаем закрытые тикеты (is_removed=True или status=closed)
        ticket_query = {
            "client_id": user_id, 
            "is_removed": {"$ne": True},
            "status": {"$ne": "closed"}
        }
        if thread_id:
            ticket_query = {
                "topic_id": thread_id, 
                "is_removed": {"$ne": True},
                "status": {"$ne": "closed"}
            }
            
        active_ticket = db.tickets.find_one(ticket_query)
        if active_ticket:
            ai_disabled = active_ticket.get("ai_disabled", False)
            is_suspicious = active_ticket.get("status") == "suspicious"
            has_provided_proof = bool(active_ticket.get("attachments"))
            
            # Синхронизируем context.user_data для совместимости с остальным кодом
            context.user_data["is_suspicious"] = is_suspicious
            context.user_data["has_provided_proof"] = has_provided_proof
            
            if not thread_id and active_ticket.get("topic_id"):
                thread_id = active_ticket.get("topic_id")
                topic_by_client[user_id] = {
                    "chat_id": support_group_id,
                    "message_thread_id": thread_id,
                    "topic_name": get_topic_name(user_name, active_ticket["status"]),
                }
                thread_to_client[(support_group_id, thread_id)] = user_id
                context.user_data["topic_id"] = thread_id
        
        if not thread_id:
            user_data = await fetch_user_data(user_id)
            balance_data = await fetch_bedolaga_balance(user_id)
            
            is_suspicious = user_data.get("not_found", False)
            context.user_data["is_suspicious"] = is_suspicious
            context.user_data["user_data_raw"] = user_data
            context.user_data["balance_data"] = balance_data
            context.user_data["has_provided_proof"] = False
            
            main_bot_username = config.get("main_bot_username", "")
            context.user_data["user_context"] = format_user_context(user_data, balance_data, False, main_bot_username)
            
            topic_name = get_topic_name(user_name, "suspicious" if is_suspicious else "open")
            
            try:
                topic = await context.bot.create_forum_topic(chat_id=support_group_id, name=topic_name[:128])
                thread_id = topic.message_thread_id
                context.user_data["topic_id"] = thread_id
                
                topic_by_client[user_id] = {"chat_id": support_group_id, "message_thread_id": thread_id, "topic_name": topic_name}
                thread_to_client[(support_group_id, thread_id)] = user_id
                
                user_info = user_data.get("user", {})
                support_clients[user_id] = {
                    "user": user_info,
                    "subscription": user_data.get("subscription"),
                    "hwid_devices": user_data.get("devices", []),
                    "bedolaga_user": balance_data,
                    "is_suspicious": is_suspicious,
                }
                
                header_user_info = user_info or {"username": user.username, "first_name": user.first_name, "id": user.id, "telegramId": user.id}
                header = build_support_header(header_user_info, balance_data, is_suspicious)
                
                card_msg = await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=header, parse_mode="HTML", reply_markup=build_support_keyboard(user_id, user_info, balance_data, is_suspicious))
                try: await context.bot.pin_chat_message(chat_id=support_group_id, message_id=card_msg.message_id) 
                except: pass
                
                if db is not None:
                    db.tickets.insert_one({
                        "client_id": user_id,
                        "client_name": user.first_name or user_name,
                        "client_username": user.username,
                        "topic_id": thread_id,
                        "status": "suspicious" if is_suspicious else "open",
                        "reason": "Пользователь не найден в системе" if is_suspicious else None,
                        "user_data": user_data if not is_suspicious else None,
                        "last_messages": [], "history": [], "attachments": [],
                        "ai_disabled": False,
                        "created_at": datetime.now(timezone.utc), "is_removed": False,
                    })
            except Exception as e:
                logger.error(f"create topic: {e}")
                await update.message.reply_text("Ошибка создания тикета.")
                return

    is_suspicious = context.user_data.get("is_suspicious", False)
    has_provided_proof = context.user_data.get("has_provided_proof", False)
    proof_received = False
    
    if text:
        sub_link = detect_subscription_link(text)
        if sub_link:
            proof_received = True
            if db is not None: db.tickets.update_one({"topic_id": thread_id}, {"$push": {"attachments": {"type": "subscription_link", "value": sub_link, "added_at": datetime.now(timezone.utc).isoformat()}}})
            await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"📎 <b>Получена ссылка:</b>\n<code>{sub_link}</code>", parse_mode="HTML")
            
    if update.message.photo:
        proof_received = True
        if db is not None: db.tickets.update_one({"topic_id": thread_id}, {"$push": {"attachments": {"type": "photo", "file_id": update.message.photo[-1].file_id, "added_at": datetime.now(timezone.utc).isoformat()}}})
        if is_suspicious and not has_provided_proof:
            await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text="📷 <b>Получен скриншот от подозрительного пользователя</b>", parse_mode="HTML")

    if is_suspicious and proof_received and not has_provided_proof:
        context.user_data["has_provided_proof"] = True
        has_provided_proof = True
        user_data = context.user_data.get("user_data_raw", {})
        balance_data = context.user_data.get("balance_data", {})
        main_bot_username = config.get("main_bot_username", "")
        context.user_data["user_context"] = format_user_context(user_data, balance_data, True, main_bot_username)
        
        try: await context.bot.edit_forum_topic(chat_id=support_group_id, message_thread_id=thread_id, name=f"{TOPIC_SUSPICIOUS} @{user_name}")
        except: pass
        
        await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"🚨 <b>ВНИМАНИЕ!</b> Пользователь @{user_name} не найден, но предоставил данные. Требуется проверка.", parse_mode="HTML")
        if db is not None: db.tickets.update_one({"topic_id": thread_id}, {"$set": {"status": "suspicious", "reason": "Пользователь не найден", "escalated_at": datetime.now(timezone.utc)}})

    # Сохраняем сообщение клиента в историю БД
    if text and db is not None and thread_id:
        try:
            db.tickets.update_one(
                {"topic_id": thread_id},
                {"$push": {"history": {
                    "role": "user",
                    "content": text,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }}}
            )
        except Exception as e:
            logger.warning(f"Failed to save client message to DB history: {e}")

    await forward_media_to_support(update, context, support_group_id, thread_id, user_name)

    # ИИ отвечает ВСЕГДА, кроме случаев когда он явно отключен (ai_disabled)
    # ai_disabled устанавливается когда:
    # 1. Клиент позвал менеджера
    # 2. ИИ эскалировал тикет
    # 3. Менеджер вмешался в тикет
    should_reply = text.strip() and not ai_disabled
    
    # Отладочные логи
    logger.info(f"[AI DECISION] user_id={user_id}, ai_disabled={ai_disabled}, should_reply={should_reply}, is_suspicious={is_suspicious}, has_provided_proof={has_provided_proof}, text={text[:50] if text else 'None'}")
    
    if should_reply:
        ai_message = text if text.strip() else "[Пользователь прислал данные]"
        ai_reply = await get_ai_reply(context, ai_message, user_id, user_name)
        
        if ai_reply:
            if should_escalate(ai_reply):
                await update.message.reply_text(ai_reply, reply_markup=client_keyboard(is_suspicious))
                
                # Меняем название темы и статус только если НЕ подозрительный
                if not is_suspicious:
                    try: await context.bot.edit_forum_topic(chat_id=support_group_id, message_thread_id=thread_id, name=f"{TOPIC_ESCALATED} @{user_name}")
                    except: pass
                    await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"🔥 <b>Эскалация</b>: AI не смог ответить.\nAI: {ai_reply[:300]}", parse_mode="HTML")
                    if db is not None: 
                        db.tickets.update_one({"topic_id": thread_id}, {"$set": {"status": "escalated", "escalated_at": datetime.now(timezone.utc)}})
                else:
                    # Для подозрительных - просто уведомляем без смены статуса
                    await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"⚠️ <b>AI не смог ответить подозрительному пользователю</b>\nAI: {ai_reply[:300]}", parse_mode="HTML")
                
                # Отключаем ИИ после эскалации в БД
                if db is not None:
                    db.tickets.update_one({"topic_id": thread_id}, {"$set": {"ai_disabled": True}})
            else:
                await update.message.reply_text(ai_reply, reply_markup=client_keyboard(is_suspicious))
                await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"🤖 AI:\n{ai_reply[:3000]}")
            
            # Сохраняем ответ ИИ в историю БД
            if db is not None and thread_id:
                try:
                    db.tickets.update_one(
                        {"topic_id": thread_id},
                        {"$push": {"history": {
                            "role": "ai",
                            "content": ai_reply,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }}}
                    )
                except Exception as e:
                    logger.warning(f"Failed to save AI reply to DB history: {e}")
        else:
            await update.message.reply_text("Ваше сообщение принято.", reply_markup=client_keyboard(is_suspicious))
    elif has_media and not text:
        await update.message.reply_text("Получил ваш файл.", reply_markup=client_keyboard(is_suspicious))

# Callbacks

async def ask_call_manager_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🔥 <b>Вызов менеджера</b>\n\nВы уверены?", parse_mode="HTML", reply_markup=confirm_client_keyboard("call_manager"))

async def ask_close_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("✅ <b>Закрытие тикета</b>\n\nВы уверены?", parse_mode="HTML", reply_markup=confirm_client_keyboard("client_close_ticket"))

async def cancel_client_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Действие отменено")
    await query.edit_message_text("❌ Действие отменено.")

async def call_manager_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Менеджер вызван!")
    db = get_db()
    support_group_id = get_support_group_id()
    user_id = query.from_user.id
    
    # Пытаемся достать из памяти, если нет - из БД
    thread_id = context.user_data.get("topic_id")
    if not thread_id and db is not None:
        ticket = db.tickets.find_one({"client_id": user_id, "is_removed": {"$ne": True}})
        if ticket:
            thread_id = ticket.get("topic_id")

    is_suspicious = context.user_data.get("is_suspicious", False)
    # Если в памяти пусто, проверяем статус в БД
    if not is_suspicious and db is not None and thread_id:
        ticket = db.tickets.find_one({"topic_id": thread_id})
        is_suspicious = ticket.get("status") == "suspicious" if ticket else False

    if support_group_id and thread_id:
        user_name = query.from_user.username or str(query.from_user.id)
        # Меняем название темы только если НЕ подозрительный
        if not is_suspicious:
            try: await context.bot.edit_forum_topic(chat_id=support_group_id, message_thread_id=thread_id, name=f"{TOPIC_ESCALATED} @{user_name}")
            except: pass
            
        await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"🔥 <b>Клиент @{user_name} вызывает менеджера!</b>", parse_mode="HTML")
        
        # Меняем статус только если он НЕ подозрительный
        if db is not None:
            update_data = {"ai_disabled": True}
            if not is_suspicious:
                update_data["status"] = "escalated"
                update_data["escalated_at"] = datetime.now(timezone.utc)
            
            db.tickets.update_one({"topic_id": thread_id}, {"$set": update_data})

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Менеджер скоро подключится.")

async def client_close_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Тикет закрыт.")
    db = get_db()
    support_group_id = get_support_group_id()
    thread_id = context.user_data.get("topic_id")
    is_suspicious = context.user_data.get("is_suspicious", False)
    user_id = query.from_user.id
    user_name = query.from_user.username or str(user_id)

    if support_group_id and thread_id:
        logger.info(f"client_close_ticket_callback: group={support_group_id}, thread={thread_id}, suspicious={is_suspicious}")
        if is_suspicious:
            # Подозрительный тикет: не закрываем тему, сохраняем эмодзи 🚨
            await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"✅ Клиент закрыл чат. Тикет остаётся для проверки!", parse_mode="HTML")
            # Оставляем в БД с пометкой closed_at
            if db is not None: 
                db.tickets.update_one(
                    {"topic_id": thread_id}, 
                    {"$set": {"status": "suspicious", "closed_at": datetime.now(timezone.utc)}}
                )
        else:
            # Обычный тикет: порядок операций - сообщение → переименование → закрытие
            # 1. Отправляем сообщение
            await context.bot.send_message(chat_id=support_group_id, message_thread_id=thread_id, text=f"✅ <b>Тикет закрыт клиентом.</b>", parse_mode="HTML")
            
            # 2. Переименовываем тему (пока она еще открыта)
            # 2. Переименовываем тему (пока она еще открыта)
            try:
                new_name = f"{TOPIC_CLOSED} @{user_name}"
                await context.bot.edit_forum_topic(chat_id=support_group_id, message_thread_id=thread_id, name=new_name)
                logger.info(f"Renamed topic {thread_id} to {new_name}")
            except Exception as e:
                logger.error(f"Failed to rename topic {thread_id}: {e}")
            
            # 3. Закрываем тему
            try:
                await context.bot.close_forum_topic(chat_id=support_group_id, message_thread_id=thread_id)
                logger.info(f"Closed topic {thread_id}")
            except Exception as e:
                logger.error(f"Failed to close topic {thread_id}: {e}")
            
            # 4. Удаляем из БД
            if db is not None: 
                db.tickets.delete_one({"topic_id": thread_id})

    if "support_topic_by_client" in context.application.bot_data: context.application.bot_data["support_topic_by_client"].pop(user_id, None)
    if "support_thread_to_client" in context.application.bot_data: context.application.bot_data["support_thread_to_client"].pop((support_group_id, thread_id), None)
    
    clear_conversation(context)
    context.user_data.pop("topic_id", None)
    
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Тикет закрыт. Если нужна помощь — пишите снова.")

async def check_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Проверяю баланс...")
    user_id = query.from_user.id
    
    balance_data = await fetch_bedolaga_balance(user_id)
    deposits = await fetch_bedolaga_deposits(user_id)
    
    if not balance_data:
        await query.message.reply_text("❌ Bedolaga API недоступен.")
        return
    
    balance = balance_data.get('balance', 0)
    currency = balance_data.get('currency', 'RUB')
    
    text = [f"💰 <b>Ваш баланс:</b> {balance} {currency}"]
    
    if deposits:
        text.append("\n📋 <b>История пополнений:</b>")
        for d in deposits[:5]:
            amt = d.get('amount', 0)
            curr = d.get('currency', 'RUB')
            date = d.get('created_at', '')[:10]
            text.append(f"• <b>+{amt} {curr}</b> — {date}")
    else:
        text.append("\n<i>История пополнений пуста</i>")
    
    await query.message.reply_text("\n".join(text), parse_mode="HTML")
