import datetime

from wtforms import Form, StringField, validators
from wtforms.validators import ValidationError
from wtforms.fields.choices import SelectField
from wtforms.fields.datetime import DateTimeLocalField
from wtforms.fields.simple import PasswordField, TextAreaField

from moerderspiel import constants
from moerderspiel.db import Player, Game, Circle, Mission
from moerderspiel.game import GameService


class BaseForm(Form):
    def __init__(self, on_submit=None, **kwargs):
        super().__init__(**kwargs)
        self.on_submit = on_submit

    def handle_form_submit(self):
        if self.validate():
            return self.on_submit(self)


class AddPlayerForm(BaseForm):
    form_id = "add-player"
    form_title = "Spieler eintragen"

    name = StringField('Spielername',
                       [
                           validators.Length(min=constants.MIN_PLAYER_NAME_LENGTH,
                                             max=constants.MAX_PLAYER_NAME_LENGTH,
                                             message=f"Dein Name muss zwischen {constants.MIN_PLAYER_NAME_LENGTH} und {constants.MAX_PLAYER_NAME_LENGTH} Zeichen lang sein."),
                           validators.Regexp(constants.PLAYER_NAME_REGEX, message="Dein Name enthält ungültige Sonderzeichen.")
                       ],
                       description="""
                        Der Spielername muss innerhalb des Spiels eindeutig sein.
                        Bitte trage hier den Namen ein, der auf deinem Namensschild steht (sofern vorhanden).
                        Er wird auf den Auftragszetteln stehen.
                        """)
    group = StringField('Gruppe',
                        [validators.optional(), validators.Length(max=constants.MAX_GROUP_NAME_LENGTH)],
                        description="""
                        Wenn du mit einer Gruppe von Menschen teilnimmst, die du bereits kennst (z.B. von deiner Schule
                        oder Uni), trage hier den Namen der Gruppe/Uni/etc. ein.
                        Das bedeutet nicht, dass ihr ein Team bildet!
                        Das Spiel wird aber vermeiden, dir als ersten Auftrag jemanden aus deiner eigenen Gruppe zu
                        geben.
                        """)
    email = StringField('E-Mail-Adresse',
                        [validators.optional(), validators.Email(check_deliverability=True)],
                        filters=[lambda s: s if s is None else str.strip(s)],
                        description="""
                        Du kannst dir optional deine Mordaufträge per E-Mail zuschicken lassen.
                        """)
    password = PasswordField('Passwort',
                             description="""
                             Du kannst optional ein Passwort angeben, um vor Spielstart die Teilname an den 
                             verschiedenen Kreisen und Multispielen zu ändern und nach Spielstart deine Aufträge
                             einzusehen.
                             Gib das Passwort nicht an andere Mitspieler weiter.
                             """)

    def __init__(self, service: GameService, **kwargs):
        super().__init__(**kwargs)
        self.service = service

    def validate_name(self, field):
        if Player.by_game_and_name(self.service.game, field.data):
            raise ValidationError("Ein Spieler mit diesem Namen existiert bereits")


class PlayerLoginForm(BaseForm):
    form_id = "login-player"
    form_title = "Login"

    name = SelectField('Spielername', [validators.InputRequired()])
    password = PasswordField('Passwort', [validators.InputRequired()])

    def __init__(self, service: GameService, **kwargs):
        super().__init__(**kwargs)
        self.service = service
        self.name.choices = [(p.name, p.name) for p in service.game.players]

    def validate_password(self, field):
        player = self.service.get_player(self.name.data)
        if not player.check_player_password(field.data):
            raise ValidationError('Falsches Passwort')


class CreateGameForm(BaseForm):
    form_id = "create-game"
    form_title = "Spiel erstellen"

    game_id = StringField('Eindeutige Spiel-ID',
                          [validators.Length(max=constants.MAX_GAME_ID_LENGTH)],
                          description="""
                     Die Spiel-ID muss eindeutig sein und darf nur Kleinbuchstaben und Zahlen enthalten.
                     """)
    title = StringField('Titel des Spiels',
                        [validators.Length(max=constants.MAX_GAME_TITLE_LENGTH)],
                        description="""
                       Der Titel des Spiels wird auf den Auftragszetteln und der Übersichtsseite verwendet.
                       """)
    template = SelectField('Spielvorlage',
                           description="""
                            Die Spielvorlage gibt die Beschreibung und Regeln des Spiels vor.
                            Du kannst diese später anpassen.
                           """,
                           choices=[
                               ('offline', 'Einfaches Offline-Spiel'),
                               ('hybrid', 'Hybrides Online-Spiel'),
                               ('paperless', 'Papierloses Spiel')
                           ])
    password = PasswordField('Passwort',
                             [validators.EqualTo('password')],
                             description="""
                             Das Passwort brauchst Du um das Spiel zu administrieren.
                             Gib das Passwort nicht an Mitspieler weiter.
                             """)
    confirm_password = PasswordField('Passwort bestätigen')

    def validate_game_id(self, field):
        if Game.exists_by_id(self.session, field.data):
            print("Foo")
            raise ValidationError("Ein Spiel mit dieser ID existiert bereits")

    def __init__(self, session, **kwargs):
        super().__init__(**kwargs)
        self.session = session


class AddCircleForm(BaseForm):
    form_id = "add-circle"
    form_title = "Kreis hinzufügen"

    name = StringField('Name des Kreises',
                       [validators.Length(min=constants.MIN_CIRCLE_NAME_LENGTH, max=constants.MAX_CIRCLE_NAME_LENGTH)],
                       description="""
                       Der Name muss innerhalb des Spiels eindeutig sein.
                       """)

    set = StringField('Kreis-Set',
                      [validators.optional(), validators.Length(max=constants.MAX_CIRCLE_SET_NAME_LENGTH)],
                      description="""
                      Ein "Set" fasst in einem Multispiel mehrere Kreise zusammen. Falls alle Spieler in allen Kreisen
                      spielen, lasse dieses Feld leer.
                      """)

    def validate_name(self, field):
        if Circle.by_game_and_name(self.service.game, field.data):
            raise ValidationError("Ein Kreis mit diesem Namen existiert bereits")

    def __init__(self, service, **kwargs):
        super().__init__(**kwargs)
        self.service = service


class GameMasterLoginForm(BaseForm):
    form_id = "gamemaster-login"
    form_title = "Gamemaster-Login"
    form_submit_text = "Login"

    password = PasswordField('Passwort', [validators.InputRequired()],
                             description="""
                             Das Gamemaster-Passwort wird beim Erstellen des Spiels gesetzt und kann aktuell leider
                             nicht zurückgesetzt werden.
                             """)

    def __init__(self, service: GameService, **kwargs):
        super().__init__(**kwargs)
        self.service = service

    def validate_password(self, field):
        if not self.service.game.check_gamemaster_password(field.data):
            raise ValidationError("Falsches Passwort")


class RecordMurderForm(BaseForm):
    form_id = "record-murder"
    form_title = "Mord eintragen"

    killer = SelectField('Mörder',
                         description="Wer hat gemordet? (Normalerweise du selbst)")

    victim = SelectField('Opfer',
                         description="Wer wurde ermordet?")

    circle = SelectField('Kreis',
                         description="In welchem Kreis ist der Mord passiert?")

    when = DateTimeLocalField('Zeitpunkt',
                              description="Wann ist der Mord passiert?",
                              default=datetime.datetime.now,
                              format='%Y-%m-%dT%H:%M')

    mission_code = StringField('Auftrags-Code',
                               [validators.Length(min=constants.MISSION_CODE_LENGTH, max=constants.MISSION_CODE_LENGTH)],
                               description="Der Code des Auftrags, der gerade erledigt wurde.")

    description = TextAreaField('Kreative Tatbeschreibung',
                                [validators.Length(max=constants.MAX_MURDER_DESCRIPTION_LENGTH)],
                                description="""
                                Beschreibe kurz, wie der Mord passiert ist. Kreative Ausschmückungen sind erwünscht.
                                """)

    def validate_killer(self, field):
        mission = Mission.by_victim_in_circle(self.service.get_player(self.victim.data),
                                              self.service.get_circle(self.circle.data))
        if mission.current_owner != self.service.get_player(field.data):
            raise ValidationError("Dieser Auftrag gehört dir nicht. Hast du alle vorherigen Morde schon eingetragen?")

    def validate_mission_code(self, field):
        mission = Mission.by_victim_in_circle(self.service.get_player(self.victim.data),
                                              self.service.get_circle(self.circle.data))
        if field.data != mission.code:
            raise ValidationError("Das ist nicht der richtige Code für diesen Auftrag")

    def __init__(self, service: GameService, **kwargs):
        super().__init__(**kwargs)
        self.service = service
        self.killer.choices = [(p.name, p.name) for p in service.game.players]
        self.victim.choices = [(p.name, p.name) for p in service.game.players]
        self.circle.choices = [(c.name, c.name) for c in service.game.circles]
