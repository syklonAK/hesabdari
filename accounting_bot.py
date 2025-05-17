import os
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

import jdatetime
from hijri_converter import convert

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

from sqlalchemy import create_engine, Column, Integer, String, Numeric, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
Base = declarative_base()
engine = create_engine('sqlite:///accounting.db')
Session = sessionmaker(bind=engine)

# Debt database setup
DebtBase = declarative_base()
debt_engine = create_engine('sqlite:///debt.db')
DebtSession = sessionmaker(bind=debt_engine)

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(String(255), nullable=False)
    is_income = Column(Boolean, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, nullable=False)

class Debt(DebtBase):
    __tablename__ = 'debts'
    
    id = Column(Integer, primary_key=True)
    debtor_id = Column(String(3), unique=True, nullable=False)  # Format: letter + 2 numbers
    debtor_name = Column(String(255), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(String(255))
    date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, nullable=False)

# Create tables
Base.metadata.create_all(engine)
DebtBase.metadata.create_all(debt_engine)

# Conversation states
AMOUNT, DESCRIPTION, CONFIRM, DEBTOR_NAME, DEBT_AMOUNT, DEBT_DESCRIPTION, DEBT_CONFIRM, DELETE_DEBT = range(8)

# Admin user ID (replace with your Telegram user ID)
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

def format_currency(amount: Decimal) -> str:
    """Format amount in Iranian Toman."""
    # Format with commas
    amount_int = int(amount)
    formatted = f"{amount_int:,}"
    return f"{formatted} تومان"

def get_solar_date(date: datetime) -> str:
    """Get formatted Solar (Persian) date."""
    solar_date = jdatetime.date.fromgregorian(
        year=date.year,
        month=date.month,
        day=date.day
    )
    return solar_date.strftime("%Y/%m/%d")

def generate_debtor_id() -> str:
    """Generate a unique debtor ID in format: letter + 2 numbers."""
    import random
    import string
    
    # Get all existing debtor IDs
    session = DebtSession()
    try:
        existing_ids = {debt.debtor_id for debt in session.query(Debt.debtor_id).all()}
    finally:
        session.close()
    
    # Generate new ID until we find an unused one
    while True:
        letter = random.choice(string.ascii_lowercase)
        numbers = ''.join(str(random.randint(1, 9)) for _ in range(2))
        new_id = f"{letter}{numbers}"
        if new_id not in existing_ids:
            return new_id

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    welcome_message = (
        "👋 به ربات حسابداری شخصی خوش آمدید!\n\n"
        "📝 دستورات موجود:\n\n"
        "💰 ثبت درآمد:\n"
        "دکمه '💰 ثبت درآمد' را بزنید\n"
        "سپس مبلغ و توضیحات را وارد کنید\n\n"
        
        "💸 ثبت هزینه:\n"
        "دکمه '💸 ثبت هزینه' را بزنید\n"
        "سپس مبلغ و توضیحات را وارد کنید\n\n"
        
        "📊 گزارش مالی:\n"
        "دکمه '📊 گزارش مالی' را بزنید\n"
        "نمایش کل درآمد، هزینه و موجودی\n\n"
        
        "✏️ ویرایش:\n"
        "دکمه '✏️ ویرایش' را بزنید\n"
        "برای ویرایش یا حذف تراکنش‌ها\n\n"
        
        "👥 بدهکاران:\n"
        "دکمه '👥 بدهکاران' را بزنید\n"
        "برای مدیریت بدهی‌ها\n\n"
        
        "📌 نکات:\n"
        "- مبالغ به تومان وارد شوند\n"
        "- برای تایید از 'بله' یا 'yes' استفاده کنید\n"
        "- هر تراکنش دارای یک شناسه منحصر به فرد است\n"
        "- تاریخ شمسی به صورت خودکار ثبت می‌شود"
    )
    
    # Create command buttons
    keyboard = [
        [KeyboardButton("💰 ثبت درآمد"), KeyboardButton("💸 ثبت هزینه")],
        [KeyboardButton("📊 گزارش مالی"), KeyboardButton("✏️ ویرایش")],
        [KeyboardButton("👥 بدهکاران")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu buttons."""
    keyboard = [
        [KeyboardButton("💰 ثبت درآمد"), KeyboardButton("💸 ثبت هزینه")],
        [KeyboardButton("📊 گزارش مالی"), KeyboardButton("✏️ ویرایش")],
        [KeyboardButton("👥 بدهکاران")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("لطفا یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)

async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the edit menu buttons."""
    keyboard = [
        [KeyboardButton("✏️ ویرایش تراکنش"), KeyboardButton("🗑️ حذف تراکنش")],
        [KeyboardButton("🗑️ حذف همه"), KeyboardButton("🔙 بازگشت به منو")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("لطفا عملیات مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

async def show_debtors_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the debtors menu buttons."""
    keyboard = [
        [KeyboardButton("➕ ثبت بدهی"), KeyboardButton("🗑️ حذف بدهی")],
        [KeyboardButton("📋 لیست بدهی‌ها"), KeyboardButton("🔙 بازگشت به منو")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("لطفا عملیات مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """Handle command buttons."""
    command = update.message.text
    
    if command == "💰 ثبت درآمد":
        keyboard = [[KeyboardButton("❌ لغو")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("💰 لطفا مبلغ درآمد را وارد کنید:", reply_markup=reply_markup)
        context.user_data['is_income'] = True
        return AMOUNT
    elif command == "💸 ثبت هزینه":
        keyboard = [[KeyboardButton("❌ لغو")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("💸 لطفا مبلغ هزینه را وارد کنید:", reply_markup=reply_markup)
        context.user_data['is_income'] = False
        return AMOUNT
    elif command == "📊 گزارش مالی":
        await summary(update, context)
        return ConversationHandler.END
    elif command == "✏️ ویرایش":
        await show_edit_menu(update, context)
        return ConversationHandler.END
    elif command == "👥 بدهکاران":
        await show_debtors_menu(update, context)
        return ConversationHandler.END
    elif command == "➕ ثبت بدهی":
        keyboard = [[KeyboardButton("❌ لغو")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("👤 لطفا نام بدهکار را وارد کنید:", reply_markup=reply_markup)
        return DEBTOR_NAME
    elif command == "🗑️ حذف بدهی":
        keyboard = [[KeyboardButton("❌ لغو")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("🔑 لطفا شناسه بدهی را وارد کنید:", reply_markup=reply_markup)
        return DELETE_DEBT
    elif command == "📋 لیست بدهی‌ها":
        await debt_list(update, context)
        return ConversationHandler.END
    elif command == "🔙 بازگشت به منو":
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        await show_main_menu(update, context)
        return ConversationHandler.END

async def process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the amount entered by the user."""
    try:
        # Check for cancel command
        if update.message.text.lower() in ['/cancel', 'لغو', 'cancel', '❌ لغو']:
            await update.message.reply_text("❌ عملیات لغو شد.")
            await show_main_menu(update, context)
            return ConversationHandler.END

        # Remove any commas and convert to decimal
        amount_str = update.message.text.replace(',', '')
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError("مبلغ باید مثبت باشد")
        
        # Store amount directly in Toman
        context.user_data['amount'] = amount
        context.user_data['is_income'] = context.user_data.get('is_income', True)
        
        keyboard = [[KeyboardButton("❌ لغو")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("📝 لطفا توضیحات این تراکنش را وارد کنید:", reply_markup=reply_markup)
        return DESCRIPTION
    except ValueError:
        keyboard = [[KeyboardButton("❌ لغو")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("❌ لطفا یک عدد معتبر وارد کنید:", reply_markup=reply_markup)
        return AMOUNT

async def process_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the description entered by the user."""
    # Check for cancel command
    if update.message.text.lower() in ['/cancel', 'لغو', 'cancel', '❌ لغو']:
        await update.message.reply_text("❌ عملیات لغو شد.")
        await show_main_menu(update, context)
        return ConversationHandler.END

    description = update.message.text
    context.user_data['description'] = description
    
    # Get current solar date
    current_date = datetime.now()
    solar_date = get_solar_date(current_date)
    
    # Create confirmation message
    transaction_type = "درآمد" if context.user_data['is_income'] else "هزینه"
    confirmation_message = (
        f"لطفا {transaction_type} زیر را تایید کنید:\n\n"
        f"مبلغ: {format_currency(context.user_data['amount'])}\n"
        f"توضیحات: {description}\n"
        f"تاریخ شمسی: {solar_date}\n\n"
        "آیا صحیح است؟ (بله/خیر)"
    )
    
    keyboard = [
        [KeyboardButton("✅ بله"), KeyboardButton("❌ خیر")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(confirmation_message, reply_markup=reply_markup)
    return CONFIRM

async def confirm_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and save the transaction."""
    if update.message.text.lower() not in ['بله', 'yes', 'y', '✅ بله']:
        await update.message.reply_text("تراکنش لغو شد.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    
    session = Session()
    try:
        transaction = Transaction(
            amount=context.user_data['amount'],
            description=context.user_data['description'],
            is_income=context.user_data['is_income'],
            user_id=update.effective_user.id
        )
        session.add(transaction)
        session.commit()
        
        # Get transaction solar date
        solar_date = get_solar_date(transaction.date)
        
        transaction_type = "درآمد" if context.user_data['is_income'] else "هزینه"
        await update.message.reply_text(
            f"✅ {transaction_type} با موفقیت ثبت شد!\n"
            f"مبلغ: {format_currency(context.user_data['amount'])}\n"
            f"توضیحات: {context.user_data['description']}\n"
            f"تاریخ شمسی: {solar_date}"
        )
        await show_main_menu(update, context)
    except Exception as e:
        logger.error(f"Error saving transaction: {e}")
        await update.message.reply_text("❌ خطایی در ثبت تراکنش رخ داد.")
        await show_main_menu(update, context)
    finally:
        session.close()
    
    return ConversationHandler.END

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a summary of transactions."""
    # Get the correct message object based on whether it's a command or callback
    message = update.message if update.message else update.callback_query.message
    
    session = Session()
    try:
        user_id = update.effective_user.id
        
        # Get all transactions for the user
        transactions = session.query(Transaction).filter_by(user_id=user_id).all()
        
        if not transactions:
            await message.reply_text("هنوز تراکنشی ثبت نشده است.")
            await show_main_menu(update, context)
            return
        
        # Calculate totals
        total_income = sum(t.amount for t in transactions if t.is_income)
        total_expenses = sum(t.amount for t in transactions if not t.is_income)
        balance = total_income - total_expenses
        
        # Create summary message
        summary_message = (
            "📊 خلاصه مالی\n\n"
            f"کل درآمد: {format_currency(total_income)}\n"
            f"کل هزینه: {format_currency(total_expenses)}\n"
            f"موجودی: {format_currency(balance)}\n\n"
            "تراکنش‌های اخیر:\n"
        )
        
        # Add recent transactions
        for t in sorted(transactions[-5:], key=lambda x: x.date, reverse=True):
            emoji = "💰" if t.is_income else "💸"
            solar_date = get_solar_date(t.date)
            summary_message += (
                f"شناسه: {t.id}\n"
                f"{emoji} {format_currency(t.amount)} - {t.description}\n"
                f"تاریخ شمسی: {solar_date}\n\n"
            )
        
        await message.reply_text(summary_message)
        await show_main_menu(update, context)
    finally:
        session.close()

async def edit_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Edit a transaction using its ID."""
    if not context.args:
        await update.message.reply_text("❌ لطفا شناسه تراکنش را وارد کنید.\nمثال: /edit_tr 123")
        await show_edit_menu(update, context)
        return
    
    try:
        transaction_id = int(context.args[0])
        session = Session()
        try:
            transaction = session.query(Transaction).filter_by(id=transaction_id).first()
            if transaction:
                keyboard = [
                    [KeyboardButton("مبلغ"), KeyboardButton("توضیحات")],
                    [KeyboardButton("🔙 بازگشت به منو")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    f"چه بخشی از تراکنش زیر را می‌خواهید ویرایش کنید؟\n\n"
                    f"شناسه: {transaction.id}\n"
                    f"{'💰' if transaction.is_income else '💸'} {format_currency(transaction.amount)} - {transaction.description}\n"
                    f"تاریخ شمسی: {get_solar_date(transaction.date)}",
                    reply_markup=reply_markup
                )
                context.user_data['edit_transaction_id'] = transaction_id
            else:
                await update.message.reply_text("❌ تراکنش با این شناسه یافت نشد.")
                await show_edit_menu(update, context)
        finally:
            session.close()
    except ValueError:
        await update.message.reply_text("❌ شناسه تراکنش باید یک عدد باشد.")
        await show_edit_menu(update, context)

async def delete_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a transaction using its ID."""
    if not context.args:
        await update.message.reply_text("❌ لطفا شناسه تراکنش را وارد کنید.\nمثال: /del_tr 123")
        await show_edit_menu(update, context)
        return
    
    try:
        transaction_id = int(context.args[0])
        session = Session()
        try:
            transaction = session.query(Transaction).filter_by(id=transaction_id).first()
            if transaction:
                session.delete(transaction)
                session.commit()
                await update.message.reply_text(
                    f"✅ تراکنش با موفقیت حذف شد.\n"
                    f"شناسه: {transaction.id}\n"
                    f"{'💰' if transaction.is_income else '💸'} {format_currency(transaction.amount)} - {transaction.description}"
                )
            else:
                await update.message.reply_text("❌ تراکنش با این شناسه یافت نشد.")
            await show_edit_menu(update, context)
        finally:
            session.close()
    except ValueError:
        await update.message.reply_text("❌ شناسه تراکنش باید یک عدد باشد.")
        await show_edit_menu(update, context)

async def delete_all_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete all transactions."""
    session = Session()
    try:
        # Get count of transactions before deletion
        count = session.query(Transaction).count()
        if count == 0:
            await update.message.reply_text("❌ هیچ تراکنشی برای حذف وجود ندارد.")
            await show_edit_menu(update, context)
            return
        
        # Delete all transactions
        session.query(Transaction).delete()
        session.commit()
        await update.message.reply_text(f"✅ {count} تراکنش با موفقیت حذف شد.")
        await show_edit_menu(update, context)
    finally:
        session.close()

async def process_debtor_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the debtor name entered by the user."""
    # Check for cancel command
    if update.message.text.lower() in ['/cancel', 'لغو', 'cancel', '❌ لغو']:
        await update.message.reply_text("❌ عملیات لغو شد.")
        await show_debtors_menu(update, context)
        return ConversationHandler.END

    debtor_name = update.message.text
    context.user_data['debtor_name'] = debtor_name
    
    # Generate unique debtor ID
    debtor_id = generate_debtor_id()
    context.user_data['debtor_id'] = debtor_id
    
    keyboard = [[KeyboardButton("❌ لغو")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"👤 نام بدهکار: {debtor_name}\n"
        f"🔑 شناسه بدهکار: {debtor_id}\n\n"
        "💰 لطفا مبلغ بدهی را وارد کنید:",
        reply_markup=reply_markup
    )
    return DEBT_AMOUNT

async def process_debt_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the debt amount entered by the user."""
    try:
        # Check for cancel command
        if update.message.text.lower() in ['/cancel', 'لغو', 'cancel', '❌ لغو']:
            await update.message.reply_text("❌ عملیات لغو شد.")
            await show_debtors_menu(update, context)
            return ConversationHandler.END

        # Remove any commas and convert to decimal
        amount_str = update.message.text.replace(',', '')
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError("مبلغ باید مثبت باشد")
        
        context.user_data['debt_amount'] = amount
        
        keyboard = [
            [KeyboardButton("❌ لغو"), KeyboardButton("⏭️ رد کردن")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("📝 لطفا توضیحات بدهی را وارد کنید (اختیاری):", reply_markup=reply_markup)
        return DEBT_DESCRIPTION
    except ValueError:
        keyboard = [[KeyboardButton("❌ لغو")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("❌ لطفا یک عدد معتبر وارد کنید:", reply_markup=reply_markup)
        return DEBT_AMOUNT

async def process_debt_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the debt description entered by the user."""
    # Check for cancel command
    if update.message.text.lower() in ['/cancel', 'لغو', 'cancel', '❌ لغو']:
        await update.message.reply_text("❌ عملیات لغو شد.")
        await show_debtors_menu(update, context)
        return ConversationHandler.END

    # Check for skip command
    if update.message.text in ['⏭️ رد کردن', 'رد کردن', 'skip']:
        description = None
    else:
        description = update.message.text

    context.user_data['debt_description'] = description
    
    # Get current solar date
    current_date = datetime.now()
    solar_date = get_solar_date(current_date)
    
    # Create confirmation message
    confirmation_message = (
        f"لطفا اطلاعات بدهی زیر را تایید کنید:\n\n"
        f"نام بدهکار: {context.user_data['debtor_name']}\n"
        f"شناسه بدهکار: {context.user_data['debtor_id']}\n"
        f"مبلغ: {format_currency(context.user_data['debt_amount'])}\n"
        f"توضیحات: {description if description else '-'}\n"
        f"تاریخ شمسی: {solar_date}\n\n"
        "آیا صحیح است؟ (بله/خیر)"
    )
    
    keyboard = [
        [KeyboardButton("✅ بله"), KeyboardButton("❌ خیر")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(confirmation_message, reply_markup=reply_markup)
    return DEBT_CONFIRM

async def confirm_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and save the debt."""
    if update.message.text.lower() not in ['بله', 'yes', 'y', '✅ بله']:
        await update.message.reply_text("ثبت بدهی لغو شد.")
        await show_debtors_menu(update, context)
        return ConversationHandler.END
    
    session = DebtSession()
    try:
        debt = Debt(
            debtor_id=context.user_data['debtor_id'],
            debtor_name=context.user_data['debtor_name'],
            amount=context.user_data['debt_amount'],
            description=context.user_data.get('debt_description'),
            user_id=update.effective_user.id
        )
        session.add(debt)
        session.commit()
        
        # Get debt solar date
        solar_date = get_solar_date(debt.date)
        
        await update.message.reply_text(
            f"✅ بدهی با موفقیت ثبت شد!\n\n"
            f"شناسه بدهکار: {debt.debtor_id}\n"
            f"نام بدهکار: {debt.debtor_name}\n"
            f"مبلغ: {format_currency(debt.amount)}\n"
            f"تاریخ: {solar_date}\n"
            f"توضیحات: {debt.description if debt.description else '-'}"
        )
        await show_debtors_menu(update, context)
    except Exception as e:
        logger.error(f"Error saving debt: {e}")
        await update.message.reply_text("❌ خطایی در ثبت بدهی رخ داد.")
        await show_debtors_menu(update, context)
    finally:
        session.close()
    
    return ConversationHandler.END

async def debt_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of all debts."""
    session = DebtSession()
    try:
        user_id = update.effective_user.id
        debts = session.query(Debt).filter_by(user_id=user_id).all()
        
        if not debts:
            await update.message.reply_text("هیچ بدهی ثبت نشده است.")
            await show_debtors_menu(update, context)
            return
        
        # Calculate total debt
        total_debt = sum(debt.amount for debt in debts)
        
        # Create message
        message = f"📋 لیست بدهی‌ها\n\nکل بدهی: {format_currency(total_debt)}\n\n"
        
        for i, debt in enumerate(debts):
            solar_date = get_solar_date(debt.date)
            message += (
                f"نام بدهکار: {debt.debtor_name}\n"
                f"شناسه بدهکار: {debt.debtor_id}\n"
                f"مبلغ: {format_currency(debt.amount)}\n"
                f"تاریخ: {solar_date}\n"
                f"توضیحات: {debt.description if debt.description else '-'}\n"
            )
            # Add separator if not the last debt
            if i < len(debts) - 1:
                message += "➖➖➖➖➖➖➖➖➖➖\n"
        
        await update.message.reply_text(message)
        await show_debtors_menu(update, context)
    finally:
        session.close()

async def delete_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Delete a debt using its ID."""
    # Check for cancel command
    if update.message.text.lower() in ['/cancel', 'لغو', 'cancel', '❌ لغو']:
        await update.message.reply_text("❌ عملیات لغو شد.")
        await show_debtors_menu(update, context)
        return ConversationHandler.END

    debt_id = update.message.text.strip()
    session = DebtSession()
    try:
        # Find the debt by ID
        debt = session.query(Debt).filter_by(debtor_id=debt_id, user_id=update.effective_user.id).first()
        
        if debt:
            # Store debt info for confirmation message
            debt_info = {
                'name': debt.debtor_name,
                'amount': debt.amount,
                'date': get_solar_date(debt.date)
            }
            
            # Delete the debt
            session.delete(debt)
            session.commit()
            
            await update.message.reply_text(
                f"✅ بدهی با موفقیت حذف شد!\n\n"
                f"شناسه بدهکار: {debt_id}\n"
                f"نام بدهکار: {debt_info['name']}\n"
                f"مبلغ: {format_currency(debt_info['amount'])}\n"
                f"تاریخ: {debt_info['date']}"
            )
        else:
            await update.message.reply_text("❌ بدهی با این شناسه یافت نشد.")
        
        await show_debtors_menu(update, context)
    except Exception as e:
        logger.error(f"Error deleting debt: {e}")
        await update.message.reply_text("❌ خطایی در حذف بدهی رخ داد.")
        await show_debtors_menu(update, context)
    finally:
        session.close()
    
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

    # Add conversation handler for income/expense and debt registration
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_command)
        ],
        states={
            AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_amount)
            ],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_description)
            ],
            CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_transaction)
            ],
            DEBTOR_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_debtor_name)
            ],
            DEBT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_debt_amount)
            ],
            DEBT_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_debt_description)
            ],
            DEBT_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_debt)
            ],
            DELETE_DEBT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_debt)
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )

    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("edit_tr", edit_transaction))
    application.add_handler(CommandHandler("del_tr", delete_transaction))
    application.add_handler(CommandHandler("del_all_tr", delete_all_transactions))
    application.add_handler(CommandHandler("debt_list", debt_list))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 