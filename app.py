from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, EqualTo, Length, ValidationError
from models import db, User, Bot, Message, Button
from config import Config
from bot_handler import start_bot, stop_bot, initialize_bots, monitor_bots
import re
import requests
import threading
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
csrf = CSRFProtect(app)

# Make csrf_token available in all templates
@app.context_processor
def inject_csrf_token():
    from flask_wtf.csrf import generate_csrf
    return dict(csrf_token=generate_csrf)

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=100)])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    repeat_password = PasswordField('Repeat Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    bot_token = StringField('Telegram Bot Token', validators=[DataRequired()])
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_bot_token(self, bot_token):
        # Basic format validation: Telegram tokens are typically 46 characters, alphanumeric with colons
        token = bot_token.data.strip()
        if not re.match(r'^[0-9]+:[A-Za-z0-9_-]+$', token):
            raise ValidationError('Invalid token format. Telegram bot tokens should be in format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz')


class BotForm(FlaskForm):
    name = StringField('Bot Name', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    token = StringField('Bot Token', validators=[DataRequired()])
    
    def validate_token(self, token):
        token_val = token.data.strip()
        if not re.match(r'^[0-9]+:[A-Za-z0-9_-]+$', token_val):
            raise ValidationError('Invalid token format. Telegram bot tokens should be in format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz')


class MessageForm(FlaskForm):
    trigger_text = StringField('Trigger Text', validators=[DataRequired(), Length(max=500)])
    response_text = TextAreaField('Response Text', validators=[DataRequired()])


class ButtonForm(FlaskForm):
    button_text = StringField('Button Text', validators=[DataRequired(), Length(max=100)])
    response_text = TextAreaField('Response Text', validators=[DataRequired()])


# Helper functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def validate_telegram_token(token):
    """Validate Telegram bot token by calling API"""
    try:
        url = f'https://api.telegram.org/bot{token}/getMe'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('ok', False)
        return False
    except:
        return False


# Routes
@app.route('/favicon.ico')
def favicon():
    """Handle favicon request to prevent 404 errors"""
    response = Response(status=204)
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    register_form = RegistrationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html', form=form, register_form=register_form, is_login=True)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    login_form = LoginForm()
    form = RegistrationForm()
    if form.validate_on_submit():
        # Optional: Validate token with Telegram API
        if not validate_telegram_token(form.bot_token.data.strip()):
            flash('Warning: Could not validate bot token with Telegram API. Please verify your token is correct.', 'warning')
        
        user = User(
            username=form.username.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Create initial bot for user
            bot = Bot(
                user_id=user.id,
                name=f"{user.first_name}'s Bot",
                description="My first Telegram bot",
                token=form.bot_token.data.strip(),
                is_active=True
            )
            db.session.add(bot)
            db.session.commit()
            
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Registration successful! Your bot has been created.', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('login.html', form=form, register_form=form, login_form=login_form, is_login=False)


@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    bots = Bot.query.filter_by(user_id=user.id).all()
    
    # Get bot statistics
    bot_stats = []
    for bot in bots:
        messages_count = Message.query.filter_by(bot_id=bot.id).count()
        buttons_count = Button.query.filter_by(bot_id=bot.id).count()
        token_valid = validate_telegram_token(bot.token)
        bot_stats.append({
            'bot': bot,
            'messages_count': messages_count,
            'buttons_count': buttons_count,
            'token_valid': token_valid
        })
    
    return render_template('dashboard.html', user=user, bot_stats=bot_stats)


@app.route('/bot/create', methods=['GET', 'POST'])
@login_required
def create_bot():
    form = BotForm()
    if form.validate_on_submit():
        # Validate token
        if not validate_telegram_token(form.token.data.strip()):
            flash('Warning: Could not validate bot token with Telegram API.', 'warning')
        
        bot = Bot(
            user_id=session['user_id'],
            name=form.name.data,
            description=form.description.data,
            token=form.token.data.strip(),
            is_active=True
        )
        
        try:
            db.session.add(bot)
            db.session.commit()
            # Start bot if it's active
            if bot.is_active:
                start_bot(bot, app)
            flash('Bot created successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to create bot. Please try again.', 'error')
    
    return render_template('bot_edit.html', form=form, bot=None)


@app.route('/bot/<int:bot_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bot(bot_id):
    bot = Bot.query.get_or_404(bot_id)
    
    # Check ownership
    if bot.user_id != session['user_id']:
        flash('You do not have permission to edit this bot.', 'error')
        return redirect(url_for('dashboard'))
    
    form = BotForm(obj=bot)
    if form.validate_on_submit():
        # Validate token
        if not validate_telegram_token(form.token.data.strip()):
            flash('Warning: Could not validate bot token with Telegram API.', 'warning')
        
        old_token = bot.token
        bot.name = form.name.data
        bot.description = form.description.data
        bot.token = form.token.data.strip()
        
        try:
            db.session.commit()
            # Restart bot if token changed or if it's active
            if old_token != bot.token or bot.is_active:
                stop_bot(bot.id)
                if bot.is_active:
                    start_bot(bot, app)
            flash('Bot updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to update bot. Please try again.', 'error')
    
    return render_template('bot_edit.html', form=form, bot=bot)


@app.route('/bot/<int:bot_id>/toggle', methods=['POST'])
@csrf.exempt
@login_required
def toggle_bot(bot_id):
    bot = Bot.query.get_or_404(bot_id)
    
    if bot.user_id != session['user_id']:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    
    bot.is_active = not bot.is_active
    try:
        db.session.commit()
        # Start or stop bot based on new status
        if bot.is_active:
            start_bot(bot, app)
        else:
            stop_bot(bot.id)
        return jsonify({'success': True, 'is_active': bot.is_active})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Failed to update: {str(e)}'}), 500


@app.route('/bot/<int:bot_id>/delete', methods=['POST'])
@login_required
def delete_bot(bot_id):
    bot = Bot.query.get_or_404(bot_id)
    
    if bot.user_id != session['user_id']:
        flash('You do not have permission to delete this bot.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        # Stop bot before deleting
        stop_bot(bot.id)
        db.session.delete(bot)
        db.session.commit()
        flash('Bot deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete bot.', 'error')
    
    return redirect(url_for('dashboard'))


@app.route('/bot/<int:bot_id>/messages', methods=['GET', 'POST'])
@login_required
def manage_messages(bot_id):
    bot = Bot.query.get_or_404(bot_id)
    
    if bot.user_id != session['user_id']:
        flash('You do not have permission to access this bot.', 'error')
        return redirect(url_for('dashboard'))
    
    form = MessageForm()
    if form.validate_on_submit():
        message = Message(
            bot_id=bot.id,
            trigger_text=form.trigger_text.data,
            response_text=form.response_text.data
        )
        try:
            db.session.add(message)
            db.session.commit()
            flash('Message added successfully!', 'success')
            return redirect(url_for('manage_messages', bot_id=bot.id))
        except:
            db.session.rollback()
            flash('Failed to add message.', 'error')
    
    messages = Message.query.filter_by(bot_id=bot.id).all()
    return render_template('messages.html', bot=bot, messages=messages, form=form)


@app.route('/message/<int:message_id>/delete', methods=['POST'])
@login_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    bot = Bot.query.get_or_404(message.bot_id)
    
    if bot.user_id != session['user_id']:
        flash('You do not have permission to delete this message.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        db.session.delete(message)
        db.session.commit()
        flash('Message deleted successfully!', 'success')
    except:
        db.session.rollback()
        flash('Failed to delete message.', 'error')
    
    return redirect(url_for('manage_messages', bot_id=bot.id))


@app.route('/bot/<int:bot_id>/buttons', methods=['GET', 'POST'])
@login_required
def manage_buttons(bot_id):
    bot = Bot.query.get_or_404(bot_id)
    
    if bot.user_id != session['user_id']:
        flash('You do not have permission to access this bot.', 'error')
        return redirect(url_for('dashboard'))
    
    form = ButtonForm()
    if form.validate_on_submit():
        button = Button(
            bot_id=bot.id,
            button_text=form.button_text.data,
            response_text=form.response_text.data
        )
        try:
            db.session.add(button)
            db.session.commit()
            flash('Button added successfully!', 'success')
            return redirect(url_for('manage_buttons', bot_id=bot.id))
        except:
            db.session.rollback()
            flash('Failed to add button.', 'error')
    
    buttons = Button.query.filter_by(bot_id=bot.id).all()
    return render_template('buttons.html', bot=bot, buttons=buttons, form=form)


@app.route('/button/<int:button_id>/delete', methods=['POST'])
@login_required
def delete_button(button_id):
    button = Button.query.get_or_404(button_id)
    bot = Bot.query.get_or_404(button.bot_id)
    
    if bot.user_id != session['user_id']:
        flash('You do not have permission to delete this button.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        db.session.delete(button)
        db.session.commit()
        flash('Button deleted successfully!', 'success')
    except:
        db.session.rollback()
        flash('Failed to delete button.', 'error')
    
    return redirect(url_for('manage_buttons', bot_id=bot.id))


@app.route('/bot/<int:bot_id>/test', methods=['GET', 'POST'])
@login_required
def test_bot(bot_id):
    bot = Bot.query.get_or_404(bot_id)
    
    if bot.user_id != session['user_id']:
        flash('You do not have permission to test this bot.', 'error')
        return redirect(url_for('dashboard'))
    
    messages_count = Message.query.filter_by(bot_id=bot.id).count()
    buttons_count = Button.query.filter_by(bot_id=bot.id).count()
    messages = Message.query.filter_by(bot_id=bot.id).all()
    buttons = Button.query.filter_by(bot_id=bot.id).all()
    
    if request.method == 'POST':
        test_message = request.form.get('test_message', '')
        if test_message:
            # This is a simple test - in a real scenario, you'd send to Telegram
            # For now, we'll just show what response would be sent
            response = None
            # Check buttons first
            for button in buttons:
                if button.button_text.lower() in test_message.lower():
                    response = button.response_text
                    break
            
            # Then check messages
            if not response:
                for msg in messages:
                    if msg.trigger_text.lower() in test_message.lower():
                        response = msg.response_text
                        break
            
            if response:
                flash(f'Bot would respond: {response}', 'success')
            else:
                flash('No matching trigger found. Bot would not respond.', 'info')
    
    return render_template('test_bot.html', bot=bot, messages_count=messages_count, buttons_count=buttons_count, messages=messages, buttons=buttons)


# Initialize database
with app.app_context():
    db.create_all()
    # Initialize active bots
    initialize_bots(app)
    # Start bot monitor thread
    monitor_thread = threading.Thread(target=monitor_bots, args=(app,), daemon=True)
    monitor_thread.start()


if __name__ == '__main__':
    app.run(debug=True)
