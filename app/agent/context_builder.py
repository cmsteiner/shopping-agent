"""
Context builder — assembles the system prompt for Claude.

build_system_prompt collects:
  - Current date
  - Sender identity (name, phone)
  - Current list items grouped by category
  - Brand preferences
  - Pending confirmations
  - Recent conversation history (last 10 messages)
"""
from datetime import date
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import User, Item, Message, BrandPreference, PendingConfirmation, ShoppingList
from app.models.item import ItemStatus
from app.models.shopping_list import ListStatus
from app.models.message import MessageDirection


def build_system_prompt(user: User, db: Session) -> str:
    today = date.today().isoformat()

    # --- Current list items grouped by category ---
    active_list = (
        db.query(ShoppingList)
        .filter(ShoppingList.status == ListStatus.ACTIVE)
        .first()
    )

    list_section = "Current shopping list: (empty)\n"
    if active_list:
        active_items = (
            db.query(Item)
            .filter(Item.list_id == active_list.id, Item.status == ItemStatus.ACTIVE)
            .all()
        )
        if active_items:
            by_category: dict[str, list[Item]] = defaultdict(list)
            for item in active_items:
                category = item.category or "Uncategorized"
                by_category[category].append(item)

            lines = ["Current shopping list:"]
            for category, items in sorted(by_category.items()):
                lines.append(f"  [{category}]")
                for item in items:
                    parts = [f"    - {item.name}"]
                    if item.quantity is not None:
                        parts.append(f" x{item.quantity}")
                    if item.unit:
                        parts.append(f" {item.unit}")
                    if item.brand_pref:
                        parts.append(f" ({item.brand_pref})")
                    lines.append("".join(parts))
            list_section = "\n".join(lines) + "\n"

    # --- Brand preferences ---
    brand_prefs = db.query(BrandPreference).all()
    brand_section = "Brand preferences: (none)\n"
    if brand_prefs:
        lines = ["Brand preferences:"]
        for bp in brand_prefs:
            lines.append(f"  - {bp.item_name}: {bp.brand}")
        brand_section = "\n".join(lines) + "\n"

    # --- Pending confirmations ---
    pending = db.query(PendingConfirmation).filter(
        PendingConfirmation.triggered_by == user.id
    ).all()
    pending_section = "Pending confirmations: (none)\n"
    if pending:
        lines = ["Pending confirmations:"]
        for pc in pending:
            item = db.query(Item).filter(Item.id == pc.item_id).first()
            existing = (
                db.query(Item).filter(Item.id == pc.existing_item_id).first()
                if pc.existing_item_id else None
            )
            if item:
                desc = f"  - '{item.name}'"
                if existing:
                    desc += f" (possible duplicate of '{existing.name}')"
                lines.append(desc)
        pending_section = "\n".join(lines) + "\n"

    # --- Recent conversation history (last 10) ---
    recent_messages = (
        db.query(Message)
        .filter(Message.user_id == user.id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .all()
    )
    recent_messages = list(reversed(recent_messages))
    history_section = "Recent conversation history: (none)\n"
    if recent_messages:
        lines = ["Recent conversation history:"]
        for msg in recent_messages:
            direction = "You" if msg.direction == MessageDirection.OUTBOUND else user.name
            lines.append(f"  [{direction}]: {msg.body}")
        history_section = "\n".join(lines) + "\n"

    prompt = (
        f"You are a smart grocery shopping assistant for a household.\n"
        f"Today's date: {today}\n"
        f"You are talking with: {user.name} ({user.phone_number})\n\n"
        f"{list_section}\n"
        f"{brand_section}\n"
        f"{pending_section}\n"
        f"{history_section}\n"
        "Use the available tools to help manage the shopping list. "
        "Always respond in a concise, friendly SMS-appropriate style."
    )

    return prompt
