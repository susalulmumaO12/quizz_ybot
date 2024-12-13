import re
import os
from dotenv import load_dotenv
from typing import Final
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext,
)

load_dotenv()

#Constants
TOKEN: Final = os.getenv('TOKEN')
BOT_USERNAME: Final = '@quizz_ybot'

#Regex Patterns
QUESTION_PATTERN = r"\?([^\.]+)\."
ANSWER_PATTERN = r"\!([^\.]+)\."
CORRECT_ANSWER_PATTERN = r":(\d+):"
EXPLANATION_PATTERN = r"::([^:]+)::"

#quizzez object for lquiz command
quizzes = {}

#commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fname = update.message.from_user.first_name
    await update.message.reply_text(
        f"Welcome, {fname}! I am your quiz-making wizard, at your service! "
        "Use /help to learn how to create quizzes."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "To create a quiz using text, format it as follows:\n"
        "1\\. Surround the question with `\\?` and `\\.`\n"
        "2\\. Add answers surrounded by `\\!` and `\\.`\n"
        "3\\. Specify the correct answer ID surrounded by colons `:`\n"
        "4\\. Optionally, add an explanation surrounded by double colons `::`\n"
        "Example:\n"
        "```\n"
        "/quiz\n"
        "?What is the color of the sky. \n"
        "!Blue\\. \n"
        "!Green\\. \n"
        "!Red\\. \n"
        ":1: \n"
        "::Just look at it!::\n"
        "```",
        parse_mode='MarkdownV2',
    )

async def quiz_command(update: Update, context: CallbackContext):
    #if quiz command is sent alone
    if len(context.args) == 0:
        await update.message.reply_text(
            "Please send your quiz in the correct format or check /help for instructions."
        )
    else:
        await create_quiz(update.message.text, update, context)


# Quiz Creation from Text
async def create_quiz(text: str, update: Update, context: CallbackContext):
    question_match = re.search(QUESTION_PATTERN, text)
    if not question_match:
        await update.message.reply_text(
            "Your input does not include a valid question. Please surround the question with `\\?` and `\\.`. See /help for an example.",
            parse_mode='MarkdownV2',
        )
        return

    question = question_match.group(1).strip()
    answers = re.findall(ANSWER_PATTERN, text)
    if len(answers) < 2:
        await update.message.reply_text(
            "Please provide at least two answers, each surrounded by `\\!` and `\\.`. See /help for an example.",
            parse_mode='MarkdownV2',
        )
        return

    correct_answer_match = re.search(CORRECT_ANSWER_PATTERN, text)
    if not correct_answer_match:
        await update.message.reply_text(
            "Please specify the correct answer ID surrounded by colons `:`. See /help for an example.",
            parse_mode='MarkdownV2',
        )
        return

    correct_answer_id = int(correct_answer_match.group(1))
    if not (1 <= correct_answer_id <= len(answers)):
        await update.message.reply_text(
            f"The correct answer ID ({correct_answer_id}) is out of range. Please provide a number between 1 and {len(answers)}.",
            parse_mode='MarkdownV2',
        )
        return

    explanation_match = re.search(EXPLANATION_PATTERN, text)
    explanation = explanation_match.group(1).strip() if explanation_match else ""

    # Create and send poll
    try:
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=question,
            options=answers,
            is_anonymous=False,
            type="quiz",
            correct_option_id=correct_answer_id - 1,
            explanation=explanation,
        )
    except Exception as e:
        await update.message.reply_text(f"An error occurred while creating the quiz: {e}")

# Step-by-Step Quiz Creation - aka long quiz - aka sequence of messages
async def lquiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    quizzes[user_id] = {"stage": "question", "question": "", "answers": [], "correct_answer": None, "explanation": ""}
    await update.message.reply_text("Creating a new quiz! Please send the question.")

async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    quiz = quizzes.get(user_id)

    if not quiz:
        await update.message.reply_text("Please start a new quiz by sending /lquiz.")
        return

    stage = quiz["stage"]

    if stage == "question":
        quiz["question"] = update.message.text.strip()
        quiz["stage"] = "answers"
        await update.message.reply_text("Now send me the list of answers, one per message. Type 'done' when you're finished.")

    elif stage == "answers":
        if update.message.text.lower() == "done":
            if len(quiz["answers"]) < 2:
                await update.message.reply_text("Please provide at least two answers.")
            else:
                quiz["stage"] = "correct_answer"
                await update.message.reply_text("Please send the number of the correct answer.")
        else:
            quiz["answers"].append(update.message.text.strip())
            await update.message.reply_text("Answer added! Send another answer or type 'done'.")

    elif stage == "correct_answer":
        try:
            correct_answer = int(update.message.text.strip())
            if 1 <= correct_answer <= len(quiz["answers"]):
                quiz["correct_answer"] = correct_answer
                quiz["stage"] = "explanation"
                await update.message.reply_text("Optionally, send an explanation for the correct answer. Type 'done' if you don't want to add one.")
            else:
                await update.message.reply_text(f"Please send a number between 1 and {len(quiz['answers'])}.")
        except ValueError:
            await update.message.reply_text("Please send a valid number.")

    elif stage == "explanation":
        quiz["explanation"] = update.message.text.strip() if update.message.text.lower() != "done" else ""
        await send_quiz_poll(update, quiz)
        del quizzes[user_id]

async def send_quiz_poll(update: Update, quiz):
    try:
        await update.effective_chat.send_poll(
            question=quiz["question"],
            options=quiz["answers"],
            is_anonymous=False,
            type='quiz',
            explanation=quiz["explanation"],
            correct_option_id=quiz["correct_answer"] - 1
        )
    except Exception as e:
        await update.message.reply_text(f"An error occurred while creating the quiz: {e}")

# Error Handling
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")
    await update.message.reply_text(
        "An unexpected error occurred. Please try again later or contact support."
    )

# Main Application
if __name__ == '__main__':
    print('Starting bot...')
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('quiz', quiz_command))
    app.add_handler(CommandHandler('lquiz', lquiz_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message))

    # Errors
    app.add_error_handler(error)

    print('Polling...')
    app.run_polling(poll_interval=3)
