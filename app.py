import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from datetime import datetime, timedelta
import random
from sqlalchemy import desc

from sqlalchemy import func

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kod.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, default=0)
    display_name = db.Column(db.String(100), nullable=False)


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    correct_answer = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f"Question('{self.text}', '{self.correct_answer}')"


class QuizLeaderboard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', backref=db.backref('quiz_leaderboard', lazy=True))


class WeatherForecast:
    def __init__(self, day_of_week, date, day_temperature, night_temperature):
        self.day_of_week = day_of_week
        self.date = date
        self.day_temperature = day_temperature
        self.night_temperature = night_temperature


with app.app_context():
    db.create_all()
    if not Question.query.all():
        question1 = Question(text="Какая библиотека в Python широко используется для машинного обучения?",
                             correct_answer="scikit-learn")
        question2 = Question(text="Какой метод используется для обучения модели в нейронных сетях?",
                             correct_answer="обратное распространение ошибки")
        question3 = Question(text="Что такое NLP в контексте разработки ИИ на Python?",
                             correct_answer="обработка естественного языка")

        db.session.add_all([question1, question2, question3])
        db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def index():
    return render_template('index.html', current_user=current_user)


@app.route('/reg', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        display_name = request.form['display_name']

        existing_user_by_display_name = User.query.filter_by(display_name=display_name).first()
        if existing_user_by_display_name:
            flash('Пользователь с таким отображаемым именем уже существует. Пожалуйста, выберите другое.', 'error')
            return redirect(url_for('register'))

        existing_user_by_username = User.query.filter_by(username=username).first()
        if existing_user_by_username:
            flash('Пользователь с таким логином уже существует. Пожалуйста, выберите другой.', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, password=password, display_name=display_name)
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация успешна. Вы можете войти в систему.', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль. Пожалуйста, попробуйте еще раз.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    flash('Вы успешно вышли из системы.', 'success')
    return redirect(url_for('index'))


@app.route('/weather', methods=['POST'])
def weather_forecast():
    try:
        city = request.form['city']
        api_key = 'bf7190af8eea098e9202122cbbbbf907'
        url = f'http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric'
        response = requests.get(url)
        data = response.json()

        if data['cod'] == '200':
            weather_forecast = {}
            today = datetime.now().date()
            for forecast in data['list']:
                date_time = forecast['dt_txt']
                date_obj = datetime.strptime(date_time, '%Y-%m-%d %H:%M:%S')
                if date_obj.hour == 12 or (date_obj.hour > 12 and date_obj.date() == today):
                    day_of_week = date_obj.strftime('%A')
                    date = date_obj.strftime('%Y-%m-%d')
                    day_temperature = forecast['main']['temp']
                    if date not in weather_forecast:
                        weather_forecast[date] = WeatherForecast(day_of_week, date, day_temperature, None)
                elif date_obj.hour == 0:
                    date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
                    night_temperature = forecast['main']['temp']
                    if date in weather_forecast:
                        weather_forecast[
                            date].night_temperature = night_temperature

            filtered_forecast = [forecast for forecast in weather_forecast.values() if
                                 datetime.strptime(forecast.date, '%Y-%m-%d').date() in [today,
                                                                                         today + timedelta(days=1),
                                                                                         today + timedelta(days=2)]]
            return render_template('index.html', weather_forecast=filtered_forecast)
        else:
            error_message = f"Ошибка при получении прогноза: {data['message']}"
            return render_template('index.html', error=error_message)
    except Exception as e:
        return render_template('index.html', error=str(e))


@app.route('/quiz')
@login_required
def quiz():
    question = Question.query.order_by(func.random()).first()
    options = [question.correct_answer, "Что-то новое", "Сортировка", "ИИ"]
    random.shuffle(options)
    return render_template('quiz.html', question=question, options=options)


@app.route('/leaderboard')
def leaderboard():
    leaderboard_data = db.session.query(User.display_name, User.score).order_by(desc(User.score)).all()
    leaderboard_data_with_rank = [(i+1, name, score) for i, (name, score) in enumerate(leaderboard_data)]
    return render_template('leaderboard.html', leaderboard_data=leaderboard_data_with_rank)


@app.route('/quiz/answer', methods=['POST'])
@login_required
def quiz_answer():
    selected_answer = request.form.get('answer')
    question_id = request.form.get('question_id')

    if not selected_answer or not question_id:
        flash('Пожалуйста, сделайте выбор.', 'error')
        return redirect(url_for('quiz'))

    question = Question.query.get(int(question_id))

    if not question:
        abort(404)

    if selected_answer == question.correct_answer:
        current_user.score += 1
        db.session.commit()
        flash('Правильный ответ!', 'success')

        leaderboard_entry = QuizLeaderboard.query.filter_by(user_id=current_user.id).first()
        if leaderboard_entry:
            leaderboard_entry.score = current_user.score
        else:
            leaderboard_entry = QuizLeaderboard(user_id=current_user.id, score=current_user.score)
            db.session.add(leaderboard_entry)
        db.session.commit()

    else:
        flash('Неверный ответ. Попробуйте еще раз.', 'error')

    return redirect(url_for('quiz'))


if __name__ == '__main__':
    app.run(debug=False)
