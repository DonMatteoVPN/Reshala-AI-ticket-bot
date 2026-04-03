import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes

from utils.support_common import (
    build_support_header, check_access, get_support_chat_ids, TOPIC_CLOSED
)
from utils.db_config import get_db, get_settings, get_support_group_id
from utils.bedolaga_api import fetch_bedolaga_balance, fetch_bedolaga_transactions
from utils.remnawave_api import remnawave_action
from services.ticket_service import TicketService
from bot.keyboards import manager_keyboard, build_support_keyboard

logger = logging.getLogger(__name__)

async def rename_topic(bot, chat_id: int, thread_id: int, prefix: str):
    """Переименовывает топик, добавляя префикс (если его там нет)"""
    try:
        # К сожалению, get_forum_topic нет в открытом API? 
        # Обычно храним имя в bot_data, но если нет — пробуем редактировать
        # Тут мы просто пытаемся добавить префикс.
        # В идеале нужно знать старое имя. 
        pass 
        # Telegram Bot API позволяет editForumTopic(name=...)
        # Мы не знаем текущее имя, поэтому это сложный момент.
        # В оригинальном коде логика была такая:
        # Пробуем получить имя из bot_data["support_topic_by_client"] если есть
        pass
    except Exception as e:
        logger.warning(f"rename_topic error: {e}")

async def handle_support_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов менеджеров в топике"""
    msg = update.message
    if not msg or not msg.message_thread_id:
        return

    support_group_id = get_support_group_id()
    if msg.chat.id != support_group_id:
        return

    thread_id = msg.message_thread_id
    
    # Игнорим сервисные сообщения
    if msg.forum_topic_created or msg.forum_topic_closed or msg.forum_topic_reopened:
        return

    # Определяем клиента
    thread_to_client = context.application.bot_data.get("support_thread_to_client", {})
    client_id = thread_to_client.get((support_group_id, thread_id))
    
    db = get_db()
    
    # Если нет в памяти, ищем в БД
    if not client_id and db:
        ticket = db.tickets.find_one({"topic_id": thread_id})
        if ticket:
            client_id = ticket.get("client_id")
            # Восстанавливаем маппинг
            thread_to_client[(support_group_id, thread_id)] = client_id
            
    if not client_id:
        return

    text = msg.text or msg.caption or ""
    
    # Отправляем клиенту
    try:
        sent = False
        if msg.text:
            await context.bot.send_message(chat_id=client_id, text=f"👨‍💼 <b>Поддержка:</b>\n{text}", parse_mode="HTML")
            sent = True
        elif msg.photo:
            await context.bot.send_photo(chat_id=client_id, photo=msg.photo[-1].file_id, caption=f"👨‍💼 <b>Поддержка:</b>\n{text}" if text else None, parse_mode="HTML")
            sent = True
        elif msg.document:
            await context.bot.send_document(chat_id=client_id, document=msg.document.file_id, caption=f"👨‍💼 <b>Поддержка:</b>\n{text}" if text else None, parse_mode="HTML")
            sent = True
        elif msg.voice:
            await context.bot.send_voice(chat_id=client_id, voice=msg.voice.file_id)
            sent = True
        elif msg.video:
            await context.bot.send_video(chat_id=client_id, video=msg.video.file_id, caption=f"👨‍💼 <b>Поддержка:</b>\n{text}" if text else None, parse_mode="HTML")
            sent = True
        elif msg.video_note:
            await context.bot.send_video_note(chat_id=client_id, video_note=msg.video_note.file_id)
            sent = True
        elif msg.sticker:
            await context.bot.send_sticker(chat_id=client_id, sticker=msg.sticker.file_id)
            sent = True
        elif msg.audio:
            await context.bot.send_audio(chat_id=client_id, audio=msg.audio.file_id, caption=f"👨‍💼 <b>Поддержка:</b>\n{text}" if text else None, parse_mode="HTML")
            sent = True
        elif msg.animation:
            await context.bot.send_animation(chat_id=client_id, animation=msg.animation.file_id, caption=f"👨‍💼 <b>Поддержка:</b>\n{text}" if text else None, parse_mode="HTML")
            sent = True

        if sent and db is not None:
            # Логируем ответ менеджера
            reply_record = {
                "role": "manager",
                "name": msg.from_user.first_name,
                "content": text or "[media]",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sent_to_telegram": True
            }
            db.tickets.update_one(
                {"topic_id": thread_id},
                {
                    "$push": {"history": reply_record},
                    "$set": {
                        "last_reply_at": datetime.now(timezone.utc),
                        "status": "answered", # Меняем статус на answered (или оставляем как есть, но для порядка)
                        "ai_disabled": True  # <--- ОТКЛЮЧАЕМ ИИ ПРИ ОТВЕТЕ МЕНЕДЖЕРА
                    }
                }
            )
            
            # Добавляем в last_messages для контекста AI
            # Нужно аккуратно, чтобы контекст AI обновлялся
            # Но context.user_data тут недоступен для CLIENT_ID напрямую (это другой update)
            # Придется полагаться на то, что history загружается заново в get_conversation_history? 
            # Нет, там memory.
            # Пока оставим только БД.

    except Exception as e:
        logger.error(f"Error sending reply to client {client_id}: {e}")
        await msg.reply_text(f"❌ Не удалось отправить клиенту: {e}")

async def close_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Менеджер закрывает тикет (close_ticket:ticket_id)"""
    query = update.callback_query
    logger.info(f"close_ticket_callback (manager) triggered by user {query.from_user.id} with data {query.data}")
    data = query.data or ""
    ticket_id = data.replace("close_ticket:", "")
    
    # Проверяем доступ
    if not check_access(query.from_user.id):
        await query.answer("Доступ запрещён.", show_alert=True)
        return

    await query.answer("Закрываю тикет...")
    
    # Создаем экземпляр сервиса с существующим ботом
    db = get_db()
    support_group_id = get_support_group_id()
    from services.telegram_service import TelegramService
    # Используем существующий бот вместо создания нового
    telegram_service = TelegramService(bot=context.bot)
    ticket_service = TicketService(db, telegram_service, support_group_id)
    
    # Используем сервис
    result = await ticket_service.close_ticket(ticket_id, user_id=None, is_manager=True)
    
    if result.get("ok"):
        support_group_id = get_support_group_id()
        client_id = result.get("client_id")
        thread_id = result.get("topic_id")
        
        # Очистка памяти
        if client_id:
            topic_by_client = context.application.bot_data.get("support_topic_by_client", {})
            topic_by_client.pop(client_id, None)
        if thread_id and support_group_id:
            thread_to_client = context.application.bot_data.get("support_thread_to_client", {})
            thread_to_client.pop((support_group_id, thread_id), None)
            
        await query.edit_message_reply_markup(reply_markup=None)
    else:
        # Если тикет не найден или ошибка
        await query.message.reply_text(f"❌ Ошибка закрытия: {result.get('error')}")

async def remove_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Менеджер убирает тикет (remove_ticket:ticket_id)"""
    query = update.callback_query
    data = query.data or ""
    ticket_id = data.replace("remove_ticket:", "")

    if not check_access(query.from_user.id):
        await query.answer("Доступ запрещён.", show_alert=True)
        return

    await query.answer("Тикет удалён.")

    db = get_db()
    support_group_id = get_support_group_id()

    if db is not None and ticket_id:
        try:
            thread_id = int(ticket_id)
            db.tickets.update_one({"topic_id": thread_id}, {"$set": {"is_removed": True, "removed_at": datetime.now(timezone.utc)}})
            try: await context.bot.close_forum_topic(chat_id=support_group_id, message_thread_id=thread_id)
            except: pass
        except Exception as e:
            logger.warning(f"remove ticket: {e}")

    await query.edit_message_reply_markup(reply_markup=None)

async def support_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение секций в карточке клиента (sup:client_id:section)."""
    query = update.callback_query
    data = query.data or ""
    
    if not check_access(query.from_user.id):
        await query.answer("Доступ запрещён.", show_alert=True)
        return
    
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer()
        return
    
    try:
        client_id = int(parts[1])
        section = parts[2]
    except ValueError:
        await query.answer()
        return
    
    await query.answer(f"Секция: {section}")
    
    support_clients = context.application.bot_data.get("support_clients", {})
    client_data = support_clients.get(client_id, {})
    
    
    # Fetch additional data for specific sections
    if section == "transactions":
        # Check if we already have transactions in memory? 
        # Better to fetch fresh ones or checking cache. 
        # Let's fetch fresh for now to be safe.
        bedolaga_user = client_data.get("bedolaga_user", {})
        bedolaga_id = bedolaga_user.get("id")
        if not bedolaga_id:
             # Try refreshing balance data
             balance_data = await fetch_bedolaga_balance(client_id)
             if balance_data:
                 bedolaga_id = balance_data.get("id")
                 client_data["bedolaga_user"] = balance_data # update cache
        
        if bedolaga_id:
            transactions = await fetch_bedolaga_transactions(int(bedolaga_id))
            if transactions:
                # Add transactions to balance_data for build_support_header
                if "bedolaga_user" not in client_data: client_data["bedolaga_user"] = {}
                client_data["bedolaga_user"]["transactions"] = transactions
    
    elif section == "balance":
        # Refresh balance
        balance_data = await fetch_bedolaga_balance(client_id)
        if balance_data:
             client_data["bedolaga_user"] = balance_data

    user_info = client_data.get("user", {})
    balance_data = client_data.get("bedolaga_user", {})
    is_suspicious = client_data.get("is_suspicious", False)
    
    header_user_info = user_info or { "first_name": str(client_id), "id": client_id, "username": client_data.get("username") }
    
    new_text = build_support_header(header_user_info, balance_data, is_suspicious, section)
    new_keyboard = build_support_keyboard(client_id, user_info, balance_data, is_suspicious, section)
    
    try:
        await query.edit_message_text(text=new_text, parse_mode="HTML", reply_markup=new_keyboard)
    except Exception as e:
        logger.debug(f"support_nav_callback edit error: {e}")

async def support_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий менеджера (sup_act:client_id:action)."""
    query = update.callback_query
    data = query.data or ""
    
    if not check_access(query.from_user.id):
        await query.answer("Доступ запрещён.", show_alert=True)
        return
    
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer()
        return
    
    try:
        client_id = int(parts[1])
        action = parts[2]
    except ValueError:
        await query.answer()
        return
    
    # AI actions
    if action == "stop_ai":
        db = get_db()
        if db is not None:
            db.tickets.update_one({"client_id": client_id, "is_removed": {"$ne": True}}, {"$set": {"ai_disabled": True}})
        await query.answer("AI остановлен.")
        return
    
    if action == "start_ai":
        db = get_db()
        if db is not None:
            db.tickets.update_one({"client_id": client_id, "is_removed": {"$ne": True}}, {"$set": {"ai_disabled": False}})
        await query.answer("AI включён.")
        return
    
    support_clients = context.application.bot_data.get("support_clients", {})
    client_data = support_clients.get(client_id, {})
    
    # Bedolaga actions
    if action == "bedolaga_tx":
        await query.answer("Загрузка транзакций...")
        bedolaga_user = client_data.get("bedolaga_user", {})
        bedolaga_id = bedolaga_user.get("id")
        
        if not bedolaga_id:
            balance_data = await fetch_bedolaga_balance(client_id)
            bedolaga_id = balance_data.get("id") if balance_data else None
        
        if not bedolaga_id:
            await query.message.reply_text("Нет данных Bedolaga.")
            return
        
        transactions = await fetch_bedolaga_transactions(int(bedolaga_id))
        if not transactions:
            await query.message.reply_text("Нет транзакций.")
            return
        
        lines = ["📜 <b>Транзакции</b>\n"]
        for t in transactions[:15]:
            amount = t.get("amount_rubles") or (t.get("amount_kopeks", 0) / 100)
            typ = t.get("type") or "-"
            created = (t.get("created_at") or "")[:19].replace("T", " ")
            lines.append(f"• {created} · {amount} ₽ · {typ}")
        
        await query.message.reply_text("\n".join(lines), parse_mode="HTML")
        return
    
    if action == "check_balance":
        await query.answer("Проверка баланса...")
        balance_data = await fetch_bedolaga_balance(client_id)
        if balance_data:
            await query.message.reply_text(f"💰 Баланс: {balance_data.get('balance')} RUB")
        else:
            await query.message.reply_text("Ошибка баланса.")
        return

    # Remnawave actions
    user_info = client_data.get("user", {})
    user_uuid = user_info.get("uuid")
    
    if not user_uuid:
        await query.answer("Пользователь не найден в системе.", show_alert=True)
        return
        
    await query.answer("Выполнение...")
    result = await remnawave_action(user_uuid, action)
    
    if result.get("ok"):
        await query.message.reply_text(f"✅ Успешно: {action}")
    else:
        await query.message.reply_text(f"❌ Ошибка {action}: {result.get('error') or result.get('status')}")


async def close_ticket_by_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Менеджер закрывает тикет через кнопку в топике.
    Паттерн: close_ticket_by_client:{client_id}

    Исправляет баг оригинала: кнопки в топике передавали client_id вместо ticket_id.
    Теперь ищем активный тикет по client_id.
    """
    query = update.callback_query
    data = query.data or ""
    client_id_str = data.replace("close_ticket_by_client:", "")

    if not check_access(query.from_user.id):
        await query.answer("Доступ запрещён.", show_alert=True)
        return

    await query.answer("Закрываю тикет...")

    db = get_db()
    support_group_id = get_support_group_id()
    from services.telegram_service import TelegramService
    telegram_service = TelegramService(bot=context.bot)
    ticket_service = TicketService(db, telegram_service, support_group_id)

    try:
        client_id = int(client_id_str)
        ticket = db.tickets.find_one({
            "client_id": client_id,
            "is_removed": {"$ne": True},
            "status": {"$ne": "closed"},
        })
        if ticket:
            result = await ticket_service.close_ticket(str(ticket["_id"]), user_id=None, is_manager=True)
        else:
            result = {"ok": False, "error": "Активный тикет не найден"}
    except ValueError:
        result = {"ok": False, "error": f"Некорректный client_id: {client_id_str}"}
    except Exception as e:
        result = {"ok": False, "error": str(e)}

    if result.get("ok"):
        resolved_client_id = result.get("client_id")
        thread_id = result.get("topic_id")

        if resolved_client_id:
            context.application.bot_data.get("support_topic_by_client", {}).pop(resolved_client_id, None)
        if thread_id and support_group_id:
            context.application.bot_data.get("support_thread_to_client", {}).pop(
                (support_group_id, thread_id), None
            )

        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await query.message.reply_text(f"❌ Не удалось закрыть: {result.get('error')}")
