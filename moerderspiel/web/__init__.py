from functools import wraps

import flask
from flask import Flask, render_template, send_from_directory, request, url_for, redirect, flash, abort, session
from flask_sqlalchemy import SQLAlchemy

from moerderspiel.db import Base, Game, Mission, Circle
from moerderspiel import config, graph, pdf
from moerderspiel.game import GameService, GameError
from moerderspiel.graph import get_circles_graph_cache_path
from moerderspiel.web.forms import AddPlayerForm, CreateGameForm, RecordMurderForm, GameMasterLoginForm

app = Flask(__name__)
app.config.from_prefixed_env()
app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
db = SQLAlchemy(app, model_class=Base)
with app.app_context():
    db.create_all()


def with_game_service(f):
    @wraps(f)
    def decorated_function(game_id: str, **kwargs):
        kwargs['service'] = GameService(db.get_or_404(Game, game_id))
        return f(**kwargs)

    return decorated_function


def needs_gamemaster_authentication(f):
    @wraps(f)
    def decorated_function(service: GameService, **kwargs):
        if service.game.id in (session.get('gamemaster_authenticated') or []):
            return f(service=service, **kwargs)
        else:
            return redirect(url_for('game', game_id=service.game.id, _anchor=GameMasterLoginForm.form_id))

    return decorated_function


@app.route('/', methods=['GET', 'POST'])
def index():
    create_game_form = CreateGameForm()

    if request.method == 'POST' and request.form['form'] == CreateGameForm.form_id:
        create_game_form = CreateGameForm(request.form)
        if create_game_form.validate():
            try:
                service = GameService.create_new_game(
                    session=db.session,
                    id=create_game_form.game_id.data,
                    title=create_game_form.title.data,
                    gamemaster_password=create_game_form.password.data,
                )
                db.session.commit()
                session['gamemaster_authenticated'] = (session.get('gamemaster_authenticated') or []) + [service.game.id]
                return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
            except GameError as e:
                flash(str(e), 'error')

    return render_template('index.html.j2',
                           create_game_form=create_game_form)


@app.route('/game/<game_id>', methods=['GET', 'POST'])
@with_game_service
def game(service: GameService):
    add_player_form = AddPlayerForm(request.form)
    record_murder_form = RecordMurderForm(service.game, request.form)
    gamemaster_login_form = GameMasterLoginForm(request.form)

    if request.method == 'POST' and request.form['form'] == add_player_form.form_id:
        if add_player_form.validate():
            try:
                player = service.add_player(name=add_player_form.name.data, group=add_player_form.group.data)
                for circle in service.game.circles:
                    service.add_player_to_circle(player, circle)
                db.session.commit()
                flash('Spieler eingetragen', 'success')
                return redirect(url_for('game', game_id=service.game.id, _anchor='top'))
            except GameError as e:
                flash(str(e), 'error')
    elif request.method == 'POST' and request.form['form'] == record_murder_form.form_id:
        if record_murder_form.validate():
            try:
                service.record_murder(killer=record_murder_form.killer.data,
                                      victim=record_murder_form.victim.data,
                                      circle=record_murder_form.circle.data,
                                      when=record_murder_form.when.data,
                                      code=record_murder_form.mission_code.data,
                                      reason=record_murder_form.description.data)
                db.session.commit()
                flash('Mord eingetragen', 'success')
                return redirect(url_for('game', game_id=service.game.id, _anchor='top'))
            except GameError as e:
                flash(str(e), 'error')
    elif request.method == 'POST' and request.form['form'] == gamemaster_login_form.form_id:
        if gamemaster_login_form.validate():
            try:
                if service.check_gamemaster_password(gamemaster_login_form.password.data):
                    session['gamemaster_authenticated'] = (session.get('gamemaster_authenticated') or []) + [service.game.id]
                    return redirect(url_for('gamemaster', game_id=service.game.id, _anchor='top'))
                else:
                    flash('Falsches Passwort', 'error')
            except GameError as e:
                flash(str(e), 'error')

    return render_template('game.html.j2',
                           game=service.game,
                           completed_missions=Mission.completed_missions_in_game(service.game),
                           mass_murderers=Mission.mass_murderers_by_game(service.game),
                           add_player_form=add_player_form,
                           record_murder_form=record_murder_form,
                           gamemaster_login_form=gamemaster_login_form)


@app.route('/gamemaster/<game_id>', methods=['GET', 'POST'])
@with_game_service
@needs_gamemaster_authentication
def gamemaster(service: GameService):
    if request.method == 'POST' and 'game-state-action' in request.form:
        try:
            if request.form['game-state-action'] == 'start':
                service.start_game()
            elif request.form['game-state-action'] == 'end':
                service.end_game()
            db.session.commit()
        except GameError as e:
            flash(str(e), 'error')
    elif request.method == 'POST' and 'circle-action' in request.form:
        try:
            if request.form['circle-action'] == 'add':
                circle = service.add_circle(f"Kreis {len(service.game.circles)}")
                for player in service.game.players:
                    service.add_player_to_circle(player, circle)
            db.session.commit()
        except GameError as e:
            flash(str(e), 'error')

    return render_template('gamemaster.html.j2',
                           game=service.game)


@app.get('/game/<game_id>/graph.svg')
@with_game_service
def game_graph(service: GameService):
    if 'circle' in request.args:
        circles = [service.get_circle(c) for c in request.args.getlist('circle')]
    else:
        circles = Circle.by_game(service.game)

    return flask.send_file(graph.generate_circles_graph(circles, show_original_owners=service.game.ended))


@app.get('/game/<game_id>/missions.pdf')
@with_game_service
@needs_gamemaster_authentication
def game_missions(service: GameService):
    pdf.generate_game_mission_sheet(service.game)
    return flask.send_file(pdf.get_game_mission_sheet_cache_path(service.game))


@app.get('/game')
def game_redirect():
    if 'id' not in request.args:
        return redirect(url_for('/'))
    else:
        return redirect(url_for('game', game_id=request.args['id']))


@app.route('/css/<path:path>')
def css(path):
    return send_from_directory('static/css', path)
